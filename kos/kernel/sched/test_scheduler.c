#include "sched.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>

static volatile sig_atomic_t running = 1;

void signal_handler(int sig) {
    (void)sig;
    running = 0;
}

int main(int argc, char *argv[]) {
    int nr_cpus = 4;
    
    if (argc > 1) {
        nr_cpus = atoi(argv[1]);
        if (nr_cpus <= 0 || nr_cpus > MAX_CPUS) {
            fprintf(stderr, "Invalid number of CPUs: %d\n", nr_cpus);
            return 1;
        }
    }
    
    printf("KOS Scheduler Test\n");
    printf("==================\n");
    printf("Initializing scheduler with %d CPUs...\n", nr_cpus);
    
    /* Initialize scheduler */
    if (sched_init(nr_cpus) != 0) {
        fprintf(stderr, "Failed to initialize scheduler\n");
        return 1;
    }
    
    /* Set up signal handler */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    /* Start scheduler */
    sched_start();
    
    /* Create some test tasks */
    printf("\nCreating test tasks...\n");
    
    struct task_struct *tasks[10];
    char task_names[10][16];
    
    for (int i = 0; i < 10; i++) {
        snprintf(task_names[i], sizeof(task_names[i]), "task_%d", i);
        tasks[i] = create_task(1000 + i, task_names[i]);
        
        if (tasks[i]) {
            /* Set different policies and priorities */
            if (i < 2) {
                /* RT tasks */
                set_task_policy(tasks[i], (i % 2) ? SCHED_FIFO : SCHED_RR);
                tasks[i]->prio = 10 + i;
            } else {
                /* Normal tasks with different nice values */
                set_user_nice(tasks[i], (i - 5) * 2);
            }
            
            wake_up_process(tasks[i]);
            printf("  Created task %d (%s) - Policy: %u, Priority: %d\n",
                   tasks[i]->pid, tasks[i]->comm, tasks[i]->policy, tasks[i]->prio);
        } else {
            printf("  Failed to create task %d\n", i);
        }
    }
    
    printf("\nScheduler running... Press Ctrl+C to stop\n");
    
    /* Let scheduler run and print periodic statistics */
    int iteration = 0;
    while (running) {
        sleep(2);
        iteration++;
        
        printf("\n=== Statistics (iteration %d) ===\n", iteration);
        print_scheduler_stats();
        
        /* Trigger load balancing */
        trigger_load_balance();
        
        /* Print some task information */
        if (iteration % 3 == 0) {
            printf("Task details:\n");
            for (int i = 0; i < 3 && tasks[i]; i++) {
                print_task_info(tasks[i]);
                printf("\n");
            }
        }
    }
    
    printf("\nStopping scheduler...\n");
    sched_stop();
    
    /* Clean up tasks */
    printf("Cleaning up tasks...\n");
    for (int i = 0; i < 10; i++) {
        if (tasks[i]) {
            destroy_task(tasks[i]);
        }
    }
    
    printf("Scheduler test completed.\n");
    return 0;
}