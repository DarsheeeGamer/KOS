#include "ipc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

void test_pipe() {
    printf("Testing pipes...\n");
    
    kos_pipe_t kos_pipe;
    if (kos_pipe_create(&kos_pipe) != KOS_IPC_SUCCESS) {
        printf("Failed to create pipe\n");
        return;
    }
    
    const char *test_msg = "Hello, KOS IPC!";
    int written = kos_pipe_write(&kos_pipe, test_msg, strlen(test_msg));
    printf("Wrote %d bytes to pipe\n", written);
    
    char buffer[1024];
    int read_bytes = kos_pipe_read(&kos_pipe, buffer, sizeof(buffer));
    buffer[read_bytes] = '\0';
    printf("Read from pipe: %s\n", buffer);
    
    kos_pipe_destroy(&kos_pipe);
    printf("Pipe test completed\n");
}

void test_semaphore() {
    printf("Testing semaphores...\n");
    
    kos_semaphore_t sem;
    if (kos_semaphore_create(&sem, "test_sem", 1, 1) != KOS_IPC_SUCCESS) {
        printf("Failed to create semaphore\n");
        return;
    }
    
    printf("Initial semaphore value: %d\n", kos_semaphore_get_value(&sem));
    
    if (kos_semaphore_wait(&sem, 1000) == KOS_IPC_SUCCESS) {
        printf("Successfully acquired semaphore\n");
        printf("Semaphore value after wait: %d\n", kos_semaphore_get_value(&sem));
        
        kos_semaphore_post(&sem);
        printf("Semaphore value after post: %d\n", kos_semaphore_get_value(&sem));
    }
    
    kos_semaphore_destroy(&sem);
    printf("Semaphore test completed\n");
}

void test_mutex() {
    printf("Testing mutex...\n");
    
    kos_mutex_t mutex;
    if (kos_mutex_init(&mutex, 0) != KOS_IPC_SUCCESS) {
        printf("Failed to initialize mutex\n");
        return;
    }
    
    if (kos_mutex_lock(&mutex) == KOS_IPC_SUCCESS) {
        printf("Mutex locked successfully\n");
        
        if (kos_mutex_try_lock(&mutex) == KOS_IPC_RESOURCE_BUSY) {
            printf("Mutex try_lock correctly returned busy\n");
        }
        
        kos_mutex_unlock(&mutex);
        printf("Mutex unlocked successfully\n");
    }
    
    kos_mutex_destroy(&mutex);
    printf("Mutex test completed\n");
}

void test_shared_memory() {
    printf("Testing shared memory...\n");
    
    kos_shm_t shm;
    size_t size = 4096;
    
    if (kos_shm_create(&shm, "test_shm", size, 0) != KOS_IPC_SUCCESS) {
        printf("Failed to create shared memory\n");
        return;
    }
    
    void *addr = kos_shm_get_addr(&shm);
    if (addr) {
        const char *test_data = "Shared memory test data";
        strcpy((char*)addr, test_data);
        printf("Wrote to shared memory: %s\n", test_data);
        printf("Read from shared memory: %s\n", (char*)addr);
    }
    
    kos_shm_destroy(&shm);
    printf("Shared memory test completed\n");
}

void signal_handler(int sig) {
    printf("Received signal %d\n", sig);
}

void test_signals() {
    printf("Testing signals...\n");
    
    if (kos_signal_register(SIGUSR1, signal_handler) == KOS_IPC_SUCCESS) {
        printf("Signal handler registered\n");
        
        // Send signal to self
        kos_signal_send(getpid(), SIGUSR1);
        usleep(100000); // Give time for signal delivery
        
        kos_signal_unregister(SIGUSR1);
        printf("Signal handler unregistered\n");
    }
    
    printf("Signal test completed\n");
}

void test_message_queue() {
    printf("Testing message queues...\n");
    
    kos_msgqueue_t mq;
    if (kos_msgqueue_create(&mq, "test_mq", 1) != KOS_IPC_SUCCESS) {
        printf("Failed to create message queue\n");
        return;
    }
    
    const char *test_msg = "Message queue test";
    if (kos_msgqueue_send(&mq, test_msg, strlen(test_msg), 1) == KOS_IPC_SUCCESS) {
        printf("Sent message: %s\n", test_msg);
        
        char buffer[256];
        int priority;
        int received = kos_msgqueue_receive(&mq, buffer, sizeof(buffer), &priority);
        if (received > 0) {
            buffer[received] = '\0';
            printf("Received message: %s (priority: %d)\n", buffer, priority);
        }
    }
    
    kos_msgqueue_destroy(&mq);
    printf("Message queue test completed\n");
}

void test_condition_variable() {
    printf("Testing condition variables...\n");
    
    kos_mutex_t mutex;
    kos_condvar_t condvar;
    
    if (kos_mutex_init(&mutex, 0) != KOS_IPC_SUCCESS) {
        printf("Failed to initialize mutex\n");
        return;
    }
    
    if (kos_condvar_init(&condvar, 0) != KOS_IPC_SUCCESS) {
        printf("Failed to initialize condition variable\n");
        kos_mutex_destroy(&mutex);
        return;
    }
    
    printf("Condition variable initialized successfully\n");
    
    // Test signal
    kos_condvar_signal(&condvar);
    printf("Sent signal to condition variable\n");
    
    // Test broadcast
    kos_condvar_broadcast(&condvar);
    printf("Broadcast to condition variable\n");
    
    kos_condvar_destroy(&condvar);
    kos_mutex_destroy(&mutex);
    printf("Condition variable test completed\n");
}

int main() {
    printf("KOS IPC Test Program\n");
    printf("====================\n");
    
    if (kos_ipc_init() != KOS_IPC_SUCCESS) {
        printf("Failed to initialize IPC system\n");
        return 1;
    }
    
    test_pipe();
    printf("\n");
    
    test_semaphore();
    printf("\n");
    
    test_mutex();
    printf("\n");
    
    test_shared_memory();
    printf("\n");
    
    test_message_queue();
    printf("\n");
    
    test_condition_variable();
    printf("\n");
    
    test_signals();
    printf("\n");
    
    kos_ipc_get_stats();
    
    kos_ipc_cleanup();
    
    printf("\nAll tests completed!\n");
    return 0;
}