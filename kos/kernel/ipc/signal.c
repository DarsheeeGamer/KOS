#include "ipc.h"
#include <sys/wait.h>

// Global signal handler registry
static kos_signal_handler_t signal_handlers[NSIG] = {0};
static pthread_mutex_t signal_mutex = PTHREAD_MUTEX_INITIALIZER;
static sigset_t blocked_signals;
static int signal_init_done = 0;

// Signal names for debugging
static const char* signal_names[] = {
    "UNKNOWN", "SIGHUP", "SIGINT", "SIGQUIT", "SIGILL", "SIGTRAP",
    "SIGABRT", "SIGBUS", "SIGFPE", "SIGKILL", "SIGUSR1", "SIGSEGV",
    "SIGUSR2", "SIGPIPE", "SIGALRM", "SIGTERM", "SIGSTKFLT", "SIGCHLD",
    "SIGCONT", "SIGSTOP", "SIGTSTP", "SIGTTIN", "SIGTTOU", "SIGURG",
    "SIGXCPU", "SIGXFSZ", "SIGVTALRM", "SIGPROF", "SIGWINCH", "SIGIO",
    "SIGPWR", "SIGSYS"
};

// Initialize signal handling system
static int kos_signal_init(void) {
    if (signal_init_done) {
        return KOS_IPC_SUCCESS;
    }

    // Initialize blocked signals set
    if (sigemptyset(&blocked_signals) == -1) {
        return KOS_IPC_ERROR;
    }

    // Block some signals by default for safety
    sigaddset(&blocked_signals, SIGPIPE);
    
    if (pthread_sigmask(SIG_BLOCK, &blocked_signals, NULL) == -1) {
        return KOS_IPC_ERROR;
    }

    signal_init_done = 1;
    return KOS_IPC_SUCCESS;
}

// Internal signal handler wrapper
static void kos_signal_wrapper(int signum) {
    pthread_mutex_lock(&signal_mutex);
    
    if (signum > 0 && signum < NSIG && signal_handlers[signum].handler) {
        signal_handlers[signum].handler(signum);
    }
    
    pthread_mutex_unlock(&signal_mutex);
}

// Register signal handler
int kos_signal_register(int signal_num, void (*handler)(int)) {
    if (signal_num <= 0 || signal_num >= NSIG || !handler) {
        return KOS_IPC_INVALID_PARAM;
    }

    // Initialize if not done
    if (kos_signal_init() != KOS_IPC_SUCCESS) {
        return KOS_IPC_ERROR;
    }

    pthread_mutex_lock(&signal_mutex);

    // Set up signal action
    struct sigaction sa;
    sa.sa_handler = kos_signal_wrapper;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART; // Restart interrupted system calls

    // Save old action
    if (sigaction(signal_num, &sa, &signal_handlers[signal_num].old_action) == -1) {
        pthread_mutex_unlock(&signal_mutex);
        return KOS_IPC_ERROR;
    }

    // Store handler information
    signal_handlers[signal_num].signal_num = signal_num;
    signal_handlers[signal_num].handler = handler;
    signal_handlers[signal_num].mask = sa.sa_mask;

    pthread_mutex_unlock(&signal_mutex);

    return KOS_IPC_SUCCESS;
}

// Unregister signal handler
int kos_signal_unregister(int signal_num) {
    if (signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    pthread_mutex_lock(&signal_mutex);

    // Restore original signal handler
    if (signal_handlers[signal_num].handler) {
        if (sigaction(signal_num, &signal_handlers[signal_num].old_action, NULL) == -1) {
            pthread_mutex_unlock(&signal_mutex);
            return KOS_IPC_ERROR;
        }

        // Clear handler information
        memset(&signal_handlers[signal_num], 0, sizeof(kos_signal_handler_t));
    }

    pthread_mutex_unlock(&signal_mutex);

    return KOS_IPC_SUCCESS;
}

// Send signal to process
int kos_signal_send(pid_t pid, int signal_num) {
    if (pid <= 0 || signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (kill(pid, signal_num) == -1) {
        switch (errno) {
            case ESRCH:
                return KOS_IPC_INVALID_PARAM; // No such process
            case EPERM:
                return KOS_IPC_ERROR; // Permission denied
            default:
                return KOS_IPC_ERROR;
        }
    }

    return KOS_IPC_SUCCESS;
}

// Block signal
int kos_signal_block(int signal_num) {
    if (signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signal_num);

    if (pthread_sigmask(SIG_BLOCK, &set, NULL) == -1) {
        return KOS_IPC_ERROR;
    }

    // Add to our blocked signals set
    pthread_mutex_lock(&signal_mutex);
    sigaddset(&blocked_signals, signal_num);
    pthread_mutex_unlock(&signal_mutex);

    return KOS_IPC_SUCCESS;
}

// Unblock signal
int kos_signal_unblock(int signal_num) {
    if (signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signal_num);

    if (pthread_sigmask(SIG_UNBLOCK, &set, NULL) == -1) {
        return KOS_IPC_ERROR;
    }

    // Remove from our blocked signals set
    pthread_mutex_lock(&signal_mutex);
    sigdelset(&blocked_signals, signal_num);
    pthread_mutex_unlock(&signal_mutex);

    return KOS_IPC_SUCCESS;
}

// Wait for signal
int kos_signal_wait(sigset_t *set, int *signal_num, int timeout_ms) {
    if (!set || !signal_num) {
        return KOS_IPC_INVALID_PARAM;
    }

    int sig;

    if (timeout_ms < 0) {
        // Blocking wait
        if (sigwait(set, &sig) != 0) {
            return KOS_IPC_ERROR;
        }
    } else if (timeout_ms == 0) {
        // Non-blocking wait
        struct timespec timeout = {0, 0};
        if (sigtimedwait(set, NULL, &timeout) == -1) {
            if (errno == EAGAIN || errno == ETIMEDOUT) {
                return KOS_IPC_RESOURCE_BUSY;
            }
            return KOS_IPC_ERROR;
        }
        sig = sigtimedwait(set, NULL, &timeout);
    } else {
        // Timed wait
        struct timespec timeout;
        timeout.tv_sec = timeout_ms / 1000;
        timeout.tv_nsec = (timeout_ms % 1000) * 1000000;

        sig = sigtimedwait(set, NULL, &timeout);
        if (sig == -1) {
            if (errno == EAGAIN || errno == ETIMEDOUT) {
                return KOS_IPC_TIMEOUT;
            }
            return KOS_IPC_ERROR;
        }
    }

    *signal_num = sig;
    return KOS_IPC_SUCCESS;
}

// Signal-safe logging function
static void kos_signal_safe_log(const char* message, int signum) {
    char buffer[256];
    const char* sig_name = (signum > 0 && signum < 32) ? signal_names[signum] : "UNKNOWN";
    
    // Use only signal-safe functions
    write(STDERR_FILENO, message, strlen(message));
    write(STDERR_FILENO, ": ", 2);
    write(STDERR_FILENO, sig_name, strlen(sig_name));
    write(STDERR_FILENO, "\n", 1);
}

// Default signal handlers
static void kos_default_sigterm_handler(int signum) {
    kos_signal_safe_log("Received SIGTERM, initiating graceful shutdown", signum);
    // Perform cleanup here
    exit(0);
}

static void kos_default_sigint_handler(int signum) {
    kos_signal_safe_log("Received SIGINT (Ctrl+C)", signum);
    // Allow user to handle interrupt
}

static void kos_default_sigchld_handler(int signum) {
    // Reap zombie children
    while (waitpid(-1, NULL, WNOHANG) > 0) {
        // Continue reaping
    }
}

static void kos_default_sigpipe_handler(int signum) {
    kos_signal_safe_log("Received SIGPIPE (broken pipe)", signum);
    // Usually ignored or logged
}

// Install default signal handlers
int kos_signal_install_defaults(void) {
    int result = KOS_IPC_SUCCESS;

    // Install default handlers for common signals
    if (kos_signal_register(SIGTERM, kos_default_sigterm_handler) != KOS_IPC_SUCCESS) {
        result = KOS_IPC_ERROR;
    }

    if (kos_signal_register(SIGINT, kos_default_sigint_handler) != KOS_IPC_SUCCESS) {
        result = KOS_IPC_ERROR;
    }

    if (kos_signal_register(SIGCHLD, kos_default_sigchld_handler) != KOS_IPC_SUCCESS) {
        result = KOS_IPC_ERROR;
    }

    if (kos_signal_register(SIGPIPE, kos_default_sigpipe_handler) != KOS_IPC_SUCCESS) {
        result = KOS_IPC_ERROR;
    }

    return result;
}

// Create signal set for common signals
int kos_signal_create_set(sigset_t *set, int *signals, int count) {
    if (!set || !signals || count <= 0) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (sigemptyset(set) == -1) {
        return KOS_IPC_ERROR;
    }

    for (int i = 0; i < count; i++) {
        if (signals[i] > 0 && signals[i] < NSIG) {
            if (sigaddset(set, signals[i]) == -1) {
                return KOS_IPC_ERROR;
            }
        }
    }

    return KOS_IPC_SUCCESS;
}

// Send signal to process group
int kos_signal_send_group(pid_t pgid, int signal_num) {
    if (pgid <= 0 || signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (killpg(pgid, signal_num) == -1) {
        switch (errno) {
            case ESRCH:
                return KOS_IPC_INVALID_PARAM; // No such process group
            case EPERM:
                return KOS_IPC_ERROR; // Permission denied
            default:
                return KOS_IPC_ERROR;
        }
    }

    return KOS_IPC_SUCCESS;
}

// Get pending signals
int kos_signal_get_pending(sigset_t *set) {
    if (!set) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (sigpending(set) == -1) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Check if signal is blocked
int kos_signal_is_blocked(int signal_num) {
    if (signal_num <= 0 || signal_num >= NSIG) {
        return KOS_IPC_INVALID_PARAM;
    }

    sigset_t current_mask;
    if (pthread_sigmask(SIG_SETMASK, NULL, &current_mask) == -1) {
        return KOS_IPC_ERROR;
    }

    return sigismember(&current_mask, signal_num) ? 1 : 0;
}

// Suspend until signal
int kos_signal_suspend(sigset_t *mask) {
    if (!mask) {
        return KOS_IPC_INVALID_PARAM;
    }

    if (sigsuspend(mask) == -1 && errno != EINTR) {
        return KOS_IPC_ERROR;
    }

    return KOS_IPC_SUCCESS;
}

// Get signal statistics
int kos_signal_get_stats(int *registered_handlers, int *blocked_count) {
    pthread_mutex_lock(&signal_mutex);
    
    if (registered_handlers) {
        *registered_handlers = 0;
        for (int i = 1; i < NSIG; i++) {
            if (signal_handlers[i].handler) {
                (*registered_handlers)++;
            }
        }
    }
    
    if (blocked_count) {
        *blocked_count = 0;
        for (int i = 1; i < NSIG; i++) {
            if (sigismember(&blocked_signals, i)) {
                (*blocked_count)++;
            }
        }
    }
    
    pthread_mutex_unlock(&signal_mutex);
    
    return KOS_IPC_SUCCESS;
}

// Cleanup signal handling system
int kos_signal_cleanup(void) {
    pthread_mutex_lock(&signal_mutex);
    
    // Unregister all handlers
    for (int i = 1; i < NSIG; i++) {
        if (signal_handlers[i].handler) {
            sigaction(i, &signal_handlers[i].old_action, NULL);
            memset(&signal_handlers[i], 0, sizeof(kos_signal_handler_t));
        }
    }
    
    // Restore default signal mask
    sigset_t empty_set;
    sigemptyset(&empty_set);
    pthread_sigmask(SIG_SETMASK, &empty_set, NULL);
    
    signal_init_done = 0;
    
    pthread_mutex_unlock(&signal_mutex);
    
    return KOS_IPC_SUCCESS;
}