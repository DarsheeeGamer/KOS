/*
 * KOS Virtual Filesystem C API
 * 
 * Provides C interface for VFS operations within KOS
 */

#ifndef KOS_VFS_API_H
#define KOS_VFS_API_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <sys/types.h>
#include <sys/stat.h>

/* VFS Error codes */
#define VFS_SUCCESS         0
#define VFS_ERROR          -1
#define VFS_ENOENT         -2
#define VFS_EACCES         -3
#define VFS_EEXIST         -4
#define VFS_ENOTDIR        -5
#define VFS_EISDIR         -6
#define VFS_ENOMEM         -7
#define VFS_ENOSPC         -8
#define VFS_EINVAL         -9
#define VFS_EBUSY         -10

/* File types */
#define VFS_TYPE_FILE      1
#define VFS_TYPE_DIR       2
#define VFS_TYPE_LINK      3
#define VFS_TYPE_DEVICE    4
#define VFS_TYPE_PIPE      5
#define VFS_TYPE_SOCKET    6

/* Open flags */
#define VFS_O_RDONLY       0x0001
#define VFS_O_WRONLY       0x0002
#define VFS_O_RDWR         0x0003
#define VFS_O_CREAT        0x0040
#define VFS_O_EXCL         0x0080
#define VFS_O_TRUNC        0x0200
#define VFS_O_APPEND       0x0400

/* VFS Handle */
typedef struct vfs_handle {
    int fd;
    void* private_data;
} vfs_handle_t;

/* VFS File info */
typedef struct vfs_stat {
    uint32_t st_dev;
    uint32_t st_ino;
    uint16_t st_mode;
    uint16_t st_nlink;
    uint32_t st_uid;
    uint32_t st_gid;
    uint64_t st_size;
    uint64_t st_atime_sec;  /* Renamed to avoid conflict */
    uint64_t st_mtime_sec;  /* Renamed to avoid conflict */
    uint64_t st_ctime_sec;  /* Renamed to avoid conflict */
    uint32_t st_blksize;
    uint64_t st_blocks;
} vfs_stat_t;

/* Directory entry */
typedef struct vfs_dirent {
    uint32_t d_ino;
    uint16_t d_type;
    char d_name[256];
} vfs_dirent_t;

/* VFS Context for user/permission info */
typedef struct vfs_context {
    uint32_t uid;
    uint32_t gid;
    uint32_t umask;
    char* cwd;
} vfs_context_t;

/* Core VFS Functions */

/* Initialize VFS subsystem */
int vfs_init(void);

/* Shutdown VFS subsystem */
int vfs_shutdown(void);

/* File operations */
vfs_handle_t* vfs_open(const char* path, int flags, mode_t mode, vfs_context_t* ctx);
int vfs_close(vfs_handle_t* handle);
ssize_t vfs_read(vfs_handle_t* handle, void* buffer, size_t size);
ssize_t vfs_write(vfs_handle_t* handle, const void* buffer, size_t size);
off_t vfs_lseek(vfs_handle_t* handle, off_t offset, int whence);
int vfs_fstat(vfs_handle_t* handle, vfs_stat_t* stat);
int vfs_fsync(vfs_handle_t* handle);
int vfs_ftruncate(vfs_handle_t* handle, off_t length);

/* Directory operations */
int vfs_mkdir(const char* path, mode_t mode, vfs_context_t* ctx);
int vfs_rmdir(const char* path, vfs_context_t* ctx);
vfs_handle_t* vfs_opendir(const char* path, vfs_context_t* ctx);
vfs_dirent_t* vfs_readdir(vfs_handle_t* dir);
int vfs_closedir(vfs_handle_t* dir);

/* Path operations */
int vfs_stat(const char* path, vfs_stat_t* stat, vfs_context_t* ctx);
int vfs_lstat(const char* path, vfs_stat_t* stat, vfs_context_t* ctx);
int vfs_access(const char* path, int mode, vfs_context_t* ctx);
int vfs_chmod(const char* path, mode_t mode, vfs_context_t* ctx);
int vfs_chown(const char* path, uid_t uid, gid_t gid, vfs_context_t* ctx);
int vfs_unlink(const char* path, vfs_context_t* ctx);
int vfs_rename(const char* oldpath, const char* newpath, vfs_context_t* ctx);
int vfs_link(const char* oldpath, const char* newpath, vfs_context_t* ctx);
int vfs_symlink(const char* target, const char* linkpath, vfs_context_t* ctx);
ssize_t vfs_readlink(const char* path, char* buffer, size_t size, vfs_context_t* ctx);

/* Mount operations */
int vfs_mount(const char* source, const char* target, const char* fstype, 
              unsigned long flags, const void* data, vfs_context_t* ctx);
int vfs_umount(const char* target, vfs_context_t* ctx);

/* Utility functions */
char* vfs_realpath(const char* path, char* resolved_path, vfs_context_t* ctx);
int vfs_mkstemp(char* path_template, vfs_context_t* ctx);
int vfs_mkdtemp(char* path_template, vfs_context_t* ctx);

/* Context management */
vfs_context_t* vfs_context_create(uid_t uid, gid_t gid);
void vfs_context_destroy(vfs_context_t* ctx);
int vfs_context_set_cwd(vfs_context_t* ctx, const char* path);
const char* vfs_context_get_cwd(vfs_context_t* ctx);

/* Error handling */
const char* vfs_strerror(int error);
int vfs_errno(void);

#ifdef __cplusplus
}
#endif

#endif /* KOS_VFS_API_H */