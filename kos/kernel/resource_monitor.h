/*
 * KOS Kernel Resource Monitor
 * Provides system resource information from within the KOS kernel
 */

#ifndef KOS_RESOURCE_MONITOR_H
#define KOS_RESOURCE_MONITOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* CPU Information */
typedef struct kos_cpu_info {
    uint32_t cpu_count;          /* Number of CPUs */
    uint32_t cpu_count_logical;  /* Logical CPU count */
    float cpu_percent;           /* Overall CPU usage percentage */
    float* per_cpu_percent;      /* Per-CPU usage (array) */
    uint64_t frequency_current;  /* Current frequency in Hz */
    uint64_t frequency_max;      /* Max frequency in Hz */
    uint64_t frequency_min;      /* Min frequency in Hz */
} kos_cpu_info_t;

/* Memory Information */
typedef struct kos_mem_info {
    uint64_t total;              /* Total memory in bytes */
    uint64_t available;          /* Available memory in bytes */
    uint64_t used;               /* Used memory in bytes */
    uint64_t free;               /* Free memory in bytes */
    uint64_t buffers;            /* Buffer memory in bytes */
    uint64_t cached;             /* Cached memory in bytes */
    float percent;               /* Memory usage percentage */
} kos_mem_info_t;

/* Swap Information */
typedef struct kos_swap_info {
    uint64_t total;              /* Total swap in bytes */
    uint64_t used;               /* Used swap in bytes */
    uint64_t free;               /* Free swap in bytes */
    float percent;               /* Swap usage percentage */
} kos_swap_info_t;

/* Disk Information */
typedef struct kos_disk_info {
    char device[256];            /* Device name */
    char mountpoint[256];        /* Mount point */
    char fstype[64];             /* Filesystem type */
    uint64_t total;              /* Total space in bytes */
    uint64_t used;               /* Used space in bytes */
    uint64_t free;               /* Free space in bytes */
    float percent;               /* Usage percentage */
} kos_disk_info_t;

/* Network Information */
typedef struct kos_net_info {
    char interface[64];          /* Interface name */
    uint64_t bytes_sent;         /* Total bytes sent */
    uint64_t bytes_recv;         /* Total bytes received */
    uint64_t packets_sent;       /* Total packets sent */
    uint64_t packets_recv;       /* Total packets received */
    uint64_t errors_in;          /* Input errors */
    uint64_t errors_out;         /* Output errors */
    uint64_t drop_in;            /* Dropped incoming packets */
    uint64_t drop_out;           /* Dropped outgoing packets */
} kos_net_info_t;

/* Process Information */
typedef struct kos_process_info {
    uint32_t pid;                /* Process ID */
    uint32_t ppid;               /* Parent process ID */
    char name[256];              /* Process name */
    char state;                  /* Process state (R/S/D/Z/T) */
    float cpu_percent;           /* CPU usage percentage */
    uint64_t memory_rss;         /* Resident set size */
    uint64_t memory_vms;         /* Virtual memory size */
    uint64_t num_threads;        /* Number of threads */
    uint64_t create_time;        /* Creation time (unix timestamp) */
} kos_process_info_t;

/* System Information */
typedef struct kos_system_info {
    uint64_t boot_time;          /* Boot time (unix timestamp) */
    uint32_t process_count;      /* Total process count */
    uint32_t thread_count;       /* Total thread count */
    float load_avg_1;            /* 1 minute load average */
    float load_avg_5;            /* 5 minute load average */
    float load_avg_15;           /* 15 minute load average */
} kos_system_info_t;

/* Initialize resource monitor */
int kos_resource_monitor_init(void);

/* Cleanup resource monitor */
void kos_resource_monitor_cleanup(void);

/* CPU functions */
int kos_get_cpu_info(kos_cpu_info_t* info);
int kos_get_cpu_times(uint64_t* user, uint64_t* system, uint64_t* idle, uint64_t* iowait);
void kos_free_cpu_info(kos_cpu_info_t* info);

/* Memory functions */
int kos_get_memory_info(kos_mem_info_t* info);
int kos_get_swap_info(kos_swap_info_t* info);

/* Disk functions */
int kos_get_disk_info(const char* path, kos_disk_info_t* info);
int kos_get_all_disk_info(kos_disk_info_t** info_array, uint32_t* count);
void kos_free_disk_info_array(kos_disk_info_t* info_array);

/* Network functions */
int kos_get_network_info(const char* interface, kos_net_info_t* info);
int kos_get_all_network_info(kos_net_info_t** info_array, uint32_t* count);
void kos_free_network_info_array(kos_net_info_t* info_array);

/* Process functions */
int kos_get_process_info(uint32_t pid, kos_process_info_t* info);
int kos_get_all_process_info(kos_process_info_t** info_array, uint32_t* count);
void kos_free_process_info_array(kos_process_info_t* info_array);

/* System functions */
int kos_get_system_info(kos_system_info_t* info);

/* Utility functions */
const char* kos_resource_error_string(int error_code);

#ifdef __cplusplus
}
#endif

#endif /* KOS_RESOURCE_MONITOR_H */