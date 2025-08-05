/*
 * KOS Kernel Core Implementation
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <errno.h>
#include <signal.h>
#include <sys/mman.h>

/* Global kernel state */
static struct {
    bool initialized;
    uint64_t boot_time;
    uint32_t next_pid;
    uint32_t next_tid;
    kos_process_t* process_list;
    pthread_mutex_t proc_lock;
    pthread_mutex_t sched_lock;
    
    /* Scheduler queues */
    kos_thread_t* ready_queue;
    kos_thread_t* blocked_queue;
    kos_thread_t* current_thread;
    
    /* Statistics */
    uint64_t context_switches;
    uint64_t syscalls;
    uint64_t interrupts;
} kos_kernel = {0};

/* Initialize kernel */
int kos_kernel_init(void* boot_params) {
    if (kos_kernel.initialized) {
        return -1;
    }
    
    /* Delegate to comprehensive init system */
    extern int kos_kernel_init_full(void* boot_params);
    return kos_kernel_init_full(boot_params);
}

/* Start kernel main loop */
void kos_kernel_start(void) {
    if (!kos_kernel.initialized) {
        kos_kernel_panic("Kernel not initialized");
    }
    
    /* Main kernel loop */
    while (1) {
        /* Handle interrupts */
        /* Schedule threads */
        kos_scheduler_schedule();
        
        /* Handle timers */
        usleep(1000); /* 1ms tick */
        kos_scheduler_tick();
    }
}

/* Kernel panic - delegate to panic.c */
void kos_kernel_panic(const char* message) {
    extern void kos_kernel_panic_detailed(const char* message, const char* file, int line, const char* func);
    kos_kernel_panic_detailed(message, __FILE__, __LINE__, __func__);
}

/* Create new process */
kos_process_t* kos_process_create(uint32_t ppid, const char* name) {
    pthread_mutex_lock(&kos_kernel.proc_lock);
    
    kos_process_t* proc = calloc(1, sizeof(kos_process_t));
    if (!proc) {
        pthread_mutex_unlock(&kos_kernel.proc_lock);
        return NULL;
    }
    
    /* Initialize process */
    proc->pid = kos_kernel.next_pid++;
    proc->ppid = ppid;
    proc->state = PROC_STATE_NEW;
    proc->priority = 20; /* Default priority */
    proc->nice = 0;
    
    /* Set default UID/GID */
    proc->uid = getuid();
    proc->gid = getgid();
    
    /* Initialize memory */
    proc->brk = 0x400000; /* Default heap start */
    proc->stack_top = 0x7fff0000; /* Default stack top */
    
    /* Get current time */
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    proc->start_time = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    
    /* Find parent */
    if (ppid > 0) {
        kos_process_t* parent = kos_process_find(ppid);
        if (parent) {
            proc->parent = parent;
            
            /* Add to parent's children list */
            if (parent->children) {
                proc->sibling = parent->children;
            }
            parent->children = proc;
            
            /* Inherit namespace and cgroup */
            proc->ns = parent->ns;
            proc->cgroup = parent->cgroup;
        }
    }
    
    /* Add to global process list */
    proc->next = kos_kernel.process_list;
    kos_kernel.process_list = proc;
    
    /* Create main thread */
    kos_thread_t* main_thread = kos_thread_create(proc->pid, NULL, NULL);
    if (!main_thread) {
        /* Cleanup on failure */
        kos_kernel.process_list = proc->next;
        free(proc);
        pthread_mutex_unlock(&kos_kernel.proc_lock);
        return NULL;
    }
    
    proc->threads = main_thread;
    proc->thread_count = 1;
    proc->state = PROC_STATE_READY;
    
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    return proc;
}

/* Find process by PID */
kos_process_t* kos_process_find(uint32_t pid) {
    pthread_mutex_lock(&kos_kernel.proc_lock);
    
    kos_process_t* proc = kos_kernel.process_list;
    while (proc) {
        if (proc->pid == pid) {
            pthread_mutex_unlock(&kos_kernel.proc_lock);
            return proc;
        }
        proc = proc->next;
    }
    
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    return NULL;
}

/* Destroy process */
int kos_process_destroy(uint32_t pid) {
    pthread_mutex_lock(&kos_kernel.proc_lock);
    
    kos_process_t* proc = kos_kernel.process_list;
    kos_process_t* prev = NULL;
    
    while (proc) {
        if (proc->pid == pid) {
            /* Remove from list */
            if (prev) {
                prev->next = proc->next;
            } else {
                kos_kernel.process_list = proc->next;
            }
            
            /* Destroy all threads */
            kos_thread_t* thread = proc->threads;
            while (thread) {
                kos_thread_t* next = thread->next;
                kos_thread_destroy(thread->tid);
                thread = next;
            }
            
            /* Free memory regions */
            kos_mem_region_t* region = proc->mem_regions;
            while (region) {
                kos_mem_region_t* next = region->next;
                free(region);
                region = next;
            }
            
            /* Update parent's children list */
            if (proc->parent) {
                kos_process_t* child = proc->parent->children;
                kos_process_t* prev_child = NULL;
                
                while (child) {
                    if (child == proc) {
                        if (prev_child) {
                            prev_child->sibling = child->sibling;
                        } else {
                            proc->parent->children = child->sibling;
                        }
                        break;
                    }
                    prev_child = child;
                    child = child->sibling;
                }
            }
            
            free(proc);
            pthread_mutex_unlock(&kos_kernel.proc_lock);
            return 0;
        }
        prev = proc;
        proc = proc->next;
    }
    
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    return -ESRCH;
}

/* Create thread */
kos_thread_t* kos_thread_create(uint32_t pid, void* (*entry)(void*), void* arg) {
    kos_process_t* proc = kos_process_find(pid);
    if (!proc) {
        return NULL;
    }
    
    pthread_mutex_lock(&kos_kernel.sched_lock);
    
    kos_thread_t* thread = calloc(1, sizeof(kos_thread_t));
    if (!thread) {
        pthread_mutex_unlock(&kos_kernel.sched_lock);
        return NULL;
    }
    
    /* Initialize thread */
    thread->tid = kos_kernel.next_tid++;
    thread->pid = pid;
    thread->state = THREAD_STATE_NEW;
    thread->timeslice = 10; /* 10ms default timeslice */
    thread->cpu_affinity = 0xFFFFFFFF; /* All CPUs */
    
    /* Allocate stack */
    thread->stack_size = KOS_KERNEL_STACK;
    thread->stack_base = mmap(NULL, thread->stack_size, 
                             PROT_READ | PROT_WRITE,
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_STACK,
                             -1, 0);
    
    if (thread->stack_base == MAP_FAILED) {
        free(thread);
        pthread_mutex_unlock(&kos_kernel.sched_lock);
        return NULL;
    }
    
    /* Set stack pointer to top of stack */
    thread->stack_pointer = (char*)thread->stack_base + thread->stack_size;
    
    /* Add to process thread list */
    pthread_mutex_lock(&kos_kernel.proc_lock);
    thread->next = proc->threads;
    proc->threads = thread;
    proc->thread_count++;
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    
    /* Add to scheduler */
    thread->state = THREAD_STATE_READY;
    kos_scheduler_add_thread(thread);
    
    pthread_mutex_unlock(&kos_kernel.sched_lock);
    return thread;
}

/* Destroy thread */
int kos_thread_destroy(uint32_t tid) {
    pthread_mutex_lock(&kos_kernel.sched_lock);
    
    /* Remove from scheduler */
    kos_scheduler_remove_thread(kos_thread_find(tid));
    
    /* Find and destroy thread */
    pthread_mutex_lock(&kos_kernel.proc_lock);
    
    kos_process_t* proc = kos_kernel.process_list;
    while (proc) {
        kos_thread_t* thread = proc->threads;
        kos_thread_t* prev = NULL;
        
        while (thread) {
            if (thread->tid == tid) {
                /* Remove from list */
                if (prev) {
                    prev->next = thread->next;
                } else {
                    proc->threads = thread->next;
                }
                proc->thread_count--;
                
                /* Free stack */
                if (thread->stack_base) {
                    munmap(thread->stack_base, thread->stack_size);
                }
                
                free(thread);
                pthread_mutex_unlock(&kos_kernel.proc_lock);
                pthread_mutex_unlock(&kos_kernel.sched_lock);
                return 0;
            }
            prev = thread;
            thread = thread->next;
        }
        proc = proc->next;
    }
    
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    pthread_mutex_unlock(&kos_kernel.sched_lock);
    return -ESRCH;
}

/* Find thread */
kos_thread_t* kos_thread_find(uint32_t tid) {
    pthread_mutex_lock(&kos_kernel.proc_lock);
    
    kos_process_t* proc = kos_kernel.process_list;
    while (proc) {
        kos_thread_t* thread = proc->threads;
        while (thread) {
            if (thread->tid == tid) {
                pthread_mutex_unlock(&kos_kernel.proc_lock);
                return thread;
            }
            thread = thread->next;
        }
        proc = proc->next;
    }
    
    pthread_mutex_unlock(&kos_kernel.proc_lock);
    return NULL;
}

/* Memory allocation */
void* kos_mem_alloc(size_t size) {
    /* For now, use standard malloc */
    return malloc(size);
}

void kos_mem_free(void* ptr) {
    free(ptr);
}

void* kos_mem_realloc(void* ptr, size_t size) {
    return realloc(ptr, size);
}

/* Scheduler initialization */
void kos_scheduler_init(void) {
    kos_kernel.ready_queue = NULL;
    kos_kernel.blocked_queue = NULL;
    kos_kernel.current_thread = NULL;
}

/* Scheduler tick */
void kos_scheduler_tick(void) {
    pthread_mutex_lock(&kos_kernel.sched_lock);
    
    if (kos_kernel.current_thread) {
        kos_kernel.current_thread->runtime++;
        
        /* Check if timeslice expired */
        if (kos_kernel.current_thread->runtime >= kos_kernel.current_thread->timeslice) {
            /* Preempt current thread */
            kos_kernel.current_thread->state = THREAD_STATE_READY;
            kos_scheduler_add_thread(kos_kernel.current_thread);
            kos_kernel.current_thread = NULL;
        }
    }
    
    pthread_mutex_unlock(&kos_kernel.sched_lock);
}

/* Schedule next thread */
void kos_scheduler_schedule(void) {
    pthread_mutex_lock(&kos_kernel.sched_lock);
    
    /* If no current thread, pick one from ready queue */
    if (!kos_kernel.current_thread && kos_kernel.ready_queue) {
        kos_kernel.current_thread = kos_kernel.ready_queue;
        kos_kernel.ready_queue = kos_kernel.ready_queue->next;
        kos_kernel.current_thread->next = NULL;
        kos_kernel.current_thread->state = THREAD_STATE_RUNNING;
        kos_kernel.current_thread->runtime = 0;
        kos_kernel.context_switches++;
    }
    
    pthread_mutex_unlock(&kos_kernel.sched_lock);
}

/* Add thread to scheduler */
void kos_scheduler_add_thread(kos_thread_t* thread) {
    if (!thread) return;
    
    /* Add to end of ready queue */
    thread->next = NULL;
    
    if (!kos_kernel.ready_queue) {
        kos_kernel.ready_queue = thread;
    } else {
        kos_thread_t* last = kos_kernel.ready_queue;
        while (last->next) {
            last = last->next;
        }
        last->next = thread;
    }
}

/* Remove thread from scheduler */
void kos_scheduler_remove_thread(kos_thread_t* thread) {
    if (!thread) return;
    
    /* Remove from ready queue */
    kos_thread_t* current = kos_kernel.ready_queue;
    kos_thread_t* prev = NULL;
    
    while (current) {
        if (current == thread) {
            if (prev) {
                prev->next = current->next;
            } else {
                kos_kernel.ready_queue = current->next;
            }
            break;
        }
        prev = current;
        current = current->next;
    }
}

/* System call handler - delegate to syscall.c */
int64_t kos_syscall(uint32_t nr, uint64_t arg1, uint64_t arg2, uint64_t arg3,
                    uint64_t arg4, uint64_t arg5, uint64_t arg6) {
    kos_kernel.syscalls++;
    
    /* Delegate to main syscall handler */
    extern int64_t kos_syscall_dispatch(uint32_t nr, uint64_t arg1, uint64_t arg2, 
                                       uint64_t arg3, uint64_t arg4, uint64_t arg5, uint64_t arg6);
    return kos_syscall_dispatch(nr, arg1, arg2, arg3, arg4, arg5, arg6);
}

/* Get current time in ticks */
uint64_t kos_time_get_ticks(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* Get Unix timestamp */
uint64_t kos_time_get_unix(void) {
    return time(NULL);
}