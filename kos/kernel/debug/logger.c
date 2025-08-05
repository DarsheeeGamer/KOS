/*
 * KOS Kernel Logging and Debugging System
 * Comprehensive logging with multiple levels and outputs
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <sys/time.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <syslog.h>

/* Log levels */
typedef enum {
    LOG_LEVEL_EMERGENCY = 0,  /* System unusable */
    LOG_LEVEL_ALERT,          /* Action must be taken immediately */
    LOG_LEVEL_CRITICAL,       /* Critical conditions */
    LOG_LEVEL_ERROR,          /* Error conditions */
    LOG_LEVEL_WARNING,        /* Warning conditions */
    LOG_LEVEL_NOTICE,         /* Normal but significant */
    LOG_LEVEL_INFO,           /* Informational */
    LOG_LEVEL_DEBUG,          /* Debug messages */
    LOG_LEVEL_TRACE           /* Detailed trace information */
} log_level_t;

/* Log categories */
typedef enum {
    LOG_CAT_KERNEL = 0,       /* Kernel core */
    LOG_CAT_MM,               /* Memory management */
    LOG_CAT_SCHED,            /* Scheduler */
    LOG_CAT_FS,               /* Filesystem */
    LOG_CAT_NET,              /* Network */
    LOG_CAT_DRIVER,           /* Device drivers */
    LOG_CAT_IPC,              /* Inter-process communication */
    LOG_CAT_SECURITY,         /* Security subsystem */
    LOG_CAT_BOOT,             /* Boot process */
    LOG_CAT_SYSCALL,          /* System calls */
    LOG_CAT_MAX
} log_category_t;

/* Log output destinations */
typedef enum {
    LOG_DEST_NONE = 0,
    LOG_DEST_CONSOLE = 1,     /* Console output */
    LOG_DEST_FILE = 2,        /* File output */
    LOG_DEST_SYSLOG = 4,      /* System log */
    LOG_DEST_BUFFER = 8,      /* Ring buffer */
    LOG_DEST_NETWORK = 16,    /* Network logging */
    LOG_DEST_ALL = 31
} log_destination_t;

/* Log entry structure */
typedef struct log_entry {
    uint64_t timestamp;       /* Microsecond timestamp */
    pid_t pid;                /* Process ID */
    pthread_t tid;            /* Thread ID */
    log_level_t level;        /* Log level */
    log_category_t category;  /* Log category */
    char function[64];        /* Function name */
    char file[128];           /* Source file */
    int line;                 /* Line number */
    char message[512];        /* Log message */
    struct log_entry *next;   /* Next entry in ring buffer */
} log_entry_t;

/* Ring buffer for log entries */
#define LOG_BUFFER_SIZE 4096
static log_entry_t log_buffer[LOG_BUFFER_SIZE];
static volatile int log_buffer_head = 0;
static volatile int log_buffer_tail = 0;
static volatile int log_buffer_count = 0;
static pthread_mutex_t log_buffer_lock = PTHREAD_MUTEX_INITIALIZER;

/* Logger configuration */
struct logger_config {
    log_level_t min_level;                    /* Minimum log level */
    log_destination_t destinations;           /* Output destinations */
    log_level_t category_levels[LOG_CAT_MAX]; /* Per-category levels */
    char log_file_path[256];                  /* Log file path */
    FILE *log_file;                           /* Log file handle */
    bool use_color;                           /* Use color output */
    bool show_timestamp;                      /* Show timestamps */
    bool show_category;                       /* Show category */
    bool show_location;                       /* Show file:line */
    bool show_thread;                         /* Show thread info */
    bool async_logging;                       /* Asynchronous logging */
    pthread_t log_thread;                     /* Background log thread */
    bool log_thread_running;                  /* Log thread status */
    uint64_t log_count[LOG_LEVEL_TRACE + 1];  /* Per-level counters */
    uint64_t total_logs;                      /* Total log count */
    pthread_mutex_t config_lock;              /* Configuration lock */
} logger_config = {
    .min_level = LOG_LEVEL_INFO,
    .destinations = LOG_DEST_CONSOLE | LOG_DEST_BUFFER,
    .use_color = true,
    .show_timestamp = true,
    .show_category = true,
    .show_location = true,
    .show_thread = false,
    .async_logging = true,
    .log_file = NULL,
    .log_thread_running = false,
    .config_lock = PTHREAD_MUTEX_INITIALIZER
};

/* Color codes for different log levels */
static const char *level_colors[] = {
    "\033[1;41m",  /* EMERGENCY - Red background */
    "\033[1;31m",  /* ALERT - Bold red */
    "\033[1;35m",  /* CRITICAL - Bold magenta */
    "\033[1;31m",  /* ERROR - Bold red */
    "\033[1;33m",  /* WARNING - Bold yellow */
    "\033[1;36m",  /* NOTICE - Bold cyan */
    "\033[1;32m",  /* INFO - Bold green */
    "\033[0;37m",  /* DEBUG - White */
    "\033[0;90m"   /* TRACE - Dark gray */
};

static const char *color_reset = "\033[0m";

/* Log level names */
static const char *level_names[] = {
    "EMRG", "ALRT", "CRIT", "ERRO", "WARN", 
    "NOTI", "INFO", "DEBG", "TRCE"
};

/* Log category names */
static const char *category_names[] = {
    "KERN", "MM  ", "SCHD", "FS  ", "NET ", 
    "DRVR", "IPC ", "SEC ", "BOOT", "SYSC"
};

/* Get current timestamp in microseconds */
static uint64_t get_timestamp_us(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000000ULL + tv.tv_usec;
}

/* Format timestamp for display */
static void format_timestamp(uint64_t timestamp_us, char *buffer, size_t buffer_size)
{
    time_t seconds = timestamp_us / 1000000;
    uint32_t microseconds = timestamp_us % 1000000;
    struct tm *tm_info = localtime(&seconds);
    
    snprintf(buffer, buffer_size, "%04d-%02d-%02d %02d:%02d:%02d.%06u",
             tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
             tm_info->tm_hour, tm_info->tm_min, tm_info->tm_sec, microseconds);
}

/* Add entry to ring buffer */
static void add_to_ring_buffer(const log_entry_t *entry)
{
    pthread_mutex_lock(&log_buffer_lock);
    
    /* Copy entry to buffer */
    log_buffer[log_buffer_head] = *entry;
    
    /* Advance head */
    log_buffer_head = (log_buffer_head + 1) % LOG_BUFFER_SIZE;
    
    /* Update count and tail */
    if (log_buffer_count < LOG_BUFFER_SIZE) {
        log_buffer_count++;
    } else {
        log_buffer_tail = (log_buffer_tail + 1) % LOG_BUFFER_SIZE;
    }
    
    pthread_mutex_unlock(&log_buffer_lock);
}

/* Write to console with formatting */
static void write_to_console(const log_entry_t *entry)
{
    char timestamp_str[32];
    char thread_str[32] = "";
    char location_str[256] = "";
    
    /* Format timestamp */
    if (logger_config.show_timestamp) {
        format_timestamp(entry->timestamp, timestamp_str, sizeof(timestamp_str));
    }
    
    /* Format thread info */
    if (logger_config.show_thread) {
        snprintf(thread_str, sizeof(thread_str), " [%lu]", (unsigned long)entry->tid);
    }
    
    /* Format location */
    if (logger_config.show_location) {
        snprintf(location_str, sizeof(location_str), " %s:%d", entry->file, entry->line);
    }
    
    /* Choose output stream based on log level */
    FILE *output = (entry->level <= LOG_LEVEL_ERROR) ? stderr : stdout;
    
    /* Print with or without color */
    if (logger_config.use_color && isatty(fileno(output))) {
        fprintf(output, "%s%s%s",
                level_colors[entry->level],
                logger_config.show_timestamp ? timestamp_str : "",
                logger_config.show_timestamp ? " " : "");
                
        if (logger_config.show_category) {
            fprintf(output, "[%s] ", category_names[entry->category]);
        }
        
        fprintf(output, "%s: %s%s%s%s%s\n",
                level_names[entry->level],
                entry->message,
                thread_str,
                location_str,
                logger_config.show_location ? " in " : "",
                logger_config.show_location ? entry->function : "",
                color_reset);
    } else {
        fprintf(output, "%s%s%s%s: %s%s%s%s%s\n",
                logger_config.show_timestamp ? timestamp_str : "",
                logger_config.show_timestamp ? " " : "",
                logger_config.show_category ? "[" : "",
                logger_config.show_category ? category_names[entry->category] : "",
                logger_config.show_category ? "] " : "",
                level_names[entry->level],
                entry->message,
                thread_str,
                location_str,
                logger_config.show_location ? " in " : "",
                logger_config.show_location ? entry->function : "");
    }
    
    fflush(output);
}

/* Write to log file */
static void write_to_file(const log_entry_t *entry)
{
    if (!logger_config.log_file) {
        return;
    }
    
    char timestamp_str[32];
    format_timestamp(entry->timestamp, timestamp_str, sizeof(timestamp_str));
    
    fprintf(logger_config.log_file, "%s [%s] %s: PID=%d TID=%lu %s:%d %s() - %s\n",
            timestamp_str,
            category_names[entry->category],
            level_names[entry->level],
            entry->pid,
            (unsigned long)entry->tid,
            entry->file,
            entry->line,
            entry->function,
            entry->message);
    
    fflush(logger_config.log_file);
}

/* Write to syslog */
static void write_to_syslog(const log_entry_t *entry)
{
    int syslog_priority;
    
    /* Map our log levels to syslog priorities */
    switch (entry->level) {
        case LOG_LEVEL_EMERGENCY: syslog_priority = LOG_EMERG; break;
        case LOG_LEVEL_ALERT:     syslog_priority = LOG_ALERT; break;
        case LOG_LEVEL_CRITICAL:  syslog_priority = LOG_CRIT; break;
        case LOG_LEVEL_ERROR:     syslog_priority = LOG_ERR; break;
        case LOG_LEVEL_WARNING:   syslog_priority = LOG_WARNING; break;
        case LOG_LEVEL_NOTICE:    syslog_priority = LOG_NOTICE; break;
        case LOG_LEVEL_INFO:      syslog_priority = LOG_INFO; break;
        case LOG_LEVEL_DEBUG:
        case LOG_LEVEL_TRACE:     syslog_priority = LOG_DEBUG; break;
        default:                  syslog_priority = LOG_INFO; break;
    }
    
    syslog(syslog_priority, "[%s] %s:%d %s() - %s",
           category_names[entry->category],
           entry->file,
           entry->line,
           entry->function,
           entry->message);
}

/* Background logging thread */
static void *log_thread_func(void *arg)
{
    (void)arg;
    
    while (logger_config.log_thread_running) {
        /* Process any pending log entries from buffer */
        if (log_buffer_count > 0) {
            pthread_mutex_lock(&log_buffer_lock);
            
            if (log_buffer_count > 0) {
                log_entry_t entry = log_buffer[log_buffer_tail];
                log_buffer_tail = (log_buffer_tail + 1) % LOG_BUFFER_SIZE;
                log_buffer_count--;
                
                pthread_mutex_unlock(&log_buffer_lock);
                
                /* Write to configured destinations */
                if (logger_config.destinations & LOG_DEST_FILE) {
                    write_to_file(&entry);
                }
                if (logger_config.destinations & LOG_DEST_SYSLOG) {
                    write_to_syslog(&entry);
                }
            } else {
                pthread_mutex_unlock(&log_buffer_lock);
            }
        } else {
            usleep(1000); /* 1ms sleep when no logs */
        }
    }
    
    return NULL;
}

/* Core logging function */
static void kos_log_internal(log_level_t level, log_category_t category,
                            const char *file, int line, const char *function,
                            const char *format, va_list args)
{
    /* Check if this log should be processed */
    if (level > logger_config.min_level ||
        level > logger_config.category_levels[category]) {
        return;
    }
    
    /* Create log entry */
    log_entry_t entry = {0};
    entry.timestamp = get_timestamp_us();
    entry.pid = getpid();
    entry.tid = pthread_self();
    entry.level = level;
    entry.category = category;
    entry.line = line;
    
    /* Copy strings safely */
    strncpy(entry.function, function, sizeof(entry.function) - 1);
    entry.function[sizeof(entry.function) - 1] = '\0';
    
    const char *filename = strrchr(file, '/');
    filename = filename ? filename + 1 : file;
    strncpy(entry.file, filename, sizeof(entry.file) - 1);
    entry.file[sizeof(entry.file) - 1] = '\0';
    
    vsnprintf(entry.message, sizeof(entry.message), format, args);
    
    /* Update statistics */
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.log_count[level]++;
    logger_config.total_logs++;
    pthread_mutex_unlock(&logger_config.config_lock);
    
    /* Output to destinations */
    if (logger_config.destinations & LOG_DEST_CONSOLE) {
        write_to_console(&entry);
    }
    
    if (logger_config.destinations & LOG_DEST_BUFFER) {
        add_to_ring_buffer(&entry);
    }
    
    if (logger_config.async_logging) {
        /* Async logging handled by background thread */
        if (logger_config.destinations & (LOG_DEST_FILE | LOG_DEST_SYSLOG)) {
            add_to_ring_buffer(&entry);
        }
    } else {
        /* Synchronous logging */
        if (logger_config.destinations & LOG_DEST_FILE) {
            write_to_file(&entry);
        }
        if (logger_config.destinations & LOG_DEST_SYSLOG) {
            write_to_syslog(&entry);
        }
    }
}

/* Public logging functions */
void kos_log(log_level_t level, log_category_t category,
             const char *file, int line, const char *function,
             const char *format, ...)
{
    va_list args;
    va_start(args, format);
    kos_log_internal(level, category, file, line, function, format, args);
    va_end(args);
}

/* Convenience macros for different log levels */
#define KOS_LOG_EMERGENCY(cat, fmt, ...) \
    kos_log(LOG_LEVEL_EMERGENCY, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_ALERT(cat, fmt, ...) \
    kos_log(LOG_LEVEL_ALERT, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_CRITICAL(cat, fmt, ...) \
    kos_log(LOG_LEVEL_CRITICAL, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_ERROR(cat, fmt, ...) \
    kos_log(LOG_LEVEL_ERROR, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_WARNING(cat, fmt, ...) \
    kos_log(LOG_LEVEL_WARNING, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_NOTICE(cat, fmt, ...) \
    kos_log(LOG_LEVEL_NOTICE, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_INFO(cat, fmt, ...) \
    kos_log(LOG_LEVEL_INFO, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_DEBUG(cat, fmt, ...) \
    kos_log(LOG_LEVEL_DEBUG, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

#define KOS_LOG_TRACE(cat, fmt, ...) \
    kos_log(LOG_LEVEL_TRACE, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

/* Configuration functions */
int kos_log_set_level(log_level_t level)
{
    if (level > LOG_LEVEL_TRACE) {
        return -1;
    }
    
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.min_level = level;
    pthread_mutex_unlock(&logger_config.config_lock);
    
    return 0;
}

int kos_log_set_category_level(log_category_t category, log_level_t level)
{
    if (category >= LOG_CAT_MAX || level > LOG_LEVEL_TRACE) {
        return -1;
    }
    
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.category_levels[category] = level;
    pthread_mutex_unlock(&logger_config.config_lock);
    
    return 0;
}

int kos_log_set_destinations(log_destination_t destinations)
{
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.destinations = destinations;
    pthread_mutex_unlock(&logger_config.config_lock);
    
    return 0;
}

int kos_log_set_file(const char *filepath)
{
    if (!filepath) {
        return -1;
    }
    
    pthread_mutex_lock(&logger_config.config_lock);
    
    /* Close existing file */
    if (logger_config.log_file) {
        fclose(logger_config.log_file);
        logger_config.log_file = NULL;
    }
    
    /* Open new file */
    logger_config.log_file = fopen(filepath, "a");
    if (!logger_config.log_file) {
        pthread_mutex_unlock(&logger_config.config_lock);
        return -1;
    }
    
    strncpy(logger_config.log_file_path, filepath, sizeof(logger_config.log_file_path) - 1);
    logger_config.log_file_path[sizeof(logger_config.log_file_path) - 1] = '\0';
    
    pthread_mutex_unlock(&logger_config.config_lock);
    
    return 0;
}

void kos_log_set_color(bool use_color)
{
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.use_color = use_color;
    pthread_mutex_unlock(&logger_config.config_lock);
}

void kos_log_set_timestamp(bool show_timestamp)
{
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.show_timestamp = show_timestamp;
    pthread_mutex_unlock(&logger_config.config_lock);
}

void kos_log_set_async(bool async_logging)
{
    pthread_mutex_lock(&logger_config.config_lock);
    logger_config.async_logging = async_logging;
    pthread_mutex_unlock(&logger_config.config_lock);
}

/* Buffer management */
int kos_log_get_buffer_entries(log_entry_t *entries, int max_entries)
{
    if (!entries || max_entries <= 0) {
        return -1;
    }
    
    pthread_mutex_lock(&log_buffer_lock);
    
    int count = (log_buffer_count < max_entries) ? log_buffer_count : max_entries;
    int tail = log_buffer_tail;
    
    for (int i = 0; i < count; i++) {
        entries[i] = log_buffer[tail];
        tail = (tail + 1) % LOG_BUFFER_SIZE;
    }
    
    pthread_mutex_unlock(&log_buffer_lock);
    
    return count;
}

void kos_log_clear_buffer(void)
{
    pthread_mutex_lock(&log_buffer_lock);
    log_buffer_head = 0;
    log_buffer_tail = 0;
    log_buffer_count = 0;
    pthread_mutex_unlock(&log_buffer_lock);
}

/* Statistics */
void kos_log_print_stats(void)
{
    pthread_mutex_lock(&logger_config.config_lock);
    
    printf("\nKOS Logging Statistics:\n");
    printf("=======================\n");
    printf("Total logs:     %lu\n", logger_config.total_logs);
    printf("Emergency:      %lu\n", logger_config.log_count[LOG_LEVEL_EMERGENCY]);
    printf("Alert:          %lu\n", logger_config.log_count[LOG_LEVEL_ALERT]);
    printf("Critical:       %lu\n", logger_config.log_count[LOG_LEVEL_CRITICAL]);
    printf("Error:          %lu\n", logger_config.log_count[LOG_LEVEL_ERROR]);
    printf("Warning:        %lu\n", logger_config.log_count[LOG_LEVEL_WARNING]);
    printf("Notice:         %lu\n", logger_config.log_count[LOG_LEVEL_NOTICE]);
    printf("Info:           %lu\n", logger_config.log_count[LOG_LEVEL_INFO]);
    printf("Debug:          %lu\n", logger_config.log_count[LOG_LEVEL_DEBUG]);
    printf("Trace:          %lu\n", logger_config.log_count[LOG_LEVEL_TRACE]);
    printf("Buffer entries: %d/%d\n", log_buffer_count, LOG_BUFFER_SIZE);
    
    pthread_mutex_unlock(&logger_config.config_lock);
}

/* Dump recent logs */
void kos_log_dump_recent(int count)
{
    log_entry_t *entries = malloc(count * sizeof(log_entry_t));
    if (!entries) {
        return;
    }
    
    int actual_count = kos_log_get_buffer_entries(entries, count);
    
    printf("\nRecent Log Entries (%d):\n", actual_count);
    printf("========================\n");
    
    for (int i = 0; i < actual_count; i++) {
        char timestamp_str[32];
        format_timestamp(entries[i].timestamp, timestamp_str, sizeof(timestamp_str));
        
        printf("%s [%s] %s: %s:%d %s() - %s\n",
               timestamp_str,
               category_names[entries[i].category],
               level_names[entries[i].level],
               entries[i].file,
               entries[i].line,
               entries[i].function,
               entries[i].message);
    }
    
    free(entries);
}

/* Initialization and cleanup */
int kos_log_init(void)
{
    /* Initialize category levels */
    for (int i = 0; i < LOG_CAT_MAX; i++) {
        logger_config.category_levels[i] = LOG_LEVEL_INFO;
    }
    
    /* Initialize syslog */
    openlog("kos", LOG_PID | LOG_CONS, LOG_KERN);
    
    /* Start background logging thread if async logging is enabled */
    if (logger_config.async_logging) {
        logger_config.log_thread_running = true;
        if (pthread_create(&logger_config.log_thread, NULL, log_thread_func, NULL) != 0) {
            logger_config.log_thread_running = false;
            return -1;
        }
    }
    
    KOS_LOG_INFO(LOG_CAT_KERNEL, "KOS logging system initialized");
    
    return 0;
}

void kos_log_cleanup(void)
{
    KOS_LOG_INFO(LOG_CAT_KERNEL, "KOS logging system shutting down");
    
    /* Stop background thread */
    if (logger_config.log_thread_running) {
        logger_config.log_thread_running = false;
        pthread_join(logger_config.log_thread, NULL);
    }
    
    /* Close log file */
    pthread_mutex_lock(&logger_config.config_lock);
    if (logger_config.log_file) {
        fclose(logger_config.log_file);
        logger_config.log_file = NULL;
    }
    pthread_mutex_unlock(&logger_config.config_lock);
    
    /* Close syslog */
    closelog();
}

/* Panic function for critical errors */
void kos_panic(const char *file, int line, const char *function, const char *format, ...)
{
    va_list args;
    va_start(args, format);
    
    /* Force emergency level logging to all destinations */
    log_level_t old_level = logger_config.min_level;
    log_destination_t old_dest = logger_config.destinations;
    
    logger_config.min_level = LOG_LEVEL_EMERGENCY;
    logger_config.destinations = LOG_DEST_ALL;
    
    kos_log_internal(LOG_LEVEL_EMERGENCY, LOG_CAT_KERNEL, file, line, function, format, args);
    
    va_end(args);
    
    /* Restore settings */
    logger_config.min_level = old_level;
    logger_config.destinations = old_dest;
    
    /* Dump recent logs */
    kos_log_dump_recent(50);
    
    /* Force sync all log outputs */
    if (logger_config.log_file) {
        fflush(logger_config.log_file);
        fsync(fileno(logger_config.log_file));
    }
    
    abort();
}

#define KOS_PANIC(fmt, ...) \
    kos_panic(__FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__)

/* Debug assertion macro */
#ifdef DEBUG
#define KOS_ASSERT(condition) \
    do { \
        if (!(condition)) { \
            KOS_PANIC("Assertion failed: %s", #condition); \
        } \
    } while (0)
#else
#define KOS_ASSERT(condition) ((void)0)
#endif

/* Memory debugging helpers */
void kos_log_hex_dump(log_level_t level, log_category_t category,
                      const char *prefix, const void *data, size_t len)
{
    const unsigned char *bytes = (const unsigned char *)data;
    char hex_str[49]; /* 16 * 3 + 1 */
    char ascii_str[17]; /* 16 + 1 */
    
    for (size_t i = 0; i < len; i += 16) {
        memset(hex_str, 0, sizeof(hex_str));
        memset(ascii_str, 0, sizeof(ascii_str));
        
        /* Format hex bytes */
        for (size_t j = 0; j < 16 && i + j < len; j++) {
            sprintf(hex_str + j * 3, "%02x ", bytes[i + j]);
            ascii_str[j] = (bytes[i + j] >= 32 && bytes[i + j] <= 126) ? bytes[i + j] : '.';
        }
        
        kos_log(level, category, __FILE__, __LINE__, __func__,
                "%s %04zx: %-48s |%s|", prefix, i, hex_str, ascii_str);
    }
}

/* Performance timing helpers */
typedef struct {
    uint64_t start_time;
    const char *name;
    log_category_t category;
} kos_timer_t;

static kos_timer_t kos_timer_start(const char *name, log_category_t category)
{
    kos_timer_t timer = {
        .start_time = get_timestamp_us(),
        .name = name,
        .category = category
    };
    
    KOS_LOG_TRACE(category, "Timer started: %s", name);
    return timer;
}

static void kos_timer_end(kos_timer_t *timer)
{
    uint64_t end_time = get_timestamp_us();
    uint64_t duration = end_time - timer->start_time;
    
    KOS_LOG_DEBUG(timer->category, "Timer %s: %lu microseconds", timer->name, duration);
}

#define KOS_TIMER_START(name, cat) kos_timer_t _timer = kos_timer_start(name, cat)
#define KOS_TIMER_END() kos_timer_end(&_timer)