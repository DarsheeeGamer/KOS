/*
 * KOS Kernel Integration Header
 * Main header for all kernel subsystems
 */

#ifndef KOS_KERNEL_H
#define KOS_KERNEL_H

#include "kcore.h"
#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Kernel subsystem initialization functions */
void syscall_init(void);
void kos_irq_init(void);
void kos_timer_init(void);
void kos_panic_init(void);

/* System call interface */
int64_t kos_syscall_dispatch(uint32_t nr, uint64_t arg1, uint64_t arg2, uint64_t arg3,
                            uint64_t arg4, uint64_t arg5, uint64_t arg6);

/* Panic and debugging */
void kos_kernel_panic_detailed(const char* message, const char* file, int line, const char* func);
void kos_panic_if(bool condition, const char* message);
void kos_assert_panic(bool condition, const char* expr, const char* file, int line, const char* func);

/* IRQ management */
int kos_irq_register_named(uint32_t irq, kos_irq_handler_t handler, void* data, 
                          const char* name, uint32_t flags);

/* Timer management */
typedef enum {
    TIMER_ONESHOT,
    TIMER_PERIODIC,
    TIMER_HRTIMER
} timer_type_t;

typedef struct kos_timer kos_timer_t;

kos_timer_t* kos_timer_create(timer_type_t type, uint64_t expires_ms, 
                             void (*callback)(kos_timer_t* timer, void* data), 
                             void* data);
int kos_timer_start(kos_timer_t* timer);
int kos_timer_stop(kos_timer_t* timer);
int kos_timer_delete(kos_timer_t* timer);

/* Time management */
uint64_t kos_time_get_ns(void);
void kos_time_delay(uint64_t microseconds);

/* Boot and shutdown */
int kos_kernel_init_full(void* boot_params);
void kos_kernel_shutdown(bool reboot);
void kos_enter_emergency_mode(const char* reason);

/* Boot information */
struct kos_boot_info {
    uint64_t boot_time;
    bool boot_complete;
    bool emergency_mode;
    char cmdline[1024];
    char kernel_version[64];
};

void kos_get_boot_info(struct kos_boot_info* info);

/* Statistics structures */
struct kos_irq_stats {
    uint64_t total_interrupts;
    uint64_t nested_interrupts;
    uint64_t max_nested_level;
    uint64_t balance_operations;
    uint32_t active_irqs;
    uint32_t num_cpus;
};

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

struct kos_panic_stats {
    uint32_t panic_count;
    uint64_t last_panic_time;
    char last_panic_message[1024];
    bool in_panic;
};

/* Statistics functions */
void kos_irq_get_stats(struct kos_irq_stats* stats);
void kos_time_get_stats(struct kos_time_stats* stats);
void kos_get_panic_stats(struct kos_panic_stats* stats);
void kos_irq_print_info(void);
void syscall_print_stats(void);

/* Cleanup functions */
void kos_irq_cleanup(void);
void kos_timer_cleanup(void);

/* Convenient macros */
#define KOS_PANIC(msg) kos_kernel_panic_detailed(msg, __FILE__, __LINE__, __func__)
#define KOS_BUG() kos_bug(__FILE__, __LINE__, __func__)
#define KOS_WARN(msg) kos_warn(msg, __FILE__, __LINE__, __func__)
#define KOS_ASSERT(cond) kos_assert_panic(cond, #cond, __FILE__, __LINE__, __func__)

/* IRQ flags */
#define IRQ_FLAG_SHARED     0x01
#define IRQ_FLAG_DISABLED   0x02
#define IRQ_FLAG_LEVEL      0x04
#define IRQ_FLAG_EDGE       0x08
#define IRQ_FLAG_ONESHOT    0x10
#define IRQ_FLAG_THREADED   0x20

#ifdef __cplusplus
}
#endif

#endif /* KOS_KERNEL_H */