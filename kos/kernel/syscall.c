/*
 * KOS System Call Implementation
 * Complete system call table and dispatcher with parameter validation
 */

#include "kcore.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include <pthread.h>

/* System call statistics */
static struct {
    uint64_t total_calls;
    uint64_t syscall_counts[512];  /* Track per-syscall counts */
    uint64_t failed_calls;
    uint64_t invalid_calls;
    pthread_mutex_t stats_lock;
} syscall_stats = {0};

/* System call numbers - following Linux x86_64 convention */
#define __NR_read           0
#define __NR_write          1
#define __NR_open           2
#define __NR_close          3
#define __NR_stat           4
#define __NR_fstat          5
#define __NR_lstat          6
#define __NR_poll           7
#define __NR_lseek          8
#define __NR_mmap           9
#define __NR_mprotect       10
#define __NR_munmap         11
#define __NR_brk            12
#define __NR_rt_sigaction   13
#define __NR_rt_sigprocmask 14
#define __NR_rt_sigreturn   15
#define __NR_ioctl          16
#define __NR_pread64        17
#define __NR_pwrite64       18
#define __NR_readv          19
#define __NR_writev         20
#define __NR_access         21
#define __NR_pipe           22
#define __NR_select         23
#define __NR_sched_yield    24
#define __NR_mremap         25
#define __NR_msync          26
#define __NR_mincore        27
#define __NR_madvise        28
#define __NR_shmget         29
#define __NR_shmat          30
#define __NR_shmctl         31
#define __NR_dup            32
#define __NR_dup2           33
#define __NR_pause          34
#define __NR_nanosleep      35
#define __NR_getitimer      36
#define __NR_alarm          37
#define __NR_setitimer      38
#define __NR_getpid         39
#define __NR_sendfile       40
#define __NR_socket         41
#define __NR_connect        42
#define __NR_accept         43
#define __NR_sendto         44
#define __NR_recvfrom       45
#define __NR_sendmsg        46
#define __NR_recvmsg        47
#define __NR_shutdown       48
#define __NR_bind           49
#define __NR_listen         50
#define __NR_getsockname    51
#define __NR_getpeername    52
#define __NR_socketpair     53
#define __NR_setsockopt     54
#define __NR_getsockopt     55
#define __NR_clone          56
#define __NR_fork           57
#define __NR_vfork          58
#define __NR_execve         59
#define __NR_exit           60
#define __NR_wait4          61
#define __NR_kill           62
#define __NR_uname          63
#define __NR_semget         64
#define __NR_semop          65
#define __NR_semctl         66
#define __NR_shmdt          67
#define __NR_msgget         68
#define __NR_msgsnd         69
#define __NR_msgrcv         70
#define __NR_msgctl         71
#define __NR_fcntl          72
#define __NR_flock          73
#define __NR_fsync          74
#define __NR_fdatasync      75
#define __NR_truncate       76
#define __NR_ftruncate      77
#define __NR_getdents       78
#define __NR_getcwd         79
#define __NR_chdir          80
#define __NR_fchdir         81
#define __NR_rename         82
#define __NR_mkdir          83
#define __NR_rmdir          84
#define __NR_creat          85
#define __NR_link           86
#define __NR_unlink         87
#define __NR_symlink        88
#define __NR_readlink       89
#define __NR_chmod          90
#define __NR_fchmod         91
#define __NR_chown          92
#define __NR_fchown         93
#define __NR_lchown         94
#define __NR_umask          95
#define __NR_gettimeofday   96
#define __NR_getrlimit      97
#define __NR_getrusage      98
#define __NR_sysinfo        99
#define __NR_times          100

/* Maximum system call number */
#define MAX_SYSCALL_NR      511

/* Forward declarations for system call implementations */
static int64_t sys_read(int fd, void *buf, size_t count);
static int64_t sys_write(int fd, const void *buf, size_t count);
static int64_t sys_open(const char *pathname, int flags, mode_t mode);
static int64_t sys_close(int fd);
static int64_t sys_getpid(void);
static int64_t sys_fork(void);
static int64_t sys_exit(int status);
static int64_t sys_wait4(pid_t pid, int *status, int options, struct rusage *rusage);
static int64_t sys_execve(const char *filename, char *const argv[], char *const envp[]);
static int64_t sys_brk(void *addr);
static int64_t sys_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
static int64_t sys_munmap(void *addr, size_t length);
static int64_t sys_kill(pid_t pid, int sig);
static int64_t sys_clone(unsigned long flags, void *child_stack, int *ptid, int *ctid, unsigned long newtls);
static int64_t sys_sched_yield(void);
static int64_t sys_nanosleep(const struct timespec *req, struct timespec *rem);
static int64_t sys_gettimeofday(struct timeval *tv, struct timezone *tz);

/* Parameter validation helpers */
static bool is_valid_user_ptr(const void *ptr, size_t len);
static bool is_valid_fd(int fd);
static bool is_valid_signal(int sig);

/* System call function pointer type */
typedef int64_t (*syscall_handler_t)(uint64_t arg1, uint64_t arg2, uint64_t arg3,
                                     uint64_t arg4, uint64_t arg5, uint64_t arg6);

/* System call table */
static syscall_handler_t syscall_table[MAX_SYSCALL_NR + 1] = {
    [__NR_read]           = (syscall_handler_t)sys_read,
    [__NR_write]          = (syscall_handler_t)sys_write,
    [__NR_open]           = (syscall_handler_t)sys_open,
    [__NR_close]          = (syscall_handler_t)sys_close,
    [__NR_getpid]         = (syscall_handler_t)sys_getpid,
    [__NR_fork]           = (syscall_handler_t)sys_fork,
    [__NR_exit]           = (syscall_handler_t)sys_exit,
    [__NR_wait4]          = (syscall_handler_t)sys_wait4,
    [__NR_execve]         = (syscall_handler_t)sys_execve,
    [__NR_brk]            = (syscall_handler_t)sys_brk,
    [__NR_mmap]           = (syscall_handler_t)sys_mmap,
    [__NR_munmap]         = (syscall_handler_t)sys_munmap,
    [__NR_kill]           = (syscall_handler_t)sys_kill,
    [__NR_clone]          = (syscall_handler_t)sys_clone,
    [__NR_sched_yield]    = (syscall_handler_t)sys_sched_yield,
    [__NR_nanosleep]      = (syscall_handler_t)sys_nanosleep,
    [__NR_gettimeofday]   = (syscall_handler_t)sys_gettimeofday,
};

/* System call names for debugging */
static const char *syscall_names[] = {
    [__NR_read] = "read",
    [__NR_write] = "write",
    [__NR_open] = "open",
    [__NR_close] = "close",
    [__NR_getpid] = "getpid",
    [__NR_fork] = "fork",
    [__NR_exit] = "exit",
    [__NR_wait4] = "wait4",
    [__NR_execve] = "execve",
    [__NR_brk] = "brk",
    [__NR_mmap] = "mmap",
    [__NR_munmap] = "munmap",
    [__NR_kill] = "kill",
    [__NR_clone] = "clone",
    [__NR_sched_yield] = "sched_yield",
    [__NR_nanosleep] = "nanosleep",
    [__NR_gettimeofday] = "gettimeofday",
};

/* Initialize system call subsystem */
void syscall_init(void) {
    memset(&syscall_stats, 0, sizeof(syscall_stats));
    pthread_mutex_init(&syscall_stats.stats_lock, NULL);
    
    /* Initialize system call table entries that weren't statically initialized */
    for (int i = 0; i <= MAX_SYSCALL_NR; i++) {
        if (!syscall_table[i]) {
            /* Set default handler for unimplemented syscalls */
            syscall_table[i] = (syscall_handler_t)sys_ni_syscall;
        }
    }
    
    printf("KOS: System call subsystem initialized\n");
}

/* Not implemented system call handler */
static int64_t sys_ni_syscall(void) {
    return -ENOSYS;
}

/* Main system call dispatcher */
int64_t kos_syscall_dispatch(uint32_t nr, uint64_t arg1, uint64_t arg2, uint64_t arg3,
                            uint64_t arg4, uint64_t arg5, uint64_t arg6) {
    int64_t ret;
    
    /* Update statistics */
    pthread_mutex_lock(&syscall_stats.stats_lock);
    syscall_stats.total_calls++;
    if (nr <= MAX_SYSCALL_NR) {
        syscall_stats.syscall_counts[nr]++;
    } else {
        syscall_stats.invalid_calls++;
    }
    pthread_mutex_unlock(&syscall_stats.stats_lock);
    
    /* Validate system call number */
    if (nr > MAX_SYSCALL_NR) {
        pthread_mutex_lock(&syscall_stats.stats_lock);
        syscall_stats.failed_calls++;
        pthread_mutex_unlock(&syscall_stats.stats_lock);
        return -ENOSYS;
    }
    
    /* Call the system call handler */
    syscall_handler_t handler = syscall_table[nr];
    if (!handler) {
        pthread_mutex_lock(&syscall_stats.stats_lock);
        syscall_stats.failed_calls++;
        pthread_mutex_unlock(&syscall_stats.stats_lock);
        return -ENOSYS;
    }
    
    /* Execute system call with error handling */
    ret = handler(arg1, arg2, arg3, arg4, arg5, arg6);
    
    /* Update failure statistics */
    if (ret < 0) {
        pthread_mutex_lock(&syscall_stats.stats_lock);
        syscall_stats.failed_calls++;
        pthread_mutex_unlock(&syscall_stats.stats_lock);
    }
    
    return ret;
}

/* System call implementations */

static int64_t sys_read(int fd, void *buf, size_t count) {
    if (!is_valid_fd(fd) || !is_valid_user_ptr(buf, count)) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard read */
    return read(fd, buf, count);
}

static int64_t sys_write(int fd, const void *buf, size_t count) {
    if (!is_valid_fd(fd) || !is_valid_user_ptr(buf, count)) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard write */
    return write(fd, buf, count);
}

static int64_t sys_open(const char *pathname, int flags, mode_t mode) {
    if (!is_valid_user_ptr(pathname, 1)) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard open */
    return open(pathname, flags, mode);
}

static int64_t sys_close(int fd) {
    if (!is_valid_fd(fd)) {
        return -EBADF;
    }
    
    /* For now, delegate to standard close */
    return close(fd);
}

static int64_t sys_getpid(void) {
    /* Return current process PID from kernel state */
    extern kos_thread_t* kos_kernel_get_current_thread(void);
    kos_thread_t *current = kos_kernel_get_current_thread();
    
    if (current) {
        return current->pid;
    }
    
    return getpid();  /* Fallback */
}

static int64_t sys_fork(void) {
    /* Create new process using KOS process management */
    extern kos_thread_t* kos_kernel_get_current_thread(void);
    kos_thread_t *current = kos_kernel_get_current_thread();
    
    if (!current) {
        return -ESRCH;
    }
    
    /* Use KOS process creation */
    kos_process_t *new_proc = kos_process_create(current->pid, "forked");
    if (!new_proc) {
        return -ENOMEM;
    }
    
    return new_proc->pid;
}

static int64_t sys_exit(int status) {
    /* Terminate current process */
    extern kos_thread_t* kos_kernel_get_current_thread(void);
    kos_thread_t *current = kos_kernel_get_current_thread();
    
    if (current) {
        kos_process_destroy(current->pid);
    }
    
    exit(status);  /* Should not return */
    return 0;
}

static int64_t sys_wait4(pid_t pid, int *status, int options, struct rusage *rusage) {
    if (status && !is_valid_user_ptr(status, sizeof(int))) {
        return -EFAULT;
    }
    if (rusage && !is_valid_user_ptr(rusage, sizeof(struct rusage))) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard wait4 */
    return wait4(pid, status, options, rusage);
}

static int64_t sys_execve(const char *filename, char *const argv[], char *const envp[]) {
    if (!is_valid_user_ptr(filename, 1) || 
        !is_valid_user_ptr(argv, sizeof(char*)) ||
        !is_valid_user_ptr(envp, sizeof(char*))) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard execve */
    return execve(filename, argv, envp);
}

static int64_t sys_brk(void *addr) {
    /* Memory management - adjust process heap */
    extern kos_thread_t* kos_kernel_get_current_thread(void);
    kos_thread_t *current = kos_kernel_get_current_thread();
    
    if (!current) {
        return -ESRCH;
    }
    
    kos_process_t *proc = kos_process_find(current->pid);
    if (!proc) {
        return -ESRCH;
    }
    
    /* Simple brk implementation */
    if (addr) {
        proc->brk = (uint64_t)addr;
    }
    
    return proc->brk;
}

static int64_t sys_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    if (length == 0) {
        return -EINVAL;
    }
    
    if (fd != -1 && !is_valid_fd(fd)) {
        return -EBADF;
    }
    
    /* For now, delegate to standard mmap */
    void *result = mmap(addr, length, prot, flags, fd, offset);
    if (result == MAP_FAILED) {
        return -errno;
    }
    
    return (int64_t)result;
}

static int64_t sys_munmap(void *addr, size_t length) {
    if (!addr || length == 0) {
        return -EINVAL;
    }
    
    /* For now, delegate to standard munmap */
    return munmap(addr, length);
}

static int64_t sys_kill(pid_t pid, int sig) {
    if (!is_valid_signal(sig)) {
        return -EINVAL;
    }
    
    /* For now, delegate to standard kill */
    return kill(pid, sig);
}

static int64_t sys_clone(unsigned long flags, void *child_stack, int *ptid, int *ctid, unsigned long newtls) {
    /* Complex process/thread creation - simplified implementation */
    if (child_stack && !is_valid_user_ptr(child_stack, 1)) {
        return -EFAULT;
    }
    
    if (ptid && !is_valid_user_ptr(ptid, sizeof(int))) {
        return -EFAULT;
    }
    
    if (ctid && !is_valid_user_ptr(ctid, sizeof(int))) {
        return -EFAULT;
    }
    
    /* For now, treat as fork */
    return sys_fork();
}

static int64_t sys_sched_yield(void) {
    /* Yield current thread */
    extern void kos_thread_yield(void);
    kos_thread_yield();
    return 0;
}

static int64_t sys_nanosleep(const struct timespec *req, struct timespec *rem) {
    if (!is_valid_user_ptr(req, sizeof(struct timespec))) {
        return -EFAULT;
    }
    
    if (rem && !is_valid_user_ptr(rem, sizeof(struct timespec))) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard nanosleep */
    return nanosleep(req, rem);
}

static int64_t sys_gettimeofday(struct timeval *tv, struct timezone *tz) {
    if (tv && !is_valid_user_ptr(tv, sizeof(struct timeval))) {
        return -EFAULT;
    }
    
    if (tz && !is_valid_user_ptr(tz, sizeof(struct timezone))) {
        return -EFAULT;
    }
    
    /* For now, delegate to standard gettimeofday */
    return gettimeofday(tv, tz);
}

/* Parameter validation helpers */

static bool is_valid_user_ptr(const void *ptr, size_t len) {
    if (!ptr) {
        return false;
    }
    
    /* Simple validation - check if pointer is reasonable */
    uintptr_t addr = (uintptr_t)ptr;
    
    /* Check for null pointer */
    if (addr == 0) {
        return false;
    }
    
    /* Check for kernel space addresses (simplified) */
    if (addr >= 0xffff800000000000UL) {
        return false;
    }
    
    /* Check for overflow */
    if (addr + len < addr) {
        return false;
    }
    
    return true;
}

static bool is_valid_fd(int fd) {
    /* Basic file descriptor validation */
    if (fd < 0 || fd >= KOS_MAX_FDS) {
        return false;
    }
    
    return true;
}

static bool is_valid_signal(int sig) {
    /* Signal number validation */
    if (sig < 0 || sig > 64) {
        return false;
    }
    
    return true;
}

/* System call statistics and debugging */

void syscall_print_stats(void) {
    pthread_mutex_lock(&syscall_stats.stats_lock);
    
    printf("System Call Statistics:\n");
    printf("  Total calls: %lu\n", syscall_stats.total_calls);
    printf("  Failed calls: %lu\n", syscall_stats.failed_calls);
    printf("  Invalid calls: %lu\n", syscall_stats.invalid_calls);
    printf("\nPer-syscall counts:\n");
    
    for (int i = 0; i <= MAX_SYSCALL_NR; i++) {
        if (syscall_stats.syscall_counts[i] > 0) {
            const char *name = (i < sizeof(syscall_names)/sizeof(syscall_names[0]) && 
                               syscall_names[i]) ? syscall_names[i] : "unknown";
            printf("  %s(%d): %lu\n", name, i, syscall_stats.syscall_counts[i]);
        }
    }
    
    pthread_mutex_unlock(&syscall_stats.stats_lock);
}

/* Get current thread helper for other modules */
kos_thread_t* kos_kernel_get_current_thread(void) {
    extern struct {
        kos_thread_t* current_thread;
    } kos_kernel;
    
    return kos_kernel.current_thread;
}