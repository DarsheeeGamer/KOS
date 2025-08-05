/*
 * KOS Kernel Configuration Management (sysctl)
 * Provides runtime kernel parameter configuration
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <errno.h>
#include <limits.h>
#include "sysctl.h"

/* Sysctl types */
typedef enum {
    SYSCTL_TYPE_INT = 0,
    SYSCTL_TYPE_UINT,
    SYSCTL_TYPE_LONG,
    SYSCTL_TYPE_ULONG,
    SYSCTL_TYPE_STRING,
    SYSCTL_TYPE_BOOL,
    SYSCTL_TYPE_PROC
} sysctl_type_t;

/* Sysctl flags */
#define SYSCTL_FLAG_RO      0x01  /* Read-only */
#define SYSCTL_FLAG_RW      0x02  /* Read-write */
#define SYSCTL_FLAG_SECURE  0x04  /* Requires CAP_SYS_ADMIN */
#define SYSCTL_FLAG_RUNTIME 0x08  /* Can be changed at runtime */
#define SYSCTL_FLAG_BOOT    0x10  /* Boot-time only */

/* Sysctl handler function */
typedef int (*sysctl_handler_t)(void *oldval, size_t *oldlen,
                                void *newval, size_t newlen);

/* Sysctl entry */
typedef struct sysctl_entry {
    char name[256];                   /* Full path name */
    char description[512];            /* Description */
    sysctl_type_t type;              /* Data type */
    uint32_t flags;                  /* Access flags */
    void *data;                      /* Pointer to data */
    size_t data_size;                /* Data size */
    void *min_value;                 /* Minimum value (for numeric) */
    void *max_value;                 /* Maximum value (for numeric) */
    sysctl_handler_t handler;        /* Custom handler */
    struct sysctl_entry *parent;     /* Parent entry */
    struct sysctl_entry *child;      /* First child */
    struct sysctl_entry *next;       /* Next sibling */
} sysctl_entry_t;

/* Global sysctl table */
static sysctl_entry_t *sysctl_root = NULL;
static pthread_rwlock_t sysctl_lock = PTHREAD_RWLOCK_INITIALIZER;

/* Kernel configuration variables */
/* VM subsystem */
static uint64_t vm_swappiness = 60;
static uint64_t vm_dirty_ratio = 20;
static uint64_t vm_dirty_background_ratio = 10;
static uint64_t vm_overcommit_memory = 0;
static uint64_t vm_overcommit_ratio = 50;
static uint64_t vm_min_free_kbytes = 65536;
static uint64_t vm_vfs_cache_pressure = 100;
static uint64_t vm_page_cluster = 3;

/* Scheduler parameters */
static uint64_t kernel_sched_latency_ns = 6000000;
static uint64_t kernel_sched_min_granularity_ns = 1500000;
static uint64_t kernel_sched_wakeup_granularity_ns = 2000000;
static uint64_t kernel_sched_migration_cost_ns = 500000;
static uint64_t kernel_sched_nr_migrate = 32;
static uint64_t kernel_sched_time_avg_ms = 1000;
static uint64_t kernel_sched_rt_period_us = 1000000;
static uint64_t kernel_sched_rt_runtime_us = 950000;

/* Network parameters */
static uint64_t net_core_rmem_default = 212992;
static uint64_t net_core_rmem_max = 212992;
static uint64_t net_core_wmem_default = 212992;
static uint64_t net_core_wmem_max = 212992;
static uint64_t net_core_netdev_max_backlog = 1000;
static uint64_t net_ipv4_tcp_keepalive_time = 7200;
static uint64_t net_ipv4_tcp_keepalive_probes = 9;
static uint64_t net_ipv4_tcp_keepalive_intvl = 75;
static bool net_ipv4_ip_forward = false;
static bool net_ipv6_conf_all_forwarding = false;

/* Kernel parameters */
static char kernel_hostname[256] = "kos";
static char kernel_domainname[256] = "localdomain";
static uint64_t kernel_pid_max = 32768;
static uint64_t kernel_threads_max = 65536;
static uint64_t kernel_msgmax = 8192;
static uint64_t kernel_msgmnb = 16384;
static uint64_t kernel_shmmax = 33554432;
static uint64_t kernel_shmall = 2097152;
static uint64_t kernel_sem[4] = {250, 32000, 32, 128};

/* Security parameters */
static bool kernel_randomize_va_space = true;
static bool kernel_dmesg_restrict = false;
static bool kernel_kptr_restrict = true;
static uint64_t kernel_perf_event_paranoid = 2;

/* Find sysctl entry by path */
static sysctl_entry_t *find_sysctl_entry(const char *path)
{
    if (!path || !sysctl_root) {
        return NULL;
    }
    
    char *path_copy = strdup(path);
    char *token = strtok(path_copy, ".");
    sysctl_entry_t *current = sysctl_root;
    
    while (token && current) {
        sysctl_entry_t *child = current->child;
        bool found = false;
        
        while (child) {
            if (strcmp(child->name + strlen(child->name) - strlen(token), token) == 0) {
                current = child;
                found = true;
                break;
            }
            child = child->next;
        }
        
        if (!found) {
            free(path_copy);
            return NULL;
        }
        
        token = strtok(NULL, ".");
    }
    
    free(path_copy);
    return (current != sysctl_root) ? current : NULL;
}

/* Create sysctl entry */
static sysctl_entry_t *create_sysctl_entry(const char *name, const char *desc,
                                            sysctl_type_t type, uint32_t flags,
                                            void *data, size_t size)
{
    sysctl_entry_t *entry = calloc(1, sizeof(sysctl_entry_t));
    if (!entry) {
        return NULL;
    }
    
    strncpy(entry->name, name, sizeof(entry->name) - 1);
    strncpy(entry->description, desc, sizeof(entry->description) - 1);
    entry->type = type;
    entry->flags = flags;
    entry->data = data;
    entry->data_size = size;
    
    return entry;
}

/* Register sysctl entry */
int register_sysctl(const char *path, const char *desc,
                    sysctl_type_t type, uint32_t flags,
                    void *data, size_t size,
                    void *min, void *max,
                    sysctl_handler_t handler)
{
    if (!path || !data) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&sysctl_lock);
    
    /* Create root if needed */
    if (!sysctl_root) {
        sysctl_root = create_sysctl_entry("", "System control root", 
                                          SYSCTL_TYPE_PROC, SYSCTL_FLAG_RO,
                                          NULL, 0);
        if (!sysctl_root) {
            pthread_rwlock_unlock(&sysctl_lock);
            return -ENOMEM;
        }
    }
    
    /* Parse path and create hierarchy */
    char *path_copy = strdup(path);
    char *token = strtok(path_copy, ".");
    sysctl_entry_t *parent = sysctl_root;
    char current_path[256] = "";
    
    while (token) {
        if (strlen(current_path) > 0) {
            strcat(current_path, ".");
        }
        strcat(current_path, token);
        
        /* Check if this level exists */
        sysctl_entry_t *child = parent->child;
        sysctl_entry_t *found = NULL;
        
        while (child) {
            if (strcmp(child->name, current_path) == 0) {
                found = child;
                break;
            }
            child = child->next;
        }
        
        /* Create if not found */
        if (!found) {
            char *next_token = strtok(NULL, ".");
            
            if (next_token) {
                /* Intermediate node */
                found = create_sysctl_entry(current_path, "",
                                            SYSCTL_TYPE_PROC, SYSCTL_FLAG_RO,
                                            NULL, 0);
            } else {
                /* Leaf node */
                found = create_sysctl_entry(current_path, desc,
                                            type, flags, data, size);
                found->min_value = min;
                found->max_value = max;
                found->handler = handler;
            }
            
            if (!found) {
                free(path_copy);
                pthread_rwlock_unlock(&sysctl_lock);
                return -ENOMEM;
            }
            
            /* Link to parent */
            found->parent = parent;
            found->next = parent->child;
            parent->child = found;
        }
        
        parent = found;
        token = next_token;
    }
    
    free(path_copy);
    pthread_rwlock_unlock(&sysctl_lock);
    
    return 0;
}

/* Read sysctl value */
int sysctl_read(const char *path, void *buffer, size_t *size)
{
    if (!path || !buffer || !size) {
        return -EINVAL;
    }
    
    pthread_rwlock_rdlock(&sysctl_lock);
    
    sysctl_entry_t *entry = find_sysctl_entry(path);
    if (!entry) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -ENOENT;
    }
    
    /* Check if it's a leaf node */
    if (entry->type == SYSCTL_TYPE_PROC) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -EISDIR;
    }
    
    /* Use custom handler if available */
    if (entry->handler) {
        int ret = entry->handler(buffer, size, NULL, 0);
        pthread_rwlock_unlock(&sysctl_lock);
        return ret;
    }
    
    /* Copy data */
    if (*size < entry->data_size) {
        *size = entry->data_size;
        pthread_rwlock_unlock(&sysctl_lock);
        return -ENOSPC;
    }
    
    memcpy(buffer, entry->data, entry->data_size);
    *size = entry->data_size;
    
    pthread_rwlock_unlock(&sysctl_lock);
    return 0;
}

/* Write sysctl value */
int sysctl_write(const char *path, const void *buffer, size_t size)
{
    if (!path || !buffer) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&sysctl_lock);
    
    sysctl_entry_t *entry = find_sysctl_entry(path);
    if (!entry) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -ENOENT;
    }
    
    /* Check permissions */
    if (!(entry->flags & SYSCTL_FLAG_RW)) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -EPERM;
    }
    
    /* Check if runtime modifiable */
    if (!(entry->flags & SYSCTL_FLAG_RUNTIME)) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -EPERM;
    }
    
    /* Validate value range for numeric types */
    if (entry->type >= SYSCTL_TYPE_INT && entry->type <= SYSCTL_TYPE_ULONG) {
        uint64_t value = 0;
        
        switch (entry->type) {
            case SYSCTL_TYPE_INT:
                value = *(int *)buffer;
                break;
            case SYSCTL_TYPE_UINT:
                value = *(unsigned int *)buffer;
                break;
            case SYSCTL_TYPE_LONG:
                value = *(long *)buffer;
                break;
            case SYSCTL_TYPE_ULONG:
                value = *(unsigned long *)buffer;
                break;
            default:
                break;
        }
        
        if (entry->min_value && value < *(uint64_t *)entry->min_value) {
            pthread_rwlock_unlock(&sysctl_lock);
            return -EINVAL;
        }
        
        if (entry->max_value && value > *(uint64_t *)entry->max_value) {
            pthread_rwlock_unlock(&sysctl_lock);
            return -EINVAL;
        }
    }
    
    /* Use custom handler if available */
    if (entry->handler) {
        size_t dummy_size = 0;
        int ret = entry->handler(NULL, &dummy_size, (void *)buffer, size);
        pthread_rwlock_unlock(&sysctl_lock);
        return ret;
    }
    
    /* Update value */
    if (entry->type == SYSCTL_TYPE_STRING) {
        strncpy((char *)entry->data, (const char *)buffer, entry->data_size - 1);
        ((char *)entry->data)[entry->data_size - 1] = '\0';
    } else {
        if (size != entry->data_size) {
            pthread_rwlock_unlock(&sysctl_lock);
            return -EINVAL;
        }
        memcpy(entry->data, buffer, size);
    }
    
    pthread_rwlock_unlock(&sysctl_lock);
    return 0;
}

/* List sysctl entries */
int sysctl_list(const char *path, void (*callback)(const char *, const char *))
{
    if (!callback) {
        return -EINVAL;
    }
    
    pthread_rwlock_rdlock(&sysctl_lock);
    
    sysctl_entry_t *parent = path ? find_sysctl_entry(path) : sysctl_root;
    if (!parent) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -ENOENT;
    }
    
    /* List children */
    sysctl_entry_t *child = parent->child;
    while (child) {
        callback(child->name, child->description);
        child = child->next;
    }
    
    pthread_rwlock_unlock(&sysctl_lock);
    return 0;
}

/* Initialize sysctl subsystem */
int sysctl_init(void)
{
    /* VM parameters */
    register_sysctl("vm.swappiness", "Swappiness value (0-100)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &vm_swappiness, sizeof(vm_swappiness),
                    &(uint64_t){0}, &(uint64_t){100}, NULL);
    
    register_sysctl("vm.dirty_ratio", "Dirty memory ratio (%)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &vm_dirty_ratio, sizeof(vm_dirty_ratio),
                    &(uint64_t){0}, &(uint64_t){100}, NULL);
    
    register_sysctl("vm.dirty_background_ratio", "Dirty background ratio (%)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &vm_dirty_background_ratio, sizeof(vm_dirty_background_ratio),
                    &(uint64_t){0}, &(uint64_t){100}, NULL);
    
    register_sysctl("vm.overcommit_memory", "Memory overcommit mode",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &vm_overcommit_memory, sizeof(vm_overcommit_memory),
                    &(uint64_t){0}, &(uint64_t){2}, NULL);
    
    register_sysctl("vm.min_free_kbytes", "Minimum free memory (KB)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &vm_min_free_kbytes, sizeof(vm_min_free_kbytes),
                    &(uint64_t){1024}, &(uint64_t){1048576}, NULL);
    
    /* Scheduler parameters */
    register_sysctl("kernel.sched_latency_ns", "Scheduler latency (ns)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &kernel_sched_latency_ns, sizeof(kernel_sched_latency_ns),
                    &(uint64_t){1000000}, &(uint64_t){1000000000}, NULL);
    
    register_sysctl("kernel.sched_min_granularity_ns", "Minimum preemption granularity (ns)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &kernel_sched_min_granularity_ns, sizeof(kernel_sched_min_granularity_ns),
                    &(uint64_t){100000}, &(uint64_t){100000000}, NULL);
    
    register_sysctl("kernel.sched_wakeup_granularity_ns", "Wakeup preemption granularity (ns)",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &kernel_sched_wakeup_granularity_ns, sizeof(kernel_sched_wakeup_granularity_ns),
                    &(uint64_t){100000}, &(uint64_t){100000000}, NULL);
    
    /* Network parameters */
    register_sysctl("net.core.rmem_default", "Default receive buffer size",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &net_core_rmem_default, sizeof(net_core_rmem_default),
                    &(uint64_t){4096}, &(uint64_t){134217728}, NULL);
    
    register_sysctl("net.core.wmem_default", "Default send buffer size",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &net_core_wmem_default, sizeof(net_core_wmem_default),
                    &(uint64_t){4096}, &(uint64_t){134217728}, NULL);
    
    register_sysctl("net.ipv4.ip_forward", "IPv4 forwarding",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &net_ipv4_ip_forward, sizeof(net_ipv4_ip_forward),
                    NULL, NULL, NULL);
    
    register_sysctl("net.ipv6.conf.all.forwarding", "IPv6 forwarding",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &net_ipv6_conf_all_forwarding, sizeof(net_ipv6_conf_all_forwarding),
                    NULL, NULL, NULL);
    
    /* Kernel parameters */
    register_sysctl("kernel.hostname", "System hostname",
                    SYSCTL_TYPE_STRING, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    kernel_hostname, sizeof(kernel_hostname),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.domainname", "System domain name",
                    SYSCTL_TYPE_STRING, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    kernel_domainname, sizeof(kernel_domainname),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.pid_max", "Maximum PID value",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &kernel_pid_max, sizeof(kernel_pid_max),
                    &(uint64_t){301}, &(uint64_t){4194304}, NULL);
    
    register_sysctl("kernel.threads_max", "Maximum threads",
                    SYSCTL_TYPE_ULONG, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &kernel_threads_max, sizeof(kernel_threads_max),
                    &(uint64_t){1}, &(uint64_t){4194304}, NULL);
    
    /* Security parameters */
    register_sysctl("kernel.randomize_va_space", "Address space randomization",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME | SYSCTL_FLAG_SECURE,
                    &kernel_randomize_va_space, sizeof(kernel_randomize_va_space),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.dmesg_restrict", "Restrict dmesg access",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME | SYSCTL_FLAG_SECURE,
                    &kernel_dmesg_restrict, sizeof(kernel_dmesg_restrict),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.kptr_restrict", "Restrict kernel pointer exposure",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME | SYSCTL_FLAG_SECURE,
                    &kernel_kptr_restrict, sizeof(kernel_kptr_restrict),
                    NULL, NULL, NULL);
    
    return 0;
}

/* Cleanup sysctl subsystem */
void sysctl_cleanup(void)
{
    pthread_rwlock_wrlock(&sysctl_lock);
    
    /* Free all entries recursively */
    /* TODO: Implement recursive free */
    
    sysctl_root = NULL;
    pthread_rwlock_unlock(&sysctl_lock);
}

/* Helper functions for command-line tool */
int sysctl_get_info(const char *path, sysctl_info_t *info)
{
    if (!path || !info) {
        return -EINVAL;
    }
    
    pthread_rwlock_rdlock(&sysctl_lock);
    
    sysctl_entry_t *entry = find_sysctl_entry(path);
    if (!entry) {
        pthread_rwlock_unlock(&sysctl_lock);
        return -ENOENT;
    }
    
    /* Fill info structure */
    strncpy(info->name, entry->name, sizeof(info->name) - 1);
    strncpy(info->description, entry->description, sizeof(info->description) - 1);
    info->type = entry->type;
    info->flags = entry->flags;
    
    /* Get current value as string */
    switch (entry->type) {
        case SYSCTL_TYPE_INT:
            snprintf(info->value, sizeof(info->value), "%d", *(int *)entry->data);
            break;
        case SYSCTL_TYPE_UINT:
            snprintf(info->value, sizeof(info->value), "%u", *(unsigned int *)entry->data);
            break;
        case SYSCTL_TYPE_LONG:
            snprintf(info->value, sizeof(info->value), "%ld", *(long *)entry->data);
            break;
        case SYSCTL_TYPE_ULONG:
            snprintf(info->value, sizeof(info->value), "%lu", *(unsigned long *)entry->data);
            break;
        case SYSCTL_TYPE_STRING:
            strncpy(info->value, (char *)entry->data, sizeof(info->value) - 1);
            break;
        case SYSCTL_TYPE_BOOL:
            snprintf(info->value, sizeof(info->value), "%s", 
                     *(bool *)entry->data ? "true" : "false");
            break;
        case SYSCTL_TYPE_PROC:
            strncpy(info->value, "<directory>", sizeof(info->value) - 1);
            break;
    }
    
    pthread_rwlock_unlock(&sysctl_lock);
    return 0;
}

int sysctl_set_string(const char *path, const char *value)
{
    if (!path || !value) {
        return -EINVAL;
    }
    
    /* Get entry info first */
    sysctl_info_t info;
    int ret = sysctl_get_info(path, &info);
    if (ret != 0) {
        return ret;
    }
    
    /* Parse and set based on type */
    switch (info.type) {
        case SYSCTL_TYPE_INT: {
            int val = atoi(value);
            return sysctl_write(path, &val, sizeof(val));
        }
        case SYSCTL_TYPE_UINT: {
            unsigned int val = strtoul(value, NULL, 10);
            return sysctl_write(path, &val, sizeof(val));
        }
        case SYSCTL_TYPE_LONG: {
            long val = strtol(value, NULL, 10);
            return sysctl_write(path, &val, sizeof(val));
        }
        case SYSCTL_TYPE_ULONG: {
            unsigned long val = strtoul(value, NULL, 10);
            return sysctl_write(path, &val, sizeof(val));
        }
        case SYSCTL_TYPE_STRING:
            return sysctl_write(path, value, strlen(value) + 1);
        case SYSCTL_TYPE_BOOL: {
            bool val = (strcmp(value, "true") == 0 || 
                        strcmp(value, "1") == 0 ||
                        strcmp(value, "yes") == 0);
            return sysctl_write(path, &val, sizeof(val));
        }
        default:
            return -EINVAL;
    }
}

int sysctl_get_string(const char *path, char *buffer, size_t size)
{
    if (!path || !buffer || size == 0) {
        return -EINVAL;
    }
    
    sysctl_info_t info;
    int ret = sysctl_get_info(path, &info);
    if (ret != 0) {
        return ret;
    }
    
    strncpy(buffer, info.value, size - 1);
    buffer[size - 1] = '\0';
    return 0;
}

/* Export configuration values for use by other kernel subsystems */
uint64_t sysctl_get_sched_latency(void) { return kernel_sched_latency_ns; }
uint64_t sysctl_get_sched_min_granularity(void) { return kernel_sched_min_granularity_ns; }
uint64_t sysctl_get_sched_wakeup_granularity(void) { return kernel_sched_wakeup_granularity_ns; }
uint64_t sysctl_get_vm_swappiness(void) { return vm_swappiness; }
bool sysctl_get_ipv4_forward(void) { return net_ipv4_ip_forward; }
bool sysctl_get_ipv6_forward(void) { return net_ipv6_conf_all_forwarding; }