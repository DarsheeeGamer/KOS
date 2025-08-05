/*
 * KOS Interrupt Request (IRQ) Management System
 * Handles IRQ registration, interrupt handlers, and IRQ balancing
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <errno.h>
#include <stdbool.h>
#include <sys/time.h>

/* IRQ constants */
#define MAX_IRQS            256
#define MAX_HANDLERS_PER_IRQ 16
#define IRQ_THREAD_STACK_SIZE 65536

/* IRQ flags */
#define IRQ_FLAG_SHARED     0x01
#define IRQ_FLAG_DISABLED   0x02
#define IRQ_FLAG_LEVEL      0x04
#define IRQ_FLAG_EDGE       0x08
#define IRQ_FLAG_ONESHOT    0x10
#define IRQ_FLAG_THREADED   0x20

/* IRQ states */
typedef enum {
    IRQ_STATE_INACTIVE,
    IRQ_STATE_ACTIVE,
    IRQ_STATE_DISABLED,
    IRQ_STATE_PENDING,
    IRQ_STATE_HANDLING
} irq_state_t;

/* IRQ handler descriptor */
typedef struct irq_handler {
    const char* name;
    kos_irq_handler_t handler;
    void* data;
    uint32_t flags;
    uint64_t count;         /* Number of times called */
    uint64_t total_time;    /* Total time spent in handler (ns) */
    uint64_t last_time;     /* Last execution time */
    struct irq_handler* next;
} irq_handler_t;

/* IRQ descriptor */
typedef struct irq_desc {
    uint32_t irq;
    irq_state_t state;
    uint32_t flags;
    irq_handler_t* handlers;
    uint32_t handler_count;
    
    /* Statistics */
    uint64_t count;         /* Total interrupt count */
    uint64_t spurious;      /* Spurious interrupt count */
    uint64_t unhandled;     /* Unhandled interrupt count */
    uint64_t total_time;    /* Total time spent handling */
    uint64_t max_time;      /* Maximum time for single handler */
    uint64_t last_time;     /* Last interrupt timestamp */
    
    /* Threading support */
    pthread_t thread;
    bool thread_active;
    pthread_mutex_t thread_lock;
    pthread_cond_t thread_cond;
    bool thread_pending;
    
    /* Load balancing */
    uint32_t cpu_affinity;
    uint32_t current_cpu;
    uint64_t load_weight;
    
    /* Synchronization */
    pthread_mutex_t lock;
} irq_desc_t;

/* IRQ balancing policy */
typedef enum {
    IRQ_BALANCE_NONE,       /* No balancing */
    IRQ_BALANCE_ROUND_ROBIN,/* Round-robin across CPUs */
    IRQ_BALANCE_LOAD_BASED, /* Based on CPU load */
    IRQ_BALANCE_ADAPTIVE    /* Adaptive based on interrupt load */
} irq_balance_policy_t;

/* Global IRQ management state */
static struct {
    irq_desc_t irq_desc[MAX_IRQS];
    
    /* IRQ balancing */
    irq_balance_policy_t balance_policy;
    uint32_t balance_interval;      /* Balance interval in ms */
    uint64_t last_balance_time;
    uint32_t next_cpu;              /* For round-robin */
    pthread_t balance_thread;
    bool balance_thread_running;
    
    /* Statistics */
    uint64_t total_interrupts;
    uint64_t nested_interrupts;
    uint64_t max_nested_level;
    uint64_t current_nested_level;
    uint64_t balance_operations;
    
    /* CPU information (simulated) */
    uint32_t num_cpus;
    uint64_t cpu_loads[32];         /* Per-CPU load (simplified) */
    
    /* Global synchronization */
    pthread_mutex_t global_lock;
    bool initialized;
    bool interrupts_enabled;
} irq_state = {0};

/* Forward declarations */
static void* irq_thread_func(void* arg);
static void* irq_balance_thread_func(void* arg);
static void handle_irq_threaded(irq_desc_t* desc);
static uint64_t get_time_ns(void);
static uint32_t select_target_cpu(uint32_t irq);
static void balance_irqs(void);
static void update_cpu_loads(void);
static int signal_to_irq(int signal);
static void irq_signal_handler(int sig);

/* Signal to IRQ mapping (simplified) */
static const struct {
    int signal;
    uint32_t irq;
    const char* name;
} signal_irq_map[] = {
    {SIGTERM, 1, "SIGTERM"},
    {SIGINT,  2, "SIGINT"},
    {SIGUSR1, 10, "SIGUSR1"},
    {SIGUSR2, 11, "SIGUSR2"},
    {SIGALRM, 14, "SIGALRM"},
    {SIGCHLD, 17, "SIGCHLD"}
};

/* Initialize IRQ management system */
void kos_irq_init(void) {
    if (irq_state.initialized) {
        return;
    }
    
    memset(&irq_state, 0, sizeof(irq_state));
    
    /* Initialize global mutex */
    pthread_mutex_init(&irq_state.global_lock, NULL);
    
    /* Initialize IRQ descriptors */
    for (uint32_t i = 0; i < MAX_IRQS; i++) {
        irq_desc_t* desc = &irq_state.irq_desc[i];
        desc->irq = i;
        desc->state = IRQ_STATE_INACTIVE;
        desc->cpu_affinity = 0xFFFFFFFF;  /* All CPUs */
        pthread_mutex_init(&desc->lock, NULL);
        pthread_mutex_init(&desc->thread_lock, NULL);
        pthread_cond_init(&desc->thread_cond, NULL);
    }
    
    /* Set up default balancing policy */
    irq_state.balance_policy = IRQ_BALANCE_ROUND_ROBIN;
    irq_state.balance_interval = 1000;  /* 1 second */
    irq_state.num_cpus = 1;  /* Simplified for userspace */
    
    /* Set up signal handlers for simulated IRQs */
    for (size_t i = 0; i < sizeof(signal_irq_map)/sizeof(signal_irq_map[0]); i++) {
        signal(signal_irq_map[i].signal, irq_signal_handler);
    }
    
    /* Start IRQ balancing thread */
    irq_state.balance_thread_running = true;
    if (pthread_create(&irq_state.balance_thread, NULL, irq_balance_thread_func, NULL) != 0) {
        printf("KOS IRQ: Failed to create IRQ balancing thread\n");
        irq_state.balance_thread_running = false;
    }
    
    irq_state.interrupts_enabled = true;
    irq_state.initialized = true;
    
    printf("KOS IRQ: Interrupt management system initialized\n");
}

/* Register an IRQ handler */
int kos_irq_register(uint32_t irq, kos_irq_handler_t handler, void* data) {
    return kos_irq_register_named(irq, handler, data, "unnamed", 0);
}

/* Register a named IRQ handler with flags */
int kos_irq_register_named(uint32_t irq, kos_irq_handler_t handler, void* data, 
                          const char* name, uint32_t flags) {
    if (irq >= MAX_IRQS || !handler) {
        return -EINVAL;
    }
    
    irq_desc_t* desc = &irq_state.irq_desc[irq];
    
    pthread_mutex_lock(&desc->lock);
    
    /* Check if IRQ is already registered and not shared */
    if (desc->handler_count > 0 && !(flags & IRQ_FLAG_SHARED) && 
        !(desc->flags & IRQ_FLAG_SHARED)) {
        pthread_mutex_unlock(&desc->lock);
        return -EBUSY;
    }
    
    /* Check handler limit */
    if (desc->handler_count >= MAX_HANDLERS_PER_IRQ) {
        pthread_mutex_unlock(&desc->lock);
        return -ENOSPC;
    }
    
    /* Allocate handler */
    irq_handler_t* h = calloc(1, sizeof(irq_handler_t));
    if (!h) {
        pthread_mutex_unlock(&desc->lock);
        return -ENOMEM;
    }
    
    /* Initialize handler */
    h->name = name ? strdup(name) : strdup("unnamed");
    h->handler = handler;
    h->data = data;
    h->flags = flags;
    
    /* Add to handler list */
    h->next = desc->handlers;
    desc->handlers = h;
    desc->handler_count++;
    desc->flags |= flags;
    
    /* Activate IRQ if this is the first handler */
    if (desc->state == IRQ_STATE_INACTIVE) {
        desc->state = IRQ_STATE_ACTIVE;
        
        /* Create threaded IRQ handler if requested */
        if (flags & IRQ_FLAG_THREADED) {
            pthread_attr_t attr;
            pthread_attr_init(&attr);
            pthread_attr_setstacksize(&attr, IRQ_THREAD_STACK_SIZE);
            
            desc->thread_active = true;
            if (pthread_create(&desc->thread, &attr, irq_thread_func, desc) != 0) {
                printf("KOS IRQ: Failed to create thread for IRQ %d\n", irq);
                desc->thread_active = false;
            }
            
            pthread_attr_destroy(&attr);
        }
        
        /* Select initial CPU */
        desc->current_cpu = select_target_cpu(irq);
    }
    
    pthread_mutex_unlock(&desc->lock);
    
    printf("KOS IRQ: Registered handler '%s' for IRQ %d (flags=0x%x)\n", 
           h->name, irq, flags);
    
    return 0;
}

/* Unregister an IRQ handler */
int kos_irq_unregister(uint32_t irq, kos_irq_handler_t handler) {
    if (irq >= MAX_IRQS || !handler) {
        return -EINVAL;
    }
    
    irq_desc_t* desc = &irq_state.irq_desc[irq];
    
    pthread_mutex_lock(&desc->lock);
    
    /* Find and remove handler */
    irq_handler_t** pos = &desc->handlers;
    while (*pos) {
        if ((*pos)->handler == handler) {
            irq_handler_t* h = *pos;
            *pos = h->next;
            desc->handler_count--;
            
            free((void*)h->name);
            free(h);
            
            /* Deactivate IRQ if no more handlers */
            if (desc->handler_count == 0) {
                desc->state = IRQ_STATE_INACTIVE;
                
                /* Stop threaded handler */
                if (desc->thread_active) {
                    desc->thread_active = false;
                    pthread_cond_signal(&desc->thread_cond);
                    pthread_mutex_unlock(&desc->lock);
                    pthread_join(desc->thread, NULL);
                    pthread_mutex_lock(&desc->lock);
                }
            }
            
            pthread_mutex_unlock(&desc->lock);
            printf("KOS IRQ: Unregistered handler for IRQ %d\n", irq);
            return 0;
        }
        pos = &(*pos)->next;
    }
    
    pthread_mutex_unlock(&desc->lock);
    return -ENOENT;
}

/* Enable an IRQ */
void kos_irq_enable(uint32_t irq) {
    if (irq >= MAX_IRQS) {
        return;
    }
    
    irq_desc_t* desc = &irq_state.irq_desc[irq];
    
    pthread_mutex_lock(&desc->lock);
    
    if (desc->state == IRQ_STATE_DISABLED) {
        desc->state = IRQ_STATE_ACTIVE;
        desc->flags &= ~IRQ_FLAG_DISABLED;
    }
    
    pthread_mutex_unlock(&desc->lock);
}

/* Disable an IRQ */
void kos_irq_disable(uint32_t irq) {
    if (irq >= MAX_IRQS) {
        return;
    }
    
    irq_desc_t* desc = &irq_state.irq_desc[irq];
    
    pthread_mutex_lock(&desc->lock);
    
    if (desc->state == IRQ_STATE_ACTIVE) {
        desc->state = IRQ_STATE_DISABLED;
        desc->flags |= IRQ_FLAG_DISABLED;
    }
    
    pthread_mutex_unlock(&desc->lock);
}

/* Handle an interrupt (internal function) */
static void handle_interrupt(uint32_t irq) {
    if (irq >= MAX_IRQS) {
        return;
    }
    
    irq_desc_t* desc = &irq_state.irq_desc[irq];
    
    pthread_mutex_lock(&irq_state.global_lock);
    irq_state.total_interrupts++;
    irq_state.current_nested_level++;
    if (irq_state.current_nested_level > 1) {
        irq_state.nested_interrupts++;
    }
    if (irq_state.current_nested_level > irq_state.max_nested_level) {
        irq_state.max_nested_level = irq_state.current_nested_level;
    }
    pthread_mutex_unlock(&irq_state.global_lock);
    
    pthread_mutex_lock(&desc->lock);
    
    /* Check if IRQ is enabled */
    if (desc->state != IRQ_STATE_ACTIVE) {
        desc->spurious++;
        pthread_mutex_unlock(&desc->lock);
        goto cleanup;
    }
    
    desc->count++;
    desc->last_time = get_time_ns();
    desc->state = IRQ_STATE_HANDLING;
    
    /* Handle threaded IRQs */
    if (desc->flags & IRQ_FLAG_THREADED) {
        pthread_mutex_lock(&desc->thread_lock);
        desc->thread_pending = true;
        pthread_cond_signal(&desc->thread_cond);
        pthread_mutex_unlock(&desc->thread_lock);
        pthread_mutex_unlock(&desc->lock);
        goto cleanup;
    }
    
    /* Handle IRQ directly */
    uint64_t start_time = get_time_ns();
    bool handled = false;
    
    irq_handler_t* handler = desc->handlers;
    while (handler) {
        if (handler->handler) {
            handler->handler(irq, handler->data);
            handler->count++;
            handled = true;
        }
        handler = handler->next;
    }
    
    uint64_t end_time = get_time_ns();
    uint64_t duration = end_time - start_time;
    
    desc->total_time += duration;
    if (duration > desc->max_time) {
        desc->max_time = duration;
    }
    
    if (!handled) {
        desc->unhandled++;
    }
    
    desc->state = IRQ_STATE_ACTIVE;
    pthread_mutex_unlock(&desc->lock);
    
cleanup:
    pthread_mutex_lock(&irq_state.global_lock);
    irq_state.current_nested_level--;
    pthread_mutex_unlock(&irq_state.global_lock);
}

/* Threaded IRQ handler */
static void* irq_thread_func(void* arg) {
    irq_desc_t* desc = (irq_desc_t*)arg;
    
    while (desc->thread_active) {
        pthread_mutex_lock(&desc->thread_lock);
        
        while (!desc->thread_pending && desc->thread_active) {
            pthread_cond_wait(&desc->thread_cond, &desc->thread_lock);
        }
        
        if (!desc->thread_active) {
            pthread_mutex_unlock(&desc->thread_lock);
            break;
        }
        
        desc->thread_pending = false;
        pthread_mutex_unlock(&desc->thread_lock);
        
        /* Handle the interrupt */
        handle_irq_threaded(desc);
    }
    
    return NULL;
}

/* Handle IRQ in thread context */
static void handle_irq_threaded(irq_desc_t* desc) {
    pthread_mutex_lock(&desc->lock);
    
    uint64_t start_time = get_time_ns();
    bool handled = false;
    
    irq_handler_t* handler = desc->handlers;
    while (handler) {
        if (handler->handler) {
            handler->handler(desc->irq, handler->data);
            handler->count++;
            handled = true;
        }
        handler = handler->next;
    }
    
    uint64_t end_time = get_time_ns();
    uint64_t duration = end_time - start_time;
    
    desc->total_time += duration;
    if (duration > desc->max_time) {
        desc->max_time = duration;
    }
    
    if (!handled) {
        desc->unhandled++;
    }
    
    desc->state = IRQ_STATE_ACTIVE;
    pthread_mutex_unlock(&desc->lock);
}

/* IRQ balancing thread */
static void* irq_balance_thread_func(void* arg) {
    (void)arg;
    
    while (irq_state.balance_thread_running) {
        usleep(irq_state.balance_interval * 1000);  /* Convert ms to us */
        
        if (irq_state.balance_policy != IRQ_BALANCE_NONE) {
            balance_irqs();
        }
        
        update_cpu_loads();
    }
    
    return NULL;
}

/* Signal handler for simulated IRQs */
static void irq_signal_handler(int sig) {
    int irq_num = signal_to_irq(sig);
    if (irq_num >= 0) {
        handle_interrupt(irq_num);
    }
}

/* Convert signal to IRQ number */
static int signal_to_irq(int signal) {
    for (size_t i = 0; i < sizeof(signal_irq_map)/sizeof(signal_irq_map[0]); i++) {
        if (signal_irq_map[i].signal == signal) {
            return signal_irq_map[i].irq;
        }
    }
    return -1;
}

/* Helper functions */
static uint64_t get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static uint32_t select_target_cpu(uint32_t irq) {
    switch (irq_state.balance_policy) {
        case IRQ_BALANCE_ROUND_ROBIN:
            return irq_state.next_cpu++ % irq_state.num_cpus;
            
        case IRQ_BALANCE_LOAD_BASED: {
            uint32_t best_cpu = 0;
            uint64_t min_load = irq_state.cpu_loads[0];
            for (uint32_t i = 1; i < irq_state.num_cpus; i++) {
                if (irq_state.cpu_loads[i] < min_load) {
                    min_load = irq_state.cpu_loads[i];
                    best_cpu = i;
                }
            }
            return best_cpu;
        }
        
        default:
            return 0;
    }
}

static void balance_irqs(void) {
    /* Simplified IRQ balancing */
    irq_state.balance_operations++;
    
    /* For now, just update the next CPU for round-robin */
    if (irq_state.balance_policy == IRQ_BALANCE_ROUND_ROBIN) {
        irq_state.next_cpu = (irq_state.next_cpu + 1) % irq_state.num_cpus;
    }
}

static void update_cpu_loads(void) {
    /* Simplified CPU load update */
    for (uint32_t i = 0; i < irq_state.num_cpus; i++) {
        /* Simulate some load variation */
        irq_state.cpu_loads[i] = (irq_state.cpu_loads[i] * 9 + (rand() % 100)) / 10;
    }
}

/* Get IRQ statistics */
void kos_irq_get_stats(struct kos_irq_stats* stats) {
    if (!stats) {
        return;
    }
    
    memset(stats, 0, sizeof(*stats));
    
    pthread_mutex_lock(&irq_state.global_lock);
    
    stats->total_interrupts = irq_state.total_interrupts;
    stats->nested_interrupts = irq_state.nested_interrupts;
    stats->max_nested_level = irq_state.max_nested_level;
    stats->balance_operations = irq_state.balance_operations;
    stats->num_cpus = irq_state.num_cpus;
    
    /* Count active IRQs */
    for (uint32_t i = 0; i < MAX_IRQS; i++) {
        if (irq_state.irq_desc[i].state != IRQ_STATE_INACTIVE) {
            stats->active_irqs++;
        }
    }
    
    pthread_mutex_unlock(&irq_state.global_lock);
}

/* Print IRQ information */
void kos_irq_print_info(void) {
    printf("IRQ Information:\n");
    printf("================\n");
    
    pthread_mutex_lock(&irq_state.global_lock);
    
    printf("Total interrupts: %lu\n", irq_state.total_interrupts);
    printf("Nested interrupts: %lu\n", irq_state.nested_interrupts);
    printf("Max nested level: %lu\n", irq_state.max_nested_level);
    printf("Balance operations: %lu\n", irq_state.balance_operations);
    printf("Balance policy: %d\n", irq_state.balance_policy);
    printf("Number of CPUs: %u\n", irq_state.num_cpus);
    
    printf("\nActive IRQs:\n");
    for (uint32_t i = 0; i < MAX_IRQS; i++) {
        irq_desc_t* desc = &irq_state.irq_desc[i];
        if (desc->state != IRQ_STATE_INACTIVE) {
            printf("  IRQ %3d: count=%8lu unhandled=%8lu handlers=%u cpu=%u\n",
                   i, desc->count, desc->unhandled, desc->handler_count, desc->current_cpu);
            
            irq_handler_t* handler = desc->handlers;
            while (handler) {
                printf("    Handler: %s (count=%lu)\n", handler->name, handler->count);
                handler = handler->next;
            }
        }
    }
    
    pthread_mutex_unlock(&irq_state.global_lock);
}

/* IRQ statistics structure */
struct kos_irq_stats {
    uint64_t total_interrupts;
    uint64_t nested_interrupts;
    uint64_t max_nested_level;
    uint64_t balance_operations;
    uint32_t active_irqs;
    uint32_t num_cpus;
};

/* Extended IRQ registration function */
int kos_irq_register_named(uint32_t irq, kos_irq_handler_t handler, void* data, 
                          const char* name, uint32_t flags);

/* Cleanup IRQ system */
void kos_irq_cleanup(void) {
    if (!irq_state.initialized) {
        return;
    }
    
    /* Stop balancing thread */
    irq_state.balance_thread_running = false;
    if (irq_state.balance_thread) {
        pthread_join(irq_state.balance_thread, NULL);
    }
    
    /* Clean up all IRQ descriptors */
    for (uint32_t i = 0; i < MAX_IRQS; i++) {
        irq_desc_t* desc = &irq_state.irq_desc[i];
        
        /* Stop threaded handler */
        if (desc->thread_active) {
            desc->thread_active = false;
            pthread_cond_signal(&desc->thread_cond);
            pthread_join(desc->thread, NULL);
        }
        
        /* Free handlers */
        irq_handler_t* handler = desc->handlers;
        while (handler) {
            irq_handler_t* next = handler->next;
            free((void*)handler->name);
            free(handler);
            handler = next;
        }
        
        /* Destroy synchronization objects */
        pthread_mutex_destroy(&desc->lock);
        pthread_mutex_destroy(&desc->thread_lock);
        pthread_cond_destroy(&desc->thread_cond);
    }
    
    pthread_mutex_destroy(&irq_state.global_lock);
    irq_state.initialized = false;
    
    printf("KOS IRQ: Interrupt management system cleaned up\n");
}