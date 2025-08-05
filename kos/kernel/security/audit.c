#define _POSIX_C_SOURCE 200809L
#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <sys/types.h>

/* Audit subsystem state */
static struct {
    bool enabled;
    FILE* log_file;
    char log_path[256];
    pthread_mutex_t lock;
    uint64_t sequence_number;
} audit_state = {
    .enabled = false,
    .log_file = NULL,
    .log_path = "/var/log/kos_audit.log",
    .lock = PTHREAD_MUTEX_INITIALIZER,
    .sequence_number = 1
};

/* Circular buffer for audit events */
static struct {
    kos_audit_event_t* events;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    pthread_mutex_t lock;
} audit_buffer = {
    .events = NULL,
    .capacity = KOS_MAX_AUDIT_ENTRIES,
    .head = 0,
    .tail = 0,
    .count = 0,
    .lock = PTHREAD_MUTEX_INITIALIZER
};

/* Audit rules */
struct audit_rule {
    kos_audit_type_t type;
    uint32_t pid;
    char field_name[64];
    char field_value[256];
    bool enabled;
};

static struct audit_rule* audit_rules = NULL;
static size_t audit_rule_count = 0;
static size_t audit_rule_capacity = 0;
static pthread_mutex_t audit_rules_lock = PTHREAD_MUTEX_INITIALIZER;

/* Audit type names for logging */
static const char* audit_type_names[] = {
    [KOS_AUDIT_SYSCALL] = "SYSCALL",
    [KOS_AUDIT_FS_WATCH] = "FS_WATCH",
    [KOS_AUDIT_PATH] = "PATH",
    [KOS_AUDIT_IPC] = "IPC",
    [KOS_AUDIT_SOCKETCALL] = "SOCKETCALL",
    [KOS_AUDIT_CONFIG_CHANGE] = "CONFIG_CHANGE",
    [KOS_AUDIT_SOCKADDR] = "SOCKADDR",
    [KOS_AUDIT_CWD] = "CWD",
    [KOS_AUDIT_EXECVE] = "EXECVE",
    [KOS_AUDIT_USER] = "USER",
    [KOS_AUDIT_LOGIN] = "LOGIN",
    [KOS_AUDIT_SELINUX_ERR] = "SELINUX_ERR",
    [KOS_AUDIT_AVC] = "AVC"
};

static uint64_t get_timestamp_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static void get_process_info(uint32_t pid, char* comm, size_t comm_size,
                             char* exe, size_t exe_size) {
    char path[256];
    FILE* f;
    
    /* Get command name */
    snprintf(path, sizeof(path), "/proc/%u/comm", pid);
    f = fopen(path, "r");
    if (f) {
        if (fgets(comm, comm_size, f)) {
            /* Remove newline */
            char* nl = strchr(comm, '\n');
            if (nl) *nl = '\0';
        }
        fclose(f);
    } else {
        snprintf(comm, comm_size, "unknown");
    }
    
    /* Get executable path */
    snprintf(path, sizeof(path), "/proc/%u/exe", pid);
    ssize_t len = readlink(path, exe, exe_size - 1);
    if (len > 0) {
        exe[len] = '\0';
    } else {
        snprintf(exe, exe_size, "unknown");
    }
}

static bool should_audit_event(kos_audit_type_t type, uint32_t pid,
                                const char* message) {
    if (!audit_state.enabled) {
        return false;
    }
    
    pthread_mutex_lock(&audit_rules_lock);
    
    /* If no rules defined, audit everything */
    if (audit_rule_count == 0) {
        pthread_mutex_unlock(&audit_rules_lock);
        return true;
    }
    
    /* Check if any rule matches */
    for (size_t i = 0; i < audit_rule_count; i++) {
        struct audit_rule* rule = &audit_rules[i];
        
        if (!rule->enabled) continue;
        
        bool matches = true;
        
        /* Check type */
        if (rule->type != type && rule->type != 0) {
            matches = false;
        }
        
        /* Check PID */
        if (rule->pid != 0 && rule->pid != pid) {
            matches = false;
        }
        
        /* Check field value in message */
        if (rule->field_name[0] && rule->field_value[0]) {
            if (!message || !strstr(message, rule->field_value)) {
                matches = false;
            }
        }
        
        if (matches) {
            pthread_mutex_unlock(&audit_rules_lock);
            return true;
        }
    }
    
    pthread_mutex_unlock(&audit_rules_lock);
    return false;
}

static void write_to_log_file(const kos_audit_event_t* event) {
    if (!audit_state.log_file) {
        return;
    }
    
    time_t timestamp = event->timestamp / 1000000000ULL;
    struct tm* tm_info = localtime(&timestamp);
    char time_str[64];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", tm_info);
    
    const char* type_name = (event->type < sizeof(audit_type_names) / sizeof(audit_type_names[0])) ?
        audit_type_names[event->type] : "UNKNOWN";
    
    fprintf(audit_state.log_file,
            "type=%s msg=audit(%llu.%03llu:%llu): pid=%u uid=%u gid=%u "
            "comm=\"%s\" exe=\"%s\" msg=\"%s\"\n",
            type_name,
            (unsigned long long)(timestamp),
            (unsigned long long)((event->timestamp % 1000000000ULL) / 1000000ULL),
            (unsigned long long)audit_state.sequence_number++,
            event->pid, event->uid, event->gid,
            event->comm, event->exe, event->message);
    
    fflush(audit_state.log_file);
}

int kos_audit_init(void) {
    pthread_mutex_lock(&audit_state.lock);
    
    /* Allocate event buffer */
    pthread_mutex_lock(&audit_buffer.lock);
    if (!audit_buffer.events) {
        audit_buffer.events = calloc(audit_buffer.capacity, 
                                     sizeof(kos_audit_event_t));
        if (!audit_buffer.events) {
            pthread_mutex_unlock(&audit_buffer.lock);
            pthread_mutex_unlock(&audit_state.lock);
            return KOS_SEC_ENOMEM;
        }
    }
    pthread_mutex_unlock(&audit_buffer.lock);
    
    /* Open log file */
    audit_state.log_file = fopen(audit_state.log_path, "a");
    if (!audit_state.log_file) {
        /* Try to create in current directory if /var/log doesn't exist */
        strcpy(audit_state.log_path, "./kos_audit.log");
        audit_state.log_file = fopen(audit_state.log_path, "a");
    }
    
    if (audit_state.log_file) {
        audit_state.enabled = true;
        printf("[KOS Security] Audit system initialized (log: %s)\n", 
               audit_state.log_path);
    } else {
        printf("[KOS Security] Warning: Could not open audit log file\n");
    }
    
    pthread_mutex_unlock(&audit_state.lock);
    
    /* Log audit system startup */
    kos_audit_log_event(KOS_AUDIT_CONFIG_CHANGE, getpid(), 
                         "Audit system initialized");
    
    return KOS_SEC_SUCCESS;
}

void kos_audit_cleanup(void) {
    pthread_mutex_lock(&audit_state.lock);
    
    if (audit_state.log_file) {
        fclose(audit_state.log_file);
        audit_state.log_file = NULL;
    }
    
    audit_state.enabled = false;
    
    pthread_mutex_unlock(&audit_state.lock);
    
    pthread_mutex_lock(&audit_buffer.lock);
    if (audit_buffer.events) {
        free(audit_buffer.events);
        audit_buffer.events = NULL;
    }
    audit_buffer.head = audit_buffer.tail = audit_buffer.count = 0;
    pthread_mutex_unlock(&audit_buffer.lock);
    
    pthread_mutex_lock(&audit_rules_lock);
    if (audit_rules) {
        free(audit_rules);
        audit_rules = NULL;
    }
    audit_rule_count = audit_rule_capacity = 0;
    pthread_mutex_unlock(&audit_rules_lock);
    
    printf("[KOS Security] Audit system cleanup completed\n");
}

int kos_audit_log_event(kos_audit_type_t type, uint32_t pid, 
                        const char* message) {
    if (!message) {
        return KOS_SEC_EINVAL;
    }
    
    if (!should_audit_event(type, pid, message)) {
        return KOS_SEC_SUCCESS;
    }
    
    kos_audit_event_t event = {0};
    event.timestamp = get_timestamp_ns();
    event.pid = pid;
    event.uid = getuid();
    event.gid = getgid();
    event.type = type;
    
    strncpy(event.message, message, sizeof(event.message) - 1);
    event.message[sizeof(event.message) - 1] = '\0';
    
    get_process_info(pid, event.comm, sizeof(event.comm),
                     event.exe, sizeof(event.exe));
    
    /* Add to circular buffer */
    pthread_mutex_lock(&audit_buffer.lock);
    if (audit_buffer.events) {
        audit_buffer.events[audit_buffer.tail] = event;
        audit_buffer.tail = (audit_buffer.tail + 1) % audit_buffer.capacity;
        
        if (audit_buffer.count < audit_buffer.capacity) {
            audit_buffer.count++;
        } else {
            /* Buffer full, advance head */
            audit_buffer.head = (audit_buffer.head + 1) % audit_buffer.capacity;
        }
    }
    pthread_mutex_unlock(&audit_buffer.lock);
    
    /* Write to log file */
    pthread_mutex_lock(&audit_state.lock);
    write_to_log_file(&event);
    pthread_mutex_unlock(&audit_state.lock);
    
    return KOS_SEC_SUCCESS;
}

int kos_audit_set_enabled(bool enabled) {
    pthread_mutex_lock(&audit_state.lock);
    
    bool old_enabled = audit_state.enabled;
    audit_state.enabled = enabled;
    
    pthread_mutex_unlock(&audit_state.lock);
    
    if (old_enabled != enabled) {
        kos_audit_log_event(KOS_AUDIT_CONFIG_CHANGE, getpid(),
                             enabled ? "Audit enabled" : "Audit disabled");
    }
    
    return KOS_SEC_SUCCESS;
}

bool kos_audit_is_enabled(void) {
    pthread_mutex_lock(&audit_state.lock);
    bool enabled = audit_state.enabled;
    pthread_mutex_unlock(&audit_state.lock);
    return enabled;
}

int kos_audit_get_events(kos_audit_event_t* events, size_t max_events,
                         size_t* count) {
    if (!events || !count) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&audit_buffer.lock);
    
    *count = 0;
    if (!audit_buffer.events) {
        pthread_mutex_unlock(&audit_buffer.lock);
        return KOS_SEC_SUCCESS;
    }
    
    size_t available = audit_buffer.count;
    size_t to_copy = (available < max_events) ? available : max_events;
    
    size_t head = audit_buffer.head;
    for (size_t i = 0; i < to_copy; i++) {
        events[i] = audit_buffer.events[head];
        head = (head + 1) % audit_buffer.capacity;
    }
    
    *count = to_copy;
    pthread_mutex_unlock(&audit_buffer.lock);
    
    return KOS_SEC_SUCCESS;
}

/* Audit rule management */
int kos_audit_add_rule(kos_audit_type_t type, uint32_t pid,
                       const char* field_name, const char* field_value) {
    pthread_mutex_lock(&audit_rules_lock);
    
    /* Expand rules array if needed */
    if (audit_rule_count >= audit_rule_capacity) {
        size_t new_capacity = audit_rule_capacity + 10;
        struct audit_rule* new_rules = realloc(audit_rules,
            sizeof(struct audit_rule) * new_capacity);
        
        if (!new_rules) {
            pthread_mutex_unlock(&audit_rules_lock);
            return KOS_SEC_ENOMEM;
        }
        
        audit_rules = new_rules;
        audit_rule_capacity = new_capacity;
    }
    
    /* Add new rule */
    struct audit_rule* rule = &audit_rules[audit_rule_count];
    rule->type = type;
    rule->pid = pid;
    rule->enabled = true;
    
    if (field_name) {
        strncpy(rule->field_name, field_name, sizeof(rule->field_name) - 1);
        rule->field_name[sizeof(rule->field_name) - 1] = '\0';
    } else {
        rule->field_name[0] = '\0';
    }
    
    if (field_value) {
        strncpy(rule->field_value, field_value, sizeof(rule->field_value) - 1);
        rule->field_value[sizeof(rule->field_value) - 1] = '\0';
    } else {
        rule->field_value[0] = '\0';
    }
    
    audit_rule_count++;
    
    pthread_mutex_unlock(&audit_rules_lock);
    
    char msg[256];
    snprintf(msg, sizeof(msg), "Added audit rule: type=%d pid=%u field=%s value=%s",
             type, pid, field_name ? field_name : "", field_value ? field_value : "");
    kos_audit_log_event(KOS_AUDIT_CONFIG_CHANGE, getpid(), msg);
    
    return KOS_SEC_SUCCESS;
}

int kos_audit_remove_rule(size_t rule_index) {
    pthread_mutex_lock(&audit_rules_lock);
    
    if (rule_index >= audit_rule_count) {
        pthread_mutex_unlock(&audit_rules_lock);
        return KOS_SEC_EINVAL;
    }
    
    /* Shift remaining rules down */
    for (size_t i = rule_index; i < audit_rule_count - 1; i++) {
        audit_rules[i] = audit_rules[i + 1];
    }
    audit_rule_count--;
    
    pthread_mutex_unlock(&audit_rules_lock);
    
    char msg[64];
    snprintf(msg, sizeof(msg), "Removed audit rule %zu", rule_index);
    kos_audit_log_event(KOS_AUDIT_CONFIG_CHANGE, getpid(), msg);
    
    return KOS_SEC_SUCCESS;
}

/* Convenience functions for common audit events */
void kos_audit_syscall(uint32_t pid, const char* syscall_name, int result) {
    char msg[256];
    snprintf(msg, sizeof(msg), "syscall=%s result=%d", syscall_name, result);
    kos_audit_log_event(KOS_AUDIT_SYSCALL, pid, msg);
}

void kos_audit_file_access(uint32_t pid, const char* path, const char* operation) {
    char msg[512];
    snprintf(msg, sizeof(msg), "path=%s op=%s", path, operation);
    kos_audit_log_event(KOS_AUDIT_PATH, pid, msg);
}

void kos_audit_process_exec(uint32_t pid, const char* executable, 
                            const char* args) {
    char msg[512];
    snprintf(msg, sizeof(msg), "exe=%s args=%s", executable, args ? args : "");
    kos_audit_log_event(KOS_AUDIT_EXECVE, pid, msg);
}

void kos_audit_login_event(uint32_t pid, const char* username, bool success) {
    char msg[256];
    snprintf(msg, sizeof(msg), "user=%s result=%s", username, 
             success ? "success" : "failure");
    kos_audit_log_event(KOS_AUDIT_LOGIN, pid, msg);
}

void kos_audit_selinux_denial(uint32_t pid, const char* scontext,
                              const char* tcontext, const char* tclass,
                              const char* perm) {
    char msg[512];
    snprintf(msg, sizeof(msg), "denied { %s } for scontext=%s tcontext=%s tclass=%s",
             perm, scontext, tcontext, tclass);
    kos_audit_log_event(KOS_AUDIT_AVC, pid, msg);
}

/* Print audit statistics */
void kos_audit_print_stats(void) {
    pthread_mutex_lock(&audit_state.lock);
    pthread_mutex_lock(&audit_buffer.lock);
    pthread_mutex_lock(&audit_rules_lock);
    
    printf("KOS Audit System Status:\n");
    printf("  Enabled: %s\n", audit_state.enabled ? "yes" : "no");
    printf("  Log file: %s\n", audit_state.log_path);
    printf("  Sequence number: %llu\n", 
           (unsigned long long)audit_state.sequence_number);
    printf("  Buffer capacity: %zu\n", audit_buffer.capacity);
    printf("  Buffer usage: %zu/%zu events\n", 
           audit_buffer.count, audit_buffer.capacity);
    printf("  Active rules: %zu\n", audit_rule_count);
    
    if (audit_rule_count > 0) {
        printf("  Rules:\n");
        for (size_t i = 0; i < audit_rule_count; i++) {
            struct audit_rule* rule = &audit_rules[i];
            const char* type_name = (rule->type < sizeof(audit_type_names) / sizeof(audit_type_names[0])) ?
                audit_type_names[rule->type] : "ANY";
            
            printf("    %zu: type=%s pid=%u field=%s value=%s enabled=%s\n",
                   i, type_name, rule->pid, rule->field_name, rule->field_value,
                   rule->enabled ? "yes" : "no");
        }
    }
    
    pthread_mutex_unlock(&audit_rules_lock);
    pthread_mutex_unlock(&audit_buffer.lock);
    pthread_mutex_unlock(&audit_state.lock);
}