#ifndef KOS_IPC_H
#define KOS_IPC_H

#include <sys/types.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <sys/shm.h>
#include <sys/sem.h>
#include <signal.h>
#include <pthread.h>
#include <fcntl.h>
#include <unistd.h>
#include <mqueue.h>
#include <semaphore.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif

// Maximum limits
#define KOS_MAX_PIPE_SIZE 65536
#define KOS_MAX_MSG_SIZE 8192
#define KOS_MAX_QUEUES 256
#define KOS_MAX_SEMAPHORES 256
#define KOS_MAX_SHM_SEGMENTS 256
#define KOS_MAX_PROCESSES 4096

// Error codes
#define KOS_IPC_SUCCESS 0
#define KOS_IPC_ERROR -1
#define KOS_IPC_TIMEOUT -2
#define KOS_IPC_INVALID_PARAM -3
#define KOS_IPC_RESOURCE_BUSY -4
#define KOS_IPC_NO_MEMORY -5

// Pipe structures and functions
typedef struct {
    int read_fd;
    int write_fd;
    char name[256];
    int is_named;
    size_t buffer_size;
    pthread_mutex_t mutex;
} kos_pipe_t;

// Pipe functions
int kos_pipe_create(kos_pipe_t *pipe);
int kos_pipe_create_named(kos_pipe_t *pipe, const char *name);
int kos_pipe_read(kos_pipe_t *pipe, void *buffer, size_t size);
int kos_pipe_write(kos_pipe_t *pipe, const void *buffer, size_t size);
int kos_pipe_close(kos_pipe_t *pipe);
int kos_pipe_destroy(kos_pipe_t *pipe);

// Shared memory structures and functions
typedef struct {
    int shm_id;
    key_t key;
    void *addr;
    size_t size;
    int flags;
    pthread_mutex_t *mutex;
    char name[256];
} kos_shm_t;

// Shared memory functions
int kos_shm_create(kos_shm_t *shm, const char *name, size_t size, int flags);
int kos_shm_attach(kos_shm_t *shm, const char *name);
int kos_shm_detach(kos_shm_t *shm);
int kos_shm_destroy(kos_shm_t *shm);
void* kos_shm_get_addr(kos_shm_t *shm);
int kos_shm_lock(kos_shm_t *shm);
int kos_shm_unlock(kos_shm_t *shm);

// Message queue structures and functions
typedef struct {
    long mtype;
    char mtext[KOS_MAX_MSG_SIZE];
} kos_msg_t;

typedef struct {
    int msqid;
    key_t key;
    mqd_t posix_mq;
    char name[256];
    int is_posix;
    struct mq_attr attr;
} kos_msgqueue_t;

// Message queue functions
int kos_msgqueue_create(kos_msgqueue_t *mq, const char *name, int is_posix);
int kos_msgqueue_send(kos_msgqueue_t *mq, const void *msg, size_t size, int priority);
int kos_msgqueue_receive(kos_msgqueue_t *mq, void *msg, size_t size, int *priority);
int kos_msgqueue_destroy(kos_msgqueue_t *mq);
int kos_msgqueue_get_attributes(kos_msgqueue_t *mq, struct mq_attr *attr);

// Semaphore structures and functions
typedef struct {
    int semid;
    key_t key;
    sem_t *posix_sem;
    char name[256];
    int is_posix;
    int value;
    int max_value;
} kos_semaphore_t;

// Semaphore functions
int kos_semaphore_create(kos_semaphore_t *sem, const char *name, int value, int is_posix);
int kos_semaphore_wait(kos_semaphore_t *sem, int timeout_ms);
int kos_semaphore_post(kos_semaphore_t *sem);
int kos_semaphore_try_wait(kos_semaphore_t *sem);
int kos_semaphore_get_value(kos_semaphore_t *sem);
int kos_semaphore_destroy(kos_semaphore_t *sem);

// Mutex and condition variable structures
typedef struct {
    pthread_mutex_t mutex;
    pthread_mutexattr_t attr;
    int initialized;
    pid_t owner;
} kos_mutex_t;

typedef struct {
    pthread_cond_t cond;
    pthread_condattr_t attr;
    int initialized;
} kos_condvar_t;

// Mutex functions
int kos_mutex_init(kos_mutex_t *mutex, int shared);
int kos_mutex_lock(kos_mutex_t *mutex);
int kos_mutex_try_lock(kos_mutex_t *mutex);
int kos_mutex_unlock(kos_mutex_t *mutex);
int kos_mutex_destroy(kos_mutex_t *mutex);

// Condition variable functions
int kos_condvar_init(kos_condvar_t *condvar, int shared);
int kos_condvar_wait(kos_condvar_t *condvar, kos_mutex_t *mutex);
int kos_condvar_timed_wait(kos_condvar_t *condvar, kos_mutex_t *mutex, int timeout_ms);
int kos_condvar_signal(kos_condvar_t *condvar);
int kos_condvar_broadcast(kos_condvar_t *condvar);
int kos_condvar_destroy(kos_condvar_t *condvar);

// Signal handling structures and functions
typedef struct {
    int signal_num;
    void (*handler)(int);
    sigset_t mask;
    struct sigaction old_action;
} kos_signal_handler_t;

// Signal functions
int kos_signal_register(int signal_num, void (*handler)(int));
int kos_signal_unregister(int signal_num);
int kos_signal_send(pid_t pid, int signal_num);
int kos_signal_block(int signal_num);
int kos_signal_unblock(int signal_num);
int kos_signal_wait(sigset_t *set, int *signal_num, int timeout_ms);

// IPC management functions
int kos_ipc_init(void);
int kos_ipc_cleanup(void);
int kos_ipc_get_stats(void);

// Utility functions
key_t kos_ipc_generate_key(const char *pathname, int proj_id);
int kos_ipc_permissions_check(int operation, pid_t pid, uid_t uid, gid_t gid);

#ifdef __cplusplus
}
#endif

#endif // KOS_IPC_H