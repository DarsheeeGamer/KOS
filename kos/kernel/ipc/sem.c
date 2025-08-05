#include "ipc.h"
#include <sys/sem.h>
#include <time.h>

// Union for semctl operations (required on some systems)
union semun {
    int val;
    struct semid_ds *buf;
    unsigned short *array;
    struct seminfo *__buf;
};

// Global semaphore registry
static kos_semaphore_t *sem_registry[KOS_MAX_SEMAPHORES] = {0};
static pthread_mutex_t sem_registry_mutex = PTHREAD_MUTEX_INITIALIZER;
static int sem_count = 0;

// Create semaphore
int kos_semaphore_create(kos_semaphore_t *sem, const char *name, int value, int is_posix) {
    if (!sem || !name || value < 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    sem->is_posix = is_posix;
    sem->value = value;
    sem->max_value = value;
    strncpy(sem->name, name, sizeof(sem->name) - 1);
    sem->name[sizeof(sem->name) - 1] = '\0';

    if (is_posix) {
        // POSIX named semaphore
        sem->posix_sem = sem_open(name, O_CREAT | O_EXCL, 0666, value);
        if (sem->posix_sem == SEM_FAILED) {
            if (errno == EEXIST) {
                // Semaphore already exists
                sem->posix_sem = sem_open(name, 0);
                if (sem->posix_sem == SEM_FAILED) {
                    return KOS_IPC_ERROR;
                }
            } else {
                return KOS_IPC_ERROR;
            }
        }
    } else {
        // System V semaphore
        sem->key = kos_ipc_generate_key(name, 3);
        if (sem->key == -1) {
            return KOS_IPC_ERROR;
        }

        sem->semid = semget(sem->key, 1, IPC_CREAT | IPC_EXCL | 0666);
        if (sem->semid == -1) {
            if (errno == EEXIST) {
                // Semaphore already exists
                sem->semid = semget(sem->key, 1, 0666);
                if (sem->semid == -1) {
                    return KOS_IPC_ERROR;
                }
            } else {
                return KOS_IPC_ERROR;
            }
        } else {
            // Initialize semaphore value
            union semun arg;
            arg.val = value;
            if (semctl(sem->semid, 0, SETVAL, arg) == -1) {
                semctl(sem->semid, 0, IPC_RMID);
                return KOS_IPC_ERROR;
            }
        }
    }

    // Register semaphore
    pthread_mutex_lock(&sem_registry_mutex);
    if (sem_count < KOS_MAX_SEMAPHORES) {
        sem_registry[sem_count] = sem;
        sem_count++;
    }
    pthread_mutex_unlock(&sem_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Wait on semaphore (P operation)
int kos_semaphore_wait(kos_semaphore_t *sem, int timeout_ms) {
    if (!sem) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (sem->is_posix) {
        // POSIX semaphore
        if (timeout_ms < 0) {
            // Blocking wait
            if (sem_wait(sem->posix_sem) == -1) {
                return KOS_IPC_ERROR;
            }
        } else if (timeout_ms == 0) {
            // Non-blocking wait
            if (sem_trywait(sem->posix_sem) == -1) {
                if (errno == EAGAIN) {
                    return KOS_IPC_RESOURCE_BUSY;
                }
                return KOS_IPC_ERROR;
            }
        } else {
            // Timed wait
            struct timespec abs_timeout;
            clock_gettime(CLOCK_REALTIME, &abs_timeout);
            abs_timeout.tv_sec += timeout_ms / 1000;
            abs_timeout.tv_nsec += (timeout_ms % 1000) * 1000000;
            
            if (abs_timeout.tv_nsec >= 1000000000) {
                abs_timeout.tv_sec++;
                abs_timeout.tv_nsec -= 1000000000;
            }

            if (sem_timedwait(sem->posix_sem, &abs_timeout) == -1) {
                if (errno == ETIMEDOUT) {
                    return KOS_IPC_TIMEOUT;
                }
                return KOS_IPC_ERROR;
            }
        }
    } else {
        // System V semaphore
        struct sembuf op;
        op.sem_num = 0;
        op.sem_op = -1; // P operation (decrement)
        op.sem_flg = (timeout_ms == 0) ? IPC_NOWAIT : 0;

        if (timeout_ms > 0) {
            // Timed wait using alarm (not perfect but functional)
            struct timespec timeout;
            timeout.tv_sec = timeout_ms / 1000;
            timeout.tv_nsec = (timeout_ms % 1000) * 1000000;
            
            if (semtimedop(sem->semid, &op, 1, &timeout) == -1) {
                if (errno == EAGAIN) {
                    return timeout_ms == 0 ? KOS_IPC_RESOURCE_BUSY : KOS_IPC_TIMEOUT;
                }
                return KOS_IPC_ERROR;
            }
        } else {
            if (semop(sem->semid, &op, 1) == -1) {
                if (errno == EAGAIN) {
                    return KOS_IPC_RESOURCE_BUSY;
                }
                return KOS_IPC_ERROR;
            }
        }
    }

    return KOS_IPC_SUCCESS;
}

// Post to semaphore (V operation)
int kos_semaphore_post(kos_semaphore_t *sem) {
    if (!sem) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (sem->is_posix) {
        // POSIX semaphore
        if (sem_post(sem->posix_sem) == -1) {
            return KOS_IPC_ERROR;
        }
    } else {
        // System V semaphore
        struct sembuf op;
        op.sem_num = 0;
        op.sem_op = 1; // V operation (increment)
        op.sem_flg = 0;

        if (semop(sem->semid, &op, 1) == -1) {
            return KOS_IPC_ERROR;
        }
    }

    return KOS_IPC_SUCCESS;
}

// Try wait on semaphore (non-blocking)
int kos_semaphore_try_wait(kos_semaphore_t *sem) {
    return kos_semaphore_wait(sem, 0);
}

// Get semaphore value
int kos_semaphore_get_value(kos_semaphore_t *sem) {
    if (!sem) {
        return KOS_IPC_INVALID_PARAM;
    }

    int value;

    if (sem->is_posix) {
        // POSIX semaphore
        if (sem_getvalue(sem->posix_sem, &value) == -1) {
            return KOS_IPC_ERROR;
        }
    } else {
        // System V semaphore
        value = semctl(sem->semid, 0, GETVAL);
        if (value == -1) {
            return KOS_IPC_ERROR;
        }
    }

    return value;
}

// Destroy semaphore
int kos_semaphore_destroy(kos_semaphore_t *sem) {
    if (!sem) {
        return KOS_IPC_INVALID_PARAM;
    }

    int result = KOS_IPC_SUCCESS;

    if (sem->is_posix) {
        // POSIX semaphore
        if (sem->posix_sem != SEM_FAILED) {
            if (sem_close(sem->posix_sem) == -1) {
                result = KOS_IPC_ERROR;
            }
            if (sem_unlink(sem->name) == -1) {
                result = KOS_IPC_ERROR;
            }
        }
    } else {
        // System V semaphore
        if (sem->semid != -1) {
            if (semctl(sem->semid, 0, IPC_RMID) == -1) {
                result = KOS_IPC_ERROR;
            }
        }
    }

    // Remove from registry
    pthread_mutex_lock(&sem_registry_mutex);
    for (int i = 0; i < sem_count; i++) {
        if (sem_registry[i] == sem) {
            // Shift remaining semaphores
            for (int j = i; j < sem_count - 1; j++) {
                sem_registry[j] = sem_registry[j + 1];
            }
            sem_count--;
            break;
        }
    }
    pthread_mutex_unlock(&sem_registry_mutex);

    // Clear structure
    memset(sem, 0, sizeof(kos_semaphore_t));
    sem->semid = -1;
    sem->posix_sem = SEM_FAILED;

    return result;
}

// Initialize mutex
int kos_mutex_init(kos_mutex_t *mutex, int shared) {
    if (!mutex) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Initialize mutex attributes
    if (pthread_mutexattr_init(&mutex->attr) != 0) {
        return KOS_IPC_ERROR;
    }

    // Set process sharing if requested
    if (shared) {
        if (pthread_mutexattr_setpshared(&mutex->attr, PTHREAD_PROCESS_SHARED) != 0) {
            pthread_mutexattr_destroy(&mutex->attr);
            return KOS_IPC_ERROR;
        }
    }

    // Set mutex type to recursive for better compatibility
    if (pthread_mutexattr_settype(&mutex->attr, PTHREAD_MUTEX_RECURSIVE) != 0) {
        pthread_mutexattr_destroy(&mutex->attr);
        return KOS_IPC_ERROR;
    }

    // Initialize mutex
    if (pthread_mutex_init(&mutex->mutex, &mutex->attr) != 0) {
        pthread_mutexattr_destroy(&mutex->attr);
        return KOS_IPC_ERROR;
    }

    mutex->initialized = 1;
    mutex->owner = 0;

    return KOS_IPC_SUCCESS;
}

// Lock mutex
int kos_mutex_lock(kos_mutex_t *mutex) {
    if (!mutex || !mutex->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_mutex_lock(&mutex->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    mutex->owner = getpid();
    return KOS_IPC_SUCCESS;
}

// Try lock mutex
int kos_mutex_try_lock(kos_mutex_t *mutex) {
    if (!mutex || !mutex->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    int result = pthread_mutex_trylock(&mutex->mutex);
    if (result == 0) {
        mutex->owner = getpid();
        return KOS_IPC_SUCCESS;
    } else if (result == EBUSY) {
        return KOS_IPC_RESOURCE_BUSY;
    } else {
        return KOS_IPC_ERROR;
    }
}

// Unlock mutex
int kos_mutex_unlock(kos_mutex_t *mutex) {
    if (!mutex || !mutex->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_mutex_unlock(&mutex->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    mutex->owner = 0;
    return KOS_IPC_SUCCESS;
}

// Destroy mutex
int kos_mutex_destroy(kos_mutex_t *mutex) {
    if (!mutex || !mutex->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_mutex_destroy(&mutex->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    if (pthread_mutexattr_destroy(&mutex->attr) != 0) {
        return KOS_IPC_ERROR;
    }

    mutex->initialized = 0;
    mutex->owner = 0;

    return KOS_IPC_SUCCESS;
}

// Initialize condition variable
int kos_condvar_init(kos_condvar_t *condvar, int shared) {
    if (!condvar) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Initialize condition variable attributes
    if (pthread_condattr_init(&condvar->attr) != 0) {
        return KOS_IPC_ERROR;
    }

    // Set process sharing if requested
    if (shared) {
        if (pthread_condattr_setpshared(&condvar->attr, PTHREAD_PROCESS_SHARED) != 0) {
            pthread_condattr_destroy(&condvar->attr);
            return KOS_IPC_ERROR;
        }
    }

    // Initialize condition variable
    if (pthread_cond_init(&condvar->cond, &condvar->attr) != 0) {
        pthread_condattr_destroy(&condvar->attr);
        return KOS_IPC_ERROR;
    }

    condvar->initialized = 1;

    return KOS_IPC_SUCCESS;
}

// Wait on condition variable
int kos_condvar_wait(kos_condvar_t *condvar, kos_mutex_t *mutex) {
    if (!condvar || !condvar->initialized || !mutex || !mutex->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_cond_wait(&condvar->cond, &mutex->mutex) != 0) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Timed wait on condition variable
int kos_condvar_timed_wait(kos_condvar_t *condvar, kos_mutex_t *mutex, int timeout_ms) {
    if (!condvar || !condvar->initialized || !mutex || !mutex->initialized || timeout_ms < 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    struct timespec abs_timeout;
    clock_gettime(CLOCK_REALTIME, &abs_timeout);
    abs_timeout.tv_sec += timeout_ms / 1000;
    abs_timeout.tv_nsec += (timeout_ms % 1000) * 1000000;
    
    if (abs_timeout.tv_nsec >= 1000000000) {
        abs_timeout.tv_sec++;
        abs_timeout.tv_nsec -= 1000000000;
    }

    int result = pthread_cond_timedwait(&condvar->cond, &mutex->mutex, &abs_timeout);
    
    if (result == 0) {
        return KOS_IPC_SUCCESS;
    } else if (result == ETIMEDOUT) {
        return KOS_IPC_TIMEOUT;
    } else {
        return KOS_IPC_ERROR;
    }
}

// Signal condition variable
int kos_condvar_signal(kos_condvar_t *condvar) {
    if (!condvar || !condvar->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_cond_signal(&condvar->cond) != 0) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Broadcast condition variable
int kos_condvar_broadcast(kos_condvar_t *condvar) {
    if (!condvar || !condvar->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_cond_broadcast(&condvar->cond) != 0) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Destroy condition variable
int kos_condvar_destroy(kos_condvar_t *condvar) {
    if (!condvar || !condvar->initialized) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (pthread_cond_destroy(&condvar->cond) != 0) {
        return KOS_IPC_ERROR;
    }

    if (pthread_condattr_destroy(&condvar->attr) != 0) {
        return KOS_IPC_ERROR;
    }

    condvar->initialized = 0;

    return KOS_IPC_SUCCESS;
}

// Get semaphore statistics
int kos_semaphore_get_stats(int *active_semaphores, int *total_value) {
    pthread_mutex_lock(&sem_registry_mutex);
    
    if (active_semaphores) {
        *active_semaphores = sem_count;
    }
    
    if (total_value) {
        *total_value = 0;
        for (int i = 0; i < sem_count; i++) {
            if (sem_registry[i]) {
                int value = kos_semaphore_get_value(sem_registry[i]);
                if (value >= 0) {
                    *total_value += value;
                }
            }
        }
    }
    
    pthread_mutex_unlock(&sem_registry_mutex);
    
    return KOS_IPC_SUCCESS;
}