/*
 * KOS Kernel Configuration Management (sysctl) Header
 */

#ifndef _KOS_SYSCTL_H
#define _KOS_SYSCTL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

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

/* Core sysctl functions */
int sysctl_init(void);
void sysctl_cleanup(void);

int register_sysctl(const char *path, const char *desc,
                    sysctl_type_t type, uint32_t flags,
                    void *data, size_t size,
                    void *min, void *max,
                    sysctl_handler_t handler);

int sysctl_read(const char *path, void *buffer, size_t *size);
int sysctl_write(const char *path, const void *buffer, size_t size);
int sysctl_list(const char *path, void (*callback)(const char *, const char *));

/* Convenience macros for registering sysctls */
#define SYSCTL_INT(path, desc, var, min, max, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_INT, flags, \
                    &(var), sizeof(var), &(min), &(max), NULL)

#define SYSCTL_UINT(path, desc, var, min, max, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_UINT, flags, \
                    &(var), sizeof(var), &(min), &(max), NULL)

#define SYSCTL_LONG(path, desc, var, min, max, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_LONG, flags, \
                    &(var), sizeof(var), &(min), &(max), NULL)

#define SYSCTL_ULONG(path, desc, var, min, max, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_ULONG, flags, \
                    &(var), sizeof(var), &(min), &(max), NULL)

#define SYSCTL_STRING(path, desc, var, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_STRING, flags, \
                    (var), sizeof(var), NULL, NULL, NULL)

#define SYSCTL_BOOL(path, desc, var, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_BOOL, flags, \
                    &(var), sizeof(var), NULL, NULL, NULL)

#define SYSCTL_PROC(path, desc, handler, flags) \
    register_sysctl(path, desc, SYSCTL_TYPE_PROC, flags, \
                    NULL, 0, NULL, NULL, handler)

/* Getter functions for commonly used parameters */
uint64_t sysctl_get_sched_latency(void);
uint64_t sysctl_get_sched_min_granularity(void);
uint64_t sysctl_get_sched_wakeup_granularity(void);
uint64_t sysctl_get_vm_swappiness(void);
bool sysctl_get_ipv4_forward(void);
bool sysctl_get_ipv6_forward(void);

/* Helper functions for sysctl command-line tool */
typedef struct {
    char name[256];
    char value[1024];
    char description[512];
    sysctl_type_t type;
    uint32_t flags;
} sysctl_info_t;

int sysctl_get_info(const char *path, sysctl_info_t *info);
int sysctl_set_string(const char *path, const char *value);
int sysctl_get_string(const char *path, char *buffer, size_t size);

#endif /* _KOS_SYSCTL_H */