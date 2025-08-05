/*
 * KOS Scheduler Error Handling and Edge Cases
 * Comprehensive scheduler error recovery and validation
 */

#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>

/* Scheduler error types */
typedef enum {
    SCHED_ERROR_NONE = 0,
    SCHED_ERROR_INVALID_TASK,      /* Invalid task pointer */
    SCHED_ERROR_INVALID_CPU,       /* Invalid CPU number */
    SCHED_ERROR_DEADLOCK,          /* Deadlock detected */
    SCHED_ERROR_RUNQUEUE_CORRUPT,  /* Runqueue corruption */
    SCHED_ERROR_PRIORITY_INVERSION,/* Priority inversion */
    SCHED_ERROR_STARVATION,        /* Task starvation */
    SCHED_ERROR_LOAD_IMBALANCE,    /* Severe load imbalance */
    SCHED_ERROR_CONTEXT_SWITCH,    /* Context switch failure */
    SCHED_ERROR_AFFINITY_VIOLATION,/* CPU affinity violation */
    SCHED_ERROR_BANDWIDTH_EXCEEDED,/* Bandwidth limit exceeded */
    SCHED_ERROR_RT_THROTTLED,      /* RT task throttled */
    SCHED_ERROR_TIMER_EXPIRED      /* Timer/deadline expired */
} sched_error_type_t;

/* Error recovery strategies */
typedef enum {
    SCHED_RECOVERY_IGNORE = 0,
    SCHED_RECOVERY_LOG,
    SCHED_RECOVERY_REBALANCE,
    SCHED_RECOVERY_RESET_TASK,
    SCHED_RECOVERY_MIGRATE_TASK,
    SCHED_RECOVERY_KILL_TASK,
    SCHED_RECOVERY_PANIC
} sched_recovery_t;

/* Scheduler error context */
typedef struct {
    sched_error_type_t type;
    const char *message;
    struct task_struct *task;
    uint32_t cpu;
    uint32_t target_cpu;
    uint64_t timestamp;
    const char *file;
    int line;
    const char *function;
    sched_recovery_t recovery;
    void *extra_data;
} sched_error_ctx_t;

/* Scheduler error statistics */
static struct {
    uint64_t total_errors;
    uint64_t invalid_task_errors;
    uint64_t invalid_cpu_errors;
    uint64_t deadlock_errors;
    uint64_t runqueue_corrupt_errors;
    uint64_t priority_inversion_errors;
    uint64_t starvation_errors;
    uint64_t load_imbalance_errors;
    uint64_t context_switch_errors;
    uint64_t affinity_violation_errors;
    uint64_t bandwidth_exceeded_errors;
    uint64_t rt_throttled_errors;
    uint64_t timer_expired_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t tasks_killed;
    uint64_t tasks_migrated;
    pthread_mutex_t lock;
} sched_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Deadlock detection state */
typedef struct {
    uint64_t last_progress_time;
    uint32_t stuck_tasks;
    bool detection_active;
    pthread_mutex_t lock;
} deadlock_detector_t;

static deadlock_detector_t deadlock_detector = {
    .lock = PTHREAD_MUTEX_INITIALIZER
};

/* Task starvation tracking */
typedef struct starvation_entry {
    struct task_struct *task;
    uint64_t last_run_time;
    uint64_t wait_time;
    struct starvation_entry *next;
} starvation_entry_t;

static starvation_entry_t *starvation_list = NULL;
static pthread_mutex_t starvation_lock = PTHREAD_MUTEX_INITIALIZER;

/* Validate task structure integrity */
static int validate_task_struct(struct task_struct *task, const char *context)
{
    if (!task) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_INVALID_TASK,
            .message = "NULL task pointer",
            .task = task,
            .cpu = 0xFFFFFFFF,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_LOG
        };
        return handle_scheduler_error(&ctx);
    }

    /* Check task magic numbers and basic integrity */
    if (task->pid == 0 && task != &init_task) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_INVALID_TASK,
            .message = "Invalid PID in task",
            .task = task,
            .cpu = task->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_KILL_TASK
        };
        return handle_scheduler_error(&ctx);
    }

    /* Check CPU affinity */
    if (task->cpu >= kos_scheduler.nr_cpus) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_INVALID_CPU,
            .message = "Task assigned to invalid CPU",
            .task = task,
            .cpu = task->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_MIGRATE_TASK
        };
        return handle_scheduler_error(&ctx);
    }

    /* Check scheduling entity consistency */
    if (task->se.on_rq && task->state != TASK_RUNNING) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_RUNQUEUE_CORRUPT,
            .message = "Task on runqueue but not in RUNNING state",
            .task = task,
            .cpu = task->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_RESET_TASK
        };
        return handle_scheduler_error(&ctx);
    }

    return 0;
}

/* Validate runqueue integrity */
static int validate_runqueue(struct rq *rq, const char *context)
{
    if (!rq) {
        return -1;
    }

    pthread_mutex_lock(&rq->cfs.lock);

    /* Check CFS runqueue consistency */
    if (rq->cfs.nr_running == 0 && rq->cfs.tasks_timeline.rb_node != NULL) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_RUNQUEUE_CORRUPT,
            .message = "CFS runqueue has no tasks but non-empty timeline",
            .task = NULL,
            .cpu = rq->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_REBALANCE
        };

        pthread_mutex_unlock(&rq->cfs.lock);
        return handle_scheduler_error(&ctx);
    }

    /* Check for runqueue load consistency */
    if (rq->cfs.nr_running > 0 && rq->cfs.load_weight == 0) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_RUNQUEUE_CORRUPT,
            .message = "CFS runqueue has tasks but zero load weight",
            .task = NULL,
            .cpu = rq->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SCHED_RECOVERY_REBALANCE
        };

        pthread_mutex_unlock(&rq->cfs.lock);
        return handle_scheduler_error(&ctx);
    }

    pthread_mutex_unlock(&rq->cfs.lock);
    return 0;
}

/* Detect priority inversion */
static int detect_priority_inversion(struct rq *rq)
{
    /* Simple priority inversion detection */
    struct task_struct *curr = rq->curr;
    if (!curr || curr->policy != SCHED_NORMAL) {
        return 0;
    }

    /* Check if lower priority task is running while higher priority tasks wait */
    pthread_mutex_lock(&rq->cfs.lock);

    if (rq->cfs.nr_running > 1) {
        struct rb_node *node = rb_first(&rq->cfs.tasks_timeline);
        if (node) {
            struct sched_entity *se = container_of(node, struct sched_entity, run_node);
            struct task_struct *next_task = task_of(se);

            if (next_task->prio < curr->prio) {
                sched_error_ctx_t ctx = {
                    .type = SCHED_ERROR_PRIORITY_INVERSION,
                    .message = "Priority inversion detected",
                    .task = curr,
                    .cpu = rq->cpu,
                    .timestamp = time(NULL),
                    .file = __FILE__,
                    .line = __LINE__,
                    .function = __func__,
                    .recovery = SCHED_RECOVERY_REBALANCE,
                    .extra_data = next_task
                };

                pthread_mutex_unlock(&rq->cfs.lock);
                return handle_scheduler_error(&ctx);
            }
        }
    }

    pthread_mutex_unlock(&rq->cfs.lock);
    return 0;
}

/* Detect task starvation */
static int detect_task_starvation(void)
{
    pthread_mutex_lock(&starvation_lock);

    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;

    starvation_entry_t *entry = starvation_list;
    while (entry) {
        if (now_us - entry->last_run_time > 10000000) { /* 10 seconds */
            sched_error_ctx_t ctx = {
                .type = SCHED_ERROR_STARVATION,
                .message = "Task starvation detected",
                .task = entry->task,
                .cpu = entry->task->cpu,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = __func__,
                .recovery = SCHED_RECOVERY_MIGRATE_TASK
            };

            pthread_mutex_unlock(&starvation_lock);
            return handle_scheduler_error(&ctx);
        }
        entry = entry->next;
    }

    pthread_mutex_unlock(&starvation_lock);
    return 0;
}

/* Detect severe load imbalance */
static int detect_load_imbalance(void)
{
    if (kos_scheduler.nr_cpus < 2) {
        return 0; /* No imbalance possible with single CPU */
    }

    uint64_t min_load = UINT64_MAX;
    uint64_t max_load = 0;
    uint32_t min_cpu = 0, max_cpu = 0;

    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        uint64_t load = rq->load_weight;

        if (load < min_load) {
            min_load = load;
            min_cpu = cpu;
        }
        if (load > max_load) {
            max_load = load;
            max_cpu = cpu;
        }
    }

    /* Check if imbalance is severe (more than 4x difference) */
    if (min_load > 0 && max_load > min_load * 4) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_LOAD_IMBALANCE,
            .message = "Severe load imbalance detected",
            .task = NULL,
            .cpu = max_cpu,
            .target_cpu = min_cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SCHED_RECOVERY_REBALANCE
        };
        return handle_scheduler_error(&ctx);
    }

    return 0;
}

/* Detect deadlocks */
static int detect_deadlock(void)
{
    pthread_mutex_lock(&deadlock_detector.lock);

    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;

    /* Check if all CPUs are stuck */
    uint32_t stuck_cpus = 0;
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        if (rq->nr_switches == 0 || now_us - rq->last_load_update.tv_sec * 1000000ULL > 5000000) {
            stuck_cpus++;
        }
    }

    if (stuck_cpus == kos_scheduler.nr_cpus && stuck_cpus > 0) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_DEADLOCK,
            .message = "System-wide deadlock detected",
            .task = NULL,
            .cpu = 0xFFFFFFFF,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SCHED_RECOVERY_PANIC
        };

        pthread_mutex_unlock(&deadlock_detector.lock);
        return handle_scheduler_error(&ctx);
    }

    pthread_mutex_unlock(&deadlock_detector.lock);
    return 0;
}

/* Log scheduler error */
static void log_scheduler_error(const sched_error_ctx_t *ctx)
{
    pthread_mutex_lock(&sched_error_stats.lock);
    sched_error_stats.total_errors++;

    switch (ctx->type) {
        case SCHED_ERROR_INVALID_TASK:
            sched_error_stats.invalid_task_errors++;
            break;
        case SCHED_ERROR_INVALID_CPU:
            sched_error_stats.invalid_cpu_errors++;
            break;
        case SCHED_ERROR_DEADLOCK:
            sched_error_stats.deadlock_errors++;
            break;
        case SCHED_ERROR_RUNQUEUE_CORRUPT:
            sched_error_stats.runqueue_corrupt_errors++;
            break;
        case SCHED_ERROR_PRIORITY_INVERSION:
            sched_error_stats.priority_inversion_errors++;
            break;
        case SCHED_ERROR_STARVATION:
            sched_error_stats.starvation_errors++;
            break;
        case SCHED_ERROR_LOAD_IMBALANCE:
            sched_error_stats.load_imbalance_errors++;
            break;
        case SCHED_ERROR_CONTEXT_SWITCH:
            sched_error_stats.context_switch_errors++;
            break;
        case SCHED_ERROR_AFFINITY_VIOLATION:
            sched_error_stats.affinity_violation_errors++;
            break;
        case SCHED_ERROR_BANDWIDTH_EXCEEDED:
            sched_error_stats.bandwidth_exceeded_errors++;
            break;
        case SCHED_ERROR_RT_THROTTLED:
            sched_error_stats.rt_throttled_errors++;
            break;
        case SCHED_ERROR_TIMER_EXPIRED:
            sched_error_stats.timer_expired_errors++;
            break;
        default:
            break;
    }

    pthread_mutex_unlock(&sched_error_stats.lock);

    /* Log error details */
    printf("[SCHED ERROR] Type: %d, Message: %s\n", ctx->type, ctx->message);
    if (ctx->task) {
        printf("[SCHED ERROR] Task: PID %u (%s), CPU: %u\n",
               ctx->task->pid, ctx->task->comm, ctx->cpu);
        printf("[SCHED ERROR] State: %d, Policy: %u, Priority: %d\n",
               ctx->task->state, ctx->task->policy, ctx->task->prio);
    } else {
        printf("[SCHED ERROR] CPU: %u\n", ctx->cpu);
    }
    printf("[SCHED ERROR] Location: %s:%d in %s()\n",
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle scheduler error with recovery */
int handle_scheduler_error(sched_error_ctx_t *ctx)
{
    log_scheduler_error(ctx);

    pthread_mutex_lock(&sched_error_stats.lock);
    sched_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&sched_error_stats.lock);

    switch (ctx->recovery) {
        case SCHED_RECOVERY_IGNORE:
            return 0;

        case SCHED_RECOVERY_LOG:
            /* Already logged above */
            return 0;

        case SCHED_RECOVERY_REBALANCE:
            /* Trigger immediate load balancing */
            for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
                load_balance(cpu);
            }
            pthread_mutex_lock(&sched_error_stats.lock);
            sched_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&sched_error_stats.lock);
            return 0;

        case SCHED_RECOVERY_RESET_TASK:
            if (ctx->task) {
                /* Reset task scheduling state */
                dequeue_task_fair(&kos_scheduler.runqueues[ctx->task->cpu], ctx->task);
                ctx->task->se.vruntime = 0;
                ctx->task->se.sum_exec_runtime = 0;
                enqueue_task_fair(&kos_scheduler.runqueues[ctx->task->cpu], ctx->task);
                
                pthread_mutex_lock(&sched_error_stats.lock);
                sched_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&sched_error_stats.lock);
            }
            return 0;

        case SCHED_RECOVERY_MIGRATE_TASK:
            if (ctx->task) {
                /* Migrate task to different CPU */
                uint32_t new_cpu = select_task_rq(ctx->task);
                if (new_cpu != ctx->task->cpu) {
                    /* Simple migration */
                    dequeue_task_fair(&kos_scheduler.runqueues[ctx->task->cpu], ctx->task);
                    ctx->task->cpu = new_cpu;
                    enqueue_task_fair(&kos_scheduler.runqueues[new_cpu], ctx->task);
                    
                    pthread_mutex_lock(&sched_error_stats.lock);
                    sched_error_stats.tasks_migrated++;
                    sched_error_stats.recoveries_successful++;
                    pthread_mutex_unlock(&sched_error_stats.lock);
                }
            }
            return 0;

        case SCHED_RECOVERY_KILL_TASK:
            if (ctx->task && ctx->task->pid > 1) { /* Don't kill init */
                printf("[SCHED FATAL] Killing corrupted task PID %u\n", ctx->task->pid);
                ctx->task->state = TASK_ZOMBIE;
                ctx->task->exit_code = -EAGAIN;
                
                pthread_mutex_lock(&sched_error_stats.lock);
                sched_error_stats.tasks_killed++;
                sched_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&sched_error_stats.lock);
            }
            return 0;

        case SCHED_RECOVERY_PANIC:
            printf("[SCHED PANIC] Unrecoverable scheduler error - system halting\n");
            abort();

        default:
            return -1;
    }
}

/* Safe context switch with error handling */
int safe_context_switch(struct rq *rq, struct task_struct *prev, struct task_struct *next)
{
    if (validate_task_struct(prev, "context_switch_prev") != 0 ||
        validate_task_struct(next, "context_switch_next") != 0) {
        return -1;
    }

    /* Check CPU affinity */
    if (!(next->cpus_allowed & (1U << rq->cpu))) {
        sched_error_ctx_t ctx = {
            .type = SCHED_ERROR_AFFINITY_VIOLATION,
            .message = "Task scheduled on CPU not in affinity mask",
            .task = next,
            .cpu = rq->cpu,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SCHED_RECOVERY_MIGRATE_TASK
        };
        return handle_scheduler_error(&ctx);
    }

    /* Perform the actual context switch */
    context_switch(rq, prev, next);

    /* Update context switch statistics */
    rq->nr_switches++;
    kos_scheduler.total_context_switches++;

    return 0;
}

/* Update task starvation tracking */
void update_task_starvation_tracking(struct task_struct *task)
{
    pthread_mutex_lock(&starvation_lock);

    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;

    /* Find or create starvation entry */
    starvation_entry_t *entry = starvation_list;
    while (entry && entry->task != task) {
        entry = entry->next;
    }

    if (!entry) {
        entry = malloc(sizeof(starvation_entry_t));
        if (entry) {
            entry->task = task;
            entry->last_run_time = now_us;
            entry->wait_time = 0;
            entry->next = starvation_list;
            starvation_list = entry;
        }
    } else {
        entry->last_run_time = now_us;
        entry->wait_time = 0;
    }

    pthread_mutex_unlock(&starvation_lock);
}

/* Comprehensive scheduler health check */
int scheduler_health_check(void)
{
    int errors = 0;

    /* Check all runqueues */
    for (uint32_t cpu = 0; cpu < kos_scheduler.nr_cpus; cpu++) {
        struct rq *rq = &kos_scheduler.runqueues[cpu];
        
        if (validate_runqueue(rq, "health_check") != 0) {
            errors++;
        }
        
        if (detect_priority_inversion(rq) != 0) {
            errors++;
        }
    }

    /* System-wide checks */
    if (detect_load_imbalance() != 0) {
        errors++;
    }

    if (detect_task_starvation() != 0) {
        errors++;
    }

    if (detect_deadlock() != 0) {
        errors++;
    }

    return errors;
}

/* Get scheduler error statistics */
void sched_get_error_stats(void)
{
    pthread_mutex_lock(&sched_error_stats.lock);

    printf("\nScheduler Error Statistics:\n");
    printf("===========================\n");
    printf("Total errors:              %lu\n", sched_error_stats.total_errors);
    printf("Invalid task errors:       %lu\n", sched_error_stats.invalid_task_errors);
    printf("Invalid CPU errors:        %lu\n", sched_error_stats.invalid_cpu_errors);
    printf("Deadlock errors:           %lu\n", sched_error_stats.deadlock_errors);
    printf("Runqueue corrupt errors:   %lu\n", sched_error_stats.runqueue_corrupt_errors);
    printf("Priority inversion errors: %lu\n", sched_error_stats.priority_inversion_errors);
    printf("Starvation errors:         %lu\n", sched_error_stats.starvation_errors);
    printf("Load imbalance errors:     %lu\n", sched_error_stats.load_imbalance_errors);
    printf("Context switch errors:     %lu\n", sched_error_stats.context_switch_errors);
    printf("Affinity violation errors: %lu\n", sched_error_stats.affinity_violation_errors);
    printf("Bandwidth exceeded errors: %lu\n", sched_error_stats.bandwidth_exceeded_errors);
    printf("RT throttled errors:       %lu\n", sched_error_stats.rt_throttled_errors);
    printf("Timer expired errors:      %lu\n", sched_error_stats.timer_expired_errors);
    printf("Recovery attempts:         %lu\n", sched_error_stats.recoveries_attempted);
    printf("Recovery successes:        %lu\n", sched_error_stats.recoveries_successful);
    printf("Tasks killed:              %lu\n", sched_error_stats.tasks_killed);
    printf("Tasks migrated:            %lu\n", sched_error_stats.tasks_migrated);

    if (sched_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)sched_error_stats.recoveries_successful / 
                             sched_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate:     %.1f%%\n", success_rate);
    }

    pthread_mutex_unlock(&sched_error_stats.lock);
}

/* Initialize scheduler error handling */
void sched_error_init(void)
{
    printf("Scheduler error handling initialized\n");
}

/* Cleanup scheduler error handling */
void sched_error_cleanup(void)
{
    pthread_mutex_lock(&starvation_lock);
    
    starvation_entry_t *entry = starvation_list;
    while (entry) {
        starvation_entry_t *next = entry->next;
        free(entry);
        entry = next;
    }
    starvation_list = NULL;
    
    pthread_mutex_unlock(&starvation_lock);
}

/* Macros for easy error checking */
#define SCHED_VALIDATE_TASK(task, context) \
    if (validate_task_struct(task, context) != 0) return -1

#define SCHED_VALIDATE_RQ(rq, context) \
    if (validate_runqueue(rq, context) != 0) return -1

#define SCHED_CHECK_CPU(cpu) \
    if (cpu >= kos_scheduler.nr_cpus) { \
        sched_error_ctx_t ctx = { \
            .type = SCHED_ERROR_INVALID_CPU, \
            .message = "Invalid CPU number", \
            .cpu = cpu, \
            .timestamp = time(NULL), \
            .file = __FILE__, \
            .line = __LINE__, \
            .function = __func__, \
            .recovery = SCHED_RECOVERY_LOG \
        }; \
        handle_scheduler_error(&ctx); \
        return -1; \
    }