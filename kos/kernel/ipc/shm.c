#include "ipc.h"
#include <sys/mman.h>

// Global shared memory registry
static kos_shm_t *shm_registry[KOS_MAX_SHM_SEGMENTS] = {0};
static pthread_mutex_t shm_registry_mutex = PTHREAD_MUTEX_INITIALIZER;
static int shm_count = 0;

// Create shared memory segment
int kos_shm_create(kos_shm_t *shm, const char *name, size_t size, int flags) {
    if (!shm || !name || size == 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Generate key from name
    key_t key = kos_ipc_generate_key(name, 1);
    if (key == -1) {
        return KOS_IPC_ERROR;
    }

    // Create System V shared memory segment
    shm->shm_id = shmget(key, size, IPC_CREAT | IPC_EXCL | 0666);
    if (shm->shm_id == -1) {
        if (errno == EEXIST) {
            // Segment already exists, try to attach
            shm->shm_id = shmget(key, 0, 0666);
            if (shm->shm_id == -1) {
                return KOS_IPC_ERROR;
            }
        } else {
            return KOS_IPC_ERROR;
        }
    }

    // Attach to shared memory
    shm->addr = shmat(shm->shm_id, NULL, 0);
    if (shm->addr == (void*)-1) {
        shmctl(shm->shm_id, IPC_RMID, NULL);
        return KOS_IPC_ERROR;
    }

    shm->key = key;
    shm->size = size;
    shm->flags = flags;
    strncpy(shm->name, name, sizeof(shm->name) - 1);
    shm->name[sizeof(shm->name) - 1] = '\0';

    // Create mutex in shared memory for synchronization
    shm->mutex = (pthread_mutex_t*)((char*)shm->addr + size - sizeof(pthread_mutex_t));
    
    // Initialize mutex attributes for process sharing
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    
    if (pthread_mutex_init(shm->mutex, &attr) != 0) {
        pthread_mutexattr_destroy(&attr);
        shmdt(shm->addr);
        shmctl(shm->shm_id, IPC_RMID, NULL);
        return KOS_IPC_ERROR;
    }
    
    pthread_mutexattr_destroy(&attr);

    // Register shared memory segment
    pthread_mutex_lock(&shm_registry_mutex);
    if (shm_count < KOS_MAX_SHM_SEGMENTS) {
        shm_registry[shm_count] = shm;
        shm_count++;
    }
    pthread_mutex_unlock(&shm_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Attach to existing shared memory segment
int kos_shm_attach(kos_shm_t *shm, const char *name) {
    if (!shm || !name) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Generate key from name
    key_t key = kos_ipc_generate_key(name, 1);
    if (key == -1) {
        return KOS_IPC_ERROR;
    }

    // Get existing shared memory segment
    shm->shm_id = shmget(key, 0, 0666);
    if (shm->shm_id == -1) {
        return KOS_IPC_ERROR;
    }

    // Get segment info
    struct shmid_ds shm_info;
    if (shmctl(shm->shm_id, IPC_STAT, &shm_info) == -1) {
        return KOS_IPC_ERROR;
    }

    // Attach to shared memory
    shm->addr = shmat(shm->shm_id, NULL, 0);
    if (shm->addr == (void*)-1) {
        return KOS_IPC_ERROR;
    }

    shm->key = key;
    shm->size = shm_info.shm_segsz;
    shm->flags = 0;
    strncpy(shm->name, name, sizeof(shm->name) - 1);
    shm->name[sizeof(shm->name) - 1] = '\0';

    // Set mutex pointer (assuming it's at the end of the segment)
    shm->mutex = (pthread_mutex_t*)((char*)shm->addr + shm->size - sizeof(pthread_mutex_t));

    // Register shared memory segment
    pthread_mutex_lock(&shm_registry_mutex);
    if (shm_count < KOS_MAX_SHM_SEGMENTS) {
        shm_registry[shm_count] = shm;
        shm_count++;
    }
    pthread_mutex_unlock(&shm_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Detach from shared memory segment
int kos_shm_detach(kos_shm_t *shm) {
    if (!shm || !shm->addr) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Detach from shared memory
    if (shmdt(shm->addr) == -1) {
        return KOS_IPC_ERROR;
    }

    // Remove from registry
    pthread_mutex_lock(&shm_registry_mutex);
    for (int i = 0; i < shm_count; i++) {
        if (shm_registry[i] == shm) {
            // Shift remaining segments
            for (int j = i; j < shm_count - 1; j++) {
                shm_registry[j] = shm_registry[j + 1];
            }
            shm_count--;
            break;
        }
    }
    pthread_mutex_unlock(&shm_registry_mutex);

    shm->addr = NULL;
    shm->mutex = NULL;

    return KOS_IPC_SUCCESS;
}

// Destroy shared memory segment
int kos_shm_destroy(kos_shm_t *shm) {
    if (!shm) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Detach first
    if (shm->addr) {
        kos_shm_detach(shm);
    }

    // Remove shared memory segment
    if (shm->shm_id != -1) {
        if (shmctl(shm->shm_id, IPC_RMID, NULL) == -1) {
            return KOS_IPC_ERROR;
        }
    }

    // Clear structure
    memset(shm, 0, sizeof(kos_shm_t));
    shm->shm_id = -1;

    return KOS_IPC_SUCCESS;
}

// Get shared memory address
void* kos_shm_get_addr(kos_shm_t *shm) {
    if (!shm) {
        return NULL;
    }
    return shm->addr;
}

// Lock shared memory mutex
int kos_shm_lock(kos_shm_t *shm) {
    if (!shm || !shm->mutex) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_mutex_lock(shm->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Unlock shared memory mutex
int kos_shm_unlock(kos_shm_t *shm) {
    if (!shm || !shm->mutex) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_mutex_unlock(shm->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// POSIX shared memory functions
int kos_shm_create_posix(kos_shm_t *shm, const char *name, size_t size, int flags) {
    if (!shm || !name || size == 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Create POSIX shared memory object
    int fd = shm_open(name, O_CREAT | O_RDWR | O_EXCL, 0666);
    if (fd == -1) {
        if (errno == EEXIST) {
            // Object already exists
            fd = shm_open(name, O_RDWR, 0666);
            if (fd == -1) {
                return KOS_IPC_ERROR;
            }
        } else {
            return KOS_IPC_ERROR;
        }
    }

    // Set size
    if (ftruncate(fd, size) == -1) {
        close(fd);
        shm_unlink(name);
        return KOS_IPC_ERROR;
    }

    // Map shared memory
    shm->addr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (shm->addr == MAP_FAILED) {
        close(fd);
        shm_unlink(name);
        return KOS_IPC_ERROR;
    }

    close(fd); // Can close fd after mmap

    shm->shm_id = -1; // Not used for POSIX
    shm->size = size;
    shm->flags = flags;
    strncpy(shm->name, name, sizeof(shm->name) - 1);
    shm->name[sizeof(shm->name) - 1] = '\0';

    // Create mutex in shared memory
    shm->mutex = (pthread_mutex_t*)((char*)shm->addr + size - sizeof(pthread_mutex_t));
    
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
    
    if (pthread_mutex_init(shm->mutex, &attr) != 0) {
        pthread_mutexattr_destroy(&attr);
        munmap(shm->addr, size);
        shm_unlink(name);
        return KOS_IPC_ERROR;
    }
    
    pthread_mutexattr_destroy(&attr);

    return KOS_IPC_SUCCESS;
}

// Utility function to get shared memory statistics
int kos_shm_get_stats(int *active_segments, size_t *total_size) {
    pthread_mutex_lock(&shm_registry_mutex);
    
    if (active_segments) {
        *active_segments = shm_count;
    }
    
    if (total_size) {
        *total_size = 0;
        for (int i = 0; i < shm_count; i++) {
            if (shm_registry[i]) {
                *total_size += shm_registry[i]->size;
            }
        }
    }
    
    pthread_mutex_unlock(&shm_registry_mutex);
    
    return KOS_IPC_SUCCESS;
}