#include "ipc.h"
#include <sys/stat.h>
#include <fcntl.h>

// Global pipe registry
static kos_pipe_t *pipe_registry[KOS_MAX_QUEUES] = {0};
static pthread_mutex_t pipe_registry_mutex = PTHREAD_MUTEX_INITIALIZER;
static int pipe_count = 0;

// Create anonymous pipe
int kos_pipe_create(kos_pipe_t *kos_pipe) {
    if (!kos_pipe) {
        return KOS_IPC_INVALID_PARAM;
    }

    int pipefd[2];
    if (pipe(pipefd) == -1) {
        return KOS_IPC_ERROR;
    }

    kos_pipe->read_fd = pipefd[0];
    kos_pipe->write_fd = pipefd[1];
    kos_pipe->is_named = 0;
    kos_pipe->name[0] = '\0';
    kos_pipe->buffer_size = KOS_MAX_PIPE_SIZE;

    // Initialize mutex
    if (pthread_mutex_init(&kos_pipe->mutex, NULL) != 0) {
        close(pipefd[0]);
        close(pipefd[1]);
        return KOS_IPC_ERROR;
    }

    // Set non-blocking mode
    int flags = fcntl(kos_pipe->read_fd, F_GETFL);
    fcntl(kos_pipe->read_fd, F_SETFL, flags | O_NONBLOCK);
    
    flags = fcntl(kos_pipe->write_fd, F_GETFL);
    fcntl(kos_pipe->write_fd, F_SETFL, flags | O_NONBLOCK);

    // Register pipe
    pthread_mutex_lock(&pipe_registry_mutex);
    if (pipe_count < KOS_MAX_QUEUES) {
        pipe_registry[pipe_count] = kos_pipe;
        pipe_count++;
    }
    pthread_mutex_unlock(&pipe_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Create named pipe (FIFO)
int kos_pipe_create_named(kos_pipe_t *kos_pipe, const char *name) {
    if (!kos_pipe || !name) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Create FIFO
    if (mkfifo(name, 0666) == -1 && errno != EEXIST) {
        return KOS_IPC_ERROR;
    }

    // Open for reading and writing
    kos_pipe->read_fd = open(name, O_RDONLY | O_NONBLOCK);
    if (kos_pipe->read_fd == -1) {
        return KOS_IPC_ERROR;
    }

    kos_pipe->write_fd = open(name, O_WRONLY | O_NONBLOCK);
    if (kos_pipe->write_fd == -1) {
        close(kos_pipe->read_fd);
        return KOS_IPC_ERROR;
    }

    kos_pipe->is_named = 1;
    strncpy(kos_pipe->name, name, sizeof(kos_pipe->name) - 1);
    kos_pipe->name[sizeof(kos_pipe->name) - 1] = '\0';
    kos_pipe->buffer_size = KOS_MAX_PIPE_SIZE;

    // Initialize mutex
    if (pthread_mutex_init(&kos_pipe->mutex, NULL) != 0) {
        close(kos_pipe->read_fd);
        close(kos_pipe->write_fd);
        return KOS_IPC_ERROR;
    }

    // Register pipe
    pthread_mutex_lock(&pipe_registry_mutex);
    if (pipe_count < KOS_MAX_QUEUES) {
        pipe_registry[pipe_count] = kos_pipe;
        pipe_count++;
    }
    pthread_mutex_unlock(&pipe_registry_mutex);

    return KOS_IPC_SUCCESS;
}

// Read from pipe
int kos_pipe_read(kos_pipe_t *kos_pipe, void *buffer, size_t size) {
    if (!kos_pipe || !buffer || size == 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    pthread_mutex_lock(&kos_pipe->mutex);
    
    ssize_t bytes_read = read(kos_pipe->read_fd, buffer, size);
    
    pthread_mutex_unlock(&kos_pipe->mutex);

    if (bytes_read == -1) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return 0; // No data available
        }
        return KOS_IPC_ERROR;
    }

    return (int)bytes_read;
}

// Write to pipe
int kos_pipe_write(kos_pipe_t *kos_pipe, const void *buffer, size_t size) {
    if (!kos_pipe || !buffer || size == 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    pthread_mutex_lock(&kos_pipe->mutex);
    
    ssize_t bytes_written = write(kos_pipe->write_fd, buffer, size);
    
    pthread_mutex_unlock(&kos_pipe->mutex);

    if (bytes_written == -1) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return 0; // Pipe full
        }
        return KOS_IPC_ERROR;
    }

    return (int)bytes_written;
}

// Close pipe file descriptors
int kos_pipe_close(kos_pipe_t *kos_pipe) {
    if (!kos_pipe) {
        return KOS_IPC_INVALID_PARAM;
    }

    pthread_mutex_lock(&kos_pipe->mutex);
    
    int result = KOS_IPC_SUCCESS;
    
    if (kos_pipe->read_fd != -1) {
        if (close(kos_pipe->read_fd) == -1) {
            result = KOS_IPC_ERROR;
        }
        kos_pipe->read_fd = -1;
    }
    
    if (kos_pipe->write_fd != -1) {
        if (close(kos_pipe->write_fd) == -1) {
            result = KOS_IPC_ERROR;
        }
        kos_pipe->write_fd = -1;
    }
    
    pthread_mutex_unlock(&kos_pipe->mutex);

    return result;
}

// Destroy pipe and cleanup resources
int kos_pipe_destroy(kos_pipe_t *kos_pipe) {
    if (!kos_pipe) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Close file descriptors
    kos_pipe_close(kos_pipe);

    // Remove named pipe file if it exists
    if (kos_pipe->is_named && kos_pipe->name[0] != '\0') {
        unlink(kos_pipe->name);
    }

    // Remove from registry
    pthread_mutex_lock(&pipe_registry_mutex);
    for (int i = 0; i < pipe_count; i++) {
        if (pipe_registry[i] == kos_pipe) {
            // Shift remaining pipes
            for (int j = i; j < pipe_count - 1; j++) {
                pipe_registry[j] = pipe_registry[j + 1];
            }
            pipe_count--;
            break;
        }
    }
    pthread_mutex_unlock(&pipe_registry_mutex);

    // Destroy mutex
    pthread_mutex_destroy(&kos_pipe->mutex);

    // Clear structure
    memset(kos_pipe, 0, sizeof(kos_pipe_t));

    return KOS_IPC_SUCCESS;
}

// Utility function to get pipe statistics
int kos_pipe_get_stats(int *active_pipes, int *total_bytes_read, int *total_bytes_written) {
    pthread_mutex_lock(&pipe_registry_mutex);
    
    if (active_pipes) {
        *active_pipes = pipe_count;
    }
    
    // For demonstration, we'll return basic stats
    // In a real implementation, you'd track these metrics
    if (total_bytes_read) *total_bytes_read = 0;
    if (total_bytes_written) *total_bytes_written = 0;
    
    pthread_mutex_unlock(&pipe_registry_mutex);
    
    return KOS_IPC_SUCCESS;
}