#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <errno.h>

/* Process seccomp state */
static struct {
    uint32_t pid;
    kos_seccomp_mode_t mode;
    kos_seccomp_filter_t* filters;
    size_t filter_count;
    size_t filter_capacity;
    bool in_use;
} seccomp_table[KOS_MAX_CONTEXTS];

static pthread_mutex_t seccomp_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool seccomp_initialized = false;

/* System call table for validation */
static const char* syscall_names[] = {
    [0] = "read", [1] = "write", [2] = "open", [3] = "close",
    [4] = "stat", [5] = "fstat", [6] = "lstat", [7] = "poll",
    [8] = "lseek", [9] = "mmap", [10] = "mprotect", [11] = "munmap",
    [12] = "brk", [13] = "rt_sigaction", [14] = "rt_sigprocmask",
    [15] = "rt_sigreturn", [16] = "ioctl", [17] = "pread64",
    [18] = "pwrite64", [19] = "readv", [20] = "writev", [21] = "access",
    [22] = "pipe", [23] = "select", [24] = "sched_yield", [25] = "mremap",
    [26] = "msync", [27] = "mincore", [28] = "madvise", [29] = "shmget",
    [30] = "shmat", [31] = "shmctl", [32] = "dup", [33] = "dup2",
    [34] = "pause", [35] = "nanosleep", [36] = "getitimer", [37] = "alarm",
    [38] = "setitimer", [39] = "getpid", [40] = "sendfile", [41] = "socket",
    [42] = "connect", [43] = "accept", [44] = "sendto", [45] = "recvfrom",
    [46] = "sendmsg", [47] = "recvmsg", [48] = "shutdown", [49] = "bind",
    [50] = "listen", [51] = "getsockname", [52] = "getpeername",
    [53] = "socketpair", [54] = "setsockopt", [55] = "getsockopt",
    [56] = "clone", [57] = "fork", [58] = "vfork", [59] = "execve",
    [60] = "exit", [61] = "wait4", [62] = "kill", [63] = "uname"
};

#define MAX_SYSCALL_NR (sizeof(syscall_names) / sizeof(syscall_names[0]))

/* BPF operation codes */
#define KOS_BPF_EQ  0x10
#define KOS_BPF_GT  0x20
#define KOS_BPF_GE  0x30
#define KOS_BPF_LT  0x40
#define KOS_BPF_LE  0x50
#define KOS_BPF_AND 0x60
#define KOS_BPF_OR  0x70

static int find_seccomp_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (seccomp_table[i].in_use && seccomp_table[i].pid == pid) {
            return i;
        }
    }
    return -1;
}

static int allocate_seccomp_slot(uint32_t pid) {
    for (int i = 0; i < KOS_MAX_CONTEXTS; i++) {
        if (!seccomp_table[i].in_use) {
            seccomp_table[i].pid = pid;
            seccomp_table[i].mode = KOS_SECCOMP_MODE_DISABLED;
            seccomp_table[i].filters = NULL;
            seccomp_table[i].filter_count = 0;
            seccomp_table[i].filter_capacity = 0;
            seccomp_table[i].in_use = true;
            return i;
        }
    }
    return -1;
}

static bool is_safe_syscall(uint32_t syscall_nr) {
    /* List of syscalls allowed in strict mode */
    static const uint32_t safe_syscalls[] = {
        SYS_read, SYS_write, SYS_exit, SYS_exit_group,
        SYS_rt_sigreturn, SYS_brk, SYS_mmap, SYS_munmap
    };
    
    for (size_t i = 0; i < sizeof(safe_syscalls) / sizeof(safe_syscalls[0]); i++) {
        if (syscall_nr == safe_syscalls[i]) {
            return true;
        }
    }
    return false;
}

static bool evaluate_filter_condition(const kos_seccomp_filter_t* filter,
                                       uint64_t* args) {
    /* Simple condition evaluation */
    for (uint32_t i = 0; i < filter->arg_count; i++) {
        if (filter->args[i].arg >= 6) continue; /* Invalid arg index */
        
        uint64_t arg_value = args[filter->args[i].arg];
        uint64_t expected = filter->args[i].value;
        
        switch (filter->args[i].op) {
            case KOS_BPF_EQ:
                if (arg_value != expected) return false;
                break;
            case KOS_BPF_GT:
                if (arg_value <= expected) return false;
                break;
            case KOS_BPF_GE:
                if (arg_value < expected) return false;
                break;
            case KOS_BPF_LT:
                if (arg_value >= expected) return false;
                break;
            case KOS_BPF_LE:
                if (arg_value > expected) return false;
                break;
            case KOS_BPF_AND:
                if ((arg_value & expected) == 0) return false;
                break;
            default:
                return false;
        }
    }
    return true;
}

int kos_seccomp_init(void) {
    pthread_mutex_lock(&seccomp_mutex);
    
    if (seccomp_initialized) {
        pthread_mutex_unlock(&seccomp_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    /* Initialize seccomp table */
    memset(seccomp_table, 0, sizeof(seccomp_table));
    
    seccomp_initialized = true;
    pthread_mutex_unlock(&seccomp_mutex);
    
    printf("[KOS Security] Seccomp system initialized\n");
    return KOS_SEC_SUCCESS;
}

int kos_seccomp_set_mode(uint32_t pid, kos_seccomp_mode_t mode) {
    if (mode > KOS_SECCOMP_MODE_FILTER) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    if (slot < 0) {
        slot = allocate_seccomp_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&seccomp_mutex);
            return KOS_SEC_ENOMEM;
        }
    }
    
    /* Seccomp mode can only be made more restrictive */
    if (mode < seccomp_table[slot].mode) {
        pthread_mutex_unlock(&seccomp_mutex);
        return KOS_SEC_EPERM;
    }
    
    seccomp_table[slot].mode = mode;
    pthread_mutex_unlock(&seccomp_mutex);
    
    const char* mode_names[] = { "disabled", "strict", "filter" };
    printf("[KOS Security] PID %u seccomp mode set to %s\n", 
           pid, mode_names[mode]);
    
    return KOS_SEC_SUCCESS;
}

kos_seccomp_mode_t kos_seccomp_get_mode(uint32_t pid) {
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    kos_seccomp_mode_t mode = KOS_SECCOMP_MODE_DISABLED;
    
    if (slot >= 0) {
        mode = seccomp_table[slot].mode;
    }
    
    pthread_mutex_unlock(&seccomp_mutex);
    return mode;
}

int kos_seccomp_add_filter(uint32_t pid, const kos_seccomp_filter_t* filter) {
    if (!filter) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    if (slot < 0) {
        slot = allocate_seccomp_slot(pid);
        if (slot < 0) {
            pthread_mutex_unlock(&seccomp_mutex);
            return KOS_SEC_ENOMEM;
        }
    }
    
    /* Expand filter array if needed */
    if (seccomp_table[slot].filter_count >= seccomp_table[slot].filter_capacity) {
        size_t new_capacity = seccomp_table[slot].filter_capacity + 16;
        kos_seccomp_filter_t* new_filters = realloc(
            seccomp_table[slot].filters,
            sizeof(kos_seccomp_filter_t) * new_capacity);
        
        if (!new_filters) {
            pthread_mutex_unlock(&seccomp_mutex);
            return KOS_SEC_ENOMEM;
        }
        
        seccomp_table[slot].filters = new_filters;
        seccomp_table[slot].filter_capacity = new_capacity;
    }
    
    /* Add the filter */
    seccomp_table[slot].filters[seccomp_table[slot].filter_count] = *filter;
    seccomp_table[slot].filter_count++;
    
    pthread_mutex_unlock(&seccomp_mutex);
    
    printf("[KOS Security] Added seccomp filter for PID %u (syscall %u)\n",
           pid, filter->syscall_nr);
    
    return KOS_SEC_SUCCESS;
}

int kos_seccomp_check_syscall(uint32_t pid, uint32_t syscall_nr,
                              uint64_t* args, size_t arg_count) {
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    if (slot < 0) {
        /* No seccomp restrictions */
        pthread_mutex_unlock(&seccomp_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    kos_seccomp_mode_t mode = seccomp_table[slot].mode;
    
    switch (mode) {
        case KOS_SECCOMP_MODE_DISABLED:
            pthread_mutex_unlock(&seccomp_mutex);
            return KOS_SEC_SUCCESS;
            
        case KOS_SECCOMP_MODE_STRICT:
            if (!is_safe_syscall(syscall_nr)) {
                pthread_mutex_unlock(&seccomp_mutex);
                printf("[KOS Security] Seccomp strict: killing PID %u for syscall %u\n",
                       pid, syscall_nr);
                return KOS_SECCOMP_RET_KILL_PROCESS;
            }
            pthread_mutex_unlock(&seccomp_mutex);
            return KOS_SEC_SUCCESS;
            
        case KOS_SECCOMP_MODE_FILTER:
            /* Check all filters for this syscall */
            for (size_t i = 0; i < seccomp_table[slot].filter_count; i++) {
                kos_seccomp_filter_t* filter = &seccomp_table[slot].filters[i];
                
                if (filter->syscall_nr == syscall_nr) {
                    if (evaluate_filter_condition(filter, args)) {
                        uint32_t action = filter->action;
                        pthread_mutex_unlock(&seccomp_mutex);
                        
                        if (action != KOS_SECCOMP_RET_ALLOW) {
                            const char* syscall_name = (syscall_nr < MAX_SYSCALL_NR) ?
                                syscall_names[syscall_nr] : "unknown";
                            printf("[KOS Security] Seccomp filter: action 0x%x for PID %u syscall %s\n",
                                   action, pid, syscall_name);
                        }
                        
                        return action;
                    }
                }
            }
            
            /* No matching filter found - default deny */
            pthread_mutex_unlock(&seccomp_mutex);
            printf("[KOS Security] Seccomp filter: no rule for PID %u syscall %u\n",
                   pid, syscall_nr);
            return KOS_SECCOMP_RET_ERRNO | EACCES;
    }
    
    pthread_mutex_unlock(&seccomp_mutex);
    return KOS_SEC_SUCCESS;
}

/* Helper functions for common filter creation */
int kos_seccomp_allow_syscall(uint32_t pid, uint32_t syscall_nr) {
    kos_seccomp_filter_t filter = {
        .syscall_nr = syscall_nr,
        .action = KOS_SECCOMP_RET_ALLOW,
        .arg_count = 0
    };
    
    return kos_seccomp_add_filter(pid, &filter);
}

int kos_seccomp_deny_syscall(uint32_t pid, uint32_t syscall_nr) {
    kos_seccomp_filter_t filter = {
        .syscall_nr = syscall_nr,
        .action = KOS_SECCOMP_RET_ERRNO | EACCES,
        .arg_count = 0
    };
    
    return kos_seccomp_add_filter(pid, &filter);
}

int kos_seccomp_kill_on_syscall(uint32_t pid, uint32_t syscall_nr) {
    kos_seccomp_filter_t filter = {
        .syscall_nr = syscall_nr,
        .action = KOS_SECCOMP_RET_KILL_PROCESS,
        .arg_count = 0
    };
    
    return kos_seccomp_add_filter(pid, &filter);
}

/* Advanced filter with argument checking */
int kos_seccomp_filter_with_args(uint32_t pid, uint32_t syscall_nr,
                                  uint32_t action, uint32_t arg_idx,
                                  uint32_t op, uint64_t value) {
    if (arg_idx >= 6) {
        return KOS_SEC_EINVAL;
    }
    
    kos_seccomp_filter_t filter = {
        .syscall_nr = syscall_nr,
        .action = action,
        .arg_count = 1,
        .args = {{
            .arg = arg_idx,
            .op = op,
            .value = value
        }}
    };
    
    return kos_seccomp_add_filter(pid, &filter);
}

/* Load common seccomp profiles */
int kos_seccomp_load_profile(uint32_t pid, const char* profile_name) {
    if (!profile_name) {
        return KOS_SEC_EINVAL;
    }
    
    if (strcmp(profile_name, "web_browser") == 0) {
        /* Web browser profile - allow network, file I/O, but restrict exec */
        kos_seccomp_set_mode(pid, KOS_SECCOMP_MODE_FILTER);
        
        /* Allow basic I/O */
        kos_seccomp_allow_syscall(pid, SYS_read);
        kos_seccomp_allow_syscall(pid, SYS_write);
        kos_seccomp_allow_syscall(pid, SYS_open);
        kos_seccomp_allow_syscall(pid, SYS_close);
        
        /* Allow network operations */
        kos_seccomp_allow_syscall(pid, SYS_socket);
        kos_seccomp_allow_syscall(pid, SYS_connect);
        kos_seccomp_allow_syscall(pid, SYS_sendto);
        kos_seccomp_allow_syscall(pid, SYS_recvfrom);
        
        /* Deny dangerous operations */
        kos_seccomp_kill_on_syscall(pid, SYS_execve);
        kos_seccomp_deny_syscall(pid, SYS_fork);
        kos_seccomp_deny_syscall(pid, SYS_clone);
        
    } else if (strcmp(profile_name, "calculator") == 0) {
        /* Calculator profile - very restrictive */
        kos_seccomp_set_mode(pid, KOS_SECCOMP_MODE_FILTER);
        
        /* Only allow basic operations */
        kos_seccomp_allow_syscall(pid, SYS_read);
        kos_seccomp_allow_syscall(pid, SYS_write);
        kos_seccomp_allow_syscall(pid, SYS_exit);
        kos_seccomp_allow_syscall(pid, SYS_brk);
        
    } else if (strcmp(profile_name, "network_service") == 0) {
        /* Network service profile */
        kos_seccomp_set_mode(pid, KOS_SECCOMP_MODE_FILTER);
        
        /* Allow network and file I/O */
        kos_seccomp_allow_syscall(pid, SYS_read);
        kos_seccomp_allow_syscall(pid, SYS_write);
        kos_seccomp_allow_syscall(pid, SYS_socket);
        kos_seccomp_allow_syscall(pid, SYS_bind);
        kos_seccomp_allow_syscall(pid, SYS_listen);
        kos_seccomp_allow_syscall(pid, SYS_accept);
        
        /* Restrict port binding to unprivileged ports only */
        kos_seccomp_filter_with_args(pid, SYS_bind, KOS_SECCOMP_RET_ERRNO | EACCES,
                                     1, KOS_BPF_LT, 1024);
        
    } else {
        return KOS_SEC_EINVAL;
    }
    
    printf("[KOS Security] Loaded seccomp profile '%s' for PID %u\n",
           profile_name, pid);
    
    return KOS_SEC_SUCCESS;
}

/* Print seccomp status */
void kos_seccomp_print_status(uint32_t pid) {
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    if (slot < 0) {
        printf("PID %u: seccomp disabled\n", pid);
        pthread_mutex_unlock(&seccomp_mutex);
        return;
    }
    
    const char* mode_names[] = { "disabled", "strict", "filter" };
    printf("PID %u seccomp status:\n", pid);
    printf("  Mode: %s\n", mode_names[seccomp_table[slot].mode]);
    printf("  Filters: %zu\n", seccomp_table[slot].filter_count);
    
    if (seccomp_table[slot].mode == KOS_SECCOMP_MODE_FILTER) {
        printf("  Filter details:\n");
        for (size_t i = 0; i < seccomp_table[slot].filter_count; i++) {
            kos_seccomp_filter_t* filter = &seccomp_table[slot].filters[i];
            const char* syscall_name = (filter->syscall_nr < MAX_SYSCALL_NR) ?
                syscall_names[filter->syscall_nr] : "unknown";
            
            printf("    %s (nr=%u) -> action=0x%x\n",
                   syscall_name, filter->syscall_nr, filter->action);
        }
    }
    
    pthread_mutex_unlock(&seccomp_mutex);
}

/* Cleanup seccomp state for a process */
void kos_seccomp_cleanup_process(uint32_t pid) {
    pthread_mutex_lock(&seccomp_mutex);
    
    int slot = find_seccomp_slot(pid);
    if (slot >= 0) {
        if (seccomp_table[slot].filters) {
            free(seccomp_table[slot].filters);
        }
        memset(&seccomp_table[slot], 0, sizeof(seccomp_table[slot]));
    }
    
    pthread_mutex_unlock(&seccomp_mutex);
}