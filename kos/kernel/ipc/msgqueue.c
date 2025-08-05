#include "ipc.h"
#include <sys/msg.h>
#include <mqueue.h>

// Global message queue registry
static kos_msgqueue_t *mq_registry[KOS_MAX_QUEUES] = {0};
static pthread_mutex_t mq_registry_mutex = PTHREAD_MUTEX_INITIALIZER;
static int mq_count = 0;

// Create message queue
int kos_msgqueue_create(kos_msgqueue_t *mq, const char *name, int is_posix) {
    if (!mq || !name) {
        return KOS_IPC_INVALID_PARAM;
    }

    mq->is_posix = is_posix;
    strncpy(mq->name, name, sizeof(mq->name) - 1);
    mq->name[sizeof(mq->name) - 1] = '\0';

    if (is_posix) {
        // POSIX message queue
        struct mq_attr attr;
        attr.mq_flags = 0;
        attr.mq_maxmsg = 10;
        attr.mq_msgsize = KOS_MAX_MSG_SIZE;
        attr.mq_curmsgs = 0;

        mq->posix_mq = mq_open(name, O_CREAT | O_RDWR | O_EXCL, 0666, &attr);
        if (mq->posix_mq == (mqd_t)-1) {
            if (errno == EEXIST) {
                // Queue already exists, try to open
                mq->posix_mq = mq_open(name, O_RDWR);
                if (mq->posix_mq == (mqd_t)-1) {
                    return KOS_IPC_ERROR;
                }
            } else {
                return KOS_IPC_ERROR;
            }
        }

        // Get queue attributes
        if (mq_getattr(mq->posix_mq, &mq->attr) == -1) {
            mq_close(mq->posix_mq);
            mq_unlink(name);
            return KOS_IPC_ERROR;
        }
    } else {
        // System V message queue
        mq->key = kos_ipc_generate_key(name, 2);
        if (mq->key == -1) {
            return KOS_IPC_ERROR;
        }

        mq->msqid = msgget(mq->key, IPC_CREAT | IPC_EXCL | 0666);
        if (mq->msqid == -1) {
            if (errno == EEXIST) {
                // Queue already exists
                mq->msqid = msgget(mq->key, 0666);
                if (mq->msqid == -1) {
                    return KOS_IPC_ERROR;
                }
            } else {
                return KOS_IPC_ERROR;
            }
        }
    }

    // Register message queue
    pthread_mutex_lock(&mq_registry_mutex);
    if (mq_count < KOS_MAX_QUEUES) {
        mq_registry[mq_count] = mq;
        mq_count++;
    }
    pthread_mutex_unlock(&mq_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Send message to queue
int kos_msgqueue_send(kos_msgqueue_t *mq, const void *msg, size_t size, int priority) {
    if (!mq || !msg || size == 0 || size > KOS_MAX_MSG_SIZE) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (mq->is_posix) {
        // POSIX message queue
        if (mq_send(mq->posix_mq, (const char*)msg, size, priority) == -1) {
            if (errno == EAGAIN) {
                return KOS_IPC_RESOURCE_BUSY;
            }
            return KOS_IPC_ERROR;
        }
    } else {
        // System V message queue
        kos_msg_t message;
        message.mtype = priority > 0 ? priority : 1; // Message type must be > 0
        
        if (size > sizeof(message.mtext)) {
            return KOS_IPC_INVALID_PARAM;
        }
        
        memcpy(message.mtext, msg, size);
        
        if (msgsnd(mq->msqid, &message, size, IPC_NOWAIT) == -1) {
            if (errno == EAGAIN) {
                return KOS_IPC_RESOURCE_BUSY;
            }
            return KOS_IPC_ERROR;
        }
    }

    return KOS_IPC_SUCCESS;
}

// Receive message from queue
int kos_msgqueue_receive(kos_msgqueue_t *mq, void *msg, size_t size, int *priority) {
    if (!mq || !msg || size == 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    ssize_t received;

    if (mq->is_posix) {
        // POSIX message queue
        unsigned int prio = 0;
        received = mq_receive(mq->posix_mq, (char*)msg, size, &prio);
        
        if (received == -1) {
            if (errno == EAGAIN) {
                return 0; // No message available
            }
            return KOS_IPC_ERROR;
        }
        
        if (priority) {
            *priority = (int)prio;
        }
    } else {
        // System V message queue
        kos_msg_t message;
        
        received = msgrcv(mq->msqid, &message, sizeof(message.mtext), 0, IPC_NOWAIT);
        
        if (received == -1) {
            if (errno == ENOMSG) {
                return 0; // No message available
            }
            return KOS_IPC_ERROR;
        }
        
        if ((size_t)received > size) {
            return KOS_IPC_ERROR; // Buffer too small
        }
        
        memcpy(msg, message.mtext, received);
        
        if (priority) {
            *priority = (int)message.mtype;
        }
    }

    return (int)received;
}

// Destroy message queue
int kos_msgqueue_destroy(kos_msgqueue_t *mq) {
    if (!mq) {
        return KOS_IPC_INVALID_PARAM;
    }

    int result = KOS_IPC_SUCCESS;

    if (mq->is_posix) {
        // POSIX message queue
        if (mq->posix_mq != (mqd_t)-1) {
            if (mq_close(mq->posix_mq) == -1) {
                result = KOS_IPC_ERROR;
            }
            if (mq_unlink(mq->name) == -1) {
                result = KOS_IPC_ERROR;
            }
        }
    } else {
        // System V message queue
        if (mq->msqid != -1) {
            if (msgctl(mq->msqid, IPC_RMID, NULL) == -1) {
                result = KOS_IPC_ERROR;
            }
        }
    }

    // Remove from registry
    pthread_mutex_lock(&mq_registry_mutex);
    for (int i = 0; i < mq_count; i++) {
        if (mq_registry[i] == mq) {
            // Shift remaining queues
            for (int j = i; j < mq_count - 1; j++) {
                mq_registry[j] = mq_registry[j + 1];
            }
            mq_count--;
            break;
        }
    }
    pthread_mutex_unlock(&mq_registry_mutex);

    // Clear structure
    memset(mq, 0, sizeof(kos_msgqueue_t));
    mq->msqid = -1;
    mq->posix_mq = (mqd_t)-1;

    return result;
}

// Get message queue attributes
int kos_msgqueue_get_attributes(kos_msgqueue_t *mq, struct mq_attr *attr) {
    if (!mq || !attr) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (mq->is_posix) {
        // POSIX message queue
        if (mq_getattr(mq->posix_mq, attr) == -1) {
            return KOS_IPC_ERROR;
        }
    } else {
        // System V message queue - simulate mq_attr structure
        struct msqid_ds buf;
        if (msgctl(mq->msqid, IPC_STAT, &buf) == -1) {
            return KOS_IPC_ERROR;
        }
        
        attr->mq_flags = 0;
        attr->mq_maxmsg = buf.msg_qbytes / KOS_MAX_MSG_SIZE;
        attr->mq_msgsize = KOS_MAX_MSG_SIZE;
        attr->mq_curmsgs = buf.msg_qnum;
    }

    return KOS_IPC_SUCCESS;
}

// Set message queue attributes (POSIX only)
int kos_msgqueue_set_attributes(kos_msgqueue_t *mq, const struct mq_attr *new_attr, struct mq_attr *old_attr) {
    if (!mq || !new_attr) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (!mq->is_posix) {
        return KOS_IPC_ERROR; // Not supported for System V queues
    }

    if (mq_setattr(mq->posix_mq, new_attr, old_attr) == -1) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Get message queue statistics
int kos_msgqueue_get_stats(int *active_queues, int *total_messages) {
    pthread_mutex_lock(&mq_registry_mutex);
    
    if (active_queues) {
        *active_queues = mq_count;
    }
    
    if (total_messages) {
        *total_messages = 0;
        for (int i = 0; i < mq_count; i++) {
            if (mq_registry[i]) {
                struct mq_attr attr;
                if (kos_msgqueue_get_attributes(mq_registry[i], &attr) == KOS_IPC_SUCCESS) {
                    *total_messages += attr.mq_curmsgs;
                }
            }
        }
    }
    
    pthread_mutex_unlock(&mq_registry_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Timed send (POSIX only)
int kos_msgqueue_timed_send(kos_msgqueue_t *mq, const void *msg, size_t size, int priority, int timeout_ms) {
    if (!mq || !msg || size == 0 || !mq->is_posix) {
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

    if (mq_timedsend(mq->posix_mq, (const char*)msg, size, priority, &abs_timeout) == -1) {
        if (errno == ETIMEDOUT) {
            return KOS_IPC_TIMEOUT;
        }
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Timed receive (POSIX only)
int kos_msgqueue_timed_receive(kos_msgqueue_t *mq, void *msg, size_t size, int *priority, int timeout_ms) {
    if (!mq || !msg || size == 0 || !mq->is_posix) {
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

    unsigned int prio = 0;
    ssize_t received = mq_timedreceive(mq->posix_mq, (char*)msg, size, &prio, &abs_timeout);
    
    if (received == -1) {
        if (errno == ETIMEDOUT) {
            return KOS_IPC_TIMEOUT;
        }
        return KOS_IPC_ERROR;
    }
    
    if (priority) {
        *priority = (int)prio;
    }

    return (int)received;
}