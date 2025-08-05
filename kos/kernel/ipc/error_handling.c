/*
 * KOS IPC Error Handling and Edge Cases
 * Comprehensive IPC error recovery and validation
 */

#include "../process/process.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <sys/sem.h>
#include <sys/shm.h>
#include <fcntl.h>
#include <unistd.h>

/* IPC error types */
typedef enum {
    IPC_ERROR_NONE = 0,
    IPC_ERROR_INVALID_ID,          /* Invalid IPC ID */
    IPC_ERROR_PERMISSION_DENIED,   /* Permission denied */
    IPC_ERROR_RESOURCE_EXHAUSTED,  /* No more IPC resources */
    IPC_ERROR_INVALID_SIZE,        /* Invalid message/segment size */
    IPC_ERROR_QUEUE_FULL,          /* Message queue full */
    IPC_ERROR_QUEUE_EMPTY,         /* Message queue empty */
    IPC_ERROR_DEADLOCK,            /* IPC deadlock detected */
    IPC_ERROR_TIMEOUT,             /* Operation timeout */
    IPC_ERROR_PROCESS_DIED,        /* Process died during IPC */
    IPC_ERROR_INVALID_MESSAGE,     /* Invalid message format */
    IPC_ERROR_BUFFER_OVERFLOW,     /* Buffer overflow */
    IPC_ERROR_SEMAPHORE_OVERFLOW,  /* Semaphore value overflow */
    IPC_ERROR_SHARED_MEM_CORRUPT,  /* Shared memory corruption */
    IPC_ERROR_PIPE_BROKEN,         /* Broken pipe */
    IPC_ERROR_SIGNAL_INTERRUPTED,  /* Signal interrupted operation */
    IPC_ERROR_INVALID_OPERATION,   /* Invalid operation for IPC type */
    IPC_ERROR_NAMESPACE_VIOLATION, /* IPC namespace violation */
    IPC_ERROR_QUOTA_EXCEEDED,      /* IPC quota exceeded */
    IPC_ERROR_LEAK_DETECTED        /* IPC resource leak detected */
} ipc_error_type_t;

/* Error recovery strategies */
typedef enum {
    IPC_RECOVERY_IGNORE = 0,
    IPC_RECOVERY_LOG,
    IPC_RECOVERY_RETRY,
    IPC_RECOVERY_CLEANUP,
    IPC_RECOVERY_RESET_IPC,
    IPC_RECOVERY_KILL_PROCESS,
    IPC_RECOVERY_FORCE_CLEANUP,
    IPC_RECOVERY_PANIC
} ipc_recovery_t;

/* IPC error context */
typedef struct {
    ipc_error_type_t type;
    const char *message;
    int ipc_id;
    int ipc_type;  /* IPC_MSG, IPC_SEM, IPC_SHM, etc. */
    pid_t pid;
    pid_t target_pid;
    size_t size;
    uint64_t timestamp;
    const char *file;
    int line;
    const char *function;
    ipc_recovery_t recovery;
    void *extra_data;
    uint32_t retry_count;
} ipc_error_ctx_t;

/* IPC error statistics */
static struct {
    uint64_t total_errors;
    uint64_t invalid_id_errors;
    uint64_t permission_denied_errors;
    uint64_t resource_exhausted_errors;
    uint64_t invalid_size_errors;
    uint64_t queue_full_errors;
    uint64_t queue_empty_errors;
    uint64_t deadlock_errors;
    uint64_t timeout_errors;
    uint64_t process_died_errors;
    uint64_t invalid_message_errors;
    uint64_t buffer_overflow_errors;
    uint64_t semaphore_overflow_errors;
    uint64_t shared_mem_corrupt_errors;
    uint64_t pipe_broken_errors;
    uint64_t signal_interrupted_errors;
    uint64_t invalid_operation_errors;
    uint64_t namespace_violation_errors;
    uint64_t quota_exceeded_errors;
    uint64_t leak_detected_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t ipc_cleaned_up;
    uint64_t processes_killed;
    uint64_t forced_cleanups;
    pthread_mutex_t lock;
} ipc_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* IPC resource tracking */
typedef struct ipc_resource {
    int id;
    int type;
    pid_t owner;
    pid_t *users;
    size_t user_count;
    size_t max_users;
    uint64_t created_time;
    uint64_t last_access;
    bool leaked;
    struct ipc_resource *next;
} ipc_resource_t;

static ipc_resource_t *ipc_resources = NULL;
static pthread_mutex_t resource_lock = PTHREAD_MUTEX_INITIALIZER;

/* Deadlock detection for IPC */
typedef struct ipc_wait_entry {
    pid_t pid;
    int ipc_id;
    int ipc_type;
    uint64_t wait_start;
    struct ipc_wait_entry *next;
} ipc_wait_entry_t;

static ipc_wait_entry_t *ipc_wait_list = NULL;
static pthread_mutex_t deadlock_lock = PTHREAD_MUTEX_INITIALIZER;

/* Validate IPC ID */
static int validate_ipc_id(int ipc_id, int ipc_type, const char *context)
{
    if (ipc_id < 0) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_INVALID_ID,
            .message = "Invalid IPC ID (negative)",
            .ipc_id = ipc_id,
            .ipc_type = ipc_type,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_LOG
        };
        return handle_ipc_error(&ctx);
    }

    /* Check if IPC object exists */
    struct msqid_ds msg_stat;
    struct semid_ds sem_stat;
    struct shmid_ds shm_stat;
    int result = -1;

    switch (ipc_type) {
        case IPC_MSG:
            result = msgctl(ipc_id, IPC_STAT, &msg_stat);
            break;
        case IPC_SEM:
            result = semctl(ipc_id, 0, IPC_STAT, &sem_stat);
            break;
        case IPC_SHM:
            result = shmctl(ipc_id, IPC_STAT, &shm_stat);
            break;
    }

    if (result == -1) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_INVALID_ID,
            .message = "IPC object does not exist",
            .ipc_id = ipc_id,
            .ipc_type = ipc_type,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_CLEANUP
        };
        return handle_ipc_error(&ctx);
    }

    return 0;
}

/* Validate message size */
static int validate_message_size(size_t size, int ipc_type, const char *context)
{
    size_t max_size = 0;

    switch (ipc_type) {
        case IPC_MSG:
            max_size = MSGMAX;
            break;
        case IPC_SHM:
            max_size = SHMMAX;
            break;
        default:
            max_size = 65536; /* Default 64KB limit */
            break;
    }

    if (size == 0) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_INVALID_SIZE,
            .message = "Zero size not allowed",
            .ipc_type = ipc_type,
            .size = size,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_LOG
        };
        return handle_ipc_error(&ctx);
    }

    if (size > max_size) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_INVALID_SIZE,
            .message = "Size exceeds maximum allowed",
            .ipc_type = ipc_type,
            .size = size,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_LOG
        };
        return handle_ipc_error(&ctx);
    }

    return 0;
}

/* Check IPC permissions */
static int check_ipc_permissions(int ipc_id, int ipc_type, int operation, const char *context)
{
    uid_t uid = getuid();
    gid_t gid = getgid();
    
    struct msqid_ds msg_stat;
    struct semid_ds sem_stat;
    struct shmid_ds shm_stat;
    
    uid_t owner_uid = 0;
    gid_t owner_gid = 0;
    mode_t mode = 0;
    
    switch (ipc_type) {
        case IPC_MSG:
            if (msgctl(ipc_id, IPC_STAT, &msg_stat) == 0) {
                owner_uid = msg_stat.msg_perm.uid;
                owner_gid = msg_stat.msg_perm.gid;
                mode = msg_stat.msg_perm.mode;
            }
            break;
        case IPC_SEM:
            if (semctl(ipc_id, 0, IPC_STAT, &sem_stat) == 0) {
                owner_uid = sem_stat.sem_perm.uid;
                owner_gid = sem_stat.sem_perm.gid;
                mode = sem_stat.sem_perm.mode;
            }
            break;
        case IPC_SHM:
            if (shmctl(ipc_id, IPC_STAT, &shm_stat) == 0) {
                owner_uid = shm_stat.shm_perm.uid;
                owner_gid = shm_stat.shm_perm.gid;
                mode = shm_stat.shm_perm.mode;
            }
            break;
    }

    /* Root can do anything */
    if (uid == 0) {
        return 0;
    }

    /* Check permissions based on operation */
    bool allowed = false;
    int required_perm = 0;

    switch (operation) {
        case IPC_R:
            required_perm = 0444;
            break;
        case IPC_W:
            required_perm = 0222;
            break;
        case IPC_M:  /* Control operations */
            if (uid == owner_uid) {
                allowed = true;
            }
            break;
    }

    if (!allowed && required_perm) {
        if (uid == owner_uid) {
            allowed = (mode & (required_perm & 0700)) != 0;
        } else if (gid == owner_gid) {
            allowed = (mode & (required_perm & 0070)) != 0;
        } else {
            allowed = (mode & (required_perm & 0007)) != 0;
        }
    }

    if (!allowed) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_PERMISSION_DENIED,
            .message = "IPC permission denied",
            .ipc_id = ipc_id,
            .ipc_type = ipc_type,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_LOG
        };
        return handle_ipc_error(&ctx);
    }

    return 0;
}

/* Track IPC resource usage */
static void track_ipc_resource(int ipc_id, int ipc_type, pid_t owner)
{
    pthread_mutex_lock(&resource_lock);

    /* Check if resource is already tracked */
    ipc_resource_t *resource = ipc_resources;
    while (resource && (resource->id != ipc_id || resource->type != ipc_type)) {
        resource = resource->next;
    }

    if (!resource) {
        resource = malloc(sizeof(ipc_resource_t));
        if (resource) {
            resource->id = ipc_id;
            resource->type = ipc_type;
            resource->owner = owner;
            resource->users = malloc(sizeof(pid_t) * 16);
            resource->user_count = 0;
            resource->max_users = 16;
            resource->created_time = time(NULL);
            resource->last_access = time(NULL);
            resource->leaked = false;
            resource->next = ipc_resources;
            ipc_resources = resource;
        }
    } else {
        resource->last_access = time(NULL);
    }

    pthread_mutex_unlock(&resource_lock);
}

/* Add user to IPC resource */
static void add_ipc_user(int ipc_id, int ipc_type, pid_t user_pid)
{
    pthread_mutex_lock(&resource_lock);

    ipc_resource_t *resource = ipc_resources;
    while (resource && (resource->id != ipc_id || resource->type != ipc_type)) {
        resource = resource->next;
    }

    if (resource) {
        /* Check if user is already tracked */
        bool found = false;
        for (size_t i = 0; i < resource->user_count; i++) {
            if (resource->users[i] == user_pid) {
                found = true;
                break;
            }
        }

        if (!found && resource->user_count < resource->max_users) {
            resource->users[resource->user_count++] = user_pid;
        }
    }

    pthread_mutex_unlock(&resource_lock);
}

/* Detect IPC deadlocks */
static int detect_ipc_deadlock(pid_t pid, int ipc_id, int ipc_type)
{
    pthread_mutex_lock(&deadlock_lock);

    /* Add current wait */
    ipc_wait_entry_t *wait_entry = malloc(sizeof(ipc_wait_entry_t));
    if (wait_entry) {
        wait_entry->pid = pid;
        wait_entry->ipc_id = ipc_id;
        wait_entry->ipc_type = ipc_type;
        wait_entry->wait_start = time(NULL);
        wait_entry->next = ipc_wait_list;
        ipc_wait_list = wait_entry;
    }

    /* Simple cycle detection */
    ipc_wait_entry_t *entry = ipc_wait_list;
    while (entry) {
        if (entry->pid != pid && entry->ipc_id == ipc_id && entry->ipc_type == ipc_type) {
            /* Check if the other process is waiting for something we have */
            ipc_wait_entry_t *other_wait = ipc_wait_list;
            while (other_wait) {
                if (other_wait->pid == pid && other_wait != wait_entry) {
                    /* Potential deadlock detected */
                    ipc_error_ctx_t ctx = {
                        .type = IPC_ERROR_DEADLOCK,
                        .message = "IPC deadlock detected",
                        .ipc_id = ipc_id,
                        .ipc_type = ipc_type,
                        .pid = pid,
                        .target_pid = entry->pid,
                        .timestamp = time(NULL),
                        .file = __FILE__,
                        .line = __LINE__,
                        .function = __func__,
                        .recovery = IPC_RECOVERY_KILL_PROCESS
                    };

                    pthread_mutex_unlock(&deadlock_lock);
                    return handle_ipc_error(&ctx);
                }
                other_wait = other_wait->next;
            }
        }
        entry = entry->next;
    }

    pthread_mutex_unlock(&deadlock_lock);
    return 0;
}

/* Remove IPC wait entry */
static void remove_ipc_wait(pid_t pid, int ipc_id, int ipc_type)
{
    pthread_mutex_lock(&deadlock_lock);

    ipc_wait_entry_t **current = &ipc_wait_list;
    while (*current) {
        ipc_wait_entry_t *entry = *current;
        if (entry->pid == pid && entry->ipc_id == ipc_id && entry->ipc_type == ipc_type) {
            *current = entry->next;
            free(entry);
            break;
        }
        current = &entry->next;
    }

    pthread_mutex_unlock(&deadlock_lock);
}

/* Detect IPC resource leaks */
static int detect_ipc_leaks(void)
{
    int leaks_found = 0;
    uint64_t now = time(NULL);

    pthread_mutex_lock(&resource_lock);

    ipc_resource_t *resource = ipc_resources;
    while (resource) {
        /* Check if resource has been unused for too long */
        if (now - resource->last_access > IPC_LEAK_THRESHOLD) {
            /* Check if owner process still exists */
            if (kill(resource->owner, 0) == -1 && errno == ESRCH) {
                if (!resource->leaked) {
                    resource->leaked = true;
                    leaks_found++;

                    ipc_error_ctx_t ctx = {
                        .type = IPC_ERROR_LEAK_DETECTED,
                        .message = "IPC resource leak detected",
                        .ipc_id = resource->id,
                        .ipc_type = resource->type,
                        .pid = resource->owner,
                        .timestamp = time(NULL),
                        .file = __FILE__,
                        .line = __LINE__,
                        .function = __func__,
                        .recovery = IPC_RECOVERY_FORCE_CLEANUP
                    };

                    pthread_mutex_unlock(&resource_lock);
                    handle_ipc_error(&ctx);
                    pthread_mutex_lock(&resource_lock);
                }
            }
        }
        resource = resource->next;
    }

    pthread_mutex_unlock(&resource_lock);
    return leaks_found;
}

/* Validate shared memory segment */
static int validate_shared_memory(int shmid, void *shmaddr, size_t size, const char *context)
{
    if (!shmaddr) {
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_SHARED_MEM_CORRUPT,
            .message = "NULL shared memory address",
            .ipc_id = shmid,
            .ipc_type = IPC_SHM,
            .size = size,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_CLEANUP
        };
        return handle_ipc_error(&ctx);
    }

    /* Check for memory corruption using simple canary patterns */
    uint32_t *canary_start = (uint32_t*)shmaddr;
    uint32_t *canary_end = (uint32_t*)((char*)shmaddr + size - sizeof(uint32_t));

    if (size >= 8 && (*canary_start == 0xDEADBEEF || *canary_end == 0xDEADBEEF)) {
        /* Corruption detected (using known corruption pattern) */
        ipc_error_ctx_t ctx = {
            .type = IPC_ERROR_SHARED_MEM_CORRUPT,
            .message = "Shared memory corruption detected",
            .ipc_id = shmid,
            .ipc_type = IPC_SHM,
            .size = size,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = IPC_RECOVERY_CLEANUP
        };
        return handle_ipc_error(&ctx);
    }

    return 0;
}

/* Log IPC error */
static void log_ipc_error(const ipc_error_ctx_t *ctx)
{
    pthread_mutex_lock(&ipc_error_stats.lock);
    ipc_error_stats.total_errors++;

    switch (ctx->type) {
        case IPC_ERROR_INVALID_ID:
            ipc_error_stats.invalid_id_errors++;
            break;
        case IPC_ERROR_PERMISSION_DENIED:
            ipc_error_stats.permission_denied_errors++;
            break;
        case IPC_ERROR_RESOURCE_EXHAUSTED:
            ipc_error_stats.resource_exhausted_errors++;
            break;
        case IPC_ERROR_INVALID_SIZE:
            ipc_error_stats.invalid_size_errors++;
            break;
        case IPC_ERROR_QUEUE_FULL:
            ipc_error_stats.queue_full_errors++;
            break;
        case IPC_ERROR_QUEUE_EMPTY:
            ipc_error_stats.queue_empty_errors++;
            break;
        case IPC_ERROR_DEADLOCK:
            ipc_error_stats.deadlock_errors++;
            break;
        case IPC_ERROR_TIMEOUT:
            ipc_error_stats.timeout_errors++;
            break;
        case IPC_ERROR_PROCESS_DIED:
            ipc_error_stats.process_died_errors++;
            break;
        case IPC_ERROR_INVALID_MESSAGE:
            ipc_error_stats.invalid_message_errors++;
            break;
        case IPC_ERROR_BUFFER_OVERFLOW:
            ipc_error_stats.buffer_overflow_errors++;
            break;
        case IPC_ERROR_SEMAPHORE_OVERFLOW:
            ipc_error_stats.semaphore_overflow_errors++;
            break;
        case IPC_ERROR_SHARED_MEM_CORRUPT:
            ipc_error_stats.shared_mem_corrupt_errors++;
            break;
        case IPC_ERROR_PIPE_BROKEN:
            ipc_error_stats.pipe_broken_errors++;
            break;
        case IPC_ERROR_SIGNAL_INTERRUPTED:
            ipc_error_stats.signal_interrupted_errors++;
            break;
        case IPC_ERROR_INVALID_OPERATION:
            ipc_error_stats.invalid_operation_errors++;
            break;
        case IPC_ERROR_NAMESPACE_VIOLATION:
            ipc_error_stats.namespace_violation_errors++;
            break;
        case IPC_ERROR_QUOTA_EXCEEDED:
            ipc_error_stats.quota_exceeded_errors++;
            break;
        case IPC_ERROR_LEAK_DETECTED:
            ipc_error_stats.leak_detected_errors++;
            break;
        default:
            break;
    }

    pthread_mutex_unlock(&ipc_error_stats.lock);

    /* Log error details */
    printf("[IPC ERROR] Type: %d, Message: %s\n", ctx->type, ctx->message);
    printf("[IPC ERROR] IPC ID: %d, Type: %d\n", ctx->ipc_id, ctx->ipc_type);
    printf("[IPC ERROR] PID: %d", ctx->pid);
    if (ctx->target_pid) {
        printf(", Target PID: %d", ctx->target_pid);
    }
    printf("\n");
    if (ctx->size) {
        printf("[IPC ERROR] Size: %zu\n", ctx->size);
    }
    printf("[IPC ERROR] Location: %s:%d in %s()\n",
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle IPC error with recovery */
int handle_ipc_error(ipc_error_ctx_t *ctx)
{
    log_ipc_error(ctx);

    pthread_mutex_lock(&ipc_error_stats.lock);
    ipc_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&ipc_error_stats.lock);

    switch (ctx->recovery) {
        case IPC_RECOVERY_IGNORE:
            return 0;

        case IPC_RECOVERY_LOG:
            /* Already logged above */
            return 0;

        case IPC_RECOVERY_RETRY:
            if (ctx->retry_count < MAX_IPC_RETRY_COUNT) {
                ctx->retry_count++;
                usleep(1000 * ctx->retry_count); /* Exponential backoff */
                pthread_mutex_lock(&ipc_error_stats.lock);
                ipc_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&ipc_error_stats.lock);
                return -EAGAIN; /* Signal retry */
            }
            return -1; /* Give up */

        case IPC_RECOVERY_CLEANUP:
            printf("[IPC RECOVERY] Cleaning up IPC resource %d\n", ctx->ipc_id);
            /* Clean up IPC resource */
            switch (ctx->ipc_type) {
                case IPC_MSG:
                    msgctl(ctx->ipc_id, IPC_RMID, NULL);
                    break;
                case IPC_SEM:
                    semctl(ctx->ipc_id, 0, IPC_RMID);
                    break;
                case IPC_SHM:
                    shmctl(ctx->ipc_id, IPC_RMID, NULL);
                    break;
            }
            pthread_mutex_lock(&ipc_error_stats.lock);
            ipc_error_stats.ipc_cleaned_up++;
            ipc_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&ipc_error_stats.lock);
            return 0;

        case IPC_RECOVERY_RESET_IPC:
            printf("[IPC RECOVERY] Resetting IPC subsystem\n");
            /* Reset IPC subsystem state */
            ipc_reset_subsystem();
            pthread_mutex_lock(&ipc_error_stats.lock);
            ipc_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&ipc_error_stats.lock);
            return 0;

        case IPC_RECOVERY_KILL_PROCESS:
            if (ctx->pid > 1 && ctx->target_pid > 1) { /* Don't kill init */
                printf("[IPC RECOVERY] Killing process %d to resolve deadlock\n", ctx->target_pid);
                kill(ctx->target_pid, SIGTERM);
                pthread_mutex_lock(&ipc_error_stats.lock);
                ipc_error_stats.processes_killed++;
                ipc_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&ipc_error_stats.lock);
            }
            return 0;

        case IPC_RECOVERY_FORCE_CLEANUP:
            printf("[IPC RECOVERY] Force cleaning up leaked IPC resources\n");
            /* Force cleanup of all IPC resources */
            cleanup_leaked_ipc_resources();
            pthread_mutex_lock(&ipc_error_stats.lock);
            ipc_error_stats.forced_cleanups++;
            ipc_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&ipc_error_stats.lock);
            return 0;

        case IPC_RECOVERY_PANIC:
            printf("[IPC PANIC] Unrecoverable IPC error - system halting\n");
            abort();

        default:
            return -1;
    }
}

/* Safe IPC operations with error handling */
int safe_msgget(key_t key, int msgflg)
{
    int msgqid = msgget(key, msgflg);
    if (msgqid >= 0) {
        track_ipc_resource(msgqid, IPC_MSG, getpid());
    } else {
        ipc_error_ctx_t ctx = {
            .type = (errno == ENOSPC) ? IPC_ERROR_RESOURCE_EXHAUSTED : IPC_ERROR_INVALID_ID,
            .message = "Message queue creation failed",
            .ipc_type = IPC_MSG,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = IPC_RECOVERY_LOG
        };
        handle_ipc_error(&ctx);
    }
    return msgqid;
}

int safe_msgsnd(int msqid, const void *msgp, size_t msgsz, int msgflg)
{
    if (validate_ipc_id(msqid, IPC_MSG, "safe_msgsnd") != 0 ||
        validate_message_size(msgsz, IPC_MSG, "safe_msgsnd") != 0 ||
        check_ipc_permissions(msqid, IPC_MSG, IPC_W, "safe_msgsnd") != 0) {
        return -1;
    }

    detect_ipc_deadlock(getpid(), msqid, IPC_MSG);
    
    int result = msgsnd(msqid, msgp, msgsz, msgflg);
    
    remove_ipc_wait(getpid(), msqid, IPC_MSG);
    
    if (result == -1) {
        ipc_error_type_t error_type = IPC_ERROR_INVALID_OPERATION;
        switch (errno) {
            case EAGAIN:
                error_type = IPC_ERROR_QUEUE_FULL;
                break;
            case EINTR:
                error_type = IPC_ERROR_SIGNAL_INTERRUPTED;
                break;
            case EINVAL:
                error_type = IPC_ERROR_INVALID_MESSAGE;
                break;
        }
        
        ipc_error_ctx_t ctx = {
            .type = error_type,
            .message = "Message send failed",
            .ipc_id = msqid,
            .ipc_type = IPC_MSG,
            .size = msgsz,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = IPC_RECOVERY_RETRY
        };
        handle_ipc_error(&ctx);
    }
    
    return result;
}

ssize_t safe_msgrcv(int msqid, void *msgp, size_t msgsz, long msgtyp, int msgflg)
{
    if (validate_ipc_id(msqid, IPC_MSG, "safe_msgrcv") != 0 ||
        check_ipc_permissions(msqid, IPC_MSG, IPC_R, "safe_msgrcv") != 0) {
        return -1;
    }

    detect_ipc_deadlock(getpid(), msqid, IPC_MSG);
    
    ssize_t result = msgrcv(msqid, msgp, msgsz, msgtyp, msgflg);
    
    remove_ipc_wait(getpid(), msqid, IPC_MSG);
    
    if (result == -1) {
        ipc_error_type_t error_type = IPC_ERROR_INVALID_OPERATION;
        switch (errno) {
            case ENOMSG:
                error_type = IPC_ERROR_QUEUE_EMPTY;
                break;
            case EINTR:
                error_type = IPC_ERROR_SIGNAL_INTERRUPTED;
                break;
            case E2BIG:
                error_type = IPC_ERROR_BUFFER_OVERFLOW;
                break;
        }
        
        ipc_error_ctx_t ctx = {
            .type = error_type,
            .message = "Message receive failed",
            .ipc_id = msqid,
            .ipc_type = IPC_MSG,
            .size = msgsz,
            .pid = getpid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = IPC_RECOVERY_RETRY
        };
        handle_ipc_error(&ctx);
    }
    
    return result;
}

/* Comprehensive IPC health check */
int ipc_health_check(void)
{
    int issues_found = 0;

    /* Check for leaked resources */
    issues_found += detect_ipc_leaks();

    /* Check for long-running deadlocks */
    pthread_mutex_lock(&deadlock_lock);
    uint64_t now = time(NULL);
    ipc_wait_entry_t *entry = ipc_wait_list;
    while (entry) {
        if (now - entry->wait_start > IPC_DEADLOCK_THRESHOLD) {
            issues_found++;
        }
        entry = entry->next;
    }
    pthread_mutex_unlock(&deadlock_lock);

    return issues_found;
}

/* Get IPC error statistics */
void ipc_get_error_stats(void)
{
    pthread_mutex_lock(&ipc_error_stats.lock);

    printf("\nIPC Error Statistics:\n");
    printf("=====================\n");
    printf("Total errors:              %lu\n", ipc_error_stats.total_errors);
    printf("Invalid ID errors:         %lu\n", ipc_error_stats.invalid_id_errors);
    printf("Permission denied errors:  %lu\n", ipc_error_stats.permission_denied_errors);
    printf("Resource exhausted errors: %lu\n", ipc_error_stats.resource_exhausted_errors);
    printf("Invalid size errors:       %lu\n", ipc_error_stats.invalid_size_errors);
    printf("Queue full errors:         %lu\n", ipc_error_stats.queue_full_errors);
    printf("Queue empty errors:        %lu\n", ipc_error_stats.queue_empty_errors);
    printf("Deadlock errors:           %lu\n", ipc_error_stats.deadlock_errors);
    printf("Timeout errors:            %lu\n", ipc_error_stats.timeout_errors);
    printf("Process died errors:       %lu\n", ipc_error_stats.process_died_errors);
    printf("Invalid message errors:    %lu\n", ipc_error_stats.invalid_message_errors);
    printf("Buffer overflow errors:    %lu\n", ipc_error_stats.buffer_overflow_errors);
    printf("Semaphore overflow errors: %lu\n", ipc_error_stats.semaphore_overflow_errors);
    printf("Shared mem corrupt errors: %lu\n", ipc_error_stats.shared_mem_corrupt_errors);
    printf("Pipe broken errors:        %lu\n", ipc_error_stats.pipe_broken_errors);
    printf("Signal interrupted errors: %lu\n", ipc_error_stats.signal_interrupted_errors);
    printf("Invalid operation errors:  %lu\n", ipc_error_stats.invalid_operation_errors);
    printf("Namespace violation errors:%lu\n", ipc_error_stats.namespace_violation_errors);
    printf("Quota exceeded errors:     %lu\n", ipc_error_stats.quota_exceeded_errors);
    printf("Leak detected errors:      %lu\n", ipc_error_stats.leak_detected_errors);
    printf("Recovery attempts:         %lu\n", ipc_error_stats.recoveries_attempted);
    printf("Recovery successes:        %lu\n", ipc_error_stats.recoveries_successful);
    printf("IPC cleaned up:            %lu\n", ipc_error_stats.ipc_cleaned_up);
    printf("Processes killed:          %lu\n", ipc_error_stats.processes_killed);
    printf("Forced cleanups:           %lu\n", ipc_error_stats.forced_cleanups);

    if (ipc_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)ipc_error_stats.recoveries_successful / 
                             ipc_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate:     %.1f%%\n", success_rate);
    }

    pthread_mutex_unlock(&ipc_error_stats.lock);
}

/* Initialize IPC error handling */
void ipc_error_init(void)
{
    printf("IPC error handling initialized\n");
}

/* Cleanup IPC error handling */
void ipc_error_cleanup(void)
{
    pthread_mutex_lock(&resource_lock);
    
    ipc_resource_t *resource = ipc_resources;
    while (resource) {
        ipc_resource_t *next = resource->next;
        if (resource->users) {
            free(resource->users);
        }
        free(resource);
        resource = next;
    }
    ipc_resources = NULL;
    
    pthread_mutex_unlock(&resource_lock);

    pthread_mutex_lock(&deadlock_lock);
    
    ipc_wait_entry_t *wait_entry = ipc_wait_list;
    while (wait_entry) {
        ipc_wait_entry_t *next = wait_entry->next;
        free(wait_entry);
        wait_entry = next;
    }
    ipc_wait_list = NULL;
    
    pthread_mutex_unlock(&deadlock_lock);
}

/* Macros for easy error checking */
#define IPC_VALIDATE_ID(id, type, context) \
    if (validate_ipc_id(id, type, context) != 0) return -1

#define IPC_CHECK_PERMISSIONS(id, type, op, context) \
    if (check_ipc_permissions(id, type, op, context) != 0) return -1

#define IPC_VALIDATE_SIZE(size, type, context) \
    if (validate_message_size(size, type, context) != 0) return -1