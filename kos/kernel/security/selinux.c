#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>

/* SELinux state */
static kos_selinux_mode_t selinux_mode = KOS_SELINUX_DISABLED;
static pthread_mutex_t selinux_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool selinux_initialized = false;

/* Security context table */
static struct {
    uint32_t pid;
    kos_selinux_context_t context;
    bool in_use;
} context_table[KOS_MAX_CONTEXTS];

/* Access Vector Cache (AVC) */
struct avc_entry {
    uint32_t ssid;  /* Source security ID */
    uint32_t tsid;  /* Target security ID */
    uint32_t tclass; /* Target class */
    uint32_t allowed;
    uint32_t denied;
    time_t timestamp;
    bool valid;
};

static struct avc_entry avc_cache[1024];
static int avc_cache_size = 1024;

/* Simple policy store */
struct policy_rule {
    char source_type[64];
    char target_type[64];
    char object_class[64];
    char permissions[256];
    bool allow;
};

static struct policy_rule* policy_rules = NULL;
static size_t policy_rule_count = 0;
static size_t policy_rule_capacity = 0;

/* Security ID counter */
static uint32_t next_sid = 1;

/* Object classes */
static const char* object_classes[] = {
    "file", "dir", "lnk_file", "chr_file", "blk_file", "sock_file",
    "fifo_file", "process", "security", "system", "capability",
    "filesystem", "node", "netif", "netlink_socket", "packet_socket",
    "key_socket", "unix_stream_socket", "unix_dgram_socket",
    "sem", "msg", "msgq", "shm", "ipc", NULL
};

/* Permission mappings */
struct permission_map {
    const char* class;
    const char* permissions[32];
};

static struct permission_map perm_maps[] = {
    { "file", { "read", "write", "execute", "append", "create", "unlink", 
                "getattr", "setattr", "lock", "relabelfrom", "relabelto", NULL } },
    { "dir", { "read", "write", "execute", "add_name", "remove_name", "reparent",
               "search", "rmdir", "create", "getattr", "setattr", NULL } },
    { "process", { "fork", "transition", "sigchld", "sigkill", "sigstop", 
                   "signull", "signal", "ptrace", "getsched", "setsched",
                   "getsession", "getpgid", "setpgid", "getcap", "setcap", NULL } },
    { "capability", { "chown", "dac_override", "dac_read_search", "fowner",
                      "fsetid", "kill", "setgid", "setuid", "setpcap", NULL } },
    { NULL, { NULL } }
};

static uint32_t hash_string(const char* str) {
    uint32_t hash = 5381;
    int c;
    while ((c = *str++)) {
        hash = ((hash << 5) + hash) + c;
    }
    return hash;
}

static int find_context_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (context_table[i].in_use && context_table[i].pid == pid) {
            return i;
        }
    }
    return -1;
}

static int allocate_context_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (!context_table[i].in_use) {
            context_table[i].pid = pid;
            context_table[i].in_use = true;
            context_table[i].context.sid = next_sid++;
            return i;
        }
    }
    return -1;
}

static uint32_t get_object_class_id(const char* class_name) {
    for (int i = 0; object_classes[i]; i++) {
        if (strcmp(object_classes[i], class_name) == 0) {
            return i + 1;
        }
    }
    return 0;
}

static uint32_t get_permission_mask(const char* class_name, const char* perm) {
    for (int i = 0; perm_maps[i].class; i++) {
        if (strcmp(perm_maps[i].class, class_name) == 0) {
            for (int j = 0; perm_maps[i].permissions[j]; j++) {
                if (strcmp(perm_maps[i].permissions[j], perm) == 0) {
                    return 1U << j;
                }
            }
            break;
        }
    }
    return 0;
}

static int avc_lookup(uint32_t ssid, uint32_t tsid, uint32_t tclass,
                      uint32_t* allowed, uint32_t* denied) {
    time_t now = time(NULL);
    
    for (int i = 0; i < avc_cache_size; i++) {
        struct avc_entry* entry = &avc_cache[i];
        if (entry->valid && entry->ssid == ssid && entry->tsid == tsid &&
            entry->tclass == tclass) {
            /* Check if cache entry is still fresh (5 minutes) */
            if (now - entry->timestamp < 300) {
                *allowed = entry->allowed;
                *denied = entry->denied;
                return 1; /* Cache hit */
            } else {
                entry->valid = false; /* Expire old entry */
            }
        }
    }
    return 0; /* Cache miss */
}

static void avc_insert(uint32_t ssid, uint32_t tsid, uint32_t tclass,
                       uint32_t allowed, uint32_t denied) {
    /* Find empty slot or oldest entry */
    int slot = -1;
    time_t oldest = time(NULL);
    
    for (int i = 0; i < avc_cache_size; i++) {
        if (!avc_cache[i].valid) {
            slot = i;
            break;
        }
        if (avc_cache[i].timestamp < oldest) {
            oldest = avc_cache[i].timestamp;
            slot = i;
        }
    }
    
    if (slot >= 0) {
        avc_cache[slot].ssid = ssid;
        avc_cache[slot].tsid = tsid;
        avc_cache[slot].tclass = tclass;
        avc_cache[slot].allowed = allowed;
        avc_cache[slot].denied = denied;
        avc_cache[slot].timestamp = time(NULL);
        avc_cache[slot].valid = true;
    }
}

static int policy_check(const char* stype, const char* ttype,
                        const char* tclass, const char* perm) {
    for (size_t i = 0; i < policy_rule_count; i++) {
        struct policy_rule* rule = &policy_rules[i];
        
        if ((strcmp(rule->source_type, stype) == 0 || 
             strcmp(rule->source_type, "*") == 0) &&
            (strcmp(rule->target_type, ttype) == 0 ||
             strcmp(rule->target_type, "*") == 0) &&
            (strcmp(rule->object_class, tclass) == 0 ||
             strcmp(rule->object_class, "*") == 0)) {
            
            /* Check if permission is in the rule */
            if (strstr(rule->permissions, perm) != NULL ||
                strcmp(rule->permissions, "*") == 0) {
                return rule->allow ? 1 : -1;
            }
        }
    }
    
    /* Default deny */
    return -1;
}

int kos_selinux_init(void) {
    pthread_mutex_lock(&selinux_mutex);
    
    if (selinux_initialized) {
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    /* Initialize context table */
    memset(context_table, 0, sizeof(context_table));
    memset(avc_cache, 0, sizeof(avc_cache));
    
    /* Set up default context for init process */
    int slot = allocate_context_slot(1);
    if (slot >= 0) {
        kos_selinux_context_t* ctx = &context_table[slot].context;
        strcpy(ctx->user, "system_u");
        strcpy(ctx->role, "system_r");
        strcpy(ctx->type, "init_t");
        strcpy(ctx->level, "s0");
    }
    
    /* Load default policy rules */
    policy_rule_capacity = 100;
    policy_rules = malloc(sizeof(struct policy_rule) * policy_rule_capacity);
    if (!policy_rules) {
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_ENOMEM;
    }
    
    /* Add some basic allow rules */
    struct policy_rule default_rules[] = {
        { "init_t", "*", "*", "*", true },
        { "unconfined_t", "*", "*", "*", true },
        { "user_t", "user_home_t", "file", "read write create unlink", true },
        { "user_t", "tmp_t", "file", "read write create unlink", true },
        { "*", "proc_t", "file", "read", true }
    };
    
    size_t default_count = sizeof(default_rules) / sizeof(default_rules[0]);
    for (size_t i = 0; i < default_count && i < policy_rule_capacity; i++) {
        policy_rules[i] = default_rules[i];
        policy_rule_count++;
    }
    
    selinux_mode = KOS_SELINUX_PERMISSIVE;
    selinux_initialized = true;
    pthread_mutex_unlock(&selinux_mutex);
    
    printf("[KOS Security] SELinux initialized in permissive mode\n");
    return KOS_SEC_SUCCESS;
}

void kos_selinux_cleanup(void) {
    pthread_mutex_lock(&selinux_mutex);
    
    if (policy_rules) {
        free(policy_rules);
        policy_rules = NULL;
    }
    policy_rule_count = 0;
    policy_rule_capacity = 0;
    
    memset(context_table, 0, sizeof(context_table));
    memset(avc_cache, 0, sizeof(avc_cache));
    
    selinux_initialized = false;
    selinux_mode = KOS_SELINUX_DISABLED;
    
    pthread_mutex_unlock(&selinux_mutex);
    
    printf("[KOS Security] SELinux cleanup completed\n");
}

int kos_selinux_set_mode(kos_selinux_mode_t mode) {
    pthread_mutex_lock(&selinux_mutex);
    selinux_mode = mode;
    pthread_mutex_unlock(&selinux_mutex);
    
    const char* mode_names[] = {
        "unconfined", "confined", "enforcing", "permissive", "disabled"
    };
    printf("[KOS Security] SELinux mode set to %s\n", mode_names[mode]);
    
    return KOS_SEC_SUCCESS;
}

kos_selinux_mode_t kos_selinux_get_mode(void) {
    pthread_mutex_lock(&selinux_mutex);
    kos_selinux_mode_t mode = selinux_mode;
    pthread_mutex_unlock(&selinux_mutex);
    return mode;
}

int kos_selinux_check_access(const kos_selinux_context_t* scontext,
                             const kos_selinux_context_t* tcontext,
                             const char* tclass, const char* perm) {
    if (!scontext || !tcontext || !tclass || !perm) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&selinux_mutex);
    
    if (selinux_mode == KOS_SELINUX_DISABLED) {
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    /* Check policy */
    int result = policy_check(scontext->type, tcontext->type, tclass, perm);
    
    if (selinux_mode == KOS_SELINUX_PERMISSIVE && result < 0) {
        /* Log but allow in permissive mode */
        printf("[SELinux] Permissive: denied %s %s:%s:%s %s\n",
               scontext->type, tcontext->user, tcontext->role,
               tcontext->type, perm);
        result = 1;
    }
    
    pthread_mutex_unlock(&selinux_mutex);
    
    return (result > 0) ? KOS_SEC_SUCCESS : KOS_SEC_EACCES;
}

int kos_selinux_compute_av(const kos_selinux_context_t* scontext,
                           const kos_selinux_context_t* tcontext,
                           const char* tclass, uint32_t* allowed,
                           uint32_t* denied) {
    if (!scontext || !tcontext || !tclass || !allowed || !denied) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&selinux_mutex);
    
    if (selinux_mode == KOS_SELINUX_DISABLED) {
        *allowed = 0xFFFFFFFF;
        *denied = 0;
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    uint32_t tclass_id = get_object_class_id(tclass);
    
    /* Check AVC cache first */
    if (avc_lookup(scontext->sid, tcontext->sid, tclass_id, allowed, denied)) {
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    *allowed = 0;
    *denied = 0;
    
    /* Find permission map for this class */
    for (int i = 0; perm_maps[i].class; i++) {
        if (strcmp(perm_maps[i].class, tclass) == 0) {
            for (int j = 0; perm_maps[i].permissions[j]; j++) {
                const char* perm = perm_maps[i].permissions[j];
                int result = policy_check(scontext->type, tcontext->type, 
                                          tclass, perm);
                uint32_t perm_mask = 1U << j;
                
                if (result > 0) {
                    *allowed |= perm_mask;
                } else {
                    *denied |= perm_mask;
                }
            }
            break;
        }
    }
    
    /* Cache the result */
    avc_insert(scontext->sid, tcontext->sid, tclass_id, *allowed, *denied);
    
    pthread_mutex_unlock(&selinux_mutex);
    return KOS_SEC_SUCCESS;
}

int kos_selinux_get_context(uint32_t pid, kos_selinux_context_t* context) {
    if (!context) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&selinux_mutex);
    
    int slot = find_context_slot(pid);
    if (slot < 0) {
        /* Allocate default context */
        slot = allocate_context_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&selinux_mutex);
            return KOS_SEC_ENOMEM;
        }
        
        kos_selinux_context_t* ctx = &context_table[slot].context;
        strcpy(ctx->user, "unconfined_u");
        strcpy(ctx->role, "unconfined_r");
        strcpy(ctx->type, "unconfined_t");
        strcpy(ctx->level, "s0");
    }
    
    *context = context_table[slot].context;
    pthread_mutex_unlock(&selinux_mutex);
    
    return KOS_SEC_SUCCESS;
}

int kos_selinux_set_context(uint32_t pid, const kos_selinux_context_t* context) {
    if (!context) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&selinux_mutex);
    
    int slot = find_context_slot(pid);
    if (slot < 0) {
        slot = allocate_context_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&selinux_mutex);
            return KOS_SEC_ENOMEM;
        }
    }
    
    context_table[slot].context = *context;
    pthread_mutex_unlock(&selinux_mutex);
    
    return KOS_SEC_SUCCESS;
}

int kos_selinux_load_policy(const void* policy_data, size_t policy_size) {
    if (!policy_data || policy_size == 0 || policy_size > KOS_MAX_POLICY_SIZE) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&selinux_mutex);
    
    /* Simple text-based policy format:
     * allow source_type target_type:object_class { permissions };
     * deny source_type target_type:object_class { permissions };
     */
    
    char* policy_text = malloc(policy_size + 1);
    if (!policy_text) {
        pthread_mutex_unlock(&selinux_mutex);
        return KOS_SEC_ENOMEM;
    }
    
    memcpy(policy_text, policy_data, policy_size);
    policy_text[policy_size] = '\0';
    
    /* Clear existing rules */
    policy_rule_count = 0;
    
    /* Parse policy */
    char* line = strtok(policy_text, "\n");
    while (line && policy_rule_count < policy_rule_capacity) {
        char action[16], source[64], target_class[128], perms[256];
        
        if (sscanf(line, "%15s %63s %127s { %255[^}] }", 
                   action, source, target_class, perms) == 4) {
            
            char* colon = strchr(target_class, ':');
            if (colon) {
                *colon = '\0';
                char* target = target_class;
                char* class = colon + 1;
                
                struct policy_rule* rule = &policy_rules[policy_rule_count];
                strcpy(rule->source_type, source);
                strcpy(rule->target_type, target);
                strcpy(rule->object_class, class);
                strcpy(rule->permissions, perms);
                rule->allow = (strcmp(action, "allow") == 0);
                
                policy_rule_count++;
            }
        }
        
        line = strtok(NULL, "\n");
    }
    
    free(policy_text);
    
    /* Clear AVC cache after policy change */
    memset(avc_cache, 0, sizeof(avc_cache));
    
    pthread_mutex_unlock(&selinux_mutex);
    
    printf("[KOS Security] SELinux policy loaded (%zu rules)\n", policy_rule_count);
    return KOS_SEC_SUCCESS;
}

/* Context transition during exec */
int kos_selinux_exec_transition(uint32_t pid, const char* filename) {
    if (!filename) {
        return KOS_SEC_EINVAL;
    }
    
    kos_selinux_context_t current_ctx, new_ctx;
    
    if (kos_selinux_get_context(pid, &current_ctx) != KOS_SEC_SUCCESS) {
        return KOS_SEC_ERROR;
    }
    
    /* Simple transition logic based on filename */
    new_ctx = current_ctx;
    
    if (strstr(filename, "/bin/") || strstr(filename, "/usr/bin/")) {
        strcpy(new_ctx.type, "bin_t");
    } else if (strstr(filename, "/sbin/") || strstr(filename, "/usr/sbin/")) {
        strcpy(new_ctx.type, "admin_t");
    } else if (strstr(filename, "/tmp/")) {
        strcpy(new_ctx.type, "tmp_t");
    }
    
    return kos_selinux_set_context(pid, &new_ctx);
}

/* Print SELinux status */
void kos_selinux_print_status(void) {
    const char* mode_names[] = {
        "unconfined", "confined", "enforcing", "permissive", "disabled"
    };
    
    printf("SELinux Status:\n");
    printf("  Mode: %s\n", mode_names[selinux_mode]);
    printf("  Policy rules: %zu\n", policy_rule_count);
    printf("  AVC cache entries: ");
    
    int cache_count = 0;
    for (int i = 0; i < avc_cache_size; i++) {
        if (avc_cache[i].valid) cache_count++;
    }
    printf("%d/%d\n", cache_count, avc_cache_size);
}