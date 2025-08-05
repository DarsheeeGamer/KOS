#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

/* Forward declarations */
bool rt_task_throttled(struct task_struct *task);

/* RT scheduling parameters */
#define MAX_RT_PRIO     100
#define DEFAULT_RR_TIMESLICE_NS  100000000ULL  /* 100ms */
#define RT_BANDWIDTH_PERIOD_NS   1000000000ULL /* 1 second */
#define RT_BANDWIDTH_QUOTA_NS    950000000ULL  /* 95% of CPU time */

/* RT priority bitmap operations */
static inline void set_bit(uint32_t nr, uint32_t *bitmap) {
    bitmap[nr / 32] |= (1U << (nr % 32));
}

static inline void clear_bit(uint32_t nr, uint32_t *bitmap) {
    bitmap[nr / 32] &= ~(1U << (nr % 32));
}

static inline int test_bit(uint32_t nr, uint32_t *bitmap) {
    return (bitmap[nr / 32] & (1U << (nr % 32))) != 0;
}

/* Find first set bit */
static inline int find_first_bit(uint32_t *bitmap, int size) {
    for (int i = 0; i < (size + 31) / 32; i++) {
        if (bitmap[i]) {
            for (int j = 0; j < 32 && i * 32 + j < size; j++) {
                if (bitmap[i] & (1U << j)) {
                    return i * 32 + j;
                }
            }
        }
    }
    return size;
}

/* Initialize RT runqueue */
void init_rt_rq(struct rt_rq *rt_rq) {
    rt_rq->queue = calloc(MAX_RT_PRIO, sizeof(struct task_struct *));
    rt_rq->bitmap = calloc(4, sizeof(uint32_t)); /* MAX_RT_PRIO / 32 */
    rt_rq->nr_running = 0;
    rt_rq->highest_prio = MAX_RT_PRIO;
    pthread_mutex_init(&rt_rq->lock, NULL);
}

/* Destroy RT runqueue */
void destroy_rt_rq(struct rt_rq *rt_rq) {
    free(rt_rq->queue);
    free(rt_rq->bitmap);
    pthread_mutex_destroy(&rt_rq->lock);
}

/* Get RT priority from task */
static inline uint32_t task_rt_prio(struct task_struct *task) {
    return task->prio;
}

/* Add task to RT priority queue */
static void __enqueue_rt_entity(struct rt_rq *rt_rq, struct sched_rt_entity *rt_se) {
    struct task_struct *task = rt_task_of(rt_se);
    uint32_t prio = task_rt_prio(task);
    
    /* Add to priority queue */
    if (rt_rq->queue[prio]) {
        /* Add to end of list for this priority */
        rt_se->next = rt_rq->queue[prio];
        rt_se->prev = rt_rq->queue[prio]->rt.prev;
        rt_rq->queue[prio]->rt.prev->rt.next = task;
        rt_rq->queue[prio]->rt.prev = task;
    } else {
        /* First task at this priority */
        rt_rq->queue[prio] = task;
        rt_se->next = task;
        rt_se->prev = task;
        
        /* Set bit in priority bitmap */
        set_bit(prio, rt_rq->bitmap);
        
        /* Update highest priority */
        if (prio < rt_rq->highest_prio) {
            rt_rq->highest_prio = prio;
        }
    }
}

/* Remove task from RT priority queue */
static void __dequeue_rt_entity(struct rt_rq *rt_rq, struct sched_rt_entity *rt_se) {
    struct task_struct *task = rt_task_of(rt_se);
    uint32_t prio = task_rt_prio(task);
    
    if (rt_se->next == task) {
        /* Only task at this priority */
        rt_rq->queue[prio] = NULL;
        clear_bit(prio, rt_rq->bitmap);
        
        /* Update highest priority */
        rt_rq->highest_prio = find_first_bit(rt_rq->bitmap, MAX_RT_PRIO);
    } else {
        /* Remove from circular list */
        rt_se->prev->rt.next = rt_se->next;
        rt_se->next->rt.prev = rt_se->prev;
        
        /* Update queue head if necessary */
        if (rt_rq->queue[prio] == task) {
            rt_rq->queue[prio] = rt_se->next;
        }
    }
    
    rt_se->next = NULL;
    rt_se->prev = NULL;
}

/* Enqueue RT task */
void enqueue_task_rt(struct rq *rq, struct task_struct *task) {
    struct rt_rq *rt_rq = &rq->rt;
    struct sched_rt_entity *rt_se = &task->rt;
    
    pthread_mutex_lock(&rt_rq->lock);
    
    /* Check if already on runqueue */
    if (rt_se->next) {
        pthread_mutex_unlock(&rt_rq->lock);
        return;
    }
    
    /* Initialize RT entity if needed */
    if (task->policy == SCHED_RR && rt_se->time_slice == 0) {
        rt_se->time_slice = DEFAULT_RR_TIMESLICE_NS / 1000000; /* Convert to ms */
    }
    
    /* Add to RT runqueue */
    __enqueue_rt_entity(rt_rq, rt_se);
    rt_rq->nr_running++;
    rq->nr_running++;
    
    pthread_mutex_unlock(&rt_rq->lock);
}

/* Dequeue RT task */
void dequeue_task_rt(struct rq *rq, struct task_struct *task) {
    struct rt_rq *rt_rq = &rq->rt;
    struct sched_rt_entity *rt_se = &task->rt;
    
    pthread_mutex_lock(&rt_rq->lock);
    
    /* Check if on runqueue */
    if (!rt_se->next) {
        pthread_mutex_unlock(&rt_rq->lock);
        return;
    }
    
    /* Remove from RT runqueue */
    __dequeue_rt_entity(rt_rq, rt_se);
    rt_rq->nr_running--;
    rq->nr_running--;
    
    pthread_mutex_unlock(&rt_rq->lock);
}

/* Pick next RT task */
struct task_struct *pick_next_task_rt(struct rq *rq) {
    struct rt_rq *rt_rq = &rq->rt;
    struct task_struct *next = NULL;
    
    pthread_mutex_lock(&rt_rq->lock);
    
    if (rt_rq->highest_prio < MAX_RT_PRIO) {
        next = rt_rq->queue[rt_rq->highest_prio];
        
        if (next) {
            /* For Round Robin, move to end of queue */
            if (next->policy == SCHED_RR && next->rt.next != next) {
                rt_rq->queue[rt_rq->highest_prio] = next->rt.next;
            }
            
            /* Don't dequeue yet - will be done when task yields or is preempted */
        }
    }
    
    pthread_mutex_unlock(&rt_rq->lock);
    return next;
}

/* Handle RT task tick */
void task_tick_rt(struct rq *rq, struct task_struct *curr) {
    struct sched_rt_entity *rt_se = &curr->rt;
    
    /* Update runtime */
    rt_se->timeout++;
    
    /* Check Round Robin time slice */
    if (curr->policy == SCHED_RR) {
        if (rt_se->timeout >= rt_se->time_slice) {
            rt_se->timeout = 0;
            set_need_resched(curr);
            
            /* Move to end of priority queue */
            struct rt_rq *rt_rq = &rq->rt;
            pthread_mutex_lock(&rt_rq->lock);
            
            if (rt_se->next != curr && rt_rq->queue[task_rt_prio(curr)] == curr) {
                rt_rq->queue[task_rt_prio(curr)] = rt_se->next;
            }
            
            pthread_mutex_unlock(&rt_rq->lock);
        }
    }
    
    /* RT bandwidth throttling check would go here */
    /* if (rt_task_throttled(curr)) {
        set_need_resched(curr);
    } */
}

/* Check if RT task should preempt current */
void check_preempt_curr_rt(struct rq *rq, struct task_struct *p, int flags) {
    (void)flags; /* Suppress unused parameter warning */
    if (p->prio < rq->curr->prio) {
        set_need_resched(rq->curr);
    }
}

/* Select CPU for RT task */
uint32_t select_task_rq_rt(struct task_struct *p, int prev_cpu, int sd_flag, int wake_flags) {
    (void)prev_cpu; (void)sd_flag; (void)wake_flags; /* Suppress unused parameter warnings */
    uint32_t best_cpu = 0;
    uint32_t min_rt_tasks = UINT32_MAX;
    
    /* Find CPU with fewest RT tasks */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        /* Check CPU affinity */
        if (!(p->cpus_allowed & (1U << cpu))) {
            continue;
        }
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        uint32_t rt_tasks = rq->rt.nr_running;
        
        if (rt_tasks < min_rt_tasks) {
            min_rt_tasks = rt_tasks;
            best_cpu = cpu;
        }
    }
    
    return best_cpu;
}

/* RT task fork handling */
void task_fork_rt(struct task_struct *p) {
    struct sched_rt_entity *rt_se = &p->rt;
    
    /* Initialize RT scheduling entity */
    rt_se->next = NULL;
    rt_se->prev = NULL;
    rt_se->timeout = 0;
    
    if (p->policy == SCHED_RR) {
        rt_se->time_slice = DEFAULT_RR_TIMESLICE_NS / 1000000; /* Convert to ms */
    } else {
        rt_se->time_slice = 0; /* FIFO has no time slice */
    }
}

/* RT bandwidth control */
struct rt_bandwidth {
    uint64_t rt_period;   /* Period length in ns */
    uint64_t rt_runtime;  /* Runtime budget in ns */
    uint64_t rt_time;     /* Current runtime usage */
    struct timeval period_start;
};

static struct rt_bandwidth rt_bandwidth = {
    .rt_period = RT_BANDWIDTH_PERIOD_NS,
    .rt_runtime = RT_BANDWIDTH_QUOTA_NS,
    .rt_time = 0
};

/* Initialize RT bandwidth */
void init_rt_bandwidth(void) {
    gettimeofday(&rt_bandwidth.period_start, NULL);
    rt_bandwidth.rt_time = 0;
}

/* Update RT bandwidth usage */
void update_rt_bandwidth(uint64_t delta_ns) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t period_elapsed = (now.tv_sec - rt_bandwidth.period_start.tv_sec) * NSEC_PER_SEC +
                             (now.tv_usec - rt_bandwidth.period_start.tv_usec) * 1000;
    
    /* Reset period if elapsed */
    if (period_elapsed >= rt_bandwidth.rt_period) {
        rt_bandwidth.period_start = now;
        rt_bandwidth.rt_time = 0;
    }
    
    rt_bandwidth.rt_time += delta_ns;
}

/* Check if RT tasks are throttled */
bool rt_task_throttled(struct task_struct *task) {
    if (task->policy != SCHED_FIFO && task->policy != SCHED_RR) {
        return false;
    }
    
    return rt_bandwidth.rt_time >= rt_bandwidth.rt_runtime;
}

/* Set RT throttling */
void set_rt_throttled(struct rq *rq, bool throttled) {
    /* Mark RT runqueue as throttled */
    (void)rq;
    (void)throttled;
    /* Implementation would set throttling flag */
}

/* RT load balancing */
struct task_struct *pick_highest_prio_rt_task(struct rq *rq) {
    struct rt_rq *rt_rq = &rq->rt;
    
    if (rt_rq->highest_prio < MAX_RT_PRIO) {
        return rt_rq->queue[rt_rq->highest_prio];
    }
    
    return NULL;
}

/* Push RT task to another CPU */
bool push_rt_task(struct rq *rq) {
    struct task_struct *next_task = pick_highest_prio_rt_task(rq);
    
    if (!next_task) {
        return false;
    }
    
    /* Find a CPU with lower priority RT task or no RT tasks */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        if (cpu == rq->cpu) {
            continue;
        }
        
        /* Check CPU affinity */
        if (!(next_task->cpus_allowed & (1U << cpu))) {
            continue;
        }
        
        struct rq *target_rq = &kos_scheduler.runqueues[cpu];
        
        /* Check if target CPU can run this task */
        if (target_rq->rt.highest_prio > (uint32_t)next_task->prio || 
            target_rq->rt.nr_running == 0) {
            
            /* Migrate task */
            dequeue_task_rt(rq, next_task);
            next_task->cpu = cpu;
            enqueue_task_rt(target_rq, next_task);
            
            return true;
        }
    }
    
    return false;
}

/* Pull RT task from another CPU */
bool pull_rt_task(struct rq *rq) {
    struct task_struct *highest_task = NULL;
    struct rq *src_rq = NULL;
    uint32_t highest_prio = MAX_RT_PRIO;
    
    /* Find highest priority RT task on other CPUs */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        if (cpu == rq->cpu) {
            continue;
        }
        
        struct rq *other_rq = &kos_scheduler.runqueues[cpu];
        struct task_struct *task = pick_highest_prio_rt_task(other_rq);
        
        if (task && (uint32_t)task->prio < highest_prio) {
            /* Check CPU affinity */
            if (task->cpus_allowed & (1U << rq->cpu)) {
                highest_task = task;
                highest_prio = task->prio;
                src_rq = other_rq;
            }
        }
    }
    
    /* Migrate highest priority task if found */
    if (highest_task && (rq->rt.highest_prio > highest_prio || rq->rt.nr_running == 0)) {
        dequeue_task_rt(src_rq, highest_task);
        highest_task->cpu = rq->cpu;
        enqueue_task_rt(rq, highest_task);
        
        return true;
    }
    
    return false;
}

/* RT scheduling class operations */
void switched_to_rt(struct rq *rq, struct task_struct *p) {
    /* Task switched to RT class */
    if (p->state == TASK_RUNNING && p != rq->curr) {
        if (p->prio < rq->curr->prio) {
            set_need_resched(rq->curr);
        }
    }
}

void switched_from_rt(struct rq *rq, struct task_struct *p) {
    /* Task switched from RT class */
    (void)rq;
    (void)p;
    /* Cleanup RT specific state if needed */
}

void prio_changed_rt(struct rq *rq, struct task_struct *p, int oldprio) {
    /* RT task priority changed */
    if (p->state == TASK_RUNNING) {
        if (p->prio < rq->curr->prio) {
            set_need_resched(rq->curr);
        } else if (p == rq->curr && p->prio > oldprio) {
            /* Current task priority decreased, check for preemption */
            struct task_struct *next = pick_highest_prio_rt_task(rq);
            if (next && next->prio < p->prio) {
                set_need_resched(p);
            }
        }
    }
}

/* RT statistics */
void print_rt_rq_stats(struct rt_rq *rt_rq, uint32_t cpu) {
    printf("RT RQ (CPU %u):\n", cpu);
    printf("  Tasks: %u\n", rt_rq->nr_running);
    printf("  Highest priority: %u\n", rt_rq->highest_prio);
    
    /* Print priority distribution */
    printf("  Priority distribution:\n");
    for (uint32_t prio = 0; prio < MAX_RT_PRIO; prio++) {
        if (test_bit(prio, rt_rq->bitmap)) {
            uint32_t count = 0;
            struct task_struct *task = rt_rq->queue[prio];
            struct task_struct *start = task;
            
            do {
                count++;
                task = task->rt.next;
            } while (task != start);
            
            printf("    Priority %u: %u tasks\n", prio, count);
        }
    }
}

/* RT debugging */
bool rt_rq_is_sane(struct rt_rq *rt_rq) {
    /* Basic sanity checks */
    if (rt_rq->nr_running == 0 && rt_rq->highest_prio < MAX_RT_PRIO) {
        return false;
    }
    
    if (rt_rq->nr_running > 0 && rt_rq->highest_prio >= MAX_RT_PRIO) {
        return false;
    }
    
    /* Check bitmap consistency */
    for (uint32_t prio = 0; prio < MAX_RT_PRIO; prio++) {
        bool has_bit = test_bit(prio, rt_rq->bitmap);
        bool has_queue = (rt_rq->queue[prio] != NULL);
        
        if (has_bit != has_queue) {
            return false;
        }
    }
    
    return true;
}

/* Get RT task count at priority */
uint32_t rt_rq_count_at_prio(struct rt_rq *rt_rq, uint32_t prio) {
    if (prio >= MAX_RT_PRIO || !test_bit(prio, rt_rq->bitmap)) {
        return 0;
    }
    
    uint32_t count = 0;
    struct task_struct *task = rt_rq->queue[prio];
    struct task_struct *start = task;
    
    do {
        count++;
        task = task->rt.next;
    } while (task != start);
    
    return count;
}