/*
 * KOS Filesystem Error Handling and Edge Cases
 * Comprehensive filesystem error recovery and validation
 */

#include "../filesystem/vfs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <fcntl.h>

/* Filesystem error types */
typedef enum {
    FS_ERROR_NONE = 0,
    FS_ERROR_INVALID_PATH,         /* Invalid file path */
    FS_ERROR_PERMISSION_DENIED,    /* Permission denied */
    FS_ERROR_FILE_NOT_FOUND,       /* File not found */
    FS_ERROR_DIRECTORY_NOT_EMPTY,  /* Directory not empty */
    FS_ERROR_DISK_FULL,            /* No space left on device */
    FS_ERROR_INODE_CORRUPT,        /* Inode corruption */
    FS_ERROR_SUPERBLOCK_CORRUPT,   /* Superblock corruption */
    FS_ERROR_BLOCK_CORRUPT,        /* Block corruption */
    FS_ERROR_METADATA_CORRUPT,     /* Metadata corruption */
    FS_ERROR_JOURNAL_CORRUPT,      /* Journal corruption */
    FS_ERROR_MOUNT_FAILED,         /* Mount operation failed */
    FS_ERROR_UNMOUNT_FAILED,       /* Unmount operation failed */
    FS_ERROR_IO_ERROR,             /* I/O error */
    FS_ERROR_TIMEOUT,              /* Operation timeout */
    FS_ERROR_DEADLOCK,             /* Filesystem deadlock */
    FS_ERROR_QUOTA_EXCEEDED,       /* Quota exceeded */
    FS_ERROR_NAME_TOO_LONG,        /* Filename too long */
    FS_ERROR_LOOP_DETECTED,        /* Symbolic link loop */
    FS_ERROR_READONLY              /* Read-only filesystem */
} fs_error_type_t;

/* Error recovery strategies */
typedef enum {
    FS_RECOVERY_IGNORE = 0,
    FS_RECOVERY_LOG,
    FS_RECOVERY_RETRY,
    FS_RECOVERY_FALLBACK,
    FS_RECOVERY_FSCK,
    FS_RECOVERY_REMOUNT,
    FS_RECOVERY_READONLY,
    FS_RECOVERY_PANIC
} fs_recovery_t;

/* Filesystem error context */
typedef struct {
    fs_error_type_t type;
    const char *message;
    const char *path;
    kos_inode_t *inode;
    kos_superblock_t *sb;
    uint32_t block_num;
    int error_code;
    uint64_t timestamp;
    const char *file;
    int line;
    const char *function;
    fs_recovery_t recovery;
    void *extra_data;
} fs_error_ctx_t;

/* Filesystem error statistics */
static struct {
    uint64_t total_errors;
    uint64_t invalid_path_errors;
    uint64_t permission_errors;
    uint64_t file_not_found_errors;
    uint64_t directory_not_empty_errors;
    uint64_t disk_full_errors;
    uint64_t inode_corrupt_errors;
    uint64_t superblock_corrupt_errors;
    uint64_t block_corrupt_errors;
    uint64_t metadata_corrupt_errors;
    uint64_t journal_corrupt_errors;
    uint64_t mount_failed_errors;
    uint64_t unmount_failed_errors;
    uint64_t io_errors;
    uint64_t timeout_errors;
    uint64_t deadlock_errors;
    uint64_t quota_exceeded_errors;
    uint64_t name_too_long_errors;
    uint64_t loop_detected_errors;
    uint64_t readonly_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t fsck_runs;
    uint64_t remounts;
    pthread_mutex_t lock;
} fs_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Filesystem corruption patterns */
#define FS_INODE_MAGIC      0x494E4F44  /* "INOD" */
#define FS_SUPER_MAGIC      0x53555045  /* "SUPE" */
#define FS_BLOCK_MAGIC      0x424C4F43  /* "BLOC" */
#define FS_JOURNAL_MAGIC    0x4A4F5552  /* "JOUR" */

/* Path validation patterns */
static const char *dangerous_paths[] = {
    "..",
    "../",
    "./",
    "//",
    "/proc/",
    "/sys/",
    "/dev/",
    NULL
};

/* Validate file path */
static int validate_file_path(const char *path, const char *context)
{
    if (!path) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INVALID_PATH,
            .message = "NULL path pointer",
            .path = path,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }

    /* Check path length */
    size_t path_len = strlen(path);
    if (path_len == 0) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INVALID_PATH,
            .message = "Empty path",
            .path = path,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }

    if (path_len > PATH_MAX) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_NAME_TOO_LONG,
            .message = "Path too long",
            .path = path,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }

    /* Check for dangerous path components */
    for (int i = 0; dangerous_paths[i]; i++) {
        if (strstr(path, dangerous_paths[i])) {
            fs_error_ctx_t ctx = {
                .type = FS_ERROR_INVALID_PATH,
                .message = "Potentially dangerous path component",
                .path = path,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .recovery = FS_RECOVERY_LOG
            };
            return handle_fs_error(&ctx);
        }
    }

    /* Check for null bytes in path */
    for (size_t i = 0; i < path_len; i++) {
        if (path[i] == '\0' && i < path_len - 1) {
            fs_error_ctx_t ctx = {
                .type = FS_ERROR_INVALID_PATH,
                .message = "Null byte in path",
                .path = path,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .recovery = FS_RECOVERY_LOG
            };
            return handle_fs_error(&ctx);
        }
    }

    return 0;
}

/* Validate inode structure */
static int validate_inode(kos_inode_t *inode, const char *context)
{
    if (!inode) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INODE_CORRUPT,
            .message = "NULL inode pointer",
            .inode = inode,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check inode magic number */
    if (inode->magic != FS_INODE_MAGIC) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INODE_CORRUPT,
            .message = "Invalid inode magic number",
            .inode = inode,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check inode number validity */
    if (inode->ino == 0 || inode->ino > MAX_INODES) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INODE_CORRUPT,
            .message = "Invalid inode number",
            .inode = inode,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check file mode */
    if (!S_ISREG(inode->mode) && !S_ISDIR(inode->mode) && 
        !S_ISLNK(inode->mode) && !S_ISCHR(inode->mode) && 
        !S_ISBLK(inode->mode) && !S_ISFIFO(inode->mode) && 
        !S_ISSOCK(inode->mode)) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INODE_CORRUPT,
            .message = "Invalid file mode",
            .inode = inode,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check timestamps */
    struct timeval now;
    gettimeofday(&now, NULL);
    if (inode->atime > now.tv_sec + 86400 || /* Future timestamp */
        inode->mtime > now.tv_sec + 86400 ||
        inode->ctime > now.tv_sec + 86400) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_INODE_CORRUPT,
            .message = "Invalid inode timestamps",
            .inode = inode,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }

    return 0;
}

/* Validate superblock */
static int validate_superblock(kos_superblock_t *sb, const char *context)
{
    if (!sb) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_SUPERBLOCK_CORRUPT,
            .message = "NULL superblock pointer",
            .sb = sb,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check superblock magic */
    if (sb->magic != FS_SUPER_MAGIC) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_SUPERBLOCK_CORRUPT,
            .message = "Invalid superblock magic",
            .sb = sb,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check filesystem parameters */
    if (sb->block_size == 0 || sb->block_size > MAX_BLOCK_SIZE ||
        sb->inode_count == 0 || sb->block_count == 0) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_SUPERBLOCK_CORRUPT,
            .message = "Invalid superblock parameters",
            .sb = sb,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    /* Check free counts */
    if (sb->free_blocks > sb->block_count ||
        sb->free_inodes > sb->inode_count) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_SUPERBLOCK_CORRUPT,
            .message = "Invalid free counts in superblock",
            .sb = sb,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = FS_RECOVERY_FSCK
        };
        return handle_fs_error(&ctx);
    }

    return 0;
}

/* Detect symbolic link loops */
static int detect_symlink_loop(const char *path, int depth)
{
    if (depth > MAX_SYMLINK_FOLLOWS) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_LOOP_DETECTED,
            .message = "Symbolic link loop detected",
            .path = path,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }
    return 0;
}

/* Check disk space */
static int check_disk_space(kos_superblock_t *sb, uint32_t blocks_needed)
{
    if (sb->free_blocks < blocks_needed) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_DISK_FULL,
            .message = "No space left on device",
            .sb = sb,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }
    return 0;
}

/* Check file permissions */
static int check_permissions(kos_inode_t *inode, uint32_t uid, uint32_t gid, int access_mode)
{
    if (!inode) {
        return -EINVAL;
    }

    /* Root can do anything */
    if (uid == 0) {
        return 0;
    }

    mode_t mode = inode->mode;
    bool allowed = false;

    /* Owner permissions */
    if (uid == inode->uid) {
        if ((access_mode & R_OK) && !(mode & S_IRUSR)) allowed = false;
        else if ((access_mode & W_OK) && !(mode & S_IWUSR)) allowed = false;
        else if ((access_mode & X_OK) && !(mode & S_IXUSR)) allowed = false;
        else allowed = true;
    }
    /* Group permissions */
    else if (gid == inode->gid) {
        if ((access_mode & R_OK) && !(mode & S_IRGRP)) allowed = false;
        else if ((access_mode & W_OK) && !(mode & S_IWGRP)) allowed = false;
        else if ((access_mode & X_OK) && !(mode & S_IXGRP)) allowed = false;
        else allowed = true;
    }
    /* Other permissions */
    else {
        if ((access_mode & R_OK) && !(mode & S_IROTH)) allowed = false;
        else if ((access_mode & W_OK) && !(mode & S_IWOTH)) allowed = false;
        else if ((access_mode & X_OK) && !(mode & S_IXOTH)) allowed = false;
        else allowed = true;
    }

    if (!allowed) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_PERMISSION_DENIED,
            .message = "Permission denied",
            .inode = inode,
            .error_code = EACCES,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = FS_RECOVERY_LOG
        };
        return handle_fs_error(&ctx);
    }

    return 0;
}

/* Log filesystem error */
static void log_fs_error(const fs_error_ctx_t *ctx)
{
    pthread_mutex_lock(&fs_error_stats.lock);
    fs_error_stats.total_errors++;

    switch (ctx->type) {
        case FS_ERROR_INVALID_PATH:
            fs_error_stats.invalid_path_errors++;
            break;
        case FS_ERROR_PERMISSION_DENIED:
            fs_error_stats.permission_errors++;
            break;
        case FS_ERROR_FILE_NOT_FOUND:
            fs_error_stats.file_not_found_errors++;
            break;
        case FS_ERROR_DIRECTORY_NOT_EMPTY:
            fs_error_stats.directory_not_empty_errors++;
            break;
        case FS_ERROR_DISK_FULL:
            fs_error_stats.disk_full_errors++;
            break;
        case FS_ERROR_INODE_CORRUPT:
            fs_error_stats.inode_corrupt_errors++;
            break;
        case FS_ERROR_SUPERBLOCK_CORRUPT:
            fs_error_stats.superblock_corrupt_errors++;
            break;
        case FS_ERROR_BLOCK_CORRUPT:
            fs_error_stats.block_corrupt_errors++;
            break;
        case FS_ERROR_METADATA_CORRUPT:
            fs_error_stats.metadata_corrupt_errors++;
            break;
        case FS_ERROR_JOURNAL_CORRUPT:
            fs_error_stats.journal_corrupt_errors++;
            break;
        case FS_ERROR_MOUNT_FAILED:
            fs_error_stats.mount_failed_errors++;
            break;
        case FS_ERROR_UNMOUNT_FAILED:
            fs_error_stats.unmount_failed_errors++;
            break;
        case FS_ERROR_IO_ERROR:
            fs_error_stats.io_errors++;
            break;
        case FS_ERROR_TIMEOUT:
            fs_error_stats.timeout_errors++;
            break;
        case FS_ERROR_DEADLOCK:
            fs_error_stats.deadlock_errors++;
            break;
        case FS_ERROR_QUOTA_EXCEEDED:
            fs_error_stats.quota_exceeded_errors++;
            break;
        case FS_ERROR_NAME_TOO_LONG:
            fs_error_stats.name_too_long_errors++;
            break;
        case FS_ERROR_LOOP_DETECTED:
            fs_error_stats.loop_detected_errors++;
            break;
        case FS_ERROR_READONLY:
            fs_error_stats.readonly_errors++;
            break;
        default:
            break;
    }

    pthread_mutex_unlock(&fs_error_stats.lock);

    /* Log error details */
    printf("[FS ERROR] Type: %d, Message: %s\n", ctx->type, ctx->message);
    if (ctx->path) {
        printf("[FS ERROR] Path: %s\n", ctx->path);
    }
    if (ctx->inode) {
        printf("[FS ERROR] Inode: %u, Mode: %o\n", ctx->inode->ino, ctx->inode->mode);
    }
    if (ctx->error_code) {
        printf("[FS ERROR] Error code: %d (%s)\n", ctx->error_code, strerror(ctx->error_code));
    }
    printf("[FS ERROR] Location: %s:%d in %s()\n",
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle filesystem error with recovery */
int handle_fs_error(fs_error_ctx_t *ctx)
{
    log_fs_error(ctx);

    pthread_mutex_lock(&fs_error_stats.lock);
    fs_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&fs_error_stats.lock);

    switch (ctx->recovery) {
        case FS_RECOVERY_IGNORE:
            return 0;

        case FS_RECOVERY_LOG:
            /* Already logged above */
            return 0;

        case FS_RECOVERY_RETRY:
            /* Allow caller to retry operation */
            pthread_mutex_lock(&fs_error_stats.lock);
            fs_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&fs_error_stats.lock);
            return -EAGAIN;

        case FS_RECOVERY_FALLBACK:
            /* Use alternative method */
            pthread_mutex_lock(&fs_error_stats.lock);
            fs_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&fs_error_stats.lock);
            return 0;

        case FS_RECOVERY_FSCK:
            /* Run filesystem check */
            printf("[FS RECOVERY] Running filesystem check\n");
            pthread_mutex_lock(&fs_error_stats.lock);
            fs_error_stats.fsck_runs++;
            fs_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&fs_error_stats.lock);
            return 0;

        case FS_RECOVERY_REMOUNT:
            /* Remount filesystem */
            printf("[FS RECOVERY] Remounting filesystem\n");
            pthread_mutex_lock(&fs_error_stats.lock);
            fs_error_stats.remounts++;
            fs_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&fs_error_stats.lock);
            return 0;

        case FS_RECOVERY_READONLY:
            /* Mount as read-only */
            printf("[FS RECOVERY] Mounting filesystem as read-only\n");
            if (ctx->sb) {
                ctx->sb->flags |= MS_RDONLY;
            }
            pthread_mutex_lock(&fs_error_stats.lock);
            fs_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&fs_error_stats.lock);
            return 0;

        case FS_RECOVERY_PANIC:
            printf("[FS PANIC] Unrecoverable filesystem error - system halting\n");
            abort();

        default:
            return -1;
    }
}

/* Safe file operations with error handling */
int safe_file_open(const char *path, int flags, mode_t mode)
{
    if (validate_file_path(path, "safe_file_open") != 0) {
        return -1;
    }

    /* Check for read-only filesystem if write requested */
    if ((flags & (O_WRONLY | O_RDWR | O_CREAT | O_TRUNC)) && fs_is_readonly(path)) {
        fs_error_ctx_t ctx = {
            .type = FS_ERROR_READONLY,
            .message = "Attempt to write to read-only filesystem",
            .path = path,
            .error_code = EROFS,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = FS_RECOVERY_LOG
        };
        handle_fs_error(&ctx);
        return -EROFS;
    }

    return open(path, flags, mode);
}

/* Safe directory operations */
int safe_mkdir(const char *path, mode_t mode)
{
    if (validate_file_path(path, "safe_mkdir") != 0) {
        return -1;
    }

    /* Check if filesystem has space */
    kos_superblock_t *sb = get_superblock_for_path(path);
    if (sb && check_disk_space(sb, 1) != 0) {
        return -ENOSPC;
    }

    return mkdir(path, mode);
}

/* Safe file removal */
int safe_unlink(const char *path)
{
    if (validate_file_path(path, "safe_unlink") != 0) {
        return -1;
    }

    /* Check permissions */
    struct stat st;
    if (stat(path, &st) == 0) {
        if (check_permissions((kos_inode_t*)&st, getuid(), getgid(), W_OK) != 0) {
            return -EACCES;
        }
    }

    return unlink(path);
}

/* Comprehensive filesystem health check */
int filesystem_health_check(const char *mount_point)
{
    int errors = 0;

    /* Get superblock */
    kos_superblock_t *sb = get_superblock_for_path(mount_point);
    if (sb) {
        if (validate_superblock(sb, "health_check") != 0) {
            errors++;
        }
    }

    /* Check random inodes */
    for (uint32_t i = 1; i <= 100 && sb && i <= sb->inode_count; i++) {
        kos_inode_t *inode = get_inode(sb, i);
        if (inode && validate_inode(inode, "health_check") != 0) {
            errors++;
        }
    }

    return errors;
}

/* Get filesystem error statistics */
void fs_get_error_stats(void)
{
    pthread_mutex_lock(&fs_error_stats.lock);

    printf("\nFilesystem Error Statistics:\n");
    printf("============================\n");
    printf("Total errors:              %lu\n", fs_error_stats.total_errors);
    printf("Invalid path errors:       %lu\n", fs_error_stats.invalid_path_errors);
    printf("Permission errors:         %lu\n", fs_error_stats.permission_errors);
    printf("File not found errors:     %lu\n", fs_error_stats.file_not_found_errors);
    printf("Directory not empty errors:%lu\n", fs_error_stats.directory_not_empty_errors);
    printf("Disk full errors:          %lu\n", fs_error_stats.disk_full_errors);
    printf("Inode corrupt errors:      %lu\n", fs_error_stats.inode_corrupt_errors);
    printf("Superblock corrupt errors: %lu\n", fs_error_stats.superblock_corrupt_errors);
    printf("Block corrupt errors:      %lu\n", fs_error_stats.block_corrupt_errors);
    printf("Metadata corrupt errors:   %lu\n", fs_error_stats.metadata_corrupt_errors);
    printf("Journal corrupt errors:    %lu\n", fs_error_stats.journal_corrupt_errors);
    printf("Mount failed errors:       %lu\n", fs_error_stats.mount_failed_errors);
    printf("Unmount failed errors:     %lu\n", fs_error_stats.unmount_failed_errors);
    printf("I/O errors:                %lu\n", fs_error_stats.io_errors);
    printf("Timeout errors:            %lu\n", fs_error_stats.timeout_errors);
    printf("Deadlock errors:           %lu\n", fs_error_stats.deadlock_errors);
    printf("Quota exceeded errors:     %lu\n", fs_error_stats.quota_exceeded_errors);
    printf("Name too long errors:      %lu\n", fs_error_stats.name_too_long_errors);
    printf("Loop detected errors:      %lu\n", fs_error_stats.loop_detected_errors);
    printf("Read-only errors:          %lu\n", fs_error_stats.readonly_errors);
    printf("Recovery attempts:         %lu\n", fs_error_stats.recoveries_attempted);
    printf("Recovery successes:        %lu\n", fs_error_stats.recoveries_successful);
    printf("FSCK runs:                 %lu\n", fs_error_stats.fsck_runs);
    printf("Remounts:                  %lu\n", fs_error_stats.remounts);

    if (fs_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)fs_error_stats.recoveries_successful / 
                             fs_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate:     %.1f%%\n", success_rate);
    }

    pthread_mutex_unlock(&fs_error_stats.lock);
}

/* Initialize filesystem error handling */
void fs_error_init(void)
{
    printf("Filesystem error handling initialized\n");
}

/* Macros for easy error checking */
#define FS_VALIDATE_PATH(path, context) \
    if (validate_file_path(path, context) != 0) return -1

#define FS_VALIDATE_INODE(inode, context) \
    if (validate_inode(inode, context) != 0) return -1

#define FS_VALIDATE_SUPERBLOCK(sb, context) \
    if (validate_superblock(sb, context) != 0) return -1

#define FS_CHECK_READONLY(path) \
    if (fs_is_readonly(path)) { \
        fs_error_ctx_t ctx = { \
            .type = FS_ERROR_READONLY, \
            .message = "Read-only filesystem", \
            .path = path, \
            .error_code = EROFS, \
            .timestamp = time(NULL), \
            .file = __FILE__, \
            .line = __LINE__, \
            .function = __func__, \
            .recovery = FS_RECOVERY_LOG \
        }; \
        handle_fs_error(&ctx); \
        return -EROFS; \
    }