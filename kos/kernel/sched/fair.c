#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/time.h>
#include "../sysctl.h"

/* Fair scheduling parameters */
#define SCHED_FEAT_GENTLE_FAIR_SLEEPERS     1
#define SCHED_FEAT_START_DEBIT              2
#define SCHED_FEAT_NEXT_BUDDY               4
#define SCHED_FEAT_LAST_BUDDY               8
#define SCHED_FEAT_CACHE_HOT_BUDDY          16
#define SCHED_FEAT_WAKEUP_PREEMPTION        32

/* Default feature flags */
static uint32_t sched_features = SCHED_FEAT_GENTLE_FAIR_SLEEPERS |
                                SCHED_FEAT_START_DEBIT |
                                SCHED_FEAT_WAKEUP_PREEMPTION;

/* Scheduling tunable parameters - now fetched from sysctl */
#define sysctl_sched_latency sysctl_get_sched_latency()
#define sysctl_sched_min_granularity sysctl_get_sched_min_granularity()
#define sysctl_sched_wakeup_granularity sysctl_get_sched_wakeup_granularity()
static uint32_t sysctl_sched_nr_migrate = 32;              /* Migration batch size */
static uint32_t sysctl_sched_time_avg = 1000;              /* Time averaging window */

/* Load tracking periods */
#define LOAD_AVG_PERIOD  32
#define LOAD_AVG_MAX     47742  /* Maximum load average */

/* Precomputed decay factors */
static const uint32_t runnable_avg_yN_inv[] = {
    0xffffffff, 0xfa83b2da, 0xf5257d14, 0xefe4b99b, 0xeac0c6e6, 0xe5b906e6,
    0xe0ccdeeb, 0xdbfbb796, 0xd744fcba, 0xd2a81d91, 0xce248c14, 0xc9b9bd85,
    0xc5672a10, 0xc12c4cc9, 0xbd08a439, 0xb8fbad5e, 0xb504f333, 0xb123f581,
    0xad583ee9, 0xa9a15ab4, 0xa5fed6a9, 0xa2704302, 0x9ef5325f, 0x9b8d39b9,
    0x9837f050, 0x94f4efa8, 0x91c3d373, 0x8ea4398a, 0x8b95c1e3, 0x88980e80,
    0x85aac367, 0x82cd8698,
};

/* Calculate decay factor */
static uint64_t decay_load(uint64_t val, uint64_t n) {
    if (n > LOAD_AVG_PERIOD * 63) {
        return 0;
    }
    
    /* Compute \Sum y^k for k=1..n */
    if (n >= LOAD_AVG_PERIOD) {
        val = (val * runnable_avg_yN_inv[LOAD_AVG_PERIOD - 1]) >> 32;
        n -= LOAD_AVG_PERIOD;
    }
    
    while (n > 0) {
        uint32_t idx = n < LOAD_AVG_PERIOD ? n - 1 : LOAD_AVG_PERIOD - 1;
        val = (val * runnable_avg_yN_inv[idx]) >> 32;
        n -= idx + 1;
    }
    
    return val;
}

/* Update entity load average */
static void update_entity_load_avg(struct sched_entity *se, int update_cfs_rq) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t now_us = now.tv_sec * 1000000 + now.tv_usec;
    uint64_t last_us = se->last_update_time.tv_sec * 1000000 + se->last_update_time.tv_usec;
    uint64_t delta_us = now_us - last_us;
    
    if (delta_us < 1000) { /* Less than 1ms, skip update */
        return;
    }
    
    /* Convert to 1024us periods */
    uint64_t periods = delta_us / 1024;
    if (periods == 0) {
        return;
    }
    
    /* Decay existing load */
    se->load_weight = decay_load(se->load_weight, periods);
    
    /* Add current contribution */
    uint64_t contrib = periods * 1024;
    se->load_weight += contrib;
    
    /* Clamp to maximum */
    if (se->load_weight > LOAD_AVG_MAX) {
        se->load_weight = LOAD_AVG_MAX;
    }
    
    se->last_update_time = now;
}

/* Calculate ideal time slice for entity */
static uint64_t sched_slice_fair(struct cfs_rq *cfs_rq, struct sched_entity *se) {
    uint64_t slice = sysctl_sched_latency;
    
    if (cfs_rq->nr_running > (sysctl_sched_latency / sysctl_sched_min_granularity)) {
        slice = sysctl_sched_min_granularity * cfs_rq->nr_running;
    }
    
    if (cfs_rq->load_weight > 0) {
        slice = slice * se->load_weight / cfs_rq->load_weight;
    }
    
    return slice;
}

/* Calculate weighted time delta */
static uint64_t calc_delta_fair(uint64_t delta, struct sched_entity *se) {
    if (se->load_weight == 1024) { /* Nice 0 */
        return delta;
    }
    
    return (delta * 1024) / se->load_weight;
}

/* Update current entity runtime */
static void update_curr_fair_entity(struct cfs_rq *cfs_rq, struct sched_entity *se) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t now_us = now.tv_sec * 1000000 + now.tv_usec;
    uint64_t last_us = se->last_update_time.tv_sec * 1000000 + se->last_update_time.tv_usec;
    uint64_t delta_exec = now_us - last_us;
    
    if (delta_exec == 0) {
        return;
    }
    
    se->sum_exec_runtime += delta_exec;
    se->last_update_time = now;
    
    /* Update vruntime */
    uint64_t vruntime_delta = calc_delta_fair(delta_exec, se);
    se->vruntime += vruntime_delta;
    
    /* Update min_vruntime */
    update_min_vruntime_fair(cfs_rq);
    
    /* Update load average */
    update_entity_load_avg(se, 1);
}

/* Forward declarations */
void update_min_vruntime_fair(struct cfs_rq *cfs_rq);

/* Update min_vruntime for CFS runqueue */
void update_min_vruntime_fair(struct cfs_rq *cfs_rq) {
    uint64_t vruntime = cfs_rq->min_vruntime;
    
    if (cfs_rq->rb_leftmost) {
        struct sched_entity *se = container_of(cfs_rq->rb_leftmost,
                                             struct sched_entity, run_node);
        
        if (cfs_rq->nr_running == 1) {
            vruntime = se->vruntime;
        } else {
            vruntime = (vruntime > se->vruntime) ? vruntime : se->vruntime;
        }
    }
    
    /* Ensure min_vruntime never goes backwards */
    cfs_rq->min_vruntime = (cfs_rq->min_vruntime > vruntime) ? 
                           cfs_rq->min_vruntime : vruntime;
}

/* Place sleeping task */
static void place_entity_fair(struct cfs_rq *cfs_rq, struct sched_entity *se, int initial) {
    uint64_t vruntime = cfs_rq->min_vruntime;
    
    if (initial && (sched_features & SCHED_FEAT_START_DEBIT)) {
        /* New tasks start with a slight penalty */
        vruntime += sysctl_sched_latency / 2;
    }
    
    /* Ensure we don't place task too far behind */
    if (!initial) {
        uint64_t thresh = sysctl_sched_latency;
        if (se->vruntime + thresh < vruntime) {
            se->vruntime = vruntime - thresh;
        }
    } else {
        se->vruntime = vruntime;
    }
}

/* Check if entity should preempt current */
static bool wakeup_preempt_entity(struct sched_entity *curr, struct sched_entity *se) {
    int64_t gran = sysctl_sched_wakeup_granularity;
    int64_t vdiff = curr->vruntime - se->vruntime;
    
    return vdiff > gran;
}

/* Select idle CPU for task */
static uint32_t select_idle_cpu_fair(struct task_struct *p) {
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        if (!(p->cpus_allowed & (1U << cpu))) {
            continue;
        }
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        if (rq->nr_running == 0 || rq->curr == rq->idle) {
            return cpu;
        }
    }
    
    return p->cpu; /* No idle CPU found */
}

/* Wake up task fairly */
void wake_up_new_task_fair(struct task_struct *p) {
    struct rq *rq = &kos_scheduler.runqueues[p->cpu];
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &p->se;
    
    /* Initialize scheduling entity */
    se->vruntime = 0;
    place_entity_fair(cfs_rq, se, 1);
    
    /* If we have a current task, use its vruntime as base */
    if (rq->curr && rq->curr->policy == SCHED_NORMAL) {
        struct sched_entity *curr_se = &rq->curr->se;
        if (se->vruntime < curr_se->vruntime) {
            se->vruntime = curr_se->vruntime;
        }
    }
    
    /* Start with current min_vruntime */
    if (se->vruntime < cfs_rq->min_vruntime) {
        se->vruntime = cfs_rq->min_vruntime;
    }
    
    enqueue_task_fair(rq, p);
    
    /* Check preemption */
    if (rq->curr && rq->curr->policy == SCHED_NORMAL) {
        if (wakeup_preempt_entity(&rq->curr->se, se)) {
            set_need_resched(rq->curr);
        }
    }
}

/* Yield current task */
void yield_task_fair(struct rq *rq) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &rq->curr->se;
    
    /* Update runtime */
    update_curr_fair_entity(cfs_rq, se);
    
    /* Set vruntime to right edge of tree */
    if (cfs_rq->rb_leftmost) {
        struct sched_entity *rightmost = se;
        struct rb_node *node = cfs_rq->tasks_timeline.rb_node;
        
        /* Find rightmost node */
        while (node) {
            struct sched_entity *entry = container_of(node, struct sched_entity, run_node);
            if (entry->vruntime > rightmost->vruntime) {
                rightmost = entry;
            }
            node = node->rb_right ? node->rb_right : node->rb_left;
        }
        
        se->vruntime = rightmost->vruntime + 1;
    }
    
    set_need_resched(rq->curr);
}

/* Task migration for load balancing */
static struct task_struct *pick_next_pushable_task_fair(struct rq *rq) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    
    if (!cfs_rq->rb_leftmost) {
        return NULL;
    }
    
    /* Find a task that can be migrated */
    struct rb_node *node = cfs_rq->rb_leftmost;
    while (node) {
        struct sched_entity *se = container_of(node, struct sched_entity, run_node);
        struct task_struct *task = task_of(se);
        
        /* Check if task can be migrated to other CPUs */
        uint32_t allowed_cpus = __builtin_popcount(task->cpus_allowed);
        if (allowed_cpus > 1) {
            return task;
        }
        
        node = rb_next(node);
    }
    
    return NULL;
}

/* Load balance between CPUs */
static int load_balance_fair(struct rq *this_rq, uint32_t this_cpu) {
    struct rq *busiest_rq = NULL;
    uint64_t max_load = 0;
    
    /* Find busiest CPU */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        if (cpu == this_cpu) {
            continue;
        }
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        if (rq->cfs.load_weight > max_load) {
            max_load = rq->cfs.load_weight;
            busiest_rq = rq;
        }
    }
    
    if (!busiest_rq || max_load <= this_rq->cfs.load_weight + 1024) {
        return 0; /* No imbalance */
    }
    
    /* Try to migrate tasks */
    uint32_t migrated = 0;
    uint32_t max_migrate = sysctl_sched_nr_migrate;
    
    while (migrated < max_migrate) {
        struct task_struct *p = pick_next_pushable_task_fair(busiest_rq);
        if (!p) {
            break;
        }
        
        /* Check CPU affinity */
        if (!(p->cpus_allowed & (1U << this_cpu))) {
            continue;
        }
        
        /* Migrate task */
        dequeue_task_fair(busiest_rq, p);
        p->cpu = this_cpu;
        enqueue_task_fair(this_rq, p);
        
        migrated++;
        
        /* Check if we've balanced enough */
        if (busiest_rq->cfs.load_weight <= this_rq->cfs.load_weight + 1024) {
            break;
        }
    }
    
    return migrated;
}

/* Periodic load balancing trigger */
void trigger_load_balance_fair(void) {
    static struct timeval last_balance = {0, 0};
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t elapsed_us = (now.tv_sec - last_balance.tv_sec) * 1000000 +
                         (now.tv_usec - last_balance.tv_usec);
    
    /* Balance every 100ms */
    if (elapsed_us < 100000) {
        return;
    }
    
    last_balance = now;
    
    /* Balance each CPU */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        load_balance_fair(rq, cpu);
    }
}

/* Calculate task's contribution to CPU load */
static uint64_t task_load_contrib(struct task_struct *task) {
    return task->se.load_weight;
}

/* Update CFS runqueue load */
static void update_cfs_rq_load_avg(struct cfs_rq *cfs_rq) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    /* Simple exponential moving average */
    uint64_t current_load = cfs_rq->load_weight;
    double alpha = 0.1; /* Smoothing factor */
    
    struct rq *rq = container_of(cfs_rq, struct rq, cfs);
    double time_delta = (now.tv_sec - rq->last_load_update.tv_sec) +
                       (now.tv_usec - rq->last_load_update.tv_usec) / 1000000.0;
    
    if (time_delta > 0.0) {
        double decay = exp(-alpha * time_delta);
        rq->load_avg_1 = decay * rq->load_avg_1 + (1.0 - decay) * current_load;
        rq->last_load_update = now;
    }
}

/* Bandwidth enforcement for CFS groups */
struct cfs_bandwidth {
    uint64_t period;        /* Period length in ns */
    uint64_t budget;        /* Budget per period in ns */
    uint64_t consumed;      /* Consumed time in current period */
    struct timeval period_start;
    bool throttled;
};

static struct cfs_bandwidth cfs_bandwidth = {
    .period = 100000000ULL,    /* 100ms */
    .budget = 50000000ULL,     /* 50ms (50% of CPU) */
    .consumed = 0,
    .throttled = false
};

/* Check CFS bandwidth */
static bool check_cfs_bandwidth(uint64_t delta_ns) {
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t period_elapsed = (now.tv_sec - cfs_bandwidth.period_start.tv_sec) * 1000000000ULL +
                             (now.tv_usec - cfs_bandwidth.period_start.tv_usec) * 1000ULL;
    
    /* Reset period if elapsed */
    if (period_elapsed >= cfs_bandwidth.period) {
        cfs_bandwidth.period_start = now;
        cfs_bandwidth.consumed = 0;
        cfs_bandwidth.throttled = false;
    }
    
    /* Check if adding delta would exceed budget */
    if (cfs_bandwidth.consumed + delta_ns > cfs_bandwidth.budget) {
        cfs_bandwidth.throttled = true;
        return false;
    }
    
    cfs_bandwidth.consumed += delta_ns;
    return true;
}

/* Entity group scheduling support */
struct sched_group_entity {
    struct sched_entity se;
    struct cfs_rq *my_q;        /* CFS runqueue for this group */
    struct cfs_rq *cfs_rq;      /* Parent CFS runqueue */
    struct task_group *tg;      /* Task group */
};

/* Task group structure */
struct task_group {
    struct cfs_rq **cfs_rq;     /* Per-CPU CFS runqueues */
    struct sched_group_entity **se; /* Per-CPU scheduling entities */
    uint64_t shares;            /* CPU shares for this group */
    uint32_t ref_count;         /* Reference count */
};

/* Initialize task group */
struct task_group *alloc_fair_sched_group(void) {
    struct task_group *tg = calloc(1, sizeof(struct task_group));
    if (!tg) {
        return NULL;
    }
    
    tg->cfs_rq = calloc(kos_scheduler.nr_cpus, sizeof(struct cfs_rq *));
    tg->se = calloc(kos_scheduler.nr_cpus, sizeof(struct sched_group_entity *));
    
    if (!tg->cfs_rq || !tg->se) {
        free(tg->cfs_rq);
        free(tg->se);
        free(tg);
        return NULL;
    }
    
    tg->shares = 1024; /* Default shares */
    tg->ref_count = 1;
    
    /* Initialize per-CPU structures */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        tg->cfs_rq[cpu] = calloc(1, sizeof(struct cfs_rq));
        tg->se[cpu] = calloc(1, sizeof(struct sched_group_entity));
        
        if (!tg->cfs_rq[cpu] || !tg->se[cpu]) {
            /* Cleanup on failure */
            for (uint32_t i = 0; i <= cpu; i++) {
                free(tg->cfs_rq[i]);
                free(tg->se[i]);
            }
            free(tg->cfs_rq);
            free(tg->se);
            free(tg);
            return NULL;
        }
        
        init_cfs_rq(tg->cfs_rq[cpu]);
        tg->se[cpu]->my_q = tg->cfs_rq[cpu];
        tg->se[cpu]->tg = tg;
    }
    
    return tg;
}

/* Destroy task group */
void free_fair_sched_group(struct task_group *tg) {
    if (!tg) {
        return;
    }
    
    tg->ref_count--;
    if (tg->ref_count > 0) {
        return;
    }
    
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        if (tg->cfs_rq[cpu]) {
            destroy_cfs_rq(tg->cfs_rq[cpu]);
            free(tg->cfs_rq[cpu]);
        }
        free(tg->se[cpu]);
    }
    
    free(tg->cfs_rq);
    free(tg->se);
    free(tg);
}

/* Print fair scheduling statistics */
void print_fair_sched_stats(void) {
    printf("\n=== Fair Scheduler Statistics ===\n");
    printf("Scheduler features: 0x%x\n", sched_features);
    printf("Target latency: %lu ns\n", sysctl_sched_latency);
    printf("Min granularity: %lu ns\n", sysctl_sched_min_granularity);
    printf("Wakeup granularity: %lu ns\n", sysctl_sched_wakeup_granularity);
    printf("Migration batch size: %u\n", sysctl_sched_nr_migrate);
    
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        struct cfs_rq *cfs_rq = &rq->cfs;
        
        printf("\nCPU %u Fair Stats:\n", cpu);
        printf("  Load weight: %lu\n", cfs_rq->load_weight);
        printf("  Min vruntime: %lu\n", cfs_rq->min_vruntime);
        printf("  Running tasks: %u\n", cfs_rq->nr_running);
        printf("  Load average: %.2f\n", rq->load_avg_1);
        
        if (cfs_rq->rb_leftmost) {
            struct sched_entity *se = container_of(cfs_rq->rb_leftmost,
                                                  struct sched_entity, run_node);
            printf("  Next task vruntime: %lu\n", se->vruntime);
        }
    }
    
    printf("\nCFS Bandwidth:\n");
    printf("  Period: %lu ns\n", cfs_bandwidth.period);
    printf("  Budget: %lu ns\n", cfs_bandwidth.budget);
    printf("  Consumed: %lu ns\n", cfs_bandwidth.consumed);
    printf("  Throttled: %s\n", cfs_bandwidth.throttled ? "yes" : "no");
    
    printf("================================\n\n");
}

/* Tune scheduling parameters */
void set_sched_latency(uint64_t latency_ns) {
    sysctl_sched_latency = latency_ns;
}

void set_sched_min_granularity(uint64_t granularity_ns) {
    sysctl_sched_min_granularity = granularity_ns;
}

void set_sched_wakeup_granularity(uint64_t granularity_ns) {
    sysctl_sched_wakeup_granularity = granularity_ns;
}

void set_sched_features(uint32_t features) {
    sched_features = features;
}

/* Get scheduling parameters */
uint64_t get_sched_latency(void) {
    return sysctl_sched_latency;
}

uint64_t get_sched_min_granularity(void) {
    return sysctl_sched_min_granularity;
}

uint64_t get_sched_wakeup_granularity(void) {
    return sysctl_sched_wakeup_granularity;
}

uint32_t get_sched_features(void) {
    return sched_features;
}