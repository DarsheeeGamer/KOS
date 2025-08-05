/*
 * KOS Kernel Resource Monitor Implementation
 * 
 * This implementation reads from /proc and /sys filesystems
 * which are available inside containers
 */

#include "resource_monitor.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <errno.h>

/* Error codes */
#define KOS_RESOURCE_SUCCESS    0
#define KOS_RESOURCE_ERROR     -1
#define KOS_RESOURCE_ENOMEM    -2
#define KOS_RESOURCE_ENOENT    -3
#define KOS_RESOURCE_EACCES    -4

/* Helper function to read entire file */
static char* read_file(const char* path, size_t* size) {
    FILE* fp = fopen(path, "r");
    if (!fp) return NULL;
    
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    char* buffer = malloc(file_size + 1);
    if (!buffer) {
        fclose(fp);
        return NULL;
    }
    
    size_t read_size = fread(buffer, 1, file_size, fp);
    buffer[read_size] = '\0';
    
    if (size) *size = read_size;
    
    fclose(fp);
    return buffer;
}

/* Initialize resource monitor */
int kos_resource_monitor_init(void) {
    /* Check if we have access to /proc */
    struct stat st;
    if (stat("/proc", &st) != 0 || !S_ISDIR(st.st_mode)) {
        return KOS_RESOURCE_EACCES;
    }
    return KOS_RESOURCE_SUCCESS;
}

/* Cleanup resource monitor */
void kos_resource_monitor_cleanup(void) {
    /* Nothing to cleanup in this implementation */
}

/* Get CPU information */
int kos_get_cpu_info(kos_cpu_info_t* info) {
    if (!info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_cpu_info_t));
    
    /* Count CPUs from /proc/cpuinfo */
    FILE* fp = fopen("/proc/cpuinfo", "r");
    if (!fp) return KOS_RESOURCE_ENOENT;
    
    char line[256];
    uint32_t cpu_count = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "processor", 9) == 0) {
            cpu_count++;
        }
    }
    
    info->cpu_count = cpu_count;
    info->cpu_count_logical = cpu_count;
    
    fclose(fp);
    
    /* Get CPU usage from /proc/stat */
    char* stat_content = read_file("/proc/stat", NULL);
    if (stat_content) {
        uint64_t user, nice, system, idle, iowait, irq, softirq, steal;
        if (sscanf(stat_content, "cpu %lu %lu %lu %lu %lu %lu %lu %lu",
                   &user, &nice, &system, &idle, &iowait, &irq, &softirq, &steal) == 8) {
            uint64_t total = user + nice + system + idle + iowait + irq + softirq + steal;
            uint64_t active = total - idle - iowait;
            info->cpu_percent = (float)active / total * 100.0f;
        }
        free(stat_content);
    }
    
    /* Get CPU frequency from /sys/devices/system/cpu/cpu0/cpufreq */
    char* freq_content = read_file("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq", NULL);
    if (freq_content) {
        info->frequency_current = strtoull(freq_content, NULL, 10) * 1000; /* Convert kHz to Hz */
        free(freq_content);
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get memory information */
int kos_get_memory_info(kos_mem_info_t* info) {
    if (!info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_mem_info_t));
    
    /* Parse /proc/meminfo */
    FILE* fp = fopen("/proc/meminfo", "r");
    if (!fp) return KOS_RESOURCE_ENOENT;
    
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        char name[64];
        uint64_t value;
        
        if (sscanf(line, "%63s %lu kB", name, &value) == 2) {
            value *= 1024; /* Convert to bytes */
            
            if (strcmp(name, "MemTotal:") == 0) {
                info->total = value;
            } else if (strcmp(name, "MemFree:") == 0) {
                info->free = value;
            } else if (strcmp(name, "MemAvailable:") == 0) {
                info->available = value;
            } else if (strcmp(name, "Buffers:") == 0) {
                info->buffers = value;
            } else if (strcmp(name, "Cached:") == 0) {
                info->cached = value;
            }
        }
    }
    
    fclose(fp);
    
    info->used = info->total - info->available;
    info->percent = (float)info->used / info->total * 100.0f;
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get swap information */
int kos_get_swap_info(kos_swap_info_t* info) {
    if (!info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_swap_info_t));
    
    /* Parse /proc/meminfo for swap info */
    FILE* fp = fopen("/proc/meminfo", "r");
    if (!fp) return KOS_RESOURCE_ENOENT;
    
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        char name[64];
        uint64_t value;
        
        if (sscanf(line, "%63s %lu kB", name, &value) == 2) {
            value *= 1024; /* Convert to bytes */
            
            if (strcmp(name, "SwapTotal:") == 0) {
                info->total = value;
            } else if (strcmp(name, "SwapFree:") == 0) {
                info->free = value;
            }
        }
    }
    
    fclose(fp);
    
    info->used = info->total - info->free;
    if (info->total > 0) {
        info->percent = (float)info->used / info->total * 100.0f;
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get disk information */
int kos_get_disk_info(const char* path, kos_disk_info_t* info) {
    if (!path || !info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_disk_info_t));
    
    struct statvfs vfs;
    if (statvfs(path, &vfs) != 0) {
        return KOS_RESOURCE_ERROR;
    }
    
    strncpy(info->mountpoint, path, sizeof(info->mountpoint) - 1);
    
    info->total = vfs.f_blocks * vfs.f_frsize;
    info->free = vfs.f_bavail * vfs.f_frsize;
    info->used = info->total - info->free;
    
    if (info->total > 0) {
        info->percent = (float)info->used / info->total * 100.0f;
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get network information */
int kos_get_network_info(const char* interface, kos_net_info_t* info) {
    if (!interface || !info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_net_info_t));
    strncpy(info->interface, interface, sizeof(info->interface) - 1);
    
    /* Read from /sys/class/net/<interface>/statistics/ */
    char path[512];
    char* content;
    
    /* Bytes received */
    snprintf(path, sizeof(path), "/sys/class/net/%s/statistics/rx_bytes", interface);
    content = read_file(path, NULL);
    if (content) {
        info->bytes_recv = strtoull(content, NULL, 10);
        free(content);
    }
    
    /* Bytes sent */
    snprintf(path, sizeof(path), "/sys/class/net/%s/statistics/tx_bytes", interface);
    content = read_file(path, NULL);
    if (content) {
        info->bytes_sent = strtoull(content, NULL, 10);
        free(content);
    }
    
    /* Packets received */
    snprintf(path, sizeof(path), "/sys/class/net/%s/statistics/rx_packets", interface);
    content = read_file(path, NULL);
    if (content) {
        info->packets_recv = strtoull(content, NULL, 10);
        free(content);
    }
    
    /* Packets sent */
    snprintf(path, sizeof(path), "/sys/class/net/%s/statistics/tx_packets", interface);
    content = read_file(path, NULL);
    if (content) {
        info->packets_sent = strtoull(content, NULL, 10);
        free(content);
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get all network interfaces */
int kos_get_all_network_info(kos_net_info_t** info_array, uint32_t* count) {
    if (!info_array || !count) return KOS_RESOURCE_ERROR;
    
    DIR* dir = opendir("/sys/class/net");
    if (!dir) return KOS_RESOURCE_ENOENT;
    
    /* Count interfaces */
    uint32_t iface_count = 0;
    struct dirent* entry;
    
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] != '.') {
            iface_count++;
        }
    }
    
    /* Allocate array */
    kos_net_info_t* array = calloc(iface_count, sizeof(kos_net_info_t));
    if (!array) {
        closedir(dir);
        return KOS_RESOURCE_ENOMEM;
    }
    
    /* Fill array */
    rewinddir(dir);
    uint32_t idx = 0;
    
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] != '.') {
            kos_get_network_info(entry->d_name, &array[idx]);
            idx++;
        }
    }
    
    closedir(dir);
    
    *info_array = array;
    *count = iface_count;
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get process information */
int kos_get_process_info(uint32_t pid, kos_process_info_t* info) {
    if (!info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_process_info_t));
    info->pid = pid;
    
    char path[256];
    
    /* Read /proc/<pid>/stat */
    snprintf(path, sizeof(path), "/proc/%u/stat", pid);
    char* stat_content = read_file(path, NULL);
    if (!stat_content) return KOS_RESOURCE_ENOENT;
    
    /* Parse stat file - format: pid (comm) state ppid ... */
    char comm[256];
    char state;
    int ppid;
    
    /* Find the last ')' to handle process names with ')' in them */
    char* close_paren = strrchr(stat_content, ')');
    if (close_paren) {
        *close_paren = '\0';
        char* open_paren = strchr(stat_content, '(');
        if (open_paren) {
            strncpy(comm, open_paren + 1, sizeof(comm) - 1);
            strncpy(info->name, comm, sizeof(info->name) - 1);
        }
        
        /* Parse remaining fields after ')' */
        sscanf(close_paren + 2, "%c %d", &state, &ppid);
        info->state = state;
        info->ppid = ppid;
    }
    
    free(stat_content);
    
    /* Read memory info from /proc/<pid>/status */
    snprintf(path, sizeof(path), "/proc/%u/status", pid);
    FILE* fp = fopen(path, "r");
    if (fp) {
        char line[256];
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "VmRSS:", 6) == 0) {
                sscanf(line, "VmRSS: %lu kB", &info->memory_rss);
                info->memory_rss *= 1024; /* Convert to bytes */
            } else if (strncmp(line, "VmSize:", 7) == 0) {
                sscanf(line, "VmSize: %lu kB", &info->memory_vms);
                info->memory_vms *= 1024; /* Convert to bytes */
            } else if (strncmp(line, "Threads:", 8) == 0) {
                sscanf(line, "Threads: %lu", &info->num_threads);
            }
        }
        fclose(fp);
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Get system information */
int kos_get_system_info(kos_system_info_t* info) {
    if (!info) return KOS_RESOURCE_ERROR;
    
    memset(info, 0, sizeof(kos_system_info_t));
    
    /* Get boot time from /proc/stat */
    FILE* fp = fopen("/proc/stat", "r");
    if (fp) {
        char line[256];
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "btime", 5) == 0) {
                sscanf(line, "btime %lu", &info->boot_time);
                break;
            }
        }
        fclose(fp);
    }
    
    /* Get load average from /proc/loadavg */
    fp = fopen("/proc/loadavg", "r");
    if (fp) {
        fscanf(fp, "%f %f %f", &info->load_avg_1, &info->load_avg_5, &info->load_avg_15);
        fclose(fp);
    }
    
    /* Count processes */
    DIR* dir = opendir("/proc");
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != NULL) {
            if (entry->d_name[0] >= '0' && entry->d_name[0] <= '9') {
                info->process_count++;
            }
        }
        closedir(dir);
    }
    
    return KOS_RESOURCE_SUCCESS;
}

/* Free allocated arrays */
void kos_free_cpu_info(kos_cpu_info_t* info) {
    if (info && info->per_cpu_percent) {
        free(info->per_cpu_percent);
        info->per_cpu_percent = NULL;
    }
}

void kos_free_disk_info_array(kos_disk_info_t* info_array) {
    if (info_array) free(info_array);
}

void kos_free_network_info_array(kos_net_info_t* info_array) {
    if (info_array) free(info_array);
}

void kos_free_process_info_array(kos_process_info_t* info_array) {
    if (info_array) free(info_array);
}

/* Error string */
const char* kos_resource_error_string(int error_code) {
    switch (error_code) {
        case KOS_RESOURCE_SUCCESS: return "Success";
        case KOS_RESOURCE_ERROR: return "General error";
        case KOS_RESOURCE_ENOMEM: return "Out of memory";
        case KOS_RESOURCE_ENOENT: return "Resource not found";
        case KOS_RESOURCE_EACCES: return "Access denied";
        default: return "Unknown error";
    }
}