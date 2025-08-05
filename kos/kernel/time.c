/*
 * KOS Time Management System
 * High resolution timers, clock sources, and time keeping
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <errno.h>
#include <stdbool.h>

/* Time constants */
#define NSEC_PER_SEC    1000000000ULL
#define NSEC_PER_MSEC   1000000ULL
#define NSEC_PER_USEC   1000ULL
#define USEC_PER_SEC    1000000ULL
#define MSEC_PER_SEC    1000ULL

#define MAX_TIMERS      1024
#define TIMER_HASH_SIZE 256

/* Clock source types */
typedef enum {
    CLOCK_SOURCE_TSC,       /* Time Stamp Counter */
    CLOCK_SOURCE_HPET,      /* High Precision Event Timer */
    CLOCK_SOURCE_ACPI_PM,   /* ACPI Power Management Timer */
    CLOCK_SOURCE_PIT,       /* Programmable Interval Timer */
    CLOCK_SOURCE_RTC,       /* Real Time Clock */
    CLOCK_SOURCE_MONOTONIC, /* Monotonic clock (userspace) */
    CLOCK_SOURCE_REALTIME   /* Real time clock (userspace) */
} clock_source_type_t;

/* Timer types */
typedef enum {
    TIMER_ONESHOT,
    TIMER_PERIODIC,
    TIMER_HRTIMER
} timer_type_t;

/* Timer states */
typedef enum {
    TIMER_STATE_INACTIVE,
    TIMER_STATE_ACTIVE,
    TIMER_STATE_EXPIRED,
    TIMER_STATE_CANCELLED
} timer_state_t;

/* Clock source structure */
typedef struct clock_source {
    const char* name;
    clock_source_type_t type;
    uint64_t frequency;     /* Hz */
    uint64_t resolution;    /* nanoseconds */
    bool available;
    uint32_t rating;        /* Higher is better */
    uint64_t (*read)(void); /* Read current time */
    struct clock_source* next;
} clock_source_t;

/* Timer structure */
typedef struct kos_timer {
    uint32_t id;
    timer_type_t type;
    timer_state_t state;
    uint64_t expires;       /* Expiration time (nanoseconds) */
    uint64_t interval;      /* For periodic timers (nanoseconds) */
    void (*callback)(struct kos_timer* timer, void* data);
    void* callback_data;
    uint32_t flags;
    
    /* Hash table linkage */
    struct kos_timer* hash_next;
    
    /* Timer wheel linkage */
    struct kos_timer* next;
    struct kos_timer* prev;
    
    /* Statistics */
    uint64_t fire_count;
    uint64_t last_fire_time;
    uint64_t total_drift;
} kos_timer_t;

/* Timer wheel for efficient timer management */
#define TIMER_WHEEL_SIZE 256
typedef struct timer_wheel {
    kos_timer_t* slots[TIMER_WHEEL_SIZE];
    uint64_t current_jiffies;
    uint32_t resolution_ns;
} timer_wheel_t;

/* High resolution timer queue */
typedef struct hr_timer_queue {
    kos_timer_t* head;
    pthread_mutex_t lock;
    uint32_t count;
} hr_timer_queue_t;

/* Global time management state */
static struct {
    /* Clock sources */
    clock_source_t* clock_sources;
    clock_source_t* current_clocksource;
    
    /* System time */
    uint64_t boot_time_ns;
    uint64_t system_time_offset;
    
    /* Timer management */
    kos_timer_t* timer_pool;
    kos_timer_t* timer_hash[TIMER_HASH_SIZE];
    timer_wheel_t timer_wheel;
    hr_timer_queue_t hr_timer_queue;
    
    /* Timer thread */
    pthread_t timer_thread;
    bool timer_thread_running;
    
    /* Statistics */
    uint64_t timer_interrupts;
    uint64_t timers_created;
    uint64_t timers_expired;
    uint64_t time_updates;
    
    /* Synchronization */
    pthread_mutex_t time_lock;
    pthread_mutex_t timer_lock;
    
    bool initialized;
} time_state = {0};

/* Forward declarations */
static uint64_t read_monotonic_clock(void);
static uint64_t read_realtime_clock(void);
static void* timer_thread_func(void* arg);
static void timer_interrupt_handler(int sig);
static void process_expired_timers(void);
static void process_hr_timers(void);
static uint32_t timer_hash(uint32_t id);
static void add_timer_to_wheel(kos_timer_t* timer);
static void remove_timer_from_wheel(kos_timer_t* timer);

/* Clock source implementations */
static clock_source_t clock_sources[] = {
    {
        .name = "monotonic",
        .type = CLOCK_SOURCE_MONOTONIC,
        .frequency = NSEC_PER_SEC,
        .resolution = 1,
        .available = true,
        .rating = 200,
        .read = read_monotonic_clock
    },
    {
        .name = "realtime", 
        .type = CLOCK_SOURCE_REALTIME,
        .frequency = NSEC_PER_SEC,
        .resolution = 1000,
        .available = true,
        .rating = 100,
        .read = read_realtime_clock
    }
};

/* Initialize time management system */
void kos_timer_init(void) {
    if (time_state.initialized) {
        return;
    }
    
    memset(&time_state, 0, sizeof(time_state));
    
    /* Initialize mutexes */
    pthread_mutex_init(&time_state.time_lock, NULL);
    pthread_mutex_init(&time_state.timer_lock, NULL);
    pthread_mutex_init(&time_state.hr_timer_queue.lock, NULL);
    
    /* Initialize clock sources */
    for (size_t i = 0; i < sizeof(clock_sources)/sizeof(clock_sources[0]); i++) {
        clock_sources[i].next = time_state.clock_sources;
        time_state.clock_sources = &clock_sources[i];
    }
    
    /* Select best clock source */
    clock_source_t* best = NULL;
    for (clock_source_t* cs = time_state.clock_sources; cs; cs = cs->next) {
        if (cs->available && (!best || cs->rating > best->rating)) {
            best = cs;
        }
    }
    time_state.current_clocksource = best;
    
    /* Initialize boot time */
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    time_state.boot_time_ns = ts.tv_sec * NSEC_PER_SEC + ts.tv_nsec;
    
    /* Initialize timer wheel */
    memset(&time_state.timer_wheel, 0, sizeof(time_state.timer_wheel));
    time_state.timer_wheel.resolution_ns = NSEC_PER_MSEC;  /* 1ms resolution */
    
    /* Set up timer interrupt handler */
    signal(SIGALRM, timer_interrupt_handler);
    
    /* Start timer thread */
    time_state.timer_thread_running = true;
    if (pthread_create(&time_state.timer_thread, NULL, timer_thread_func, NULL) != 0) {
        printf("KOS TIMER: Failed to create timer thread\n");
        time_state.timer_thread_running = false;
    }
    
    time_state.initialized = true;
    
    printf("KOS TIMER: Time management initialized with clocksource '%s'\n", 
           time_state.current_clocksource->name);
}

/* Get current time in nanoseconds since boot */
uint64_t kos_time_get_ns(void) {
    if (!time_state.current_clocksource) {
        return 0;
    }
    
    return time_state.current_clocksource->read() - time_state.boot_time_ns;
}

/* Get current time in ticks (milliseconds since boot) */
uint64_t kos_time_get_ticks(void) {
    return kos_time_get_ns() / NSEC_PER_MSEC;
}

/* Get Unix timestamp */
uint64_t kos_time_get_unix(void) {
    return time(NULL);
}

/* High resolution delay */
void kos_time_delay(uint64_t microseconds) {
    struct timespec ts;
    ts.tv_sec = microseconds / USEC_PER_SEC;
    ts.tv_nsec = (microseconds % USEC_PER_SEC) * NSEC_PER_USEC;
    nanosleep(&ts, NULL);
}

/* Create a new timer */
kos_timer_t* kos_timer_create(timer_type_t type, uint64_t expires_ms, 
                             void (*callback)(kos_timer_t* timer, void* data), 
                             void* data) {
    if (!callback) {
        return NULL;
    }
    
    pthread_mutex_lock(&time_state.timer_lock);
    
    /* Allocate timer */
    kos_timer_t* timer = calloc(1, sizeof(kos_timer_t));
    if (!timer) {
        pthread_mutex_unlock(&time_state.timer_lock);
        return NULL;
    }
    
    /* Initialize timer */
    static uint32_t next_timer_id = 1;
    timer->id = next_timer_id++;
    timer->type = type;
    timer->state = TIMER_STATE_INACTIVE;
    timer->expires = kos_time_get_ns() + (expires_ms * NSEC_PER_MSEC);
    timer->callback = callback;
    timer->callback_data = data;
    
    /* Add to hash table */
    uint32_t hash_idx = timer_hash(timer->id);
    timer->hash_next = time_state.timer_hash[hash_idx];
    time_state.timer_hash[hash_idx] = timer;
    
    time_state.timers_created++;
    
    pthread_mutex_unlock(&time_state.timer_lock);
    
    return timer;
}

/* Start a timer */
int kos_timer_start(kos_timer_t* timer) {
    if (!timer) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&time_state.timer_lock);
    
    if (timer->state == TIMER_STATE_ACTIVE) {
        pthread_mutex_unlock(&time_state.timer_lock);
        return -EBUSY;
    }
    
    timer->state = TIMER_STATE_ACTIVE;
    
    /* Add to appropriate timer management structure */
    if (timer->type == TIMER_HRTIMER) {
        /* Add to high-resolution timer queue */
        pthread_mutex_lock(&time_state.hr_timer_queue.lock);
        
        /* Insert in sorted order */
        kos_timer_t** pos = &time_state.hr_timer_queue.head;
        while (*pos && (*pos)->expires <= timer->expires) {
            pos = &(*pos)->next;
        }
        timer->next = *pos;
        if (*pos) {
            (*pos)->prev = timer;
        }
        *pos = timer;
        
        time_state.hr_timer_queue.count++;
        pthread_mutex_unlock(&time_state.hr_timer_queue.lock);
    } else {
        /* Add to timer wheel */
        add_timer_to_wheel(timer);
    }
    
    pthread_mutex_unlock(&time_state.timer_lock);
    
    return 0;
}

/* Stop a timer */
int kos_timer_stop(kos_timer_t* timer) {
    if (!timer) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&time_state.timer_lock);
    
    if (timer->state != TIMER_STATE_ACTIVE) {
        pthread_mutex_unlock(&time_state.timer_lock);
        return -EINVAL;
    }
    
    timer->state = TIMER_STATE_CANCELLED;
    
    /* Remove from timer management structures */
    if (timer->type == TIMER_HRTIMER) {
        pthread_mutex_lock(&time_state.hr_timer_queue.lock);
        
        if (timer->prev) {
            timer->prev->next = timer->next;
        } else {
            time_state.hr_timer_queue.head = timer->next;
        }
        
        if (timer->next) {
            timer->next->prev = timer->prev;
        }
        
        timer->next = timer->prev = NULL;
        time_state.hr_timer_queue.count--;
        
        pthread_mutex_unlock(&time_state.hr_timer_queue.lock);
    } else {
        remove_timer_from_wheel(timer);
    }
    
    pthread_mutex_unlock(&time_state.timer_lock);
    
    return 0;
}

/* Delete a timer */
int kos_timer_delete(kos_timer_t* timer) {
    if (!timer) {
        return -EINVAL;
    }
    
    /* Stop timer first */
    kos_timer_stop(timer);
    
    pthread_mutex_lock(&time_state.timer_lock);
    
    /* Remove from hash table */
    uint32_t hash_idx = timer_hash(timer->id);
    kos_timer_t** pos = &time_state.timer_hash[hash_idx];
    
    while (*pos) {
        if (*pos == timer) {
            *pos = timer->hash_next;
            break;
        }
        pos = &(*pos)->hash_next;
    }
    
    /* Free timer */
    free(timer);
    
    pthread_mutex_unlock(&time_state.timer_lock);
    
    return 0;
}

/* Clock source implementations */
static uint64_t read_monotonic_clock(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * NSEC_PER_SEC + ts.tv_nsec;
}

static uint64_t read_realtime_clock(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return ts.tv_sec * NSEC_PER_SEC + ts.tv_nsec;
}

/* Timer thread */
static void* timer_thread_func(void* arg) {
    (void)arg;
    
    while (time_state.timer_thread_running) {
        /* Process expired timers */
        process_expired_timers();
        process_hr_timers();
        
        /* Update time statistics */
        time_state.time_updates++;
        
        /* Sleep for timer resolution */
        usleep(1000);  /* 1ms */
    }
    
    return NULL;
}

/* Timer interrupt handler */
static void timer_interrupt_handler(int sig) {
    (void)sig;
    time_state.timer_interrupts++;
    
    /* This would normally trigger timer processing */
    /* For now, the timer thread handles this */
}

/* Process expired timers in timer wheel */
static void process_expired_timers(void) {
    uint64_t current_time = kos_time_get_ns();
    uint64_t current_jiffies = current_time / time_state.timer_wheel.resolution_ns;
    
    pthread_mutex_lock(&time_state.timer_lock);
    
    /* Process all slots up to current time */
    while (time_state.timer_wheel.current_jiffies <= current_jiffies) {
        uint32_t slot = time_state.timer_wheel.current_jiffies % TIMER_WHEEL_SIZE;
        kos_timer_t* timer = time_state.timer_wheel.slots[slot];
        time_state.timer_wheel.slots[slot] = NULL;
        
        while (timer) {
            kos_timer_t* next = timer->next;
            
            if (timer->expires <= current_time) {
                /* Timer expired */
                timer->state = TIMER_STATE_EXPIRED;
                timer->fire_count++;
                timer->last_fire_time = current_time;
                time_state.timers_expired++;
                
                /* Call callback */
                if (timer->callback) {
                    timer->callback(timer, timer->callback_data);
                }
                
                /* Handle periodic timers */
                if (timer->type == TIMER_PERIODIC && timer->interval > 0) {
                    timer->expires = current_time + timer->interval;
                    timer->state = TIMER_STATE_ACTIVE;
                    add_timer_to_wheel(timer);
                }
            } else {
                /* Re-add to appropriate slot */
                add_timer_to_wheel(timer);
            }
            
            timer = next;
        }
        
        time_state.timer_wheel.current_jiffies++;
    }
    
    pthread_mutex_unlock(&time_state.timer_lock);
}

/* Process high-resolution timers */
static void process_hr_timers(void) {
    uint64_t current_time = kos_time_get_ns();
    
    pthread_mutex_lock(&time_state.hr_timer_queue.lock);
    
    while (time_state.hr_timer_queue.head && 
           time_state.hr_timer_queue.head->expires <= current_time) {
        
        kos_timer_t* timer = time_state.hr_timer_queue.head;
        
        /* Remove from queue */
        time_state.hr_timer_queue.head = timer->next;
        if (timer->next) {
            timer->next->prev = NULL;
        }
        time_state.hr_timer_queue.count--;
        
        /* Fire timer */
        timer->state = TIMER_STATE_EXPIRED;
        timer->fire_count++;
        timer->last_fire_time = current_time;
        time_state.timers_expired++;
        
        pthread_mutex_unlock(&time_state.hr_timer_queue.lock);
        
        /* Call callback */
        if (timer->callback) {
            timer->callback(timer, timer->callback_data);
        }
        
        pthread_mutex_lock(&time_state.hr_timer_queue.lock);
        
        /* Handle periodic timers */
        if (timer->type == TIMER_PERIODIC && timer->interval > 0) {
            timer->expires = current_time + timer->interval;
            timer->state = TIMER_STATE_ACTIVE;
            
            /* Re-insert in sorted order */
            kos_timer_t** pos = &time_state.hr_timer_queue.head;
            while (*pos && (*pos)->expires <= timer->expires) {
                pos = &(*pos)->next;
            }
            timer->next = *pos;
            timer->prev = NULL;
            if (*pos) {
                (*pos)->prev = timer;
            }
            *pos = timer;
            time_state.hr_timer_queue.count++;
        }
    }
    
    pthread_mutex_unlock(&time_state.hr_timer_queue.lock);
}

/* Timer management helpers */
static uint32_t timer_hash(uint32_t id) {
    return id % TIMER_HASH_SIZE;
}

static void add_timer_to_wheel(kos_timer_t* timer) {
    uint64_t jiffies = timer->expires / time_state.timer_wheel.resolution_ns;
    uint32_t slot = jiffies % TIMER_WHEEL_SIZE;
    
    timer->next = time_state.timer_wheel.slots[slot];
    timer->prev = NULL;
    if (timer->next) {
        timer->next->prev = timer;
    }
    time_state.timer_wheel.slots[slot] = timer;
}

static void remove_timer_from_wheel(kos_timer_t* timer) {
    if (timer->prev) {
        timer->prev->next = timer->next;
    } else {
        /* Find and update slot head */
        for (int i = 0; i < TIMER_WHEEL_SIZE; i++) {
            if (time_state.timer_wheel.slots[i] == timer) {
                time_state.timer_wheel.slots[i] = timer->next;
                break;
            }
        }
    }
    
    if (timer->next) {
        timer->next->prev = timer->prev;
    }
    
    timer->next = timer->prev = NULL;
}

/* Get time statistics */
void kos_time_get_stats(struct kos_time_stats* stats) {
    if (!stats) {
        return;
    }
    
    pthread_mutex_lock(&time_state.time_lock);
    
    stats->boot_time = time_state.boot_time_ns;
    stats->current_time = kos_time_get_ns();
    stats->timer_interrupts = time_state.timer_interrupts;
    stats->timers_created = time_state.timers_created;
    stats->timers_expired = time_state.timers_expired;
    stats->time_updates = time_state.time_updates;
    stats->active_timers = time_state.hr_timer_queue.count;
    
    if (time_state.current_clocksource) {
        strncpy(stats->clocksource_name, time_state.current_clocksource->name,
                sizeof(stats->clocksource_name) - 1);
        stats->clocksource_name[sizeof(stats->clocksource_name) - 1] = '\0';
        stats->clocksource_frequency = time_state.current_clocksource->frequency;
        stats->clocksource_resolution = time_state.current_clocksource->resolution;
    }
    
    pthread_mutex_unlock(&time_state.time_lock);
}

/* Time statistics structure */
struct kos_time_stats {
    uint64_t boot_time;
    uint64_t current_time;
    uint64_t timer_interrupts;
    uint64_t timers_created;
    uint64_t timers_expired;
    uint64_t time_updates;
    uint32_t active_timers;
    char clocksource_name[32];
    uint64_t clocksource_frequency;
    uint64_t clocksource_resolution;
};

/* Cleanup time management system */
void kos_timer_cleanup(void) {
    if (!time_state.initialized) {
        return;
    }
    
    /* Stop timer thread */
    time_state.timer_thread_running = false;
    if (time_state.timer_thread) {
        pthread_join(time_state.timer_thread, NULL);
    }
    
    /* Clean up all timers */
    pthread_mutex_lock(&time_state.timer_lock);
    
    for (int i = 0; i < TIMER_HASH_SIZE; i++) {
        kos_timer_t* timer = time_state.timer_hash[i];
        while (timer) {
            kos_timer_t* next = timer->hash_next;
            free(timer);
            timer = next;
        }
        time_state.timer_hash[i] = NULL;
    }
    
    pthread_mutex_unlock(&time_state.timer_lock);
    
    /* Destroy mutexes */
    pthread_mutex_destroy(&time_state.time_lock);
    pthread_mutex_destroy(&time_state.timer_lock);
    pthread_mutex_destroy(&time_state.hr_timer_queue.lock);
    
    time_state.initialized = false;
    
    printf("KOS TIMER: Time management system cleaned up\n");
}