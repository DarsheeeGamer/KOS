/*
 * KOS Memory Management Error Handling and Edge Cases
 * Comprehensive error recovery and validation
 */

#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <setjmp.h>

/* Memory error types */
typedef enum {
    MM_ERROR_NONE = 0,
    MM_ERROR_OOM,           /* Out of memory */
    MM_ERROR_CORRUPTION,    /* Memory corruption detected */
    MM_ERROR_LEAK,          /* Memory leak detected */
    MM_ERROR_DOUBLE_FREE,   /* Double free attempt */
    MM_ERROR_INVALID_PTR,   /* Invalid pointer */
    MM_ERROR_ALIGNMENT,     /* Alignment error */
    MM_ERROR_BOUNDS,        /* Buffer overflow/underflow */
    MM_ERROR_FRAGMENTATION, /* Excessive fragmentation */
    MM_ERROR_STACK_OVERFLOW,/* Stack overflow */
    MM_ERROR_HEAP_OVERFLOW  /* Heap overflow */
} mm_error_type_t;

/* Error recovery strategies */
typedef enum {
    MM_RECOVERY_IGNORE = 0,
    MM_RECOVERY_LOG,
    MM_RECOVERY_TERMINATE,
    MM_RECOVERY_RESTART,
    MM_RECOVERY_FALLBACK,
    MM_RECOVERY_PANIC
} mm_recovery_t;

/* Memory error handler */
typedef struct {
    mm_error_type_t type;
    const char *message;
    void *address;
    size_t size;
    const char *file;
    int line;
    const char *function;
    pid_t pid;
    uint64_t timestamp;
    mm_recovery_t recovery;
} mm_error_t;

/* Error statistics */
static struct {
    uint64_t total_errors;
    uint64_t oom_errors;
    uint64_t corruption_errors;
    uint64_t leak_errors;
    uint64_t double_free_errors;
    uint64_t invalid_ptr_errors;
    uint64_t alignment_errors;
    uint64_t bounds_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    pthread_mutex_t lock;
} mm_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Memory corruption detection patterns */
#define MM_GUARD_MAGIC_START    0xDEADBEEF
#define MM_GUARD_MAGIC_END      0xCAFEBABE
#define MM_FREE_MAGIC           0xFEEDFACE
#define MM_CANARY_SIZE          16

/* Guard structure for allocated memory */
typedef struct mm_guard {
    uint32_t magic_start;
    size_t size;
    const char *file;
    int line;
    const char *function;
    uint64_t timestamp;
    uint8_t canary[MM_CANARY_SIZE];
    /* User data follows */
    /* uint32_t magic_end at end of user data */
} mm_guard_t;

/* Exception handling for memory errors */
static jmp_buf mm_error_jmp;
static volatile int mm_error_recovery_active = 0;

/* Generate random canary values */
static void generate_canary(uint8_t *canary, size_t size)
{
    for (size_t i = 0; i < size; i++) {
        canary[i] = (uint8_t)(rand() ^ (rand() >> 8) ^ (i * 0x5A));
    }
}

/* Validate canary values */
static int validate_canary(const uint8_t *canary, const uint8_t *expected, size_t size)
{
    for (size_t i = 0; i < size; i++) {
        if (canary[i] != expected[i]) {
            return 0;
        }
    }
    return 1;
}

/* Log memory error */
static void log_memory_error(const mm_error_t *error)
{
    pthread_mutex_lock(&mm_error_stats.lock);
    mm_error_stats.total_errors++;
    
    switch (error->type) {
        case MM_ERROR_OOM:
            mm_error_stats.oom_errors++;
            break;
        case MM_ERROR_CORRUPTION:
            mm_error_stats.corruption_errors++;
            break;
        case MM_ERROR_LEAK:
            mm_error_stats.leak_errors++;
            break;
        case MM_ERROR_DOUBLE_FREE:
            mm_error_stats.double_free_errors++;
            break;
        case MM_ERROR_INVALID_PTR:
            mm_error_stats.invalid_ptr_errors++;
            break;
        case MM_ERROR_ALIGNMENT:
            mm_error_stats.alignment_errors++;
            break;
        case MM_ERROR_BOUNDS:
            mm_error_stats.bounds_errors++;
            break;
        default:
            break;
    }
    
    pthread_mutex_unlock(&mm_error_stats.lock);
    
    /* Log to system log */
    printf("[MM ERROR] Type: %d, Message: %s, Address: %p, Size: %zu\n",
           error->type, error->message, error->address, error->size);
    printf("[MM ERROR] Location: %s:%d in %s(), PID: %d\n",
           error->file ? error->file : "unknown",
           error->line, 
           error->function ? error->function : "unknown",
           error->pid);
}

/* Handle memory error with recovery */
static int handle_memory_error(mm_error_t *error)
{
    log_memory_error(error);
    
    pthread_mutex_lock(&mm_error_stats.lock);
    mm_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&mm_error_stats.lock);
    
    switch (error->recovery) {
        case MM_RECOVERY_IGNORE:
            return 0;
            
        case MM_RECOVERY_LOG:
            /* Already logged above */
            return 0;
            
        case MM_RECOVERY_TERMINATE:
            printf("[MM FATAL] Terminating process due to memory error\n");
            exit(EXIT_FAILURE);
            
        case MM_RECOVERY_RESTART:
            /* Attempt to restart the failing subsystem */
            if (mm_error_recovery_active) {
                pthread_mutex_lock(&mm_error_stats.lock);
                mm_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&mm_error_stats.lock);
                longjmp(mm_error_jmp, error->type);
            }
            return -1;
            
        case MM_RECOVERY_FALLBACK:
            /* Use alternative allocation strategy */
            return mm_try_fallback_allocation(error->size);
            
        case MM_RECOVERY_PANIC:
            printf("[MM PANIC] Unrecoverable memory error - system halting\n");
            abort();
            
        default:
            return -1;
    }
}

/* Guarded malloc with corruption detection */
void *mm_guarded_malloc(size_t size, const char *file, int line, const char *func)
{
    if (size == 0) {
        mm_error_t error = {
            .type = MM_ERROR_INVALID_PTR,
            .message = "Zero-size allocation requested",
            .address = NULL,
            .size = size,
            .file = file,
            .line = line,
            .function = func,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_LOG
        };
        handle_memory_error(&error);
        return NULL;
    }
    
    /* Check for integer overflow */
    if (size > SIZE_MAX - sizeof(mm_guard_t) - sizeof(uint32_t)) {
        mm_error_t error = {
            .type = MM_ERROR_BOUNDS,
            .message = "Integer overflow in allocation size",
            .address = NULL,
            .size = size,
            .file = file,
            .line = line,
            .function = func,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
        return NULL;
    }
    
    size_t total_size = sizeof(mm_guard_t) + size + sizeof(uint32_t);
    
    /* Try allocation with fallback */
    mm_guard_t *guard = malloc(total_size);
    if (!guard) {
        mm_error_t error = {
            .type = MM_ERROR_OOM,
            .message = "Out of memory",
            .address = NULL,
            .size = size,
            .file = file,
            .line = line,
            .function = func,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_FALLBACK
        };
        
        if (handle_memory_error(&error) == 0) {
            /* Fallback succeeded, try again */
            guard = malloc(total_size);
        }
        
        if (!guard) {
            return NULL;
        }
    }
    
    /* Initialize guard structure */
    guard->magic_start = MM_GUARD_MAGIC_START;
    guard->size = size;
    guard->file = file;
    guard->line = line;
    guard->function = func;
    guard->timestamp = time(NULL);
    generate_canary(guard->canary, MM_CANARY_SIZE);
    
    /* Set end magic */
    uint8_t *user_data = (uint8_t *)(guard + 1);
    uint32_t *magic_end = (uint32_t *)(user_data + size);
    *magic_end = MM_GUARD_MAGIC_END;
    
    /* Clear user data */
    memset(user_data, 0, size);
    
    return user_data;
}

/* Validate memory block integrity */
static int validate_memory_block(void *ptr, const char *operation)
{
    if (!ptr) {
        mm_error_t error = {
            .type = MM_ERROR_INVALID_PTR,
            .message = "NULL pointer in memory operation",
            .address = ptr,
            .size = 0,
            .file = __FILE__,
            .line = __LINE__,
            .function = operation,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_LOG
        };
        handle_memory_error(&error);
        return 0;
    }
    
    mm_guard_t *guard = ((mm_guard_t *)ptr) - 1;
    
    /* Check start magic */
    if (guard->magic_start != MM_GUARD_MAGIC_START) {
        mm_error_t error = {
            .type = MM_ERROR_CORRUPTION,
            .message = "Memory corruption detected (start guard)",
            .address = ptr,
            .size = guard->size,
            .file = guard->file,
            .line = guard->line,
            .function = operation,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
        return 0;
    }
    
    /* Check end magic */
    uint32_t *magic_end = (uint32_t *)((uint8_t *)ptr + guard->size);
    if (*magic_end != MM_GUARD_MAGIC_END) {
        mm_error_t error = {
            .type = MM_ERROR_CORRUPTION,
            .message = "Memory corruption detected (end guard)",
            .address = ptr,
            .size = guard->size,
            .file = guard->file,
            .line = guard->line,
            .function = operation,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
        return 0;
    }
    
    /* Validate canary */
    uint8_t expected_canary[MM_CANARY_SIZE];
    generate_canary(expected_canary, MM_CANARY_SIZE);
    if (!validate_canary(guard->canary, expected_canary, MM_CANARY_SIZE)) {
        mm_error_t error = {
            .type = MM_ERROR_CORRUPTION,
            .message = "Memory corruption detected (canary)",
            .address = ptr,
            .size = guard->size,
            .file = guard->file,
            .line = guard->line,
            .function = operation,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
        return 0;
    }
    
    return 1;
}

/* Guarded free with double-free detection */
void mm_guarded_free(void *ptr, const char *file, int line, const char *func)
{
    if (!ptr) {
        return; /* Allow free(NULL) */
    }
    
    if (!validate_memory_block(ptr, "free")) {
        return;
    }
    
    mm_guard_t *guard = ((mm_guard_t *)ptr) - 1;
    
    /* Check for double free */
    if (guard->magic_start == MM_FREE_MAGIC) {
        mm_error_t error = {
            .type = MM_ERROR_DOUBLE_FREE,
            .message = "Double free detected",
            .address = ptr,
            .size = guard->size,
            .file = file,
            .line = line,
            .function = func,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
        return;
    }
    
    /* Mark as freed */
    guard->magic_start = MM_FREE_MAGIC;
    
    /* Fill with recognizable pattern */
    memset(ptr, 0xDD, guard->size);
    
    free(guard);
}

/* Fallback allocation when primary allocator fails */
int mm_try_fallback_allocation(size_t size)
{
    /* Try to free some cached memory */
    kmem_cache_shrink_all();
    
    /* Try emergency memory pool */
    static uint8_t emergency_pool[1024 * 1024]; /* 1MB emergency pool */
    static size_t emergency_used = 0;
    static pthread_mutex_t emergency_lock = PTHREAD_MUTEX_INITIALIZER;
    
    pthread_mutex_lock(&emergency_lock);
    
    if (emergency_used + size <= sizeof(emergency_pool)) {
        emergency_used += size;
        pthread_mutex_unlock(&emergency_lock);
        return 0; /* Success */
    }
    
    pthread_mutex_unlock(&emergency_lock);
    
    /* Try to trigger garbage collection */
    mm_run_garbage_collector();
    
    return -1; /* Failed */
}

/* Stack overflow detection */
void mm_check_stack_overflow(void)
{
    char stack_var;
    static char *stack_base = NULL;
    static size_t stack_size = 8 * 1024 * 1024; /* 8MB default */
    
    if (!stack_base) {
        stack_base = &stack_var;
        return;
    }
    
    ptrdiff_t stack_used = abs(&stack_var - stack_base);
    
    if ((size_t)stack_used > stack_size - 4096) { /* 4KB safety margin */
        mm_error_t error = {
            .type = MM_ERROR_STACK_OVERFLOW,
            .message = "Stack overflow detected",
            .address = &stack_var,
            .size = stack_used,
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_TERMINATE
        };
        handle_memory_error(&error);
    }
}

/* Memory leak detector */
void mm_detect_leaks(void)
{
    /* This would scan all allocated blocks and detect potential leaks */
    /* For now, just check if we have excessive allocations */
    
    size_t total_allocated = get_total_allocated_memory();
    size_t threshold = 100 * 1024 * 1024; /* 100MB threshold */
    
    if (total_allocated > threshold) {
        mm_error_t error = {
            .type = MM_ERROR_LEAK,
            .message = "Potential memory leak detected",
            .address = NULL,
            .size = total_allocated,
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .pid = getpid(),
            .timestamp = time(NULL),
            .recovery = MM_RECOVERY_LOG
        };
        handle_memory_error(&error);
    }
}

/* Get error statistics */
void mm_get_error_stats(void)
{
    pthread_mutex_lock(&mm_error_stats.lock);
    
    printf("\nMemory Management Error Statistics:\n");
    printf("==================================\n");
    printf("Total errors:          %lu\n", mm_error_stats.total_errors);
    printf("OOM errors:            %lu\n", mm_error_stats.oom_errors);
    printf("Corruption errors:     %lu\n", mm_error_stats.corruption_errors);
    printf("Memory leak errors:    %lu\n", mm_error_stats.leak_errors);
    printf("Double free errors:    %lu\n", mm_error_stats.double_free_errors);
    printf("Invalid pointer errors:%lu\n", mm_error_stats.invalid_ptr_errors);
    printf("Alignment errors:      %lu\n", mm_error_stats.alignment_errors);
    printf("Bounds errors:         %lu\n", mm_error_stats.bounds_errors);
    printf("Recovery attempts:     %lu\n", mm_error_stats.recoveries_attempted);
    printf("Recovery successes:    %lu\n", mm_error_stats.recoveries_successful);
    
    if (mm_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)mm_error_stats.recoveries_successful / 
                             mm_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate: %.1f%%\n", success_rate);
    }
    
    pthread_mutex_unlock(&mm_error_stats.lock);
}

/* Initialize error handling system */
void mm_error_init(void)
{
    /* Set up signal handlers for memory-related errors */
    signal(SIGSEGV, mm_segfault_handler);
    signal(SIGBUS, mm_bus_error_handler);
    
    /* Initialize random seed for canaries */
    srand(time(NULL) ^ getpid());
    
    printf("Memory management error handling initialized\n");
}

/* Macros for easy use */
#define MM_MALLOC(size) mm_guarded_malloc(size, __FILE__, __LINE__, __func__)
#define MM_FREE(ptr) mm_guarded_free(ptr, __FILE__, __LINE__, __func__)
#define MM_CHECK_STACK() mm_check_stack_overflow()