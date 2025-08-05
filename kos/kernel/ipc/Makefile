# KOS IPC Library Makefile
CC = gcc
CFLAGS = -Wall -Wextra -fPIC -O2 -std=c99 -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L
LDFLAGS = -shared -lpthread -lrt
TARGET = libkos_ipc.so
SOURCES = pipe.c shm.c msgqueue.c sem.c signal.c
OBJECTS = $(SOURCES:.c=.o)
HEADER = ipc.h

# Utility functions implementation
UTIL_SOURCES = ipc_utils.c
UTIL_OBJECTS = $(UTIL_SOURCES:.c=.o)

.PHONY: all clean install test

all: $(TARGET)

$(TARGET): $(OBJECTS) $(UTIL_OBJECTS)
	$(CC) $(OBJECTS) $(UTIL_OBJECTS) -o $@ $(LDFLAGS)

%.o: %.c $(HEADER)
	$(CC) $(CFLAGS) -c $< -o $@

# Create utility functions file
ipc_utils.c:
	@echo "Creating utility functions..."
	@cat > ipc_utils.c << 'EOF'
#include "ipc.h"
#include <sys/stat.h>

// Global IPC statistics
static struct {
    int initialized;
    int active_pipes;
    int active_shm_segments;
    int active_queues;
    int active_semaphores;
    pthread_mutex_t stats_mutex;
} ipc_stats = {0, 0, 0, 0, 0, PTHREAD_MUTEX_INITIALIZER};

// Initialize IPC system
int kos_ipc_init(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    if (ipc_stats.initialized) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_SUCCESS;
    }
    
    // Initialize signal handling
    if (kos_signal_install_defaults() != KOS_IPC_SUCCESS) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_ERROR;
    }
    
    ipc_stats.initialized = 1;
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Cleanup IPC system
int kos_ipc_cleanup(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    if (!ipc_stats.initialized) {
        pthread_mutex_unlock(&ipc_stats.stats_mutex);
        return KOS_IPC_SUCCESS;
    }
    
    // Cleanup signal handling
    kos_signal_cleanup();
    
    ipc_stats.initialized = 0;
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Get IPC statistics
int kos_ipc_get_stats(void) {
    pthread_mutex_lock(&ipc_stats.stats_mutex);
    
    printf("KOS IPC Statistics:\n");
    printf("  Initialized: %s\n", ipc_stats.initialized ? "Yes" : "No");
    printf("  Active Pipes: %d\n", ipc_stats.active_pipes);
    printf("  Active Shared Memory Segments: %d\n", ipc_stats.active_shm_segments);
    printf("  Active Message Queues: %d\n", ipc_stats.active_queues);
    printf("  Active Semaphores: %d\n", ipc_stats.active_semaphores);
    
    pthread_mutex_unlock(&ipc_stats.stats_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Generate IPC key from pathname and project ID
key_t kos_ipc_generate_key(const char *pathname, int proj_id) {
    if (!pathname) {
        return -1;
    }
    
    // Use ftok to generate System V IPC key
    key_t key = ftok(pathname, proj_id);
    if (key == -1) {
        // If ftok fails, create a simple hash-based key
        key = 0;
        const char *p = pathname;
        while (*p) {
            key = key * 31 + *p;
            p++;
        }
        key = key * 31 + proj_id;
        
        // Ensure positive key
        if (key < 0) {
            key = -key;
        }
    }
    
    return key;
}

// Check permissions for IPC operations
int kos_ipc_permissions_check(int operation, pid_t pid, uid_t uid, gid_t gid) {
    // Basic permission checking
    // In a real implementation, this would check against system policies
    
    // For now, allow all operations for the same user
    if (getuid() == uid) {
        return KOS_IPC_SUCCESS;
    }
    
    // Root can do anything
    if (getuid() == 0) {
        return KOS_IPC_SUCCESS;
    }
    
    // Check group permissions
    if (getgid() == gid) {
        return KOS_IPC_SUCCESS;
    }
    
    return KOS_IPC_ERROR;
}

// Signal installation function declarations (implemented in signal.c)
extern int kos_signal_install_defaults(void);
extern int kos_signal_cleanup(void);
EOF

ipc_utils.o: ipc_utils.c
	$(CC) $(CFLAGS) -c $< -o $@

# Test program
test: $(TARGET) test_ipc.c
	$(CC) -Wall -Wextra -O2 -std=c99 -D_GNU_SOURCE test_ipc.c -L. -lkos_ipc -lpthread -lrt -o test_ipc

test_ipc.c:
	@echo "Creating test program..."
	@cat > test_ipc.c << 'EOF'
#include "ipc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

void test_pipe() {
    printf("Testing pipes...\n");
    
    kos_pipe_t pipe;
    if (kos_pipe_create(&pipe) != KOS_IPC_SUCCESS) {
        printf("Failed to create pipe\n");
        return;
    }
    
    const char *test_msg = "Hello, KOS IPC!";
    int written = kos_pipe_write(&pipe, test_msg, strlen(test_msg));
    printf("Wrote %d bytes to pipe\n", written);
    
    char buffer[1024];
    int read_bytes = kos_pipe_read(&pipe, buffer, sizeof(buffer));
    buffer[read_bytes] = '\0';
    printf("Read from pipe: %s\n", buffer);
    
    kos_pipe_destroy(&pipe);
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
    
    test_signals();
    printf("\n");
    
    kos_ipc_get_stats();
    
    kos_ipc_cleanup();
    
    printf("\nAll tests completed!\n");
    return 0;
}
EOF

# Install library
install: $(TARGET)
	sudo cp $(TARGET) /usr/local/lib/
	sudo cp $(HEADER) /usr/local/include/
	sudo ldconfig

# Clean build files
clean:
	rm -f $(OBJECTS) $(UTIL_OBJECTS) $(TARGET) test_ipc test_ipc.c ipc_utils.c

# Help
help:
	@echo "KOS IPC Library Build System"
	@echo "Available targets:"
	@echo "  all     - Build the IPC library"
	@echo "  test    - Build and create test program"
	@echo "  install - Install library system-wide"
	@echo "  clean   - Clean build files"
	@echo "  help    - Show this help"