#ifndef _KOS_SCHED_H
#define _KOS_SCHED_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <sys/time.h>
#include <stddef.h>

/* Maximum number of CPUs supported */
#define MAX_CPUS 32
#define MAX_PROCESSES 65536

/* Priority levels */
#define MAX_NICE 19
#define MIN_NICE -20
#define NICE_WIDTH (MAX_NICE - MIN_NICE + 1)
#define DEFAULT_NICE 0

/* Real-time scheduling classes */
#define SCHED_NORMAL    0
#define SCHED_FIFO      1
#define SCHED_RR        2
#define SCHED_BATCH     3
#define SCHED_IDLE      5
#define SCHED_DEADLINE  6

/* Process states */
typedef enum {
    TASK_RUNNING = 0,
    TASK_INTERRUPTIBLE,
    TASK_UNINTERRUPTIBLE,
    TASK_ZOMBIE,
    TASK_STOPPED,
    TASK_TRACED
} task_state_t;

/* Red-Black tree colors */
typedef enum {
    RB_RED = 0,
    RB_BLACK = 1
} rb_color_t;

/* Forward declarations */
struct task_struct;
struct rq;
struct sched_entity;

/* Red-Black tree node for CFS */
struct rb_node {
    struct rb_node *rb_parent;
    struct rb_node *rb_left;
    struct rb_node *rb_right;
    rb_color_t rb_color;
};

/* Red-Black tree root */
struct rb_root {
    struct rb_node *rb_node;
};

/* CFS run queue */
struct cfs_rq {
    struct rb_root tasks_timeline;      /* Red-black tree of tasks */
    struct rb_node *rb_leftmost;       /* Leftmost node (next to run) */
    uint64_t min_vruntime;              /* Minimum vruntime */
    uint32_t nr_running;                /* Number of running tasks */
    uint64_t load_weight;               /* Total load weight */
    pthread_mutex_t lock;               /* Runqueue lock */
    
    /* Bandwidth control */
    uint64_t runtime_remaining;         /* Remaining runtime in period */
    uint64_t runtime_expires;           /* When runtime period expires */
    uint32_t throttled;                 /* Is runqueue throttled */
    uint64_t throttled_clock;           /* When throttled */
    uint64_t throttled_clock_task;      /* Task time when throttled */
    uint64_t throttle_count;            /* Times throttled */
    uint64_t unthrottle_count;          /* Times unthrottled */
    
    /* Load tracking */
    uint64_t blocked_load_avg;          /* Blocked load average */
    uint64_t last_update_time_copy;     /* Last update time */
    uint64_t shares;                    /* Group shares */
};

/* Real-time run queue */
struct rt_rq {
    struct task_struct **queue;         /* Priority array */
    uint32_t *bitmap;                   /* Priority bitmap */
    uint32_t nr_running;                /* Number of RT tasks */
    uint32_t highest_prio;              /* Highest priority task */
    pthread_mutex_t lock;               /* RT runqueue lock */
};

/* Per-CPU run queue */
struct rq {
    uint32_t cpu;                       /* CPU ID */
    struct task_struct *curr;           /* Currently running task */
    struct task_struct *idle;           /* Idle task for this CPU */
    
    struct cfs_rq cfs;                  /* CFS runqueue */
    struct rt_rq rt;                    /* RT runqueue */
    
    uint64_t nr_switches;               /* Context switch count */
    uint64_t nr_running;                /* Total running tasks */
    
    /* Load balancing */
    uint64_t load_weight;               /* CPU load weight */
    double load_avg_1;                  /* 1-minute load average */
    double load_avg_5;                  /* 5-minute load average */
    double load_avg_15;                 /* 15-minute load average */
    struct timeval last_load_update;    /* Last load update time */
    
    pthread_mutex_t lock;               /* Per-CPU runqueue lock */
};

/* Scheduling entity (part of task_struct) */
struct sched_entity {
    struct rb_node run_node;            /* RB tree node */
    uint64_t vruntime;                  /* Virtual runtime */
    uint64_t sum_exec_runtime;          /* Total execution time */
    uint64_t prev_sum_exec_runtime;     /* Previous total execution time */
    uint64_t load_weight;               /* Load weight */
    struct timeval last_update_time;    /* Last update timestamp */
    bool on_rq;                         /* On runqueue flag */
};

/* Real-time scheduling entity */
struct sched_rt_entity {
    struct task_struct *next;           /* Next task in priority queue */
    struct task_struct *prev;           /* Previous task in priority queue */
    uint32_t time_slice;                /* Time slice for RR */
    uint32_t timeout;                   /* RT timeout */
};

/* Deadline scheduling entity */
struct sched_dl_entity {
    uint64_t deadline;                  /* Absolute deadline */
    uint64_t runtime;                   /* Runtime budget */
    uint64_t period;                    /* Period */
    uint64_t dl_throttled;              /* Throttled flag */
};

/* Task structure */
struct task_struct {
    uint32_t pid;                       /* Process ID */
    uint32_t tgid;                      /* Thread group ID */
    task_state_t state;                 /* Task state */
    
    /* Scheduling */
    int prio;                           /* Dynamic priority */
    int static_prio;                    /* Static priority */
    int normal_prio;                    /* Normal priority */
    uint32_t policy;                    /* Scheduling policy */
    
    struct sched_entity se;             /* CFS scheduling entity */
    struct sched_rt_entity rt;          /* RT scheduling entity */
    struct sched_dl_entity dl;          /* Deadline scheduling entity */
    
    /* CPU affinity */
    uint32_t cpu;                       /* Current CPU */
    uint32_t cpus_allowed;              /* CPU affinity mask */
    
    /* Timing */
    struct timeval start_time;          /* Process start time */
    uint64_t utime;                     /* User time */
    uint64_t stime;                     /* System time */
    
    /* Memory management */
    void *stack;                        /* Kernel stack */
    uint32_t stack_size;                /* Stack size */
    
    /* Process relations */
    struct task_struct *parent;         /* Parent process */
    struct task_struct *real_parent;    /* Real parent */
    
    /* Files and signals */
    void *files;                        /* File descriptors */
    void *signal;                       /* Signal handlers */
    
    /* Exit status */
    int exit_code;                      /* Exit code */
    int exit_signal;                    /* Exit signal */
    
    /* Process name */
    char comm[16];                      /* Command name */
    
    /* Reference count */
    int usage;                          /* Reference count */
    
    /* Synchronization */
    pthread_mutex_t lock;               /* Task lock */
};

/* Load weight table (nice to weight mapping) */
extern const uint32_t prio_to_weight[40];
extern const uint32_t prio_to_wmult[40];

/* Global scheduler state */
struct scheduler {
    struct rq runqueues[MAX_CPUS];      /* Per-CPU runqueues */
    uint32_t nr_cpus;                   /* Number of CPUs */
    bool running;                       /* Scheduler running flag */
    pthread_t scheduler_thread;          /* Scheduler thread */
    
    /* Global statistics */
    uint64_t total_forks;               /* Total process forks */
    uint64_t total_context_switches;    /* Total context switches */
    struct timeval boot_time;           /* System boot time */
    
    /* Load balancing */
    bool load_balance_enabled;          /* Load balancing flag */
    uint32_t balance_interval;          /* Balance interval (ms) */
    struct timeval last_balance;        /* Last balance time */
    
    pthread_mutex_t lock;               /* Global scheduler lock */
};

/* Global scheduler instance */
extern struct scheduler kos_scheduler;

/* Core scheduler functions */
int sched_init(uint32_t nr_cpus);
void sched_start(void);
void sched_stop(void);
void schedule(void);
void schedule_cpu(uint32_t cpu);

/* Task management */
struct task_struct *create_task(uint32_t pid, const char *comm);
void destroy_task(struct task_struct *task);
void wake_up_process(struct task_struct *task);
void set_task_state(struct task_struct *task, task_state_t state);

/* Scheduling policy functions */
void set_user_nice(struct task_struct *task, int nice);
int task_nice(const struct task_struct *task);
void set_task_policy(struct task_struct *task, uint32_t policy);

/* CFS functions */
void enqueue_task_fair(struct rq *rq, struct task_struct *task);
void dequeue_task_fair(struct rq *rq, struct task_struct *task);
struct task_struct *pick_next_task_fair(struct rq *rq);
void task_tick_fair(struct rq *rq, struct task_struct *curr);
void update_curr_fair(struct rq *rq);

/* RT functions */
void enqueue_task_rt(struct rq *rq, struct task_struct *task);
void dequeue_task_rt(struct rq *rq, struct task_struct *task);
struct task_struct *pick_next_task_rt(struct rq *rq);
void task_tick_rt(struct rq *rq, struct task_struct *curr);

/* Load balancing */
void load_balance(uint32_t cpu);
void trigger_load_balance(void);
uint32_t select_task_rq(struct task_struct *task);

/* Statistics and debugging */
void update_rq_clock(struct rq *rq);
void scheduler_tick(void);
void print_scheduler_stats(void);
void print_task_info(const struct task_struct *task);

/* Red-Black tree operations */
void rb_insert_color(struct rb_node *node, struct rb_root *root);
void rb_erase(struct rb_node *node, struct rb_root *root);
struct rb_node *rb_first(const struct rb_root *root);
struct rb_node *rb_next(const struct rb_node *node);

/* Utility macros */
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

#define task_of(se) \
    container_of(se, struct task_struct, se)

#define rt_task_of(rt_se) \
    container_of(rt_se, struct task_struct, rt)

/* Time conversion helpers */
#define NSEC_PER_SEC    1000000000ULL
#define NSEC_PER_MSEC   1000000ULL
#define NSEC_PER_USEC   1000ULL

uint64_t sched_clock(void);
uint64_t local_clock(void);
void update_rq_clock_task(struct rq *rq, int64_t delta);

/* CPU hotplug support */
void sched_cpu_activate(uint32_t cpu);
void sched_cpu_deactivate(uint32_t cpu);

/* Preemption control */
void preempt_disable(void);
void preempt_enable(void);
bool need_resched(void);
void set_need_resched(struct task_struct *task);
void clear_need_resched(struct task_struct *task);

/* Context switching */
void context_switch(struct rq *rq, struct task_struct *prev, struct task_struct *next);
void finish_task_switch(struct task_struct *prev);

#endif /* _KOS_SCHED_H */