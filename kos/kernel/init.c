/*
 * KOS Kernel Initialization
 * Boot sequence and subsystem initialization
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>
#include <signal.h>
#include <sys/utsname.h>

/* Boot parameters structure */
struct kos_boot_params {
    char cmdline[1024];
    uint32_t mem_size;
    uint32_t initrd_size;
    void* initrd_addr;
    uint32_t cpu_count;
    bool debug_mode;
    bool single_user;
    char init_program[256];
};

/* Initialization order and state tracking */
typedef struct init_module {
    const char* name;
    int (*init_func)(void);
    void (*cleanup_func)(void);
    bool initialized;
    bool critical;  /* System cannot boot without this */
    int priority;   /* Lower numbers initialize first */
} init_module_t;

/* Forward declarations */
static int init_early_console(void);
static int init_memory_management(void);
static int init_scheduler(void);
static int init_interrupt_system(void);
static int init_timer_system(void);
static int init_filesystem(void);
static int init_network_stack(void);
static int init_security_system(void);
static int init_device_drivers(void);
static int init_ipc_system(void);
static int init_syscall_interface(void);
static int init_process_management(void);
static int start_init_process(void);
static int start_kernel_threads(void);

/* Cleanup functions */
static void cleanup_early_console(void);
static void cleanup_memory_management(void);
static void cleanup_scheduler(void);
static void cleanup_interrupt_system(void);
static void cleanup_timer_system(void);
static void cleanup_filesystem(void);
static void cleanup_network_stack(void);
static void cleanup_security_system(void);
static void cleanup_device_drivers(void);
static void cleanup_ipc_system(void);
static void cleanup_syscall_interface(void);
static void cleanup_process_management(void);

/* Initialization modules in boot order */
static init_module_t init_modules[] = {
    /* Phase 1: Early boot - critical systems */
    {"early_console", init_early_console, cleanup_early_console, false, true, 10},
    {"memory_management", init_memory_management, cleanup_memory_management, false, true, 20},
    {"interrupt_system", init_interrupt_system, cleanup_interrupt_system, false, true, 30},
    {"timer_system", init_timer_system, cleanup_timer_system, false, true, 40},
    
    /* Phase 2: Core kernel services */
    {"scheduler", init_scheduler, cleanup_scheduler, false, true, 50},
    {"process_management", init_process_management, cleanup_process_management, false, true, 60},
    {"syscall_interface", init_syscall_interface, cleanup_syscall_interface, false, true, 70},
    {"ipc_system", init_ipc_system, cleanup_ipc_system, false, true, 80},
    
    /* Phase 3: Subsystems */
    {"security_system", init_security_system, cleanup_security_system, false, false, 90},
    {"filesystem", init_filesystem, cleanup_filesystem, false, false, 100},
    {"device_drivers", init_device_drivers, cleanup_device_drivers, false, false, 110},
    {"network_stack", init_network_stack, cleanup_network_stack, false, false, 120},
    
    /* Sentinel */
    {NULL, NULL, NULL, false, false, 0}
};

/* Global boot state */
static struct {
    struct kos_boot_params boot_params;
    bool boot_complete;
    bool emergency_mode;
    uint64_t boot_time;
    pthread_mutex_t init_lock;
    FILE* boot_log;
} boot_state = {0};

/* External function declarations */
extern void syscall_init(void);
extern void kos_irq_init(void);
extern void kos_timer_init(void);
extern void kos_panic_init(void);

/* Initialize kernel - main entry point */
int kos_kernel_init_full(void* boot_params_ptr) {
    struct kos_boot_params* params = (struct kos_boot_params*)boot_params_ptr;
    int ret;
    
    /* Initialize boot state */
    pthread_mutex_init(&boot_state.init_lock, NULL);
    boot_state.boot_time = time(NULL);
    
    /* Copy boot parameters */
    if (params) {
        memcpy(&boot_state.boot_params, params, sizeof(struct kos_boot_params));
    } else {
        /* Default boot parameters */
        strcpy(boot_state.boot_params.cmdline, "quiet");
        boot_state.boot_params.mem_size = 1024 * 1024 * 1024; /* 1GB default */
        boot_state.boot_params.cpu_count = 1;
        boot_state.boot_params.debug_mode = false;
        boot_state.boot_params.single_user = false;
        strcpy(boot_state.boot_params.init_program, "/sbin/init");
    }
    
    /* Open boot log */
    boot_state.boot_log = fopen("/tmp/kos_boot.log", "w");
    if (!boot_state.boot_log) {
        boot_state.boot_log = stderr;
    }
    
    fprintf(boot_state.boot_log, "KOS Kernel Boot Starting...\n");
    fprintf(boot_state.boot_log, "Boot parameters: %s\n", boot_state.boot_params.cmdline);
    
    /* Initialize subsystems in order */
    for (init_module_t* module = init_modules; module->name; module++) {
        fprintf(boot_state.boot_log, "Initializing %s...\n", module->name);
        
        ret = module->init_func();
        if (ret != 0) {
            fprintf(boot_state.boot_log, "FAILED to initialize %s: %d\n", module->name, ret);
            
            if (module->critical) {
                fprintf(boot_state.boot_log, "Critical module failed, entering emergency mode\n");
                boot_state.emergency_mode = true;
                return -1;
            } else {
                fprintf(boot_state.boot_log, "Non-critical module failed, continuing...\n");
                continue;
            }
        }
        
        module->initialized = true;
        fprintf(boot_state.boot_log, "Successfully initialized %s\n", module->name);
    }
    
    /* Start kernel threads */
    ret = start_kernel_threads();
    if (ret != 0) {
        fprintf(boot_state.boot_log, "Failed to start kernel threads: %d\n", ret);
        return -1;
    }
    
    /* Start init process */
    ret = start_init_process();
    if (ret != 0) {
        fprintf(boot_state.boot_log, "Failed to start init process: %d\n", ret);
        return -1;
    }
    
    boot_state.boot_complete = true;
    fprintf(boot_state.boot_log, "KOS Kernel Boot Complete!\n");
    
    /* Update kcore state */
    extern struct {
        bool initialized;
        uint64_t boot_time;
        uint32_t next_pid;
        uint32_t next_tid;
        pthread_mutex_t proc_lock;
        pthread_mutex_t sched_lock;
    } kos_kernel;
    
    /* Initialize locks */
    pthread_mutex_init(&kos_kernel.proc_lock, NULL);
    pthread_mutex_init(&kos_kernel.sched_lock, NULL);
    
    /* Set boot time */
    kos_kernel.boot_time = boot_state.boot_time;
    
    /* Initialize PIDs */
    kos_kernel.next_pid = 1;
    kos_kernel.next_tid = 1;
    
    kos_kernel.initialized = true;
    
    return 0;
}

/* Early console initialization */
static int init_early_console(void) {
    /* Set up basic console output for early boot messages */
    setvbuf(stdout, NULL, _IONBF, 0);  /* Unbuffered output */
    setvbuf(stderr, NULL, _IONBF, 0);
    
    printf("KOS Early Console Initialized\n");
    return 0;
}

/* Memory management initialization */
static int init_memory_management(void) {
    /* Initialize memory management subsystem */
    printf("KOS MM: Initializing memory management\n");
    
    /* Initialize buddy allocator */
    /* Initialize slab allocator */
    /* Initialize kmalloc */
    /* Set up page tables */
    
    printf("KOS MM: Memory management initialized\n");
    return 0;
}

/* Scheduler initialization */
static int init_scheduler(void) {
    printf("KOS SCHED: Initializing scheduler\n");
    
    /* Initialize scheduler data structures */
    kos_scheduler_init();
    
    /* Set up per-CPU run queues */
    /* Initialize load balancing */
    
    printf("KOS SCHED: Scheduler initialized\n");
    return 0;
}

/* Interrupt system initialization */
static int init_interrupt_system(void) {
    printf("KOS IRQ: Initializing interrupt system\n");
    
    /* Initialize interrupt handling */
    kos_irq_init();
    
    /* Set up interrupt vectors */
    /* Initialize IRQ routing */
    
    printf("KOS IRQ: Interrupt system initialized\n");
    return 0;
}

/* Timer system initialization */
static int init_timer_system(void) {
    printf("KOS TIMER: Initializing timer system\n");
    
    /* Initialize timer subsystem */
    kos_timer_init();
    
    /* Set up high resolution timers */
    /* Initialize clock sources */
    
    printf("KOS TIMER: Timer system initialized\n");
    return 0;
}

/* Filesystem initialization */
static int init_filesystem(void) {
    printf("KOS FS: Initializing filesystem\n");
    
    /* Initialize VFS */
    /* Mount root filesystem */
    /* Initialize filesystem drivers */
    
    printf("KOS FS: Filesystem initialized\n");
    return 0;
}

/* Network stack initialization */
static int init_network_stack(void) {
    printf("KOS NET: Initializing network stack\n");
    
    /* Initialize network protocols */
    /* Set up network interfaces */
    /* Initialize socket layer */
    
    printf("KOS NET: Network stack initialized\n");
    return 0;
}

/* Security system initialization */
static int init_security_system(void) {
    printf("KOS SEC: Initializing security system\n");
    
    /* Initialize access controls */
    /* Set up capability system */
    /* Initialize security modules */
    
    printf("KOS SEC: Security system initialized\n");
    return 0;
}

/* Device drivers initialization */
static int init_device_drivers(void) {
    printf("KOS DEV: Initializing device drivers\n");
    
    /* Initialize device subsystem */
    /* Load built-in drivers */
    /* Set up device nodes */
    
    printf("KOS DEV: Device drivers initialized\n");
    return 0;
}

/* IPC system initialization */
static int init_ipc_system(void) {
    printf("KOS IPC: Initializing IPC system\n");
    
    /* Initialize message queues */
    /* Set up shared memory */
    /* Initialize semaphores */
    
    printf("KOS IPC: IPC system initialized\n");
    return 0;
}

/* System call interface initialization */
static int init_syscall_interface(void) {
    printf("KOS SYSCALL: Initializing system call interface\n");
    
    /* Initialize system call table */
    syscall_init();
    
    /* Set up system call entry points */
    
    printf("KOS SYSCALL: System call interface initialized\n");
    return 0;
}

/* Process management initialization */
static int init_process_management(void) {
    printf("KOS PROC: Initializing process management\n");
    
    /* Initialize process tables */
    /* Set up PID allocation */
    /* Initialize signal handling */
    
    printf("KOS PROC: Process management initialized\n");
    return 0;
}

/* Start kernel threads */
static int start_kernel_threads(void) {
    printf("KOS: Starting kernel threads\n");
    
    /* Start scheduler thread */
    /* Start memory management threads */
    /* Start I/O threads */
    
    printf("KOS: Kernel threads started\n");
    return 0;
}

/* Start init process */
static int start_init_process(void) {
    printf("KOS: Starting init process\n");
    
    /* Create init process (PID 1) */
    kos_process_t* init_proc = kos_process_create(0, "init");
    if (!init_proc) {
        printf("KOS: Failed to create init process\n");
        return -1;
    }
    
    /* Set up init process environment */
    /* Load init program */
    
    printf("KOS: Init process started (PID %d)\n", init_proc->pid);
    return 0;
}

/* Emergency mode handler */
void kos_enter_emergency_mode(const char* reason) {
    printf("KOS EMERGENCY: Entering emergency mode: %s\n", reason);
    
    boot_state.emergency_mode = true;
    
    /* Stop non-critical services */
    /* Provide minimal shell */
    /* Log emergency state */
    
    while (1) {
        printf("KOS Emergency Shell> ");
        char command[256];
        if (fgets(command, sizeof(command), stdin)) {
            if (strncmp(command, "reboot", 6) == 0) {
                kos_kernel_shutdown(true);
            } else if (strncmp(command, "shutdown", 8) == 0) {
                kos_kernel_shutdown(false);
            } else if (strncmp(command, "continue", 8) == 0) {
                printf("Attempting to continue boot...\n");
                break;
            } else {
                printf("Available commands: reboot, shutdown, continue\n");
            }
        }
    }
}

/* Kernel shutdown */
void kos_kernel_shutdown(bool reboot) {
    printf("KOS: Kernel shutdown initiated (reboot=%d)\n", reboot);
    
    /* Stop all processes */
    /* Sync filesystems */
    /* Clean up subsystems in reverse order */
    
    for (int i = sizeof(init_modules)/sizeof(init_modules[0]) - 1; i >= 0; i--) {
        init_module_t* module = &init_modules[i];
        if (module->initialized && module->cleanup_func) {
            printf("KOS: Cleaning up %s\n", module->name);
            module->cleanup_func();
            module->initialized = false;
        }
    }
    
    /* Close boot log */
    if (boot_state.boot_log && boot_state.boot_log != stderr) {
        fclose(boot_state.boot_log);
    }
    
    printf("KOS: Kernel shutdown complete\n");
    
    if (reboot) {
        /* Perform system reboot */
        execl("/sbin/reboot", "reboot", NULL);
    } else {
        /* Perform system halt */
        execl("/sbin/halt", "halt", NULL);
    }
    
    exit(0);
}

/* Get boot information */
void kos_get_boot_info(struct kos_boot_info* info) {
    if (!info) return;
    
    info->boot_time = boot_state.boot_time;
    info->boot_complete = boot_state.boot_complete;
    info->emergency_mode = boot_state.emergency_mode;
    strncpy(info->cmdline, boot_state.boot_params.cmdline, sizeof(info->cmdline) - 1);
    info->cmdline[sizeof(info->cmdline) - 1] = '\0';
    
    /* Get system information */
    struct utsname uts;
    if (uname(&uts) == 0) {
        strncpy(info->kernel_version, uts.release, sizeof(info->kernel_version) - 1);
        info->kernel_version[sizeof(info->kernel_version) - 1] = '\0';
    }
}

/* Cleanup functions */

static void cleanup_early_console(void) {
    /* Nothing to clean up for early console */
}

static void cleanup_memory_management(void) {
    printf("KOS: Cleaning up memory management\n");
    /* Free memory pools, cleanup allocators */
}

static void cleanup_scheduler(void) {
    printf("KOS: Cleaning up scheduler\n");
    /* Stop scheduler threads, cleanup run queues */
}

static void cleanup_interrupt_system(void) {
    printf("KOS: Cleaning up interrupt system\n");
    /* Disable interrupts, cleanup handlers */
}

static void cleanup_timer_system(void) {
    printf("KOS: Cleaning up timer system\n");
    /* Stop timers, cleanup timer structures */
}

static void cleanup_filesystem(void) {
    printf("KOS: Cleaning up filesystem\n");
    /* Unmount filesystems, sync data */
}

static void cleanup_network_stack(void) {
    printf("KOS: Cleaning up network stack\n");
    /* Close network connections, cleanup interfaces */
}

static void cleanup_security_system(void) {
    printf("KOS: Cleaning up security system\n");
    /* Cleanup security contexts */
}

static void cleanup_device_drivers(void) {
    printf("KOS: Cleaning up device drivers\n");
    /* Unload drivers, cleanup device nodes */
}

static void cleanup_ipc_system(void) {
    printf("KOS: Cleaning up IPC system\n");
    /* Cleanup message queues, shared memory */
}

static void cleanup_syscall_interface(void) {
    printf("KOS: Cleaning up system call interface\n");
    /* Cleanup system call table */
}

static void cleanup_process_management(void) {
    printf("KOS: Cleaning up process management\n");
    /* Terminate processes, cleanup process tables */
}

/* Boot information structure */
struct kos_boot_info {
    uint64_t boot_time;
    bool boot_complete;
    bool emergency_mode;
    char cmdline[1024];
    char kernel_version[64];
};