#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <errno.h>

/* Process capability table */
static struct {
    uint32_t pid;
    kos_capability_set_t caps;
    bool in_use;
} capability_table[KOS_MAX_CONTEXTS];

static pthread_mutex_t cap_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool cap_initialized = false;

/* Default capability names for debugging */
static const char* capability_names[KOS_CAP_MAX] = {
    [KOS_CAP_CHOWN] = "chown",
    [KOS_CAP_DAC_OVERRIDE] = "dac_override",
    [KOS_CAP_DAC_READ_SEARCH] = "dac_read_search",
    [KOS_CAP_FOWNER] = "fowner",
    [KOS_CAP_FSETID] = "fsetid",
    [KOS_CAP_KILL] = "kill",
    [KOS_CAP_SETGID] = "setgid",
    [KOS_CAP_SETUID] = "setuid",
    [KOS_CAP_SETPCAP] = "setpcap",
    [KOS_CAP_LINUX_IMMUTABLE] = "linux_immutable",
    [KOS_CAP_NET_BIND_SERVICE] = "net_bind_service",
    [KOS_CAP_NET_BROADCAST] = "net_broadcast",
    [KOS_CAP_NET_ADMIN] = "net_admin",
    [KOS_CAP_NET_RAW] = "net_raw",
    [KOS_CAP_IPC_LOCK] = "ipc_lock",
    [KOS_CAP_IPC_OWNER] = "ipc_owner",
    [KOS_CAP_SYS_MODULE] = "sys_module",
    [KOS_CAP_SYS_RAWIO] = "sys_rawio",
    [KOS_CAP_SYS_CHROOT] = "sys_chroot",
    [KOS_CAP_SYS_PTRACE] = "sys_ptrace",
    [KOS_CAP_SYS_PACCT] = "sys_pacct",
    [KOS_CAP_SYS_ADMIN] = "sys_admin",
    [KOS_CAP_SYS_BOOT] = "sys_boot",
    [KOS_CAP_SYS_NICE] = "sys_nice",
    [KOS_CAP_SYS_RESOURCE] = "sys_resource",
    [KOS_CAP_SYS_TIME] = "sys_time",
    [KOS_CAP_SYS_TTY_CONFIG] = "sys_tty_config",
    [KOS_CAP_MKNOD] = "mknod",
    [KOS_CAP_LEASE] = "lease",
    [KOS_CAP_AUDIT_WRITE] = "audit_write",
    [KOS_CAP_AUDIT_CONTROL] = "audit_control",
    [KOS_CAP_SETFCAP] = "setfcap",
    [KOS_CAP_MAC_OVERRIDE] = "mac_override",
    [KOS_CAP_MAC_ADMIN] = "mac_admin",
    [KOS_CAP_SYSLOG] = "syslog",
    [KOS_CAP_WAKE_ALARM] = "wake_alarm",
    [KOS_CAP_BLOCK_SUSPEND] = "block_suspend",
    [KOS_CAP_AUDIT_READ] = "audit_read",
    [KOS_CAP_PERFMON] = "perfmon",
    [KOS_CAP_BPF] = "bpf",
    [KOS_CAP_CHECKPOINT_RESTORE] = "checkpoint_restore"
};

static int find_capability_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (capability_table[i].in_use && capability_table[i].pid == pid) {
            return i;
        }
    }
    return -1;
}

static int allocate_capability_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (!capability_table[i].in_use) {
            capability_table[i].pid = pid;
            capability_table[i].in_use = true;
            memset(&capability_table[i].caps, 0, sizeof(kos_capability_set_t));
            return i;
        }
    }
    return -1;
}

int kos_cap_init(void) {
    pthread_mutex_lock(&cap_mutex);
    
    if (cap_initialized) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    /* Initialize capability table */
    memset(capability_table, 0, sizeof(capability_table));
    
    /* Set up default capabilities for init process (PID 1) */
    int slot = allocate_capability_slot(1);
    if (slot >= 0) {
        kos_capability_set_t* caps = &capability_table[slot].caps;
        /* Give init full capabilities */
        caps->effective = 0xFFFFFFFFFFFFFFFFULL;
        caps->permitted = 0xFFFFFFFFFFFFFFFFULL;
        caps->inheritable = 0xFFFFFFFFFFFFFFFFULL;
        caps->bounding = 0xFFFFFFFFFFFFFFFFULL;
        caps->ambient = 0;
    }
    
    cap_initialized = true;
    pthread_mutex_unlock(&cap_mutex);
    
    printf("[KOS Security] Capability system initialized\n");
    return KOS_SEC_SUCCESS;
}

int kos_cap_get(uint32_t pid, kos_capability_set_t* caps) {
    if (!caps) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        /* Allocate new slot with default capabilities */
        slot = allocate_capability_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&cap_mutex);
            return KOS_SEC_ENOMEM;
        }
        
        /* Set default capabilities for regular processes */
        kos_capability_set_t* default_caps = &capability_table[slot].caps;
        default_caps->effective = 0;
        default_caps->permitted = 0;
        default_caps->inheritable = 0;
        default_caps->bounding = 0xFFFFFFFFFFFFFFFFULL;
        default_caps->ambient = 0;
    }
    
    *caps = capability_table[slot].caps;
    pthread_mutex_unlock(&cap_mutex);
    
    return KOS_SEC_SUCCESS;
}

int kos_cap_set(uint32_t pid, const kos_capability_set_t* caps) {
    if (!caps) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        slot = allocate_capability_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&cap_mutex);
            return KOS_SEC_ENOMEM;
        }
    }
    
    /* Validate capability transition rules */
    kos_capability_set_t* current = &capability_table[slot].caps;
    
    /* New permitted capabilities must be subset of current permitted */
    if ((caps->permitted & ~current->permitted) != 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EPERM;
    }
    
    /* New effective capabilities must be subset of new permitted */
    if ((caps->effective & ~caps->permitted) != 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EINVAL;
    }
    
    /* New inheritable capabilities must be subset of new permitted and bounding */
    if ((caps->inheritable & ~(caps->permitted & current->bounding)) != 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EPERM;
    }
    
    /* Bounding set can only be reduced */
    if ((caps->bounding & ~current->bounding) != 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EPERM;
    }
    
    capability_table[slot].caps = *caps;
    pthread_mutex_unlock(&cap_mutex);
    
    return KOS_SEC_SUCCESS;
}

bool kos_cap_capable(uint32_t pid, kos_capability_t cap) {
    if (cap >= KOS_CAP_MAX) {
        return false;
    }
    
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        pthread_mutex_unlock(&cap_mutex);
        return false;
    }
    
    bool capable = KOS_CAP_IS_SET(capability_table[slot].caps.effective, cap);
    pthread_mutex_unlock(&cap_mutex);
    
    return capable;
}

int kos_cap_drop(uint32_t pid, kos_capability_t cap) {
    if (cap >= KOS_CAP_MAX) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EINVAL;
    }
    
    kos_capability_set_t* caps = &capability_table[slot].caps;
    KOS_CAP_CLEAR(caps->effective, cap);
    KOS_CAP_CLEAR(caps->permitted, cap);
    KOS_CAP_CLEAR(caps->inheritable, cap);
    KOS_CAP_CLEAR(caps->bounding, cap);
    KOS_CAP_CLEAR(caps->ambient, cap);
    
    pthread_mutex_unlock(&cap_mutex);
    
    return KOS_SEC_SUCCESS;
}

int kos_cap_raise(uint32_t pid, kos_capability_t cap) {
    if (cap >= KOS_CAP_MAX) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EINVAL;
    }
    
    kos_capability_set_t* caps = &capability_table[slot].caps;
    
    /* Can only raise capabilities that are in permitted set */
    if (!KOS_CAP_IS_SET(caps->permitted, cap)) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EPERM;
    }
    
    KOS_CAP_SET(caps->effective, cap);
    pthread_mutex_unlock(&cap_mutex);
    
    return KOS_SEC_SUCCESS;
}

/* Capability transition during exec */
int kos_cap_exec_transition(uint32_t pid, const char* filename) {
    pthread_mutex_lock(&cap_mutex);
    
    int slot = find_capability_slot(pid);
    if (slot < 0) {
        pthread_mutex_unlock(&cap_mutex);
        return KOS_SEC_EINVAL;
    }
    
    kos_capability_set_t* caps = &capability_table[slot].caps;
    
    /* Standard exec capability transition:
     * P'(effective) = F(effective) ? P'(permitted) : P'(ambient)
     * P'(permitted) = (P(inheritable) & F(inheritable)) | 
     *                 (F(permitted) & cap_bset) | P'(ambient)
     * P'(inheritable) = P(inheritable)
     * P'(bounding) = P(bounding)
     * P'(ambient) = (file has no caps) ? P(ambient) : 0
     */
    
    /* For simplicity, assume file has no capabilities */
    uint64_t new_permitted = caps->inheritable & caps->bounding;
    uint64_t new_effective = caps->ambient;
    uint64_t new_inheritable = caps->inheritable;
    uint64_t new_bounding = caps->bounding;
    uint64_t new_ambient = caps->ambient;
    
    caps->effective = new_effective;
    caps->permitted = new_permitted;
    caps->inheritable = new_inheritable;
    caps->bounding = new_bounding;
    caps->ambient = new_ambient;
    
    pthread_mutex_unlock(&cap_mutex);
    
    return KOS_SEC_SUCCESS;
}

/* Check if capability is required for operation */
int kos_cap_check_operation(uint32_t pid, const char* operation) {
    if (!operation) {
        return KOS_SEC_EINVAL;
    }
    
    kos_capability_t required_cap = KOS_CAP_MAX;
    
    /* Map operations to required capabilities */
    if (strcmp(operation, "chown") == 0) {
        required_cap = KOS_CAP_CHOWN;
    } else if (strcmp(operation, "setuid") == 0) {
        required_cap = KOS_CAP_SETUID;
    } else if (strcmp(operation, "setgid") == 0) {
        required_cap = KOS_CAP_SETGID;
    } else if (strcmp(operation, "kill") == 0) {
        required_cap = KOS_CAP_KILL;
    } else if (strcmp(operation, "net_bind_service") == 0) {
        required_cap = KOS_CAP_NET_BIND_SERVICE;
    } else if (strcmp(operation, "sys_admin") == 0) {
        required_cap = KOS_CAP_SYS_ADMIN;
    } else if (strcmp(operation, "sys_module") == 0) {
        required_cap = KOS_CAP_SYS_MODULE;
    } else if (strcmp(operation, "ptrace") == 0) {
        required_cap = KOS_CAP_SYS_PTRACE;
    }
    
    if (required_cap == KOS_CAP_MAX) {
        /* Unknown operation, allow by default */
        return KOS_SEC_SUCCESS;
    }
    
    if (!kos_cap_capable(pid, required_cap)) {
        return KOS_SEC_EPERM;
    }
    
    return KOS_SEC_SUCCESS;
}

/* Debug function to print capabilities */
void kos_cap_print(uint32_t pid) {
    kos_capability_set_t caps;
    if (kos_cap_get(pid, &caps) != KOS_SEC_SUCCESS) {
        printf("Failed to get capabilities for PID %u\n", pid);
        return;
    }
    
    printf("Capabilities for PID %u:\n", pid);
    printf("  Effective:   0x%016llx\n", (unsigned long long)caps.effective);
    printf("  Permitted:   0x%016llx\n", (unsigned long long)caps.permitted);
    printf("  Inheritable: 0x%016llx\n", (unsigned long long)caps.inheritable);
    printf("  Bounding:    0x%016llx\n", (unsigned long long)caps.bounding);
    printf("  Ambient:     0x%016llx\n", (unsigned long long)caps.ambient);
    
    printf("  Active capabilities: ");
    for (int i = 0; i < KOS_CAP_MAX; i++) {
        if (KOS_CAP_IS_SET(caps.effective, i) && capability_names[i]) {
            printf("%s ", capability_names[i]);
        }
    }
    printf("\n");
}