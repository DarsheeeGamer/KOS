/*
 * KOS Kernel Tracing and Profiling System
 * Runtime tracing with minimal overhead
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <sys/time.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>

/* Trace event types */
typedef enum {
    TRACE_EVENT_SYSCALL_ENTER = 0,
    TRACE_EVENT_SYSCALL_EXIT,
    TRACE_EVENT_INTERRUPT_ENTER,
    TRACE_EVENT_INTERRUPT_EXIT,
    TRACE_EVENT_SCHED_SWITCH,
    TRACE_EVENT_SCHED_WAKEUP,
    TRACE_EVENT_MM_ALLOC,
    TRACE_EVENT_MM_FREE,
    TRACE_EVENT_FS_OPEN,
    TRACE_EVENT_FS_CLOSE,
    TRACE_EVENT_FS_READ,
    TRACE_EVENT_FS_WRITE,
    TRACE_EVENT_NET_SEND,
    TRACE_EVENT_NET_RECV,
    TRACE_EVENT_LOCK_ACQUIRE,
    TRACE_EVENT_LOCK_RELEASE,
    TRACE_EVENT_CUSTOM,
    TRACE_EVENT_MAX
} trace_event_type_t;

/* Trace event flags */
#define TRACE_FLAG_NONE        0x00
#define TRACE_FLAG_STACK_TRACE 0x01
#define TRACE_FLAG_TIMESTAMP   0x02
#define TRACE_FLAG_CPU_ID      0x04
#define TRACE_FLAG_PROCESS_CTX 0x08

/* Trace event structure */
typedef struct trace_event {
    uint64_t timestamp;           /* Event timestamp */
    trace_event_type_t type;      /* Event type */
    uint32_t flags;               /* Event flags */
    pid_t pid;                    /* Process ID */
    pid_t tid;                    /* Thread ID */
    uint32_t cpu_id;              /* CPU ID */
    uint64_t arg1, arg2, arg3;    /* Generic arguments */
    char data[256];               /* Event-specific data */
    void *stack_trace[16];        /* Stack backtrace */
    int stack_depth;              /* Stack trace depth */
} trace_event_t;

/* Trace buffer configuration */
#define TRACE_BUFFER_SIZE (1024 * 1024)  /* 1M events */
#define TRACE_PER_CPU_BUFFER_SIZE (TRACE_BUFFER_SIZE / MAX_CPUS)

/* Per-CPU trace buffer */
typedef struct trace_buffer {
    trace_event_t *events;        /* Event array */
    volatile uint32_t head;       /* Write position */
    volatile uint32_t tail;       /* Read position */
    volatile uint32_t count;      /* Event count */
    uint32_t size;                /* Buffer size */
    uint32_t overruns;            /* Overrun count */
    pthread_spinlock_t lock;      /* Buffer lock */
} trace_buffer_t;

/* Global trace state */
static struct {
    bool enabled;                                    /* Tracing enabled */
    uint64_t event_mask;                            /* Event type mask */
    trace_buffer_t cpu_buffers[MAX_CPUS];          /* Per-CPU buffers */
    uint32_t nr_cpus;                               /* Number of CPUs */
    pthread_t reader_thread;                        /* Reader thread */
    bool reader_running;                            /* Reader status */
    FILE *trace_file;                               /* Trace output file */
    char trace_file_path[256];                      /* Trace file path */
    uint64_t total_events;                          /* Total events */
    uint64_t lost_events;                           /* Lost events */
    uint64_t event_counts[TRACE_EVENT_MAX];        /* Per-type counts */
    pthread_mutex_t config_lock;                    /* Configuration lock */
} trace_state = {
    .enabled = false,
    .event_mask = 0xFFFFFFFFFFFFFFFF,  /* All events enabled by default */
    .nr_cpus = 1,
    .config_lock = PTHREAD_MUTEX_INITIALIZER
};

/* Event type names */
static const char *trace_event_names[] = {
    "SYSCALL_ENTER",
    "SYSCALL_EXIT",
    "INTERRUPT_ENTER",
    "INTERRUPT_EXIT",
    "SCHED_SWITCH",
    "SCHED_WAKEUP",
    "MM_ALLOC",
    "MM_FREE",
    "FS_OPEN",
    "FS_CLOSE",
    "FS_READ",
    "FS_WRITE",
    "NET_SEND",
    "NET_RECV",
    "LOCK_ACQUIRE",
    "LOCK_RELEASE",
    "CUSTOM"
};

/* Get current CPU ID */
static inline uint32_t get_cpu_id(void)
{
    /* Simplified - in real kernel this would use CPU-specific instructions */
    return 0;
}

/* Get current timestamp */
static inline uint64_t get_trace_timestamp(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

/* Get stack backtrace */
static int get_stack_trace(void **buffer, int max_depth)
{
    /* Simplified backtrace - in real kernel this would walk stack frames */
    int depth = 0;
    
    /* Get return addresses from stack */
    void *frame = __builtin_frame_address(0);
    while (frame && depth < max_depth) {
        void **fp = (void **)frame;
        void *ret_addr = fp[1];
        
        if (!ret_addr) break;
        
        buffer[depth++] = ret_addr;
        frame = fp[0];
        
        /* Sanity check to prevent infinite loops */
        if (frame <= fp || (char *)frame - (char *)fp > 8192) {
            break;
        }
    }
    
    return depth;
}

/* Add event to trace buffer */
static void trace_add_event(trace_event_t *event)
{
    if (!trace_state.enabled) {
        return;
    }
    
    /* Check event mask */
    if (!(trace_state.event_mask & (1ULL << event->type))) {
        return;
    }
    
    uint32_t cpu = get_cpu_id();
    if (cpu >= trace_state.nr_cpus) {
        cpu = 0;
    }
    
    trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
    
    pthread_spin_lock(&buffer->lock);
    
    /* Check for buffer full */
    if (buffer->count >= buffer->size) {
        buffer->overruns++;
        trace_state.lost_events++;
        
        /* Overwrite oldest event */
        buffer->tail = (buffer->tail + 1) % buffer->size;
        buffer->count--;
    }
    
    /* Copy event to buffer */
    buffer->events[buffer->head] = *event;
    buffer->head = (buffer->head + 1) % buffer->size;
    buffer->count++;
    
    /* Update statistics */
    trace_state.total_events++;
    trace_state.event_counts[event->type]++;
    
    pthread_spin_unlock(&buffer->lock);
}

/* Core trace function */
void kos_trace_event(trace_event_type_t type, uint32_t flags,
                     uint64_t arg1, uint64_t arg2, uint64_t arg3,
                     const char *format, ...)
{
    if (!trace_state.enabled) {
        return;
    }
    
    trace_event_t event = {0};
    
    /* Fill basic event data */
    event.timestamp = get_trace_timestamp();
    event.type = type;
    event.flags = flags;
    event.pid = getpid();
    event.tid = pthread_self();
    event.cpu_id = get_cpu_id();
    event.arg1 = arg1;
    event.arg2 = arg2;
    event.arg3 = arg3;
    
    /* Format event-specific data */
    if (format) {
        va_list args;
        va_start(args, format);
        vsnprintf(event.data, sizeof(event.data), format, args);
        va_end(args);
    }
    
    /* Get stack trace if requested */
    if (flags & TRACE_FLAG_STACK_TRACE) {
        event.stack_depth = get_stack_trace(event.stack_trace, 16);
    }
    
    /* Add to trace buffer */
    trace_add_event(&event);
}

/* Specialized trace functions */
void kos_trace_syscall_enter(int syscall_nr, uint64_t arg1, uint64_t arg2, uint64_t arg3)
{
    kos_trace_event(TRACE_EVENT_SYSCALL_ENTER, 
                    TRACE_FLAG_TIMESTAMP | TRACE_FLAG_PROCESS_CTX,
                    syscall_nr, arg1, arg2,
                    "syscall=%d", syscall_nr);
}

void kos_trace_syscall_exit(int syscall_nr, int64_t result)
{
    kos_trace_event(TRACE_EVENT_SYSCALL_EXIT,
                    TRACE_FLAG_TIMESTAMP | TRACE_FLAG_PROCESS_CTX,
                    syscall_nr, result, 0,
                    "syscall=%d result=%ld", syscall_nr, result);
}

void kos_trace_sched_switch(pid_t prev_pid, pid_t next_pid)
{
    kos_trace_event(TRACE_EVENT_SCHED_SWITCH,
                    TRACE_FLAG_TIMESTAMP | TRACE_FLAG_CPU_ID,
                    prev_pid, next_pid, 0,
                    "prev_pid=%d next_pid=%d", prev_pid, next_pid);
}

void kos_trace_mm_alloc(void *addr, size_t size, const char *caller)
{
    kos_trace_event(TRACE_EVENT_MM_ALLOC,
                    TRACE_FLAG_TIMESTAMP | TRACE_FLAG_STACK_TRACE,
                    (uint64_t)addr, size, 0,
                    "addr=%p size=%zu caller=%s", addr, size, caller);
}

void kos_trace_mm_free(void *addr, const char *caller)
{
    kos_trace_event(TRACE_EVENT_MM_FREE,
                    TRACE_FLAG_TIMESTAMP | TRACE_FLAG_STACK_TRACE,
                    (uint64_t)addr, 0, 0,
                    "addr=%p caller=%s", addr, caller);
}

/* Format event for output */
static void format_trace_event(trace_event_t *event, char *buffer, size_t buffer_size)
{
    char timestamp_str[32];
    struct tm *tm_info;
    time_t seconds = event->timestamp / 1000000000;
    uint32_t nanoseconds = event->timestamp % 1000000000;
    
    tm_info = localtime(&seconds);
    strftime(timestamp_str, sizeof(timestamp_str), "%H:%M:%S", tm_info);
    
    snprintf(buffer, buffer_size,
             "%s.%09u [%05d:%lu] CPU%u %s: %s (args: %lx,%lx,%lx)",
             timestamp_str, nanoseconds,
             event->pid, (unsigned long)event->tid,
             event->cpu_id,
             trace_event_names[event->type],
             event->data,
             event->arg1, event->arg2, event->arg3);
}

/* Trace reader thread */
static void *trace_reader_thread(void *arg)
{
    (void)arg;
    char output_buffer[1024];
    
    while (trace_state.reader_running) {
        bool found_events = false;
        
        /* Process events from all CPU buffers */
        for (uint32_t cpu = 0; cpu < trace_state.nr_cpus; cpu++) {
            trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
            
            pthread_spin_lock(&buffer->lock);
            
            while (buffer->count > 0) {
                trace_event_t event = buffer->events[buffer->tail];
                buffer->tail = (buffer->tail + 1) % buffer->size;
                buffer->count--;
                
                pthread_spin_unlock(&buffer->lock);
                
                /* Format and output event */
                format_trace_event(&event, output_buffer, sizeof(output_buffer));
                
                if (trace_state.trace_file) {
                    fprintf(trace_state.trace_file, "%s\n", output_buffer);
                    fflush(trace_state.trace_file);
                } else {
                    printf("%s\n", output_buffer);
                }
                
                /* Output stack trace if available */
                if (event.stack_depth > 0) {
                    for (int i = 0; i < event.stack_depth; i++) {
                        if (trace_state.trace_file) {
                            fprintf(trace_state.trace_file, "  [%d] %p\n", i, event.stack_trace[i]);
                        } else {
                            printf("  [%d] %p\n", i, event.stack_trace[i]);
                        }
                    }
                }
                
                found_events = true;
                pthread_spin_lock(&buffer->lock);
            }
            
            pthread_spin_unlock(&buffer->lock);
        }
        
        if (!found_events) {
            usleep(10000); /* 10ms sleep when no events */
        }
    }
    
    return NULL;
}

/* Trace control functions */
int kos_trace_enable(void)
{
    pthread_mutex_lock(&trace_state.config_lock);
    
    if (trace_state.enabled) {
        pthread_mutex_unlock(&trace_state.config_lock);
        return 0;
    }
    
    /* Start reader thread */
    trace_state.reader_running = true;
    if (pthread_create(&trace_state.reader_thread, NULL, trace_reader_thread, NULL) != 0) {
        trace_state.reader_running = false;
        pthread_mutex_unlock(&trace_state.config_lock);
        return -1;
    }
    
    trace_state.enabled = true;
    pthread_mutex_unlock(&trace_state.config_lock);
    
    return 0;
}

void kos_trace_disable(void)
{
    pthread_mutex_lock(&trace_state.config_lock);
    
    if (!trace_state.enabled) {
        pthread_mutex_unlock(&trace_state.config_lock);
        return;
    }
    
    trace_state.enabled = false;
    
    /* Stop reader thread */
    trace_state.reader_running = false;
    pthread_join(trace_state.reader_thread, NULL);
    
    pthread_mutex_unlock(&trace_state.config_lock);
}

int kos_trace_set_mask(uint64_t event_mask)
{
    pthread_mutex_lock(&trace_state.config_lock);
    trace_state.event_mask = event_mask;
    pthread_mutex_unlock(&trace_state.config_lock);
    return 0;
}

int kos_trace_set_output(const char *filepath)
{
    pthread_mutex_lock(&trace_state.config_lock);
    
    /* Close existing file */
    if (trace_state.trace_file) {
        fclose(trace_state.trace_file);
        trace_state.trace_file = NULL;
    }
    
    if (filepath) {
        trace_state.trace_file = fopen(filepath, "w");
        if (!trace_state.trace_file) {
            pthread_mutex_unlock(&trace_state.config_lock);
            return -1;
        }
        strncpy(trace_state.trace_file_path, filepath, sizeof(trace_state.trace_file_path) - 1);
    }
    
    pthread_mutex_unlock(&trace_state.config_lock);
    return 0;
}

/* Get trace statistics */
void kos_trace_print_stats(void)
{
    pthread_mutex_lock(&trace_state.config_lock);
    
    printf("\nKOS Trace Statistics:\n");
    printf("=====================\n");
    printf("Enabled:        %s\n", trace_state.enabled ? "Yes" : "No");
    printf("Total events:   %lu\n", trace_state.total_events);
    printf("Lost events:    %lu\n", trace_state.lost_events);
    printf("\nEvent counts:\n");
    
    for (int i = 0; i < TRACE_EVENT_MAX; i++) {
        if (trace_state.event_counts[i] > 0) {
            printf("  %-20s: %lu\n", trace_event_names[i], trace_state.event_counts[i]);
        }
    }
    
    printf("\nPer-CPU buffer stats:\n");
    for (uint32_t cpu = 0; cpu < trace_state.nr_cpus; cpu++) {
        trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
        printf("  CPU%u: %u/%u events, %u overruns\n",
               cpu, buffer->count, buffer->size, buffer->overruns);
    }
    
    pthread_mutex_unlock(&trace_state.config_lock);
}

/* Clear trace buffers */
void kos_trace_clear_buffers(void)
{
    for (uint32_t cpu = 0; cpu < trace_state.nr_cpus; cpu++) {
        trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
        
        pthread_spin_lock(&buffer->lock);
        buffer->head = 0;
        buffer->tail = 0;
        buffer->count = 0;
        buffer->overruns = 0;
        pthread_spin_unlock(&buffer->lock);
    }
    
    /* Clear statistics */
    pthread_mutex_lock(&trace_state.config_lock);
    trace_state.total_events = 0;
    trace_state.lost_events = 0;
    memset(trace_state.event_counts, 0, sizeof(trace_state.event_counts));
    pthread_mutex_unlock(&trace_state.config_lock);
}

/* Initialize trace system */
int kos_trace_init(uint32_t nr_cpus)
{
    if (nr_cpus == 0 || nr_cpus > MAX_CPUS) {
        nr_cpus = 1;
    }
    
    trace_state.nr_cpus = nr_cpus;
    
    /* Initialize per-CPU buffers */
    for (uint32_t cpu = 0; cpu < nr_cpus; cpu++) {
        trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
        
        buffer->size = TRACE_PER_CPU_BUFFER_SIZE;
        buffer->events = malloc(buffer->size * sizeof(trace_event_t));
        if (!buffer->events) {
            /* Cleanup already allocated buffers */
            for (uint32_t i = 0; i < cpu; i++) {
                free(trace_state.cpu_buffers[i].events);
            }
            return -1;
        }
        
        buffer->head = 0;
        buffer->tail = 0;
        buffer->count = 0;
        buffer->overruns = 0;
        
        if (pthread_spin_init(&buffer->lock, PTHREAD_PROCESS_PRIVATE) != 0) {
            /* Cleanup */
            for (uint32_t i = 0; i <= cpu; i++) {
                free(trace_state.cpu_buffers[i].events);
                if (i < cpu) {
                    pthread_spin_destroy(&trace_state.cpu_buffers[i].lock);
                }
            }
            return -1;
        }
    }
    
    return 0;
}

/* Cleanup trace system */
void kos_trace_cleanup(void)
{
    /* Disable tracing */
    kos_trace_disable();
    
    /* Free per-CPU buffers */
    for (uint32_t cpu = 0; cpu < trace_state.nr_cpus; cpu++) {
        trace_buffer_t *buffer = &trace_state.cpu_buffers[cpu];
        
        if (buffer->events) {
            free(buffer->events);
            buffer->events = NULL;
        }
        
        pthread_spin_destroy(&buffer->lock);
    }
    
    /* Close trace file */
    pthread_mutex_lock(&trace_state.config_lock);
    if (trace_state.trace_file) {
        fclose(trace_state.trace_file);
        trace_state.trace_file = NULL;
    }
    pthread_mutex_unlock(&trace_state.config_lock);
}

/* Trace points for various subsystems */
#define TRACE_SYSCALL_ENTER(nr, a1, a2, a3) \
    kos_trace_syscall_enter(nr, a1, a2, a3)

#define TRACE_SYSCALL_EXIT(nr, result) \
    kos_trace_syscall_exit(nr, result)

#define TRACE_SCHED_SWITCH(prev, next) \
    kos_trace_sched_switch(prev, next)

#define TRACE_MM_ALLOC(addr, size) \
    kos_trace_mm_alloc(addr, size, __func__)

#define TRACE_MM_FREE(addr) \
    kos_trace_mm_free(addr, __func__)

#define TRACE_CUSTOM(fmt, ...) \
    kos_trace_event(TRACE_EVENT_CUSTOM, TRACE_FLAG_TIMESTAMP, \
                    0, 0, 0, fmt, ##__VA_ARGS__)

/* Performance profiling helpers */
typedef struct {
    uint64_t start_time;
    const char *name;
} kos_profile_t;

static inline kos_profile_t kos_profile_start(const char *name)
{
    kos_profile_t profile = {
        .start_time = get_trace_timestamp(),
        .name = name
    };
    
    TRACE_CUSTOM("Profile start: %s", name);
    return profile;
}

static inline void kos_profile_end(kos_profile_t *profile)
{
    uint64_t end_time = get_trace_timestamp();
    uint64_t duration = end_time - profile->start_time;
    
    TRACE_CUSTOM("Profile end: %s, duration=%lu ns", profile->name, duration);
}

#define PROFILE_START(name) kos_profile_t _profile = kos_profile_start(name)
#define PROFILE_END() kos_profile_end(&_profile)