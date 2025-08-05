/*
 * KOS Kernel Core Header
 * Main kernel data structures and interfaces
 */

#ifndef KOS_KCORE_H
#define KOS_KCORE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* Kernel version */
#define KOS_VERSION_MAJOR 1
#define KOS_VERSION_MINOR 0
#define KOS_VERSION_PATCH 0

/* Kernel constants */
#define KOS_PAGE_SIZE       4096
#define KOS_MAX_PROCESSES   1024
#define KOS_MAX_THREADS     4096
#define KOS_MAX_FDS         1024
#define KOS_KERNEL_STACK    8192

/* Process states */
typedef enum {
    PROC_STATE_NEW = 0,
    PROC_STATE_READY,
    PROC_STATE_RUNNING,
    PROC_STATE_BLOCKED,
    PROC_STATE_ZOMBIE,
    PROC_STATE_DEAD
} kos_proc_state_t;

/* Thread states */
typedef enum {
    THREAD_STATE_NEW = 0,
    THREAD_STATE_READY,
    THREAD_STATE_RUNNING,
    THREAD_STATE_BLOCKED,
    THREAD_STATE_SLEEPING,
    THREAD_STATE_DEAD
} kos_thread_state_t;

/* Memory regions */
typedef struct kos_mem_region {
    uint64_t start;
    uint64_t size;
    uint32_t flags;
    struct kos_mem_region* next;
} kos_mem_region_t;

/* Process control block */
typedef struct kos_process {
    uint32_t pid;
    uint32_t ppid;
    uint32_t uid;
    uint32_t gid;
    kos_proc_state_t state;
    
    /* Memory management */
    kos_mem_region_t* mem_regions;
    uint64_t brk;
    uint64_t stack_top;
    
    /* File descriptors */
    void* fds[KOS_MAX_FDS];
    
    /* Scheduling */
    uint64_t cpu_time;
    uint32_t priority;
    uint32_t nice;
    
    /* Threads */
    struct kos_thread* threads;
    uint32_t thread_count;
    
    /* Signals */
    uint64_t signal_pending;
    uint64_t signal_mask;
    
    /* Namespace and cgroups */
    struct kos_namespace* ns;
    struct kos_cgroup* cgroup;
    
    /* Statistics */
    uint64_t start_time;
    uint64_t utime;
    uint64_t stime;
    
    struct kos_process* next;
    struct kos_process* parent;
    struct kos_process* children;
    struct kos_process* sibling;
} kos_process_t;

/* Thread control block */
typedef struct kos_thread {
    uint32_t tid;
    uint32_t pid;
    kos_thread_state_t state;
    
    /* CPU context */
    void* cpu_context;
    void* fpu_context;
    
    /* Stack */
    void* stack_base;
    uint64_t stack_size;
    void* stack_pointer;
    
    /* Scheduling */
    uint64_t timeslice;
    uint64_t runtime;
    uint32_t cpu_affinity;
    
    /* Synchronization */
    void* wait_queue;
    void* mutex_list;
    
    struct kos_thread* next;
} kos_thread_t;

/* Kernel namespace */
typedef struct kos_namespace {
    uint32_t id;
    uint32_t type;  /* PID, NET, MNT, UTS, IPC, USER, CGROUP */
    uint32_t ref_count;
    void* private_data;
} kos_namespace_t;

/* Control group */
typedef struct kos_cgroup {
    char name[256];
    uint32_t id;
    
    /* Resource limits */
    uint64_t cpu_shares;
    uint64_t memory_limit;
    uint64_t memory_soft_limit;
    uint32_t cpu_quota;
    uint32_t cpu_period;
    
    /* Statistics */
    uint64_t cpu_usage;
    uint64_t memory_usage;
    
    struct kos_cgroup* parent;
    struct kos_cgroup* children;
    struct kos_cgroup* sibling;
} kos_cgroup_t;

/* Kernel initialization */
int kos_kernel_init(void* boot_params);
void kos_kernel_start(void);
void kos_kernel_panic(const char* message);

/* Process management */
kos_process_t* kos_process_create(uint32_t ppid, const char* name);
int kos_process_destroy(uint32_t pid);
kos_process_t* kos_process_find(uint32_t pid);
int kos_process_exec(uint32_t pid, const char* path, char* const argv[], char* const envp[]);
int kos_process_fork(uint32_t ppid);
int kos_process_wait(uint32_t pid, int* status, int options);

/* Thread management */
kos_thread_t* kos_thread_create(uint32_t pid, void* (*entry)(void*), void* arg);
int kos_thread_destroy(uint32_t tid);
kos_thread_t* kos_thread_find(uint32_t tid);
void kos_thread_yield(void);
int kos_thread_sleep(uint64_t milliseconds);

/* Memory management */
void* kos_mem_alloc(size_t size);
void kos_mem_free(void* ptr);
void* kos_mem_realloc(void* ptr, size_t size);
int kos_mem_map(uint64_t vaddr, uint64_t paddr, size_t size, uint32_t flags);
int kos_mem_unmap(uint64_t vaddr, size_t size);
int kos_mem_protect(uint64_t vaddr, size_t size, uint32_t flags);

/* Scheduling */
void kos_scheduler_init(void);
void kos_scheduler_tick(void);
void kos_scheduler_schedule(void);
void kos_scheduler_add_thread(kos_thread_t* thread);
void kos_scheduler_remove_thread(kos_thread_t* thread);

/* System calls */
int64_t kos_syscall(uint32_t nr, uint64_t arg1, uint64_t arg2, uint64_t arg3, 
                    uint64_t arg4, uint64_t arg5, uint64_t arg6);

/* IPC */
int kos_ipc_send(uint32_t dest_pid, void* msg, size_t size);
int kos_ipc_recv(void* msg, size_t size, uint32_t* src_pid);
int kos_ipc_call(uint32_t dest_pid, void* msg, size_t msg_size, 
                 void* reply, size_t reply_size);

/* Synchronization */
void* kos_mutex_create(void);
int kos_mutex_lock(void* mutex);
int kos_mutex_trylock(void* mutex);
int kos_mutex_unlock(void* mutex);
void kos_mutex_destroy(void* mutex);

void* kos_semaphore_create(uint32_t initial);
int kos_semaphore_wait(void* sem);
int kos_semaphore_post(void* sem);
void kos_semaphore_destroy(void* sem);

/* Namespace management */
kos_namespace_t* kos_namespace_create(uint32_t type);
int kos_namespace_enter(kos_namespace_t* ns);
int kos_namespace_destroy(kos_namespace_t* ns);

/* Cgroup management */
kos_cgroup_t* kos_cgroup_create(const char* name, kos_cgroup_t* parent);
int kos_cgroup_destroy(kos_cgroup_t* cgroup);
int kos_cgroup_attach(kos_cgroup_t* cgroup, uint32_t pid);
int kos_cgroup_set_limit(kos_cgroup_t* cgroup, const char* resource, uint64_t limit);

/* Time management */
uint64_t kos_time_get_ticks(void);
uint64_t kos_time_get_unix(void);
void kos_time_delay(uint64_t microseconds);

/* Interrupt handling */
typedef void (*kos_irq_handler_t)(uint32_t irq, void* data);
int kos_irq_register(uint32_t irq, kos_irq_handler_t handler, void* data);
int kos_irq_unregister(uint32_t irq);
void kos_irq_enable(uint32_t irq);
void kos_irq_disable(uint32_t irq);

#ifdef __cplusplus
}
#endif

#endif /* KOS_KCORE_H */