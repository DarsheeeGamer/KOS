/*
 * KOS Kernel Panic and Debugging System
 * Handles kernel panics, stack traces, and core dumps
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <execinfo.h>
#include <time.h>
#include <sys/utsname.h>
#include <pthread.h>
#include <stdarg.h>
#include <errno.h>

/* Panic state tracking */
static struct {
    bool in_panic;
    bool panic_blink;
    FILE* panic_log;
    pthread_mutex_t panic_lock;
    uint32_t panic_count;
    char last_panic_msg[1024];
    uint64_t last_panic_time;
} panic_state = {0};

/* Debug output levels */
typedef enum {
    DEBUG_LEVEL_EMERGENCY = 0,
    DEBUG_LEVEL_ALERT     = 1,
    DEBUG_LEVEL_CRITICAL  = 2,
    DEBUG_LEVEL_ERROR     = 3,
    DEBUG_LEVEL_WARNING   = 4,
    DEBUG_LEVEL_NOTICE    = 5,
    DEBUG_LEVEL_INFO      = 6,
    DEBUG_LEVEL_DEBUG     = 7
} debug_level_t;

static const char* debug_level_names[] = {
    "EMERGENCY", "ALERT", "CRITICAL", "ERROR",
    "WARNING", "NOTICE", "INFO", "DEBUG"
};

/* Stack trace buffer */
#define MAX_STACK_FRAMES 64
static void* stack_trace[MAX_STACK_FRAMES];
static char** stack_symbols;

/* Core dump information */
struct kos_core_dump {
    uint64_t timestamp;
    uint32_t pid;
    uint32_t tid;
    char process_name[64];
    char panic_message[1024];
    void* stack_frames[MAX_STACK_FRAMES];
    int num_frames;
    struct {
        uint64_t total_memory;
        uint64_t free_memory;
        uint64_t processes;
        uint64_t threads;
        uint64_t context_switches;
        uint64_t syscalls;
    } system_state;
};

/* Forward declarations */
static void panic_signal_handler(int sig);
static void print_stack_trace(void);
static void print_system_state(void);
static void print_process_info(void);
static void save_core_dump(const char* reason);
static void emergency_sync(void);
static void panic_blink_led(void);

/* Initialize panic handling system */
void kos_panic_init(void) {
    pthread_mutex_init(&panic_state.panic_lock, NULL);
    
    /* Open panic log file */
    panic_state.panic_log = fopen("/tmp/kos_panic.log", "a");
    if (!panic_state.panic_log) {
        panic_state.panic_log = stderr;
    }
    
    /* Set up signal handlers for panic conditions */
    signal(SIGSEGV, panic_signal_handler);
    signal(SIGBUS, panic_signal_handler);
    signal(SIGFPE, panic_signal_handler);
    signal(SIGILL, panic_signal_handler);
    signal(SIGABRT, panic_signal_handler);
    
    printf("KOS: Panic handler initialized\n");
}

/* Main kernel panic function */
void kos_kernel_panic(const char* message) {
    kos_kernel_panic_detailed(message, __FILE__, __LINE__, __func__);
}

/* Detailed kernel panic with location information */
void kos_kernel_panic_detailed(const char* message, const char* file, int line, const char* func) {
    pthread_mutex_lock(&panic_state.panic_lock);
    
    /* Prevent recursive panics */
    if (panic_state.in_panic) {
        fprintf(stderr, "DOUBLE PANIC: %s\n", message);
        fprintf(stderr, "System halted due to recursive panic\n");
        abort();
    }
    
    panic_state.in_panic = true;
    panic_state.panic_count++;
    panic_state.last_panic_time = time(NULL);
    strncpy(panic_state.last_panic_msg, message, sizeof(panic_state.last_panic_msg) - 1);
    panic_state.last_panic_msg[sizeof(panic_state.last_panic_msg) - 1] = '\0';
    
    /* Disable interrupts (simulated) */
    /* Stop other CPUs */
    
    /* Print panic header */
    fprintf(panic_state.panic_log, "================================================================================\n");
    fprintf(panic_state.panic_log, "                                KERNEL PANIC\n");
    fprintf(panic_state.panic_log, "================================================================================\n");
    fprintf(panic_state.panic_log, "Time: %s", ctime(&panic_state.last_panic_time));
    fprintf(panic_state.panic_log, "Panic #%d: %s\n", panic_state.panic_count, message);
    fprintf(panic_state.panic_log, "Location: %s:%d in %s()\n", file, line, func);
    fprintf(panic_state.panic_log, "================================================================================\n");
    
    /* Also print to console */
    fprintf(stderr, "\n*** KERNEL PANIC ***\n");
    fprintf(stderr, "Panic: %s\n", message);
    fprintf(stderr, "Location: %s:%d in %s()\n", file, line, func);
    
    /* Print stack trace */
    print_stack_trace();
    
    /* Print system state */
    print_system_state();
    
    /* Print process information */
    print_process_info();
    
    /* Save core dump */
    save_core_dump(message);
    
    /* Emergency filesystem sync */
    emergency_sync();
    
    /* Start panic blink pattern */
    panic_blink_led();
    
    fprintf(panic_state.panic_log, "================================================================================\n");
    fprintf(panic_state.panic_log, "System halted. Manual intervention required.\n");
    fprintf(panic_state.panic_log, "================================================================================\n");
    
    fflush(panic_state.panic_log);
    fflush(stderr);
    
    pthread_mutex_unlock(&panic_state.panic_lock);
    
    /* Final halt */
    abort();
}

/* Conditional panic - panic only if condition is true */
void kos_panic_if(bool condition, const char* message) {
    if (condition) {
        kos_kernel_panic(message);
    }
}

/* Assert with panic */
void kos_assert_panic(bool condition, const char* expr, const char* file, int line, const char* func) {
    if (!condition) {
        char panic_msg[512];
        snprintf(panic_msg, sizeof(panic_msg), "Assertion failed: %s", expr);
        kos_kernel_panic_detailed(panic_msg, file, line, func);
    }
}

/* Debug output with levels */
void kos_debug_print(debug_level_t level, const char* fmt, ...) {
    if (level > DEBUG_LEVEL_ERROR) {
        return;  /* Only show important messages */
    }
    
    va_list args;
    va_start(args, fmt);
    
    /* Print timestamp and level */
    time_t now = time(NULL);
    struct tm* tm_info = localtime(&now);
    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%H:%M:%S", tm_info);
    
    fprintf(stderr, "[%s] %s: ", timestamp, debug_level_names[level]);
    vfprintf(stderr, fmt, args);
    fprintf(stderr, "\n");
    
    /* Also log to panic log if available */
    if (panic_state.panic_log && panic_state.panic_log != stderr) {
        fprintf(panic_state.panic_log, "[%s] %s: ", timestamp, debug_level_names[level]);
        vfprintf(panic_state.panic_log, fmt, args);
        fprintf(panic_state.panic_log, "\n");
        fflush(panic_state.panic_log);
    }
    
    va_end(args);
}

/* Signal handler for panic conditions */
static void panic_signal_handler(int sig) {
    const char* sig_name;
    
    switch (sig) {
        case SIGSEGV: sig_name = "SIGSEGV (Segmentation fault)"; break;
        case SIGBUS:  sig_name = "SIGBUS (Bus error)"; break;
        case SIGFPE:  sig_name = "SIGFPE (Floating point exception)"; break;
        case SIGILL:  sig_name = "SIGILL (Illegal instruction)"; break;
        case SIGABRT: sig_name = "SIGABRT (Abort)"; break;
        default:      sig_name = "Unknown signal"; break;
    }
    
    char panic_msg[256];
    snprintf(panic_msg, sizeof(panic_msg), "Fatal signal received: %s (%d)", sig_name, sig);
    kos_kernel_panic(panic_msg);
}

/* Print stack trace */
static void print_stack_trace(void) {
    int num_frames;
    
    fprintf(panic_state.panic_log, "\nStack trace:\n");
    fprintf(stderr, "\nStack trace:\n");
    
    /* Get backtrace */
    num_frames = backtrace(stack_trace, MAX_STACK_FRAMES);
    stack_symbols = backtrace_symbols(stack_trace, num_frames);
    
    if (stack_symbols) {
        for (int i = 0; i < num_frames; i++) {
            fprintf(panic_state.panic_log, "  [%d] %s\n", i, stack_symbols[i]);
            fprintf(stderr, "  [%d] %s\n", i, stack_symbols[i]);
        }
        free(stack_symbols);
    } else {
        fprintf(panic_state.panic_log, "  Unable to generate stack trace\n");
        fprintf(stderr, "  Unable to generate stack trace\n");
    }
    
    fprintf(panic_state.panic_log, "\n");
    fprintf(stderr, "\n");
}

/* Print system state */
static void print_system_state(void) {
    fprintf(panic_state.panic_log, "System state at panic:\n");
    fprintf(stderr, "System state at panic:\n");
    
    /* Get system information */
    struct utsname uts;
    if (uname(&uts) == 0) {
        fprintf(panic_state.panic_log, "  Kernel: %s %s %s\n", uts.sysname, uts.release, uts.machine);
        fprintf(stderr, "  Kernel: %s %s %s\n", uts.sysname, uts.release, uts.machine);
    }
    
    /* Memory information */
    fprintf(panic_state.panic_log, "  Memory: Information not available in userspace\n");
    fprintf(stderr, "  Memory: Information not available in userspace\n");
    
    /* Process information */
    fprintf(panic_state.panic_log, "  Current PID: %d\n", getpid());
    fprintf(stderr, "  Current PID: %d\n", getpid());
    
    /* Time information */
    time_t now = time(NULL);
    fprintf(panic_state.panic_log, "  Current time: %s", ctime(&now));
    fprintf(stderr, "  Current time: %s", ctime(&now));
    
    fprintf(panic_state.panic_log, "\n");
    fprintf(stderr, "\n");
}

/* Print process information */
static void print_process_info(void) {
    fprintf(panic_state.panic_log, "Process information:\n");
    fprintf(stderr, "Process information:\n");
    
    fprintf(panic_state.panic_log, "  PID: %d\n", getpid());
    fprintf(panic_state.panic_log, "  PPID: %d\n", getppid());
    fprintf(panic_state.panic_log, "  UID: %d\n", getuid());
    fprintf(panic_state.panic_log, "  GID: %d\n", getgid());
    
    fprintf(stderr, "  PID: %d\n", getpid());
    fprintf(stderr, "  PPID: %d\n", getppid());
    fprintf(stderr, "  UID: %d\n", getuid());
    fprintf(stderr, "  GID: %d\n", getgid());
    
    /* Get process name */
    char proc_name[256] = "unknown";
    FILE* comm_file = fopen("/proc/self/comm", "r");
    if (comm_file) {
        if (fgets(proc_name, sizeof(proc_name), comm_file)) {
            /* Remove newline */
            char* newline = strchr(proc_name, '\n');
            if (newline) *newline = '\0';
        }
        fclose(comm_file);
    }
    
    fprintf(panic_state.panic_log, "  Process name: %s\n", proc_name);
    fprintf(stderr, "  Process name: %s\n", proc_name);
    
    fprintf(panic_state.panic_log, "\n");
    fprintf(stderr, "\n");
}

/* Save core dump */
static void save_core_dump(const char* reason) {
    char core_path[256];
    snprintf(core_path, sizeof(core_path), "/tmp/kos_core.%d.%lu", getpid(), time(NULL));
    
    FILE* core_file = fopen(core_path, "wb");
    if (!core_file) {
        fprintf(panic_state.panic_log, "Failed to create core dump file: %s\n", strerror(errno));
        return;
    }
    
    struct kos_core_dump core_dump = {0};
    
    /* Fill core dump structure */
    core_dump.timestamp = time(NULL);
    core_dump.pid = getpid();
    core_dump.tid = pthread_self();
    strncpy(core_dump.panic_message, reason, sizeof(core_dump.panic_message) - 1);
    
    /* Get process name */
    FILE* comm_file = fopen("/proc/self/comm", "r");
    if (comm_file) {
        if (fgets(core_dump.process_name, sizeof(core_dump.process_name), comm_file)) {
            char* newline = strchr(core_dump.process_name, '\n');
            if (newline) *newline = '\0';
        }
        fclose(comm_file);
    }
    
    /* Copy stack trace */
    core_dump.num_frames = backtrace(core_dump.stack_frames, MAX_STACK_FRAMES);
    
    /* System state (simplified) */
    core_dump.system_state.processes = 0;  /* Would need kernel access */
    core_dump.system_state.threads = 0;
    core_dump.system_state.total_memory = 0;
    core_dump.system_state.free_memory = 0;
    
    /* Write core dump */
    fwrite(&core_dump, sizeof(core_dump), 1, core_file);
    fclose(core_file);
    
    fprintf(panic_state.panic_log, "Core dump saved to: %s\n", core_path);
    fprintf(stderr, "Core dump saved to: %s\n", core_path);
}

/* Emergency filesystem sync */
static void emergency_sync(void) {
    fprintf(panic_state.panic_log, "Performing emergency sync...\n");
    fprintf(stderr, "Performing emergency sync...\n");
    
    sync();  /* Force filesystem writes */
    
    /* Close panic log to ensure it's written */
    if (panic_state.panic_log && panic_state.panic_log != stderr) {
        fclose(panic_state.panic_log);
        panic_state.panic_log = stderr;
    }
}

/* Panic LED blink pattern (simulated) */
static void panic_blink_led(void) {
    /* In a real kernel, this would blink physical LEDs */
    /* For now, we'll just print a pattern */
    fprintf(stderr, "\n*** PANIC BLINK PATTERN ***\n");
    
    for (int i = 0; i < 10; i++) {
        fprintf(stderr, "*BLINK* ");
        fflush(stderr);
        usleep(200000);  /* 200ms */
    }
    
    fprintf(stderr, "\n");
}

/* Get panic statistics */
void kos_get_panic_stats(struct kos_panic_stats* stats) {
    if (!stats) return;
    
    pthread_mutex_lock(&panic_state.panic_lock);
    
    stats->panic_count = panic_state.panic_count;
    stats->last_panic_time = panic_state.last_panic_time;
    strncpy(stats->last_panic_message, panic_state.last_panic_msg, 
            sizeof(stats->last_panic_message) - 1);
    stats->last_panic_message[sizeof(stats->last_panic_message) - 1] = '\0';
    stats->in_panic = panic_state.in_panic;
    
    pthread_mutex_unlock(&panic_state.panic_lock);
}

/* BUG() macro implementation */
void kos_bug(const char* file, int line, const char* func) {
    char bug_msg[256];
    snprintf(bug_msg, sizeof(bug_msg), "BUG detected");
    kos_kernel_panic_detailed(bug_msg, file, line, func);
}

/* Warn and continue (non-fatal) */
void kos_warn(const char* message, const char* file, int line, const char* func) {
    fprintf(stderr, "WARNING: %s at %s:%d in %s()\n", message, file, line, func);
    
    if (panic_state.panic_log && panic_state.panic_log != stderr) {
        fprintf(panic_state.panic_log, "WARNING: %s at %s:%d in %s()\n", 
                message, file, line, func);
        fflush(panic_state.panic_log);
    }
    
    /* Print stack trace for warnings too */
    int num_frames = backtrace(stack_trace, MAX_STACK_FRAMES);
    char** symbols = backtrace_symbols(stack_trace, num_frames);
    
    if (symbols) {
        fprintf(stderr, "Warning stack trace:\n");
        for (int i = 0; i < num_frames && i < 5; i++) {  /* Limit to 5 frames */
            fprintf(stderr, "  [%d] %s\n", i, symbols[i]);
        }
        free(symbols);
    }
}

/* Panic statistics structure */
struct kos_panic_stats {
    uint32_t panic_count;
    uint64_t last_panic_time;
    char last_panic_message[1024];
    bool in_panic;
};

/* Convenient macros for use in other files */
#define KOS_PANIC(msg) kos_kernel_panic_detailed(msg, __FILE__, __LINE__, __func__)
#define KOS_BUG() kos_bug(__FILE__, __LINE__, __func__)
#define KOS_WARN(msg) kos_warn(msg, __FILE__, __LINE__, __func__)
#define KOS_ASSERT(cond) kos_assert_panic(cond, #cond, __FILE__, __LINE__, __func__)

/* Debug output macros */
#define kos_emergency(fmt, ...) kos_debug_print(DEBUG_LEVEL_EMERGENCY, fmt, ##__VA_ARGS__)
#define kos_alert(fmt, ...)     kos_debug_print(DEBUG_LEVEL_ALERT, fmt, ##__VA_ARGS__)
#define kos_critical(fmt, ...)  kos_debug_print(DEBUG_LEVEL_CRITICAL, fmt, ##__VA_ARGS__)
#define kos_error(fmt, ...)     kos_debug_print(DEBUG_LEVEL_ERROR, fmt, ##__VA_ARGS__)
#define kos_warning(fmt, ...)   kos_debug_print(DEBUG_LEVEL_WARNING, fmt, ##__VA_ARGS__)
#define kos_notice(fmt, ...)    kos_debug_print(DEBUG_LEVEL_NOTICE, fmt, ##__VA_ARGS__)
#define kos_info(fmt, ...)      kos_debug_print(DEBUG_LEVEL_INFO, fmt, ##__VA_ARGS__)
#define kos_debug(fmt, ...)     kos_debug_print(DEBUG_LEVEL_DEBUG, fmt, ##__VA_ARGS__)