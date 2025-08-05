#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/time.h>

/* CFS parameters */
#define SCHED_LATENCY_NS    6000000ULL      /* 6ms target latency */
#define MIN_GRANULARITY_NS  1500000ULL      /* 1.5ms minimum granularity */
#define WAKEUP_GRANULARITY_NS 2000000ULL    /* 2ms wakeup granularity */

/* Red-Black tree operations for CFS */

/* Left rotate */
static void rb_rotate_left(struct rb_node *node, struct rb_root *root) {
    struct rb_node *right = node->rb_right;
    
    node->rb_right = right->rb_left;
    if (right->rb_left) {
        right->rb_left->rb_parent = node;
    }
    
    right->rb_parent = node->rb_parent;
    if (!node->rb_parent) {
        root->rb_node = right;
    } else if (node == node->rb_parent->rb_left) {
        node->rb_parent->rb_left = right;
    } else {
        node->rb_parent->rb_right = right;
    }
    
    right->rb_left = node;
    node->rb_parent = right;
}

/* Right rotate */
static void rb_rotate_right(struct rb_node *node, struct rb_root *root) {
    struct rb_node *left = node->rb_left;
    
    node->rb_left = left->rb_right;
    if (left->rb_right) {
        left->rb_right->rb_parent = node;
    }
    
    left->rb_parent = node->rb_parent;
    if (!node->rb_parent) {
        root->rb_node = left;
    } else if (node == node->rb_parent->rb_right) {
        node->rb_parent->rb_right = left;
    } else {
        node->rb_parent->rb_left = left;
    }
    
    left->rb_right = node;
    node->rb_parent = left;
}

/* Insert and rebalance */
void rb_insert_color(struct rb_node *node, struct rb_root *root) {
    struct rb_node *parent, *gparent;
    
    while ((parent = node->rb_parent) && parent->rb_color == RB_RED) {
        gparent = parent->rb_parent;
        
        if (parent == gparent->rb_left) {
            struct rb_node *uncle = gparent->rb_right;
            
            if (uncle && uncle->rb_color == RB_RED) {
                uncle->rb_color = RB_BLACK;
                parent->rb_color = RB_BLACK;
                gparent->rb_color = RB_RED;
                node = gparent;
                continue;
            }
            
            if (parent->rb_right == node) {
                rb_rotate_left(parent, root);
                struct rb_node *tmp = parent;
                parent = node;
                node = tmp;
            }
            
            parent->rb_color = RB_BLACK;
            gparent->rb_color = RB_RED;
            rb_rotate_right(gparent, root);
        } else {
            struct rb_node *uncle = gparent->rb_left;
            
            if (uncle && uncle->rb_color == RB_RED) {
                uncle->rb_color = RB_BLACK;
                parent->rb_color = RB_BLACK;
                gparent->rb_color = RB_RED;
                node = gparent;
                continue;
            }
            
            if (parent->rb_left == node) {
                rb_rotate_right(parent, root);
                struct rb_node *tmp = parent;
                parent = node;
                node = tmp;
            }
            
            parent->rb_color = RB_BLACK;
            gparent->rb_color = RB_RED;
            rb_rotate_left(gparent, root);
        }
    }
    
    root->rb_node->rb_color = RB_BLACK;
}

/* Remove and rebalance */
void rb_erase(struct rb_node *node, struct rb_root *root) {
    struct rb_node *child, *parent;
    rb_color_t color;
    
    if (!node->rb_left) {
        child = node->rb_right;
    } else if (!node->rb_right) {
        child = node->rb_left;
    } else {
        struct rb_node *old = node, *left;
        
        node = node->rb_right;
        while ((left = node->rb_left) != NULL) {
            node = left;
        }
        
        if (old->rb_parent) {
            if (old->rb_parent->rb_left == old) {
                old->rb_parent->rb_left = node;
            } else {
                old->rb_parent->rb_right = node;
            }
        } else {
            root->rb_node = node;
        }
        
        child = node->rb_right;
        parent = node->rb_parent;
        color = node->rb_color;
        
        if (parent == old) {
            parent = node;
        } else {
            if (child) {
                child->rb_parent = parent;
            }
            parent->rb_left = child;
            
            node->rb_right = old->rb_right;
            old->rb_right->rb_parent = node;
        }
        
        node->rb_parent = old->rb_parent;
        node->rb_color = old->rb_color;
        node->rb_left = old->rb_left;
        old->rb_left->rb_parent = node;
        
        goto color_fixup;
    }
    
    parent = node->rb_parent;
    color = node->rb_color;
    
    if (child) {
        child->rb_parent = parent;
    }
    
    if (parent) {
        if (parent->rb_left == node) {
            parent->rb_left = child;
        } else {
            parent->rb_right = child;
        }
    } else {
        root->rb_node = child;
    }
    
color_fixup:
    if (color == RB_BLACK) {
        /* Fixup tree after black node removal */
        while ((!child || child->rb_color == RB_BLACK) && child != root->rb_node) {
            if (parent->rb_left == child) {
                struct rb_node *other = parent->rb_right;
                
                if (other->rb_color == RB_RED) {
                    other->rb_color = RB_BLACK;
                    parent->rb_color = RB_RED;
                    rb_rotate_left(parent, root);
                    other = parent->rb_right;
                }
                
                if ((!other->rb_left || other->rb_left->rb_color == RB_BLACK) &&
                    (!other->rb_right || other->rb_right->rb_color == RB_BLACK)) {
                    other->rb_color = RB_RED;
                    child = parent;
                    parent = child->rb_parent;
                } else {
                    if (!other->rb_right || other->rb_right->rb_color == RB_BLACK) {
                        other->rb_left->rb_color = RB_BLACK;
                        other->rb_color = RB_RED;
                        rb_rotate_right(other, root);
                        other = parent->rb_right;
                    }
                    
                    other->rb_color = parent->rb_color;
                    parent->rb_color = RB_BLACK;
                    other->rb_right->rb_color = RB_BLACK;
                    rb_rotate_left(parent, root);
                    child = root->rb_node;
                    break;
                }
            } else {
                struct rb_node *other = parent->rb_left;
                
                if (other->rb_color == RB_RED) {
                    other->rb_color = RB_BLACK;
                    parent->rb_color = RB_RED;
                    rb_rotate_right(parent, root);
                    other = parent->rb_left;
                }
                
                if ((!other->rb_left || other->rb_left->rb_color == RB_BLACK) &&
                    (!other->rb_right || other->rb_right->rb_color == RB_BLACK)) {
                    other->rb_color = RB_RED;
                    child = parent;
                    parent = child->rb_parent;
                } else {
                    if (!other->rb_left || other->rb_left->rb_color == RB_BLACK) {
                        other->rb_right->rb_color = RB_BLACK;
                        other->rb_color = RB_RED;
                        rb_rotate_left(other, root);
                        other = parent->rb_left;
                    }
                    
                    other->rb_color = parent->rb_color;
                    parent->rb_color = RB_BLACK;
                    other->rb_left->rb_color = RB_BLACK;
                    rb_rotate_right(parent, root);
                    child = root->rb_node;
                    break;
                }
            }
        }
        
        if (child) {
            child->rb_color = RB_BLACK;
        }
    }
}

/* Find first (leftmost) node */
struct rb_node *rb_first(const struct rb_root *root) {
    struct rb_node *n = root->rb_node;
    
    if (!n) {
        return NULL;
    }
    
    while (n->rb_left) {
        n = n->rb_left;
    }
    
    return n;
}

/* Find next node */
struct rb_node *rb_next(const struct rb_node *node) {
    if (!node) {
        return NULL;
    }
    
    if (node->rb_right) {
        node = node->rb_right;
        while (node->rb_left) {
            node = node->rb_left;
        }
        return (struct rb_node *)node;
    }
    
    while (node->rb_parent && node == node->rb_parent->rb_right) {
        node = node->rb_parent;
    }
    
    return node->rb_parent;
}

/* CFS specific functions */

/* Calculate time slice for a task */
static uint64_t sched_slice(struct cfs_rq *cfs_rq, struct sched_entity *se) {
    uint64_t slice = SCHED_LATENCY_NS;
    
    if (cfs_rq->nr_running > 1) {
        slice = SCHED_LATENCY_NS * se->load_weight / cfs_rq->load_weight;
        if (slice < MIN_GRANULARITY_NS) {
            slice = MIN_GRANULARITY_NS;
        }
    }
    
    return slice;
}

/* Update current task runtime */
void update_curr_fair(struct rq *rq) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct task_struct *curr = rq->curr;
    
    if (!curr || curr->policy != SCHED_NORMAL) {
        return;
    }
    
    struct sched_entity *se = &curr->se;
    struct timeval now;
    gettimeofday(&now, NULL);
    
    uint64_t delta_exec = (now.tv_sec - se->last_update_time.tv_sec) * 1000000 +
                         (now.tv_usec - se->last_update_time.tv_usec);
    
    if (delta_exec > 0) {
        se->sum_exec_runtime += delta_exec;
        
        /* Update vruntime */
        uint64_t vruntime_delta = delta_exec * 1024 / se->load_weight;
        se->vruntime += vruntime_delta;
        
        /* Update min_vruntime */
        if (cfs_rq->nr_running == 1) {
            cfs_rq->min_vruntime = se->vruntime;
        } else {
            cfs_rq->min_vruntime = (cfs_rq->min_vruntime > se->vruntime) ?
                                   cfs_rq->min_vruntime : se->vruntime;
        }
        
        se->last_update_time = now;
    }
}

/* Place new task in CFS timeline */
static void place_entity(struct cfs_rq *cfs_rq, struct sched_entity *se, int initial) {
    uint64_t vruntime = cfs_rq->min_vruntime;
    
    if (!initial) {
        /* Existing task - use current min_vruntime */
        se->vruntime = vruntime;
    } else {
        /* New task - give it a slight boost to prevent starvation */
        if (vruntime >= (SCHED_LATENCY_NS / 2)) {
            se->vruntime = vruntime - (SCHED_LATENCY_NS / 2);
        } else {
            se->vruntime = 0;
        }
    }
}

/* Insert task into CFS red-black tree */
static void __enqueue_entity(struct cfs_rq *cfs_rq, struct sched_entity *se) {
    struct rb_node **link = &cfs_rq->tasks_timeline.rb_node;
    struct rb_node *parent = NULL;
    struct sched_entity *entry;
    int leftmost = 1;
    
    /* Find the right place in the tree */
    while (*link) {
        parent = *link;
        entry = container_of(parent, struct sched_entity, run_node);
        
        if (se->vruntime < entry->vruntime) {
            link = &parent->rb_left;
        } else {
            link = &parent->rb_right;
            leftmost = 0;
        }
    }
    
    /* Maintain leftmost pointer */
    if (leftmost) {
        cfs_rq->rb_leftmost = &se->run_node;
    }
    
    /* Insert and rebalance */
    se->run_node.rb_parent = parent;
    se->run_node.rb_left = NULL;
    se->run_node.rb_right = NULL;
    se->run_node.rb_color = RB_RED;
    *link = &se->run_node;
    
    rb_insert_color(&se->run_node, &cfs_rq->tasks_timeline);
}

/* Remove task from CFS red-black tree */
static void __dequeue_entity(struct cfs_rq *cfs_rq, struct sched_entity *se) {
    if (cfs_rq->rb_leftmost == &se->run_node) {
        struct rb_node *next_node = rb_next(&se->run_node);
        cfs_rq->rb_leftmost = next_node;
    }
    
    rb_erase(&se->run_node, &cfs_rq->tasks_timeline);
}

/* Enqueue task in CFS runqueue */
void enqueue_task_fair(struct rq *rq, struct task_struct *task) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &task->se;
    
    pthread_mutex_lock(&cfs_rq->lock);
    
    if (se->on_rq) {
        pthread_mutex_unlock(&cfs_rq->lock);
        return; /* Already on runqueue */
    }
    
    /* Place entity in timeline */
    place_entity(cfs_rq, se, 0);
    
    /* Add to runqueue statistics */
    cfs_rq->nr_running++;
    cfs_rq->load_weight += se->load_weight;
    rq->nr_running++;
    rq->load_weight += se->load_weight;
    
    /* Insert into red-black tree */
    __enqueue_entity(cfs_rq, se);
    se->on_rq = true;
    
    pthread_mutex_unlock(&cfs_rq->lock);
}

/* Dequeue task from CFS runqueue */
void dequeue_task_fair(struct rq *rq, struct task_struct *task) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &task->se;
    
    pthread_mutex_lock(&cfs_rq->lock);
    
    if (!se->on_rq) {
        pthread_mutex_unlock(&cfs_rq->lock);
        return; /* Not on runqueue */
    }
    
    /* Update current task before dequeue */
    if (rq->curr == task) {
        update_curr_fair(rq);
    }
    
    /* Remove from red-black tree */
    __dequeue_entity(cfs_rq, se);
    se->on_rq = false;
    
    /* Update runqueue statistics */
    cfs_rq->nr_running--;
    cfs_rq->load_weight -= se->load_weight;
    rq->nr_running--;
    rq->load_weight -= se->load_weight;
    
    pthread_mutex_unlock(&cfs_rq->lock);
}

/* Pick next task from CFS runqueue */
struct task_struct *pick_next_task_fair(struct rq *rq) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se;
    
    pthread_mutex_lock(&cfs_rq->lock);
    
    if (!cfs_rq->rb_leftmost) {
        pthread_mutex_unlock(&cfs_rq->lock);
        return NULL;
    }
    
    se = container_of(cfs_rq->rb_leftmost, struct sched_entity, run_node);
    
    /* Remove from tree but keep statistics (will be added back on yield/preempt) */
    __dequeue_entity(cfs_rq, se);
    se->on_rq = false;
    
    cfs_rq->nr_running--;
    cfs_rq->load_weight -= se->load_weight;
    rq->nr_running--;
    rq->load_weight -= se->load_weight;
    
    /* Update timing */
    gettimeofday(&se->last_update_time, NULL);
    
    pthread_mutex_unlock(&cfs_rq->lock);
    
    return task_of(se);
}

/* Check if current task should yield to another */
static bool check_preempt_wakeup(struct rq *rq, struct task_struct *p) {
    struct task_struct *curr = rq->curr;
    struct sched_entity *se = &curr->se, *pse = &p->se;
    uint64_t gran = WAKEUP_GRANULARITY_NS;
    
    if (!curr || curr->policy != SCHED_NORMAL) {
        return true;
    }
    
    /* Don't preempt if the difference is too small */
    if (pse->vruntime + gran < se->vruntime) {
        return true;
    }
    
    return false;
}

/* Handle task tick for CFS */
void task_tick_fair(struct rq *rq, struct task_struct *curr) {
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &curr->se;
    
    /* Update current task runtime */
    update_curr_fair(rq);
    
    /* Check if task should be preempted */
    if (cfs_rq->nr_running > 1) {
        uint64_t ideal_runtime = sched_slice(cfs_rq, se);
        uint64_t delta_exec = se->sum_exec_runtime - se->prev_sum_exec_runtime;
        
        if (delta_exec > ideal_runtime) {
            set_need_resched(curr);
        }
    }
}

/* Wakeup preemption check */
void check_preempt_curr_fair(struct rq *rq, struct task_struct *p, int wake_flags) {
    (void)wake_flags; /* Suppress unused parameter warning */
    if (check_preempt_wakeup(rq, p)) {
        set_need_resched(rq->curr);
    }
}

/* Set next buddy hint */
void set_next_buddy(struct sched_entity *se) {
    /* For simplicity, we don't implement buddy hints */
    (void)se;
}

/* Set last buddy hint */
void set_last_buddy(struct sched_entity *se) {
    /* For simplicity, we don't implement buddy hints */
    (void)se;
}

/* Task fork handling for CFS */
void task_fork_fair(struct task_struct *p) {
    struct rq *rq = &kos_scheduler.runqueues[p->cpu];
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct sched_entity *se = &p->se, *curr_se;
    
    pthread_mutex_lock(&cfs_rq->lock);
    
    /* Initialize scheduling entity */
    se->vruntime = 0;
    se->sum_exec_runtime = 0;
    se->prev_sum_exec_runtime = 0;
    se->load_weight = prio_to_weight[p->prio - 100];
    gettimeofday(&se->last_update_time, NULL);
    se->on_rq = false;
    
    /* Place entity based on current task */
    if (rq->curr && rq->curr->policy == SCHED_NORMAL) {
        curr_se = &rq->curr->se;
        se->vruntime = curr_se->vruntime;
    } else {
        place_entity(cfs_rq, se, 1);
    }
    
    /* Give child a slight penalty to prevent fork bombs */
    se->vruntime += SCHED_LATENCY_NS / 4;
    
    pthread_mutex_unlock(&cfs_rq->lock);
}

/* Select CPU for fair task */
uint32_t select_task_rq_fair(struct task_struct *p, int prev_cpu, int sd_flag, int wake_flags) {
    (void)prev_cpu; (void)sd_flag; (void)wake_flags; /* Suppress unused parameter warnings */
    uint32_t best_cpu = 0;
    uint64_t min_load = UINT64_MAX;
    
    /* Simple load balancing - find CPU with minimum load */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        /* Check CPU affinity */
        if (!(p->cpus_allowed & (1U << cpu))) {
            continue;
        }
        
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        uint64_t load = rq->cfs.load_weight;
        
        if (load < min_load) {
            min_load = load;
            best_cpu = cpu;
        }
    }
    
    return best_cpu;
}

/* CFS bandwidth control */
void init_cfs_bandwidth(struct cfs_rq *cfs_rq) {
    /* Initialize bandwidth control structures */
    cfs_rq->runtime_expires = 0;
    cfs_rq->runtime_remaining = 0;
    cfs_rq->throttled = 0;
    cfs_rq->throttled_clock = 0;
    cfs_rq->throttled_clock_task = 0;
    cfs_rq->throttle_count = 0;
    cfs_rq->unthrottle_count = 0;
    cfs_rq->blocked_load_avg = 0;
    cfs_rq->last_update_time_copy = 0;
    cfs_rq->shares = 1024; /* Default shares */
}

/* Update CFS bandwidth */
void update_cfs_bandwidth(struct cfs_rq *cfs_rq) {
    /* Update bandwidth usage */
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;
    
    /* Check if runtime period expired */
    if (now_us >= cfs_rq->runtime_expires) {
        /* Refill runtime quota - 100ms per 1s period by default */
        cfs_rq->runtime_remaining = 100000; /* 100ms in microseconds */
        cfs_rq->runtime_expires = now_us + 1000000; /* 1 second period */
        
        /* Unthrottle if was throttled */
        if (cfs_rq->throttled) {
            cfs_rq->throttled = 0;
            cfs_rq->unthrottle_count++;
        }
    }
}

/* Check if CFS task is throttled */
bool cfs_task_throttled(struct task_struct *task) {
    /* Check if task is throttled due to bandwidth limits */
    struct rq *rq = &kos_scheduler.runqueues[task->cpu];
    struct cfs_rq *cfs_rq = &rq->cfs;
    
    return cfs_rq->throttled != 0;
}

/* Throttle CFS runqueue */
void throttle_cfs_rq(struct cfs_rq *cfs_rq) {
    /* Mark runqueue as throttled */
    if (!cfs_rq->throttled) {
        struct timeval now;
        gettimeofday(&now, NULL);
        
        cfs_rq->throttled = 1;
        cfs_rq->throttled_clock = now.tv_sec * 1000000ULL + now.tv_usec;
        cfs_rq->throttle_count++;
        
        /* Dequeue all tasks from this cfs_rq */
        struct rb_node *node;
        while ((node = rb_first(&cfs_rq->tasks_timeline))) {
            struct sched_entity *se = rb_entry(node, struct sched_entity, run_node);
            rb_erase(node, &cfs_rq->tasks_timeline);
            se->on_rq = false;
            cfs_rq->nr_running--;
        }
    }
}

/* Update blocked load averages */
void update_blocked_averages(int cpu) {
    struct rq *rq = &kos_scheduler.runqueues[cpu];
    struct cfs_rq *cfs_rq = &rq->cfs;
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;
    
    pthread_mutex_lock(&cfs_rq->lock);
    
    /* Update load averages for blocked tasks */
    cfs_rq->blocked_load_avg = (cfs_rq->blocked_load_avg * 7 + cfs_rq->nr_running * 1024) / 8;
    
    /* Decay old load */
    uint64_t delta = now_us - cfs_rq->last_update_time_copy;
    if (delta > 1000000) { /* More than 1 second */
        cfs_rq->blocked_load_avg = cfs_rq->blocked_load_avg * 95 / 100;
    }
    
    cfs_rq->last_update_time_copy = now_us;
    
    pthread_mutex_unlock(&cfs_rq->lock);
}

/* Update CFS shares for group scheduling */
void update_cfs_shares(struct cfs_rq *cfs_rq) {
    /* Update shares based on group weight */
    pthread_mutex_lock(&cfs_rq->lock);
    
    /* Calculate shares based on load and group weight */
    uint64_t shares = 1024; /* Default shares */
    
    if (cfs_rq->nr_running > 0) {
        /* Adjust shares based on number of running tasks */
        shares = (1024 * cfs_rq->nr_running) / (cfs_rq->nr_running + 1);
        
        /* Apply any group weight multiplier */
        shares = shares * cfs_rq->shares / 1024;
    }
    
    cfs_rq->shares = shares;
    
    pthread_mutex_unlock(&cfs_rq->lock);
}

/* CFS group scheduling support (simplified) */
void init_cfs_rq(struct cfs_rq *cfs_rq) {
    cfs_rq->tasks_timeline.rb_node = NULL;
    cfs_rq->rb_leftmost = NULL;
    cfs_rq->min_vruntime = 0;
    cfs_rq->nr_running = 0;
    cfs_rq->load_weight = 0;
    pthread_mutex_init(&cfs_rq->lock, NULL);
}

/* Destroy CFS runqueue */
void destroy_cfs_rq(struct cfs_rq *cfs_rq) {
    pthread_mutex_destroy(&cfs_rq->lock);
}

/* Print CFS statistics */
void print_cfs_rq_stats(struct cfs_rq *cfs_rq, uint32_t cpu) {
    printf("CFS RQ (CPU %u):\n", cpu);
    printf("  Tasks: %u\n", cfs_rq->nr_running);
    printf("  Load weight: %lu\n", cfs_rq->load_weight);
    printf("  Min vruntime: %lu\n", cfs_rq->min_vruntime);
    printf("  Timeline root: %p\n", (void*)cfs_rq->tasks_timeline.rb_node);
    printf("  Leftmost: %p\n", (void*)cfs_rq->rb_leftmost);
}

/* CFS load balancing helper */
struct task_struct *pick_next_entity(struct cfs_rq *cfs_rq) {
    if (!cfs_rq->rb_leftmost) {
        return NULL;
    }
    
    struct sched_entity *se = container_of(cfs_rq->rb_leftmost, 
                                          struct sched_entity, run_node);
    return task_of(se);
}

/* Check CFS runqueue sanity */
bool cfs_rq_is_sane(struct cfs_rq *cfs_rq) {
    /* Basic sanity checks */
    if (cfs_rq->nr_running == 0 && cfs_rq->tasks_timeline.rb_node != NULL) {
        return false;
    }
    
    if (cfs_rq->nr_running > 0 && cfs_rq->rb_leftmost == NULL) {
        return false;
    }
    
    return true;
}