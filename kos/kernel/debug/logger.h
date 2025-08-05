/*
 * KOS Kernel Logging and Debugging System Header
 */

#ifndef _KOS_LOGGER_H
#define _KOS_LOGGER_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>

/* Log levels */
typedef enum {
    LOG_LEVEL_EMERGENCY = 0,
    LOG_LEVEL_ALERT,
    LOG_LEVEL_CRITICAL,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_NOTICE,
    LOG_LEVEL_INFO,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_TRACE
} log_level_t;

/* Log categories */
typedef enum {
    LOG_CAT_KERNEL = 0,
    LOG_CAT_MM,
    LOG_CAT_SCHED,
    LOG_CAT_FS,
    LOG_CAT_NET,
    LOG_CAT_DRIVER,
    LOG_CAT_IPC,
    LOG_CAT_SECURITY,
    LOG_CAT_BOOT,
    LOG_CAT_SYSCALL,
    LOG_CAT_MAX
} log_category_t;

/* Log output destinations */
typedef enum {
    LOG_DEST_NONE = 0,
    LOG_DEST_CONSOLE = 1,
    LOG_DEST_FILE = 2,
    LOG_DEST_SYSLOG = 4,
    LOG_DEST_BUFFER = 8,
    LOG_DEST_NETWORK = 16,
    LOG_DEST_ALL = 31
} log_destination_t;

/* Log entry structure */
typedef struct log_entry {
    uint64_t timestamp;
    pid_t pid;
    pthread_t tid;
    log_level_t level;
    log_category_t category;
    char function[64];
    char file[128];
    int line;
    char message[512];
    struct log_entry *next;
} log_entry_t;

/* Core logging function */
void kos_log(log_level_t level, log_category_t category,
             const char *file, int line, const char *function,
             const char *format, ...);

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
int kos_log_set_level(log_level_t level);
int kos_log_set_category_level(log_category_t category, log_level_t level);
int kos_log_set_destinations(log_destination_t destinations);
int kos_log_set_file(const char *filepath);
void kos_log_set_color(bool use_color);
void kos_log_set_timestamp(bool show_timestamp);
void kos_log_set_async(bool async_logging);

/* Buffer management */
int kos_log_get_buffer_entries(log_entry_t *entries, int max_entries);
void kos_log_clear_buffer(void);

/* Statistics and debugging */
void kos_log_print_stats(void);
void kos_log_dump_recent(int count);

/* Initialization and cleanup */
int kos_log_init(void);
void kos_log_cleanup(void);

/* Panic function */
void kos_panic(const char *file, int line, const char *function, const char *format, ...);

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
                      const char *prefix, const void *data, size_t len);

/* Performance timing helpers */
typedef struct {
    uint64_t start_time;
    const char *name;
    log_category_t category;
} kos_timer_t;

#define KOS_TIMER_START(name, cat) kos_timer_t _timer = kos_timer_start(name, cat)
#define KOS_TIMER_END() kos_timer_end(&_timer)

/* Function entry/exit tracing */
#ifdef TRACE_FUNCTIONS
#define KOS_FUNC_ENTER(cat) KOS_LOG_TRACE(cat, "ENTER")
#define KOS_FUNC_EXIT(cat) KOS_LOG_TRACE(cat, "EXIT")
#else
#define KOS_FUNC_ENTER(cat) ((void)0)
#define KOS_FUNC_EXIT(cat) ((void)0)
#endif

/* Conditional debugging */
#define KOS_DEBUG_IF(condition, cat, fmt, ...) \
    do { \
        if (condition) { \
            KOS_LOG_DEBUG(cat, fmt, ##__VA_ARGS__); \
        } \
    } while (0)

/* Error code logging */
#define KOS_LOG_ERRNO(cat, fmt, ...) \
    KOS_LOG_ERROR(cat, fmt ": %s", ##__VA_ARGS__, strerror(errno))

/* Rate-limited logging */
#define KOS_LOG_RATELIMIT(level, cat, fmt, ...) \
    do { \
        static uint64_t _last_log = 0; \
        static int _log_count = 0; \
        uint64_t _now = time(NULL); \
        if (_now != _last_log) { \
            if (_log_count > 1) { \
                kos_log(level, cat, __FILE__, __LINE__, __func__, \
                       "Previous message repeated %d times", _log_count - 1); \
            } \
            kos_log(level, cat, __FILE__, __LINE__, __func__, fmt, ##__VA_ARGS__); \
            _last_log = _now; \
            _log_count = 1; \
        } else { \
            _log_count++; \
        } \
    } while (0)

#endif /* _KOS_LOGGER_H */