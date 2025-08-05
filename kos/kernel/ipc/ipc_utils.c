#include "ipc.h"
#include <sys/stat.h>

// Global IPC statistics
static struct {
    int initialized;
    int active_pipes;
    int active_shm_segments;
    int active_queues;
    int active_semaphores;
    pthread_mutex_t stats_mutex;
} ipc_stats = {0, 0, 0, 0, 0, PTHREAD_MUTEX_INITIALIZER};

// Forward declarations for functions implemented in signal.c
extern int kos_signal_install_defaults(void);
extern int kos_signal_cleanup(void);

// Initialize IPC system
int kos_ipc_init(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    if (ipc_stats.initialized) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_SUCCESS;
    }
    
    // Initialize signal handling
    if (kos_signal_install_defaults() != KOS_IPC_SUCCESS) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_ERROR;
    }
    
    ipc_stats.initialized = 1;
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Cleanup IPC system
int kos_ipc_cleanup(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    if (!ipc_stats.initialized) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_SUCCESS;
    }
    
    // Cleanup signal handling
    kos_signal_cleanup();
    
    ipc_stats.initialized = 0;
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Get IPC statistics
int kos_ipc_get_stats(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    printf("KOS IPC Statistics:\n");
    printf("  Initialized: %s\n", ipc_stats.initialized ? "Yes" : "No");
    printf("  Active Pipes: %d\n", ipc_stats.active_pipes);
    printf("  Active Shared Memory Segments: %d\n", ipc_stats.active_shm_segments);
    printf("  Active Message Queues: %d\n", ipc_stats.active_queues);
    printf("  Active Semaphores: %d\n", ipc_stats.active_semaphores);
    
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Generate IPC key from pathname and project ID
key_t kos_ipc_generate_key(const char *pathname, int proj_id) {
    if (!pathname) {
        return -1;
    }
    
    // Use ftok to generate System V IPC key
    key_t key = ftok(pathname, proj_id);
    if (key == -1) {
        // If ftok fails, create a simple hash-based key
        key = 0;
        const char *p = pathname;
        while (*p) {
            key = key * 31 + *p;
            p++;
        }
        key = key * 31 + proj_id;
        
        // Ensure positive key
        if (key < 0) {
            key = -key;
        }
    }
    
    return key;
}

// Check permissions for IPC operations
int kos_ipc_permissions_check(int operation, pid_t pid, uid_t uid, gid_t gid) {
    // Basic permission checking
    // In a real implementation, this would check against system policies
    
    // For now, allow all operations for the same user
    if (getuid() == uid) {
        return KOS_IPC_SUCCESS;
    }
    
    // Root can do anything
    if (getuid() == 0) {
        return KOS_IPC_SUCCESS;
    }
    
    // Check group permissions
    if (getgid() == gid) {
        return KOS_IPC_SUCCESS;
    }
    
    return KOS_IPC_ERROR;
}