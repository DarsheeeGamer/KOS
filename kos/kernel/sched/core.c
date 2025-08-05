#define _POSIX_C_SOURCE 199309L
#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <sys/time.h>
#include <signal.h>
#include <math.h>
#include <stdint.h>
#include <limits.h>

/* Forward declarations */
void *scheduler_main_loop(void *arg);
static void update_load_average(struct rq *rq);
static bool need_resched_task(struct task_struct *task);
static struct task_struct *pick_next_task(struct rq *rq);

/* Global scheduler instance */
struct scheduler kos_scheduler;

/* Load weight table for nice values */
const uint32_t prio_to_weight[40] = {
    /* -20 */ 88761, 71755, 56483, 46273, 36291,
    /* -15 */ 29154, 23254, 18705, 14949, 11916,
    /* -10 */  9548,  7620,  6100,  4904,  3906,
    /*  -5 */  3121,  2501,  1991,  1586,  1277,
    /*   0 */  1024,   820,   655,   526,   423,
    /*   5 */   335,   272,   215,   172,   137,
    /*  10 */   110,    87,    70,    56,    45,
    /*  15 */    36,    29,    23,    18,    15
};

/* Inverse multiplication factors for load weights */
const uint32_t prio_to_wmult[40] = {
    /* -20 */ 48388, 59856, 76040, 92818, 118348,
    /* -15 */ 147320, 184698, 229616, 287308, 360437,
    /* -10 */ 449829, 563644, 704093, 875809, 1099582,
    /*  -5 */ 1376151, 1717300, 2157191, 2708050, 3363326,
    /*   0 */ 4194304, 5237765, 6557202, 8165337, 10153587,
    /*   5 */ 12820798, 15790321, 19976592, 24970740, 31350126,
    /*  10 */ 39045157, 49367440, 61356676, 76695844, 95443717,
    /*  15 */ 119304647, 148102320, 186737708, 238609294, 286331153
};

/* Initialize the scheduler */
int sched_init(uint32_t nr_cpus) {
    if (nr_cpus > MAX_CPUS) {
        fprintf(stderr, "sched_init: too many CPUs (%u > %u)\n", nr_cpus, MAX_CPUS);
        return -EINVAL;
    }
    
    memset(&kos_scheduler, 0, sizeof(kos_scheduler));
    kos_scheduler.nr_cpus = nr_cpus;
    kos_scheduler.load_balance_enabled = true;
    kos_scheduler.balance_interval = 100; /* 100ms */
    
    gettimeofday(&kos_scheduler.boot_time, NULL);
    gettimeofday(&kos_scheduler.last_balance, NULL);
    
    /* Initialize global scheduler lock */
    if (pthread_mutex_init(&kos_scheduler.lock, NULL) != 0) {
        fprintf(stderr, "sched_init: failed to initialize scheduler lock\n");
        return -ENOMEM;
    }
    
    /* Initialize per-CPU runqueues */
    for (uint32_t cpu = 0; cpu < nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        
        rq->cpu = cpu;
        rq->curr = NULL;
        rq->idle = NULL;
        rq->nr_switches = 0;
        rq->nr_running = 0;
        rq->load_weight = 0;
        rq->load_avg_1 = 0.0;
        rq->load_avg_5 = 0.0;
        rq->load_avg_15 = 0.0;
        gettimeofday(&rq->last_load_update, NULL);
        
        /* Initialize CFS runqueue */
        rq->cfs.tasks_timeline.rb_node = NULL;
        rq->cfs.rb_leftmost = NULL;
        rq->cfs.min_vruntime = 0;
        rq->cfs.nr_running = 0;
        rq->cfs.load_weight = 0;
        
        if (pthread_mutex_init(&rq->cfs.lock, NULL) != 0) {
            fprintf(stderr, "sched_init: failed to initialize CFS lock for CPU %u\n", cpu);
            return -ENOMEM;
        }
        
        /* Initialize RT runqueue */
        rq->rt.queue = calloc(100, sizeof(struct task_struct *)); /* Support 100 RT priorities */
        rq->rt.bitmap = calloc(4, sizeof(uint32_t)); /* 100 priorities / 32 bits */
        rq->rt.nr_running = 0;
        rq->rt.highest_prio = 100; /* Invalid priority initially */
        
        if (!rq->rt.queue || !rq->rt.bitmap) {
            fprintf(stderr, "sched_init: failed to allocate RT queues for CPU %u\n", cpu);
            return -ENOMEM;
        }
        
        if (pthread_mutex_init(&rq->rt.lock, NULL) != 0) {
            fprintf(stderr, "sched_init: failed to initialize RT lock for CPU %u\n", cpu);
            return -ENOMEM;
        }
        
        /* Initialize per-CPU runqueue lock */
        if (pthread_mutex_init(&rq->lock, NULL) != 0) {
            fprintf(stderr, "sched_init: failed to initialize runqueue lock for CPU %u\n", cpu);
            return -ENOMEM;
        }
        
        /* Create idle task for this CPU */
        rq->idle = create_task(0, "idle");
        if (!rq->idle) {
            fprintf(stderr, "sched_init: failed to create idle task for CPU %u\n", cpu);
            return -ENOMEM;
        }
        
        rq->idle->policy = SCHED_IDLE;
        rq->idle->cpu = cpu;
        rq->idle->state = TASK_RUNNING;
        rq->curr = rq->idle;
    }
    
    printf("KOS Scheduler initialized with %u CPUs\n", nr_cpus);
    return 0;
}

/* Start the scheduler */
void sched_start(void) {
    pthread_mutex_lock(&kos_scheduler.lock);
    
    if (kos_scheduler.running) {
        pthread_mutex_unlock(&kos_scheduler.lock);
        return;
    }
    
    kos_scheduler.running = true;
    
    /* Create scheduler thread */
    if (pthread_create(&kos_scheduler.scheduler_thread, NULL, 
                      scheduler_main_loop, NULL) != 0) {
        fprintf(stderr, "sched_start: failed to create scheduler thread\n");
        kos_scheduler.running = false;
        pthread_mutex_unlock(&kos_scheduler.lock);
        return;
    }
    
    pthread_mutex_unlock(&kos_scheduler.lock);
    printf("KOS Scheduler started\n");
}

/* Stop the scheduler */
void sched_stop(void) {
    pthread_mutex_lock(&kos_scheduler.lock);
    
    if (!kos_scheduler.running) {
        pthread_mutex_unlock(&kos_scheduler.lock);
        return;
    }
    
    kos_scheduler.running = false;
    pthread_mutex_unlock(&kos_scheduler.lock);
    
    /* Wait for scheduler thread to finish */
    pthread_join(kos_scheduler.scheduler_thread, NULL);
    
    printf("KOS Scheduler stopped\n");
}

/* Main scheduler loop */
void *scheduler_main_loop(void *arg) {
    (void)arg; /* Suppress unused parameter warning */
    struct timespec ts = {0, 1000000}; /* 1ms */
    
    while (kos_scheduler.running) {
        /* Schedule all CPUs */
        for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
            schedule_cpu(cpu);
        }
        
        /* Periodic load balancing */
        struct timeval now;
        gettimeofday(&now, NULL);
        
        uint64_t elapsed_ms = (now.tv_sec - kos_scheduler.last_balance.tv_sec) * 1000 +
                             (now.tv_usec - kos_scheduler.last_balance.tv_usec) / 1000;
        
        if (elapsed_ms >= kos_scheduler.balance_interval) {
            trigger_load_balance();
            kos_scheduler.last_balance = now;
        }
        
        /* Update scheduler tick */
        scheduler_tick();
        
        /* Sleep for 1ms */
        nanosleep(&ts, NULL);
    }
    
    return NULL;
}

/* Schedule a specific CPU */
void schedule_cpu(uint32_t cpu) {
    if (cpu >= kos_scheduler.nr_cpus) {
        return;
    }
    
    struct rq *rq = &kos_scheduler.runqueues[cpu];
    struct task_struct *prev, *next;
    
    pthread_mutex_lock(&rq->lock);
    
    prev = rq->curr;
    
    /* Update current task runtime */
    if (prev && prev != rq->idle) {
        update_curr_fair(rq);
        
        /* Check if task should be preempted */
        if (prev->state == TASK_RUNNING && need_resched_task(prev)) {
            /* Put task back on runqueue if still runnable */
            if (prev->policy == SCHED_NORMAL || prev->policy == SCHED_BATCH) {
                enqueue_task_fair(rq, prev);
            } else if (prev->policy == SCHED_FIFO || prev->policy == SCHED_RR) {
                enqueue_task_rt(rq, prev);
            }
        }
    }
    
    /* Pick next task to run */
    next = pick_next_task(rq);
    
    if (next && next != prev) {
        /* Context switch */
        context_switch(rq, prev, next);
        rq->curr = next;
        rq->nr_switches++;
        kos_scheduler.total_context_switches++;
    }
    
    pthread_mutex_unlock(&rq->lock);
}

/* Pick the next task to run */
static struct task_struct *pick_next_task(struct rq *rq) {
    struct task_struct *next;
    
    /* First try RT tasks */
    next = pick_next_task_rt(rq);
    if (next) {
        return next;
    }
    
    /* Then try CFS tasks */
    next = pick_next_task_fair(rq);
    if (next) {
        return next;
    }
    
    /* Fall back to idle task */
    return rq->idle;
}

/* Create a new task */
struct task_struct *create_task(uint32_t pid, const char *comm) {
    struct task_struct *task = calloc(1, sizeof(struct task_struct));
    if (!task) {
        return NULL;
    }
    
    task->pid = pid;
    task->tgid = pid;
    task->state = TASK_INTERRUPTIBLE;
    task->prio = 120; /* Nice 0 */
    task->static_prio = 120;
    task->normal_prio = 120;
    task->policy = SCHED_NORMAL;
    task->cpu = 0;
    task->cpus_allowed = (1ULL << kos_scheduler.nr_cpus) - 1; /* All CPUs allowed */
    task->usage = 1;
    
    /* Initialize scheduling entity */
    task->se.vruntime = 0;
    task->se.sum_exec_runtime = 0;
    task->se.prev_sum_exec_runtime = 0;
    task->se.load_weight = prio_to_weight[task->prio - 100];
    gettimeofday(&task->se.last_update_time, NULL);
    task->se.on_rq = false;
    
    /* Initialize RT scheduling entity */
    task->rt.next = NULL;
    task->rt.prev = NULL;
    task->rt.time_slice = 100; /* 100ms default time slice for RR */
    task->rt.timeout = 0;
    
    /* Copy command name */
    strncpy(task->comm, comm, sizeof(task->comm) - 1);
    task->comm[sizeof(task->comm) - 1] = '\0';
    
    /* Initialize timing */
    gettimeofday(&task->start_time, NULL);
    task->utime = 0;
    task->stime = 0;
    
    /* Initialize task lock */
    if (pthread_mutex_init(&task->lock, NULL) != 0) {
        free(task);
        return NULL;
    }
    
    return task;
}

/* Destroy a task */
void destroy_task(struct task_struct *task) {
    if (!task) {
        return;
    }
    
    /* Remove from any runqueues */
    if (task->se.on_rq) {
        struct rq *rq = &kos_scheduler.runqueues[task->cpu];
        if (task->policy == SCHED_NORMAL || task->policy == SCHED_BATCH) {
            dequeue_task_fair(rq, task);
        } else if (task->policy == SCHED_FIFO || task->policy == SCHED_RR) {
            dequeue_task_rt(rq, task);
        }
    }
    
    /* Cleanup */
    pthread_mutex_destroy(&task->lock);
    free(task->stack);
    free(task);
}

/* Wake up a process */
void wake_up_process(struct task_struct *task) {
    if (!task) {
        return;
    }
    
    pthread_mutex_lock(&task->lock);
    
    if (task->state != TASK_RUNNING) {
        task->state = TASK_RUNNING;
        
        /* Select CPU for the task */
        uint32_t cpu = select_task_rq(task);
        task->cpu = cpu;
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        
        /* Enqueue task based on scheduling policy */
        if (task->policy == SCHED_NORMAL || task->policy == SCHED_BATCH) {
            enqueue_task_fair(rq, task);
        } else if (task->policy == SCHED_FIFO || task->policy == SCHED_RR) {
            enqueue_task_rt(rq, task);
        }
    }
    
    pthread_mutex_unlock(&task->lock);
}

/* Set task state */
void set_task_state(struct task_struct *task, task_state_t state) {
    if (!task) {
        return;
    }
    
    pthread_mutex_lock(&task->lock);
    
    if (task->state != state) {
        task_state_t old_state = task->state;
        task->state = state;
        
        /* If task is no longer running, remove from runqueue */
        if (old_state == TASK_RUNNING && state != TASK_RUNNING) {
            struct rq *rq = &kos_scheduler.runqueues[task->cpu];
            if (task->policy == SCHED_NORMAL || task->policy == SCHED_BATCH) {
                dequeue_task_fair(rq, task);
            } else if (task->policy == SCHED_FIFO || task->policy == SCHED_RR) {
                dequeue_task_rt(rq, task);
            }
        }
        /* If task becomes running, add to runqueue */
        else if (old_state != TASK_RUNNING && state == TASK_RUNNING) {
            wake_up_process(task);
        }
    }
    
    pthread_mutex_unlock(&task->lock);
}

/* Set user nice value */
void set_user_nice(struct task_struct *task, int nice) {
    if (!task) {
        return;
    }
    
    nice = nice < MIN_NICE ? MIN_NICE : nice;
    nice = nice > MAX_NICE ? MAX_NICE : nice;
    
    pthread_mutex_lock(&task->lock);
    
    int old_prio __attribute__((unused)) = task->static_prio;
    task->static_prio = 120 + nice; /* Convert nice to priority */
    task->normal_prio = task->static_prio;
    task->prio = task->normal_prio;
    
    /* Update load weight */
    task->se.load_weight = prio_to_weight[task->prio - 100];
    
    /* If task is on runqueue, we need to requeue it */
    if (task->se.on_rq) {
        struct rq *rq = &kos_scheduler.runqueues[task->cpu];
        if (task->policy == SCHED_NORMAL || task->policy == SCHED_BATCH) {
            dequeue_task_fair(rq, task);
            enqueue_task_fair(rq, task);
        }
    }
    
    pthread_mutex_unlock(&task->lock);
}

/* Get task nice value */
int task_nice(const struct task_struct *task) {
    if (!task) {
        return 0;
    }
    
    return task->static_prio - 120;
}

/* Set task scheduling policy */
void set_task_policy(struct task_struct *task, uint32_t policy) {
    if (!task) {
        return;
    }
    
    pthread_mutex_lock(&task->lock);
    
    uint32_t old_policy = task->policy;
    task->policy = policy;
    
    /* Adjust priority based on policy */
    if (policy == SCHED_FIFO || policy == SCHED_RR) {
        /* RT policies have priorities 0-99 */
        if (task->prio >= 100) {
            task->prio = 50; /* Default RT priority */
        }
    } else {
        /* Normal policies have priorities 100-139 */
        if (task->prio < 100) {
            task->prio = 120; /* Default normal priority */
        }
    }
    
    /* If task is on runqueue, move it to appropriate queue */
    if (task->se.on_rq) {
        struct rq *rq = &kos_scheduler.runqueues[task->cpu];
        
        /* Remove from old queue */
        if (old_policy == SCHED_NORMAL || old_policy == SCHED_BATCH) {
            dequeue_task_fair(rq, task);
        } else if (old_policy == SCHED_FIFO || old_policy == SCHED_RR) {
            dequeue_task_rt(rq, task);
        }
        
        /* Add to new queue */
        if (policy == SCHED_NORMAL || policy == SCHED_BATCH) {
            enqueue_task_fair(rq, task);
        } else if (policy == SCHED_FIFO || policy == SCHED_RR) {
            enqueue_task_rt(rq, task);
        }
    }
    
    pthread_mutex_unlock(&task->lock);
}

/* Get current time in nanoseconds */
uint64_t sched_clock(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * NSEC_PER_SEC + ts.tv_nsec;
}

/* Get local CPU clock */
uint64_t local_clock(void) {
    return sched_clock();
}

/* Update runqueue clock */
void update_rq_clock(struct rq *rq) {
    /* For simplicity, we'll use system time */
    (void)rq; /* Unused parameter */
}

/* Scheduler tick function */
void scheduler_tick(void) {
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        struct task_struct *curr = rq->curr;
        
        if (curr && curr != rq->idle) {
            /* Update task runtime */
            if (curr->policy == SCHED_NORMAL || curr->policy == SCHED_BATCH) {
                task_tick_fair(rq, curr);
            } else if (curr->policy == SCHED_FIFO || curr->policy == SCHED_RR) {
                task_tick_rt(rq, curr);
            }
        }
        
        /* Update load averages */
        update_load_average(rq);
    }
}

/* Update load average for a runqueue */
static void update_load_average(struct rq *rq) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    double time_delta = (now.tv_sec - rq->last_load_update.tv_sec) +
                       (now.tv_usec - rq->last_load_update.tv_usec) / 1000000.0;
    
    if (time_delta > 0.0) {
        double exp_1 = exp(-time_delta / 60.0);    /* 1 minute */
        double exp_5 = exp(-time_delta / 300.0);   /* 5 minutes */
        double exp_15 = exp(-time_delta / 900.0);  /* 15 minutes */
        
        double current_load = (double)rq->nr_running;
        
        rq->load_avg_1 = exp_1 * rq->load_avg_1 + (1.0 - exp_1) * current_load;
        rq->load_avg_5 = exp_5 * rq->load_avg_5 + (1.0 - exp_5) * current_load;
        rq->load_avg_15 = exp_15 * rq->load_avg_15 + (1.0 - exp_15) * current_load;
        
        rq->last_load_update = now;
    }
}

/* Check if task needs to be rescheduled */
static bool need_resched_task(struct task_struct *task) {
    (void)task; /* Suppress unused parameter warning */
    /* For simplicity, always check if we should reschedule */
    return true;
}

/* Context switch between tasks */
void context_switch(struct rq *rq, struct task_struct *prev, struct task_struct *next) {
    /* In a real kernel, this would involve:
     * 1. Saving processor state (registers, etc.)
     * 2. Switching memory context (page tables)
     * 3. Switching kernel stack
     * 4. Restoring processor state for next task
     * 
     * For our simulation, we'll just track the switch
     */
    
    if (prev) {
        prev->stime++; /* Increment system time */
    }
    
    if (next) {
        next->utime++; /* Increment user time */
        clear_need_resched(next);
    }
    
    /* Update timing statistics */
    struct timeval now;
    gettimeofday(&now, NULL);
    
    if (prev && prev != rq->idle) {
        uint64_t runtime = (now.tv_sec - prev->se.last_update_time.tv_sec) * 1000000 +
                          (now.tv_usec - prev->se.last_update_time.tv_usec);
        prev->se.sum_exec_runtime += runtime;
    }
    
    if (next && next != rq->idle) {
        next->se.last_update_time = now;
    }
}

/* Preemption control functions */
void preempt_disable(void) {
    /* In a real kernel, this would disable preemption */
}

void preempt_enable(void) {
    /* In a real kernel, this would enable preemption and check for reschedule */
}

bool need_resched(void) {
    /* Check if current task needs to be rescheduled */
    return false; /* Simplified */
}

void set_need_resched(struct task_struct *task) {
    /* Set reschedule flag for task */
    (void)task; /* Unused parameter */
}

void clear_need_resched(struct task_struct *task) {
    /* Clear reschedule flag for task */
    (void)task; /* Unused parameter */
}

/* Print scheduler statistics */
void print_scheduler_stats(void) {
    printf("\n=== KOS Scheduler Statistics ===\n");
    printf("CPUs: %u\n", kos_scheduler.nr_cpus);
    printf("Total forks: %lu\n", kos_scheduler.total_forks);
    printf("Total context switches: %lu\n", kos_scheduler.total_context_switches);
    printf("Load balancing: %s\n", kos_scheduler.load_balance_enabled ? "enabled" : "disabled");
    
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        printf("\nCPU %u:\n", cpu);
        printf("  Running tasks: %lu\n", rq->nr_running);
        printf("  Context switches: %lu\n", rq->nr_switches);
        printf("  Load weight: %lu\n", rq->load_weight);
        printf("  Load avg (1/5/15): %.2f/%.2f/%.2f\n", 
               rq->load_avg_1, rq->load_avg_5, rq->load_avg_15);
        printf("  CFS tasks: %u (min_vruntime: %lu)\n", 
               rq->cfs.nr_running, rq->cfs.min_vruntime);
        printf("  RT tasks: %u (highest_prio: %u)\n", 
               rq->rt.nr_running, rq->rt.highest_prio);
    }
    printf("================================\n\n");
}

/* Select CPU for task */
uint32_t select_task_rq(struct task_struct *task) {
    uint32_t best_cpu = 0;
    uint64_t min_load = UINT64_MAX;
    
    /* Find CPU with minimum load that allows this task */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        /* Check CPU affinity */
        if (!(task->cpus_allowed & (1U << cpu))) {
            continue;
        }
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        uint64_t load = rq->load_weight;
        
        if (load < min_load) {
            min_load = load;
            best_cpu = cpu;
        }
    }
    
    return best_cpu;
}

/* Trigger load balancing across all CPUs */
void trigger_load_balance(void) {
    if (!kos_scheduler.load_balance_enabled) {
        return;
    }
    
    /* Simple load balancing algorithm */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        load_balance(cpu);
    }
}

/* Load balance for specific CPU */
void load_balance(uint32_t cpu) {
    if (cpu >= kos_scheduler.nr_cpus) {
        return;
    }
    
    struct rq *this_rq = &kos_scheduler.runqueues[cpu];
    
    /* Find most loaded CPU */
    struct rq *busiest_rq = NULL;
    uint64_t max_load = 0;
    
    for (uint32_t i = 0; i < kos_scheduler.nr_cpus; i++) {
        if (i == cpu) continue;
        
        struct rq *rq = &kos_scheduler.runqueues[i];
        if (rq->load_weight > max_load) {
            max_load = rq->load_weight;
            busiest_rq = rq;
        }
    }
    
    /* Check if load balancing is needed */
    if (!busiest_rq || max_load <= this_rq->load_weight + 1024) {
        return; /* No significant imbalance */
    }
    
    /* For simplicity, we just record that balancing occurred */
    /* In a real implementation, we would migrate tasks here */
}

/* Print task information */
void print_task_info(const struct task_struct *task) {
    if (!task) {
        return;
    }
    
    printf("Task PID=%u (%s):\n", task->pid, task->comm);
    printf("  State: %d, Policy: %u, Priority: %d\n", 
           task->state, task->policy, task->prio);
    printf("  CPU: %u, Affinity: 0x%x\n", task->cpu, task->cpus_allowed);
    printf("  VRuntime: %lu, Load Weight: %lu\n", 
           task->se.vruntime, task->se.load_weight);
    printf("  Runtime: %lu, User: %lu, System: %lu\n", 
           task->se.sum_exec_runtime, task->utime, task->stime);
}