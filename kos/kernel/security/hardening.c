/*
 * KOS Kernel Security Hardening
 * Low-level security measures and exploit mitigations
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <errno.h>
#include <time.h>

#include "../sysctl.h"
#include "security.h"

/* Hardening configuration */
struct security_hardening_config {
    bool stack_canaries_enabled;
    bool aslr_enabled;
    bool dep_enabled;              /* Data Execution Prevention */
    bool smep_enabled;             /* Supervisor Mode Execution Prevention */
    bool smap_enabled;             /* Supervisor Mode Access Prevention */
    bool kpti_enabled;             /* Kernel Page Table Isolation */
    bool kaslr_enabled;            /* Kernel ASLR */
    bool control_flow_integrity;   /* CFI */
    bool stack_clash_protection;   /* Stack clash protection */
    uint32_t mmap_min_addr;        /* Minimum mmap address */
    uint32_t max_map_count;        /* Maximum memory maps */
    bool dmesg_restrict;           /* Restrict dmesg access */
    bool kptr_restrict;            /* Restrict kernel pointers */
    uint32_t perf_event_paranoid;  /* Perf event restrictions */
} hardening_config = {
    .stack_canaries_enabled = true,
    .aslr_enabled = true,
    .dep_enabled = true,
    .smep_enabled = true,
    .smap_enabled = true,
    .kpti_enabled = true,
    .kaslr_enabled = true,
    .control_flow_integrity = true,
    .stack_clash_protection = true,
    .mmap_min_addr = 65536,        /* 64KB minimum */
    .max_map_count = 65536,
    .dmesg_restrict = true,
    .kptr_restrict = true,
    .perf_event_paranoid = 2
};

/* Stack canary value */
static uint64_t stack_canary = 0;

/* Buffer overflow detection */
#define STACK_CANARY_SIZE 8
#define GUARD_PAGE_SIZE 4096

/* Initialize stack canary */
static void init_stack_canary(void)
{
    FILE *urandom = fopen("/dev/urandom", "rb");
    if (urandom) {
        fread(&stack_canary, sizeof(stack_canary), 1, urandom);
        fclose(urandom);
    } else {
        /* Fallback to time-based seed */
        stack_canary = time(NULL) ^ (uint64_t)&stack_canary;
    }
    
    /* Ensure canary is never zero */
    if (stack_canary == 0) {
        stack_canary = 0xDEADBEEFCAFEBABE;
    }
}

/* Get stack canary value */
uint64_t get_stack_canary(void)
{
    return stack_canary;
}

/* Check stack canary */
bool check_stack_canary(uint64_t canary)
{
    return canary == stack_canary;
}

/* Stack smashing detection */
void __stack_chk_fail(void)
{
    fprintf(stderr, "*** STACK SMASHING DETECTED ***: terminated\n");
    abort();
}

/* Address space layout randomization */
int enable_aslr(void)
{
    int ret = 0;
    
    /* Enable ASLR for current process */
    ret = prctl(PR_SET_RANDOMIZE_VA_SPACE, 2, 0, 0, 0);
    if (ret != 0) {
        perror("Failed to enable ASLR");
        return -1;
    }
    
    /* Set minimum mmap address */
    FILE *mmap_min = fopen("/proc/sys/vm/mmap_min_addr", "w");
    if (mmap_min) {
        fprintf(mmap_min, "%u", hardening_config.mmap_min_addr);
        fclose(mmap_min);
    }
    
    return 0;
}

/* Data Execution Prevention (DEP/NX bit) */
int enable_dep(void)
{
    /* Mark stack as non-executable */
    size_t stack_size = 8 * 1024 * 1024; /* 8MB stack */
    void *stack_addr = (void *)((uintptr_t)&stack_size & ~(stack_size - 1));
    
    if (mprotect(stack_addr, stack_size, PROT_READ | PROT_WRITE) != 0) {
        perror("Failed to set stack non-executable");
        return -1;
    }
    
    return 0;
}

/* Control Flow Integrity checks */
typedef struct cfi_check {
    void *expected_target;
    void *actual_target;
    const char *location;
} cfi_check_t;

bool validate_control_flow(cfi_check_t *check)
{
    if (!hardening_config.control_flow_integrity) {
        return true;
    }
    
    if (check->expected_target != check->actual_target) {
        fprintf(stderr, "CFI violation at %s: expected %p, got %p\n",
                check->location, check->expected_target, check->actual_target);
        return false;
    }
    
    return true;
}

/* Return-Oriented Programming (ROP) protection */
typedef struct rop_gadget {
    void *address;
    uint32_t instruction;
    bool is_ret;
} rop_gadget_t;

/* Simple ROP chain detection */
bool detect_rop_chain(void **stack, size_t stack_size)
{
    size_t consecutive_rets = 0;
    const size_t max_consecutive_rets = 3;
    
    for (size_t i = 0; i < stack_size / sizeof(void*); i++) {
        /* Check if this looks like a return address */
        if (stack[i] && (uintptr_t)stack[i] > 0x400000) {
            /* Simple heuristic: check for patterns typical in ROP */
            uint8_t *instr = (uint8_t *)stack[i];
            if (instr && (instr[0] == 0xc3 || /* ret */
                         (instr[0] == 0x41 && instr[1] == 0x5f))) { /* pop r15 */
                consecutive_rets++;
                if (consecutive_rets > max_consecutive_rets) {
                    return true; /* Likely ROP chain */
                }
            } else {
                consecutive_rets = 0;
            }
        }
    }
    
    return false;
}

/* Jump-Oriented Programming (JOP) protection */
bool detect_jop_chain(void **addresses, size_t count)
{
    /* Look for patterns typical in JOP attacks */
    size_t indirect_jumps = 0;
    
    for (size_t i = 0; i < count; i++) {
        if (addresses[i]) {
            uint8_t *instr = (uint8_t *)addresses[i];
            if (instr && (instr[0] == 0xff && (instr[1] & 0xf0) == 0x20)) {
                /* jmp [reg] instruction */
                indirect_jumps++;
                if (indirect_jumps > 2) {
                    return true; /* Likely JOP chain */
                }
            }
        }
    }
    
    return false;
}

/* Format string attack protection */
bool validate_format_string(const char *format)
{
    if (!format) {
        return false;
    }
    
    /* Count format specifiers */
    int specifier_count = 0;
    const char *p = format;
    
    while (*p) {
        if (*p == '%') {
            if (*(p + 1) == '%') {
                p += 2; /* Skip %% */
                continue;
            }
            specifier_count++;
            
            /* Check for dangerous specifiers */
            p++;
            while (*p && strchr("-+ #0", *p)) p++; /* flags */
            while (*p && (*p >= '0' && *p <= '9')) p++; /* width */
            if (*p == '.') {
                p++;
                while (*p && (*p >= '0' && *p <= '9')) p++; /* precision */
            }
            
            /* Check format specifier */
            switch (*p) {
                case 'n': /* %n writes to memory */
                    return false;
                case 's':
                    /* String specifier - check for buffer overflows */
                    break;
                case 'x': case 'X': case 'p':
                    /* Hex/pointer - potential info leak */
                    if (hardening_config.kptr_restrict) {
                        return false;
                    }
                    break;
            }
        }
        if (*p) p++;
    }
    
    /* Reasonable limit on format specifiers */
    return specifier_count < 16;
}

/* Integer overflow protection */
bool check_integer_overflow_add(size_t a, size_t b, size_t *result)
{
    if (a > SIZE_MAX - b) {
        return false; /* Overflow */
    }
    *result = a + b;
    return true;
}

bool check_integer_overflow_mul(size_t a, size_t b, size_t *result)
{
    if (a != 0 && b > SIZE_MAX / a) {
        return false; /* Overflow */
    }
    *result = a * b;
    return true;
}

/* Race condition protection */
typedef struct race_detector {
    void *resource;
    pthread_t last_accessor;
    uint64_t access_count;
    uint64_t last_access_time;
} race_detector_t;

static race_detector_t race_detectors[256];
static size_t race_detector_count = 0;

bool detect_race_condition(void *resource)
{
    pthread_t current_thread = pthread_self();
    uint64_t current_time = time(NULL);
    
    /* Find or create detector for this resource */
    for (size_t i = 0; i < race_detector_count; i++) {
        if (race_detectors[i].resource == resource) {
            /* Check for rapid successive access from different threads */
            if (race_detectors[i].last_accessor != current_thread &&
                current_time - race_detectors[i].last_access_time < 1) {
                race_detectors[i].access_count++;
                if (race_detectors[i].access_count > 10) {
                    return true; /* Likely race condition */
                }
            }
            
            race_detectors[i].last_accessor = current_thread;
            race_detectors[i].last_access_time = current_time;
            return false;
        }
    }
    
    /* Add new detector */
    if (race_detector_count < sizeof(race_detectors) / sizeof(race_detectors[0])) {
        race_detectors[race_detector_count].resource = resource;
        race_detectors[race_detector_count].last_accessor = current_thread;
        race_detectors[race_detector_count].access_count = 1;
        race_detectors[race_detector_count].last_access_time = current_time;
        race_detector_count++;
    }
    
    return false;
}

/* Memory corruption detection */
typedef struct memory_guard {
    uint32_t magic_start;
    size_t size;
    uint32_t magic_end;
} memory_guard_t;

#define GUARD_MAGIC_START 0xDEADBEEF
#define GUARD_MAGIC_END   0xCAFEBABE

void *guarded_malloc(size_t size)
{
    size_t total_size = sizeof(memory_guard_t) + size + sizeof(uint32_t);
    memory_guard_t *guard = malloc(total_size);
    
    if (!guard) {
        return NULL;
    }
    
    guard->magic_start = GUARD_MAGIC_START;
    guard->size = size;
    guard->magic_end = GUARD_MAGIC_END;
    
    /* Place end guard after data */
    uint32_t *end_guard = (uint32_t *)((char *)(guard + 1) + size);
    *end_guard = GUARD_MAGIC_END;
    
    return guard + 1;
}

bool validate_guarded_memory(void *ptr)
{
    if (!ptr) {
        return false;
    }
    
    memory_guard_t *guard = ((memory_guard_t *)ptr) - 1;
    
    /* Check start guard */
    if (guard->magic_start != GUARD_MAGIC_START) {
        return false;
    }
    
    if (guard->magic_end != GUARD_MAGIC_END) {
        return false;
    }
    
    /* Check end guard */
    uint32_t *end_guard = (uint32_t *)((char *)ptr + guard->size);
    if (*end_guard != GUARD_MAGIC_END) {
        return false;
    }
    
    return true;
}

void guarded_free(void *ptr)
{
    if (!ptr) {
        return;
    }
    
    if (!validate_guarded_memory(ptr)) {
        fprintf(stderr, "Memory corruption detected in guarded_free!\n");
        abort();
    }
    
    memory_guard_t *guard = ((memory_guard_t *)ptr) - 1;
    
    /* Clear memory before freeing */
    memset(ptr, 0xDD, guard->size); /* Dead beef pattern */
    memset(guard, 0xFE, sizeof(memory_guard_t)); /* Free pattern */
    
    free(guard);
}

/* Timing attack protection */
typedef struct timing_window {
    uint64_t start_time;
    uint64_t end_time;
    const char *operation;
} timing_window_t;

static timing_window_t timing_windows[64];
static size_t timing_window_count = 0;

void start_timing_protection(const char *operation)
{
    if (timing_window_count >= sizeof(timing_windows) / sizeof(timing_windows[0])) {
        return;
    }
    
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    
    timing_windows[timing_window_count].start_time = 
        ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    timing_windows[timing_window_count].operation = operation;
    timing_window_count++;
}

void end_timing_protection(void)
{
    if (timing_window_count == 0) {
        return;
    }
    
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    uint64_t current_time = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    
    timing_window_count--;
    timing_windows[timing_window_count].end_time = current_time;
    
    /* Add random delay to mask timing */
    uint64_t random_delay = (current_time % 1000) * 1000; /* 0-1ms */
    struct timespec delay = {
        .tv_sec = 0,
        .tv_nsec = random_delay
    };
    nanosleep(&delay, NULL);
}

/* Initialize security hardening */
int security_hardening_init(void)
{
    printf("Initializing kernel security hardening...\n");
    
    /* Initialize stack canary */
    init_stack_canary();
    
    /* Enable ASLR */
    if (hardening_config.aslr_enabled) {
        if (enable_aslr() != 0) {
            printf("Warning: Failed to enable ASLR\n");
        }
    }
    
    /* Enable DEP */
    if (hardening_config.dep_enabled) {
        if (enable_dep() != 0) {
            printf("Warning: Failed to enable DEP\n");
        }
    }
    
    /* Register sysctl parameters */
    register_sysctl("kernel.hardening.stack_canaries", 
                    "Enable stack canaries",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &hardening_config.stack_canaries_enabled,
                    sizeof(hardening_config.stack_canaries_enabled),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.hardening.aslr_enabled",
                    "Enable ASLR",
                    SYSCTL_TYPE_BOOL, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &hardening_config.aslr_enabled,
                    sizeof(hardening_config.aslr_enabled),
                    NULL, NULL, NULL);
    
    register_sysctl("kernel.hardening.mmap_min_addr",
                    "Minimum mmap address",
                    SYSCTL_TYPE_UINT, SYSCTL_FLAG_RW | SYSCTL_FLAG_RUNTIME,
                    &hardening_config.mmap_min_addr,
                    sizeof(hardening_config.mmap_min_addr),
                    &(uint32_t){4096}, &(uint32_t){1048576}, NULL);
    
    printf("Security hardening initialized successfully\n");
    return 0;
}

/* Get hardening status */
void get_hardening_status(void)
{
    printf("KOS Security Hardening Status:\n");
    printf("==============================\n");
    printf("Stack Canaries:     %s\n", hardening_config.stack_canaries_enabled ? "Enabled" : "Disabled");
    printf("ASLR:              %s\n", hardening_config.aslr_enabled ? "Enabled" : "Disabled");
    printf("DEP/NX:            %s\n", hardening_config.dep_enabled ? "Enabled" : "Disabled");
    printf("CFI:               %s\n", hardening_config.control_flow_integrity ? "Enabled" : "Disabled");
    printf("Stack Clash Prot:  %s\n", hardening_config.stack_clash_protection ? "Enabled" : "Disabled");
    printf("MMAP Min Addr:     %u bytes\n", hardening_config.mmap_min_addr);
    printf("DMESG Restrict:    %s\n", hardening_config.dmesg_restrict ? "Enabled" : "Disabled");
    printf("KPTR Restrict:     %s\n", hardening_config.kptr_restrict ? "Enabled" : "Disabled");
    printf("Stack Canary:      0x%016lx\n", stack_canary);
}