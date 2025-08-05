#ifndef __KOS_FS_H__
#define __KOS_FS_H__

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <pthread.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum filename length */
#define KOS_MAX_FILENAME 255
#define KOS_MAX_PATH 4096

/* File system types */
#define KOS_FS_TYPE_RAMFS    1
#define KOS_FS_TYPE_DEVFS    2
#define KOS_FS_TYPE_PROCFS   3
#define KOS_FS_TYPE_SYSFS    4
#define KOS_FS_TYPE_EXT4     5

/* File types */
#define KOS_S_IFMT   0170000
#define KOS_S_IFREG  0100000
#define KOS_S_IFDIR  0040000
#define KOS_S_IFCHR  0020000
#define KOS_S_IFBLK  0060000
#define KOS_S_IFIFO  0010000
#define KOS_S_IFLNK  0120000
#define KOS_S_IFSOCK 0140000

/* File permissions */
#define KOS_S_ISUID  04000
#define KOS_S_ISGID  02000
#define KOS_S_ISVTX  01000
#define KOS_S_IRUSR  00400
#define KOS_S_IWUSR  00200
#define KOS_S_IXUSR  00100
#define KOS_S_IRGRP  00040
#define KOS_S_IWGRP  00020
#define KOS_S_IXGRP  00010
#define KOS_S_IROTH  00004
#define KOS_S_IWOTH  00002
#define KOS_S_IXOTH  00001

/* File flags */
#define KOS_O_RDONLY     00000000
#define KOS_O_WRONLY     00000001
#define KOS_O_RDWR       00000002
#define KOS_O_CREAT      00000100
#define KOS_O_EXCL       00000200
#define KOS_O_NOCTTY     00000400
#define KOS_O_TRUNC      00001000
#define KOS_O_APPEND     00002000
#define KOS_O_NONBLOCK   00004000
#define KOS_O_SYNC       04010000
#define KOS_O_DIRECTORY  00200000

/* Seek operations */
#define KOS_SEEK_SET     0
#define KOS_SEEK_CUR     1
#define KOS_SEEK_END     2

/* Lock types */
#define KOS_F_RDLCK      0
#define KOS_F_WRLCK      1
#define KOS_F_UNLCK      2

/* Extended attribute limits */
#define KOS_XATTR_NAME_MAX    255
#define KOS_XATTR_SIZE_MAX    65536
#define KOS_XATTR_LIST_MAX    65536

/* Forward declarations */
struct kos_inode;
struct kos_dentry;
struct kos_file;
struct kos_super_block;
struct kos_file_operations;
struct kos_inode_operations;
struct kos_super_operations;

/* Extended attribute structure */
struct kos_xattr {
    char name[KOS_XATTR_NAME_MAX + 1];
    void *value;
    size_t size;
    struct kos_xattr *next;
};

/* Access Control List entry */
struct kos_acl_entry {
    uint16_t tag;         /* ACL_USER, ACL_GROUP, etc. */
    uint16_t perm;        /* Permissions */
    uint32_t id;          /* User/Group ID */
};

struct kos_acl {
    int count;
    struct kos_acl_entry entries[];
};

/* File lock structure */
struct kos_file_lock {
    int type;             /* F_RDLCK, F_WRLCK, F_UNLCK */
    off_t start;
    off_t len;
    pid_t pid;
    struct kos_file_lock *next;
    pthread_mutex_t mutex;
    pthread_cond_t cond;
};

/* Inode structure */
struct kos_inode {
    uint64_t ino;                    /* Inode number */
    uint32_t mode;                   /* File mode and permissions */
    uint32_t nlink;                  /* Number of hard links */
    uid_t uid;                       /* User ID */
    gid_t gid;                       /* Group ID */
    dev_t rdev;                      /* Device ID (for special files) */
    off_t size;                      /* File size in bytes */
    time_t atime;                    /* Access time */
    time_t mtime;                    /* Modification time */
    time_t ctime;                    /* Change time */
    blksize_t blksize;              /* Block size */
    blkcnt_t blocks;                /* Number of blocks allocated */
    
    /* File system specific data */
    void *private_data;
    
    /* Operations */
    const struct kos_inode_operations *i_op;
    const struct kos_file_operations *i_fop;
    
    /* Extended attributes */
    struct kos_xattr *xattrs;
    
    /* Access Control Lists */
    struct kos_acl *acl_access;
    struct kos_acl *acl_default;
    
    /* File locks */
    struct kos_file_lock *locks;
    
    /* Reference counting and locking */
    int ref_count;
    pthread_rwlock_t i_lock;
    
    /* Hash table linkage */
    struct kos_inode *i_hash_next;
    struct kos_inode *i_hash_prev;
    
    /* Super block reference */
    struct kos_super_block *i_sb;
};

/* Directory entry structure */
struct kos_dentry {
    char name[KOS_MAX_FILENAME + 1]; /* Directory entry name */
    struct kos_inode *inode;         /* Associated inode */
    struct kos_dentry *parent;       /* Parent directory */
    struct kos_dentry *child;        /* First child (for directories) */
    struct kos_dentry *sibling;      /* Next sibling */
    
    /* Hash table linkage */
    struct kos_dentry *d_hash_next;
    struct kos_dentry *d_hash_prev;
    
    /* Reference counting and locking */
    int ref_count;
    pthread_mutex_t d_lock;
    
    /* Flags */
    uint32_t flags;
    
    /* Time stamp for cache invalidation */
    time_t cache_time;
};

/* File structure */
struct kos_file {
    struct kos_dentry *dentry;       /* Associated dentry */
    const struct kos_file_operations *f_op; /* File operations */
    off_t position;                  /* Current file position */
    uint32_t flags;                  /* File flags (O_RDONLY, etc.) */
    mode_t mode;                     /* File mode */
    
    /* File locks */
    struct kos_file_lock *locks;
    
    /* Reference counting and locking */
    int ref_count;
    pthread_mutex_t f_lock;
    
    /* Private data for file system specific info */
    void *private_data;
};

/* Super block structure */
struct kos_super_block {
    uint32_t fs_type;                /* File system type */
    uint32_t block_size;             /* Block size */
    uint64_t total_blocks;           /* Total number of blocks */
    uint64_t free_blocks;            /* Number of free blocks */
    uint64_t total_inodes;           /* Total number of inodes */
    uint64_t free_inodes;            /* Number of free inodes */
    
    /* Root directory */
    struct kos_dentry *root;
    
    /* Operations */
    const struct kos_super_operations *s_op;
    
    /* File system specific data */
    void *private_data;
    
    /* Mount information */
    char *device_name;
    char *mount_point;
    uint32_t mount_flags;
    
    /* Locking */
    pthread_rwlock_t s_lock;
    
    /* List linkage */
    struct kos_super_block *next;
};

/* File operations structure */
struct kos_file_operations {
    ssize_t (*read)(struct kos_file *file, char *buffer, size_t count, off_t *offset);
    ssize_t (*write)(struct kos_file *file, const char *buffer, size_t count, off_t *offset);
    off_t (*lseek)(struct kos_file *file, off_t offset, int whence);
    int (*open)(struct kos_inode *inode, struct kos_file *file);
    int (*release)(struct kos_inode *inode, struct kos_file *file);
    int (*fsync)(struct kos_file *file, int datasync);
    int (*lock)(struct kos_file *file, int cmd, struct kos_file_lock *lock);
    int (*flock)(struct kos_file *file, int operation);
};

/* Inode operations structure */
struct kos_inode_operations {
    struct kos_dentry *(*lookup)(struct kos_inode *dir, struct kos_dentry *dentry);
    int (*create)(struct kos_inode *dir, struct kos_dentry *dentry, mode_t mode);
    int (*link)(struct kos_dentry *old_dentry, struct kos_inode *dir, struct kos_dentry *new_dentry);
    int (*unlink)(struct kos_inode *dir, struct kos_dentry *dentry);
    int (*symlink)(struct kos_inode *dir, struct kos_dentry *dentry, const char *target);
    int (*mkdir)(struct kos_inode *dir, struct kos_dentry *dentry, mode_t mode);
    int (*rmdir)(struct kos_inode *dir, struct kos_dentry *dentry);
    int (*mknod)(struct kos_inode *dir, struct kos_dentry *dentry, mode_t mode, dev_t rdev);
    int (*rename)(struct kos_inode *old_dir, struct kos_dentry *old_dentry,
                  struct kos_inode *new_dir, struct kos_dentry *new_dentry);
    ssize_t (*readlink)(struct kos_dentry *dentry, char *buffer, size_t buflen);
    int (*permission)(struct kos_inode *inode, int mask);
    int (*setattr)(struct kos_dentry *dentry, struct iattr *attr);
    int (*getattr)(struct kos_dentry *dentry, struct kstat *stat);
    int (*setxattr)(struct kos_dentry *dentry, const char *name, const void *value, size_t size, int flags);
    ssize_t (*getxattr)(struct kos_dentry *dentry, const char *name, void *value, size_t size);
    ssize_t (*listxattr)(struct kos_dentry *dentry, char *list, size_t size);
    int (*removexattr)(struct kos_dentry *dentry, const char *name);
};

/* Super block operations structure */
struct kos_super_operations {
    struct kos_inode *(*alloc_inode)(struct kos_super_block *sb);
    void (*destroy_inode)(struct kos_inode *inode);
    int (*write_inode)(struct kos_inode *inode, int sync);
    void (*drop_inode)(struct kos_inode *inode);
    void (*delete_inode)(struct kos_inode *inode);
    void (*put_super)(struct kos_super_block *sb);
    int (*sync_fs)(struct kos_super_block *sb, int wait);
    int (*statfs)(struct kos_dentry *dentry, struct kstatfs *buf);
    int (*remount_fs)(struct kos_super_block *sb, int *flags, char *data);
};

/* File system type structure */
struct kos_file_system_type {
    const char *name;
    int fs_flags;
    struct kos_super_block *(*mount)(struct kos_file_system_type *fs_type,
                                     int flags, const char *dev_name, void *data);
    void (*kill_sb)(struct kos_super_block *sb);
    struct kos_file_system_type *next;
};

/* Mount information structure */
struct kos_mount {
    struct kos_super_block *sb;
    struct kos_dentry *mountpoint;
    struct kos_dentry *root;
    struct kos_mount *parent;
    struct kos_mount *next;
    char *device_name;
    char *mount_point;
    uint32_t flags;
};

/* Directory reading structure */
struct kos_dirent {
    uint64_t ino;
    off_t offset;
    uint16_t reclen;
    uint8_t type;
    char name[];
};

/* File system statistics */
struct kos_statfs {
    uint32_t f_type;
    uint32_t f_bsize;
    uint64_t f_blocks;
    uint64_t f_bfree;
    uint64_t f_bavail;
    uint64_t f_files;
    uint64_t f_ffree;
    uint64_t f_fsid;
    uint32_t f_namelen;
    uint32_t f_frsize;
    uint32_t f_flags;
};

/* VFS function prototypes */

/* Super block operations */
struct kos_super_block *kos_alloc_super_block(struct kos_file_system_type *type);
void kos_free_super_block(struct kos_super_block *sb);
int kos_register_filesystem(struct kos_file_system_type *fs_type);
int kos_unregister_filesystem(struct kos_file_system_type *fs_type);

/* Mount operations */
int kos_mount(const char *source, const char *target, const char *filesystemtype,
              unsigned long mountflags, const void *data);
int kos_umount(const char *target);
struct kos_mount *kos_lookup_mount(const char *path);

/* Inode operations */
struct kos_inode *kos_alloc_inode(struct kos_super_block *sb);
void kos_free_inode(struct kos_inode *inode);
struct kos_inode *kos_iget(struct kos_super_block *sb, uint64_t ino);
void kos_iput(struct kos_inode *inode);
void kos_inode_init_once(struct kos_inode *inode);
int kos_inode_permission(struct kos_inode *inode, int mask);

/* Dentry operations */
struct kos_dentry *kos_alloc_dentry(const char *name);
void kos_free_dentry(struct kos_dentry *dentry);
struct kos_dentry *kos_dget(struct kos_dentry *dentry);
void kos_dput(struct kos_dentry *dentry);
void kos_d_instantiate(struct kos_dentry *dentry, struct kos_inode *inode);

/* File operations */
struct kos_file *kos_alloc_file(void);
void kos_free_file(struct kos_file *file);
struct kos_file *kos_dentry_open(struct kos_dentry *dentry, int flags);
int kos_file_close(struct kos_file *file);

/* Path name resolution */
struct kos_dentry *kos_path_lookup(const char *path, int flags, struct kos_dentry *base);
int kos_path_walk(const char *name, struct kos_dentry *base, struct kos_dentry **result);

/* Directory cache operations */
void kos_dcache_init(void);
void kos_dcache_cleanup(void);
struct kos_dentry *kos_dcache_lookup(struct kos_dentry *parent, const char *name);
void kos_dcache_add(struct kos_dentry *dentry);
void kos_dcache_remove(struct kos_dentry *dentry);
void kos_dcache_prune(void);

/* File locking */
int kos_file_lock(struct kos_file *file, int cmd, struct kos_file_lock *lock);
int kos_file_unlock(struct kos_file *file, struct kos_file_lock *lock);
void kos_locks_remove_posix(struct kos_file *file, pid_t pid);

/* Extended attributes */
int kos_setxattr(struct kos_dentry *dentry, const char *name, const void *value, size_t size, int flags);
ssize_t kos_getxattr(struct kos_dentry *dentry, const char *name, void *value, size_t size);
ssize_t kos_listxattr(struct kos_dentry *dentry, char *list, size_t size);
int kos_removexattr(struct kos_dentry *dentry, const char *name);

/* Access Control Lists */
struct kos_acl *kos_get_acl(struct kos_inode *inode, int type);
int kos_set_acl(struct kos_inode *inode, int type, struct kos_acl *acl);
void kos_free_acl(struct kos_acl *acl);
int kos_acl_permission_check(struct kos_inode *inode, int mask);

/* Utility functions */
int kos_generic_permission(struct kos_inode *inode, int mask);
void kos_update_time(struct kos_inode *inode, int flags);
int kos_notify_change(struct kos_dentry *dentry, struct iattr *attr);

/* System calls interface */
int kos_sys_open(const char *pathname, int flags, mode_t mode);
int kos_sys_close(int fd);
ssize_t kos_sys_read(int fd, void *buf, size_t count);
ssize_t kos_sys_write(int fd, const void *buf, size_t count);
off_t kos_sys_lseek(int fd, off_t offset, int whence);
int kos_sys_stat(const char *pathname, struct stat *statbuf);
int kos_sys_fstat(int fd, struct stat *statbuf);
int kos_sys_lstat(const char *pathname, struct stat *statbuf);
int kos_sys_mkdir(const char *pathname, mode_t mode);
int kos_sys_rmdir(const char *pathname);
int kos_sys_unlink(const char *pathname);
int kos_sys_link(const char *oldpath, const char *newpath);
int kos_sys_symlink(const char *target, const char *linkpath);
ssize_t kos_sys_readlink(const char *pathname, char *buf, size_t bufsiz);
int kos_sys_rename(const char *oldpath, const char *newpath);
int kos_sys_chmod(const char *pathname, mode_t mode);
int kos_sys_chown(const char *pathname, uid_t owner, gid_t group);

/* Global variables */
extern struct kos_super_block *kos_super_blocks;
extern struct kos_file_system_type *kos_file_systems;
extern struct kos_mount *kos_root_mount;
extern pthread_rwlock_t kos_mount_lock;

/* Hash table sizes */
#define KOS_INODE_HASH_SIZE 1024
#define KOS_DENTRY_HASH_SIZE 1024

/* Hash tables */
extern struct kos_inode *kos_inode_hashtbl[KOS_INODE_HASH_SIZE];
extern struct kos_dentry *kos_dentry_hashtbl[KOS_DENTRY_HASH_SIZE];
extern pthread_rwlock_t kos_inode_hash_lock;
extern pthread_rwlock_t kos_dentry_hash_lock;

#ifdef __cplusplus
}
#endif

#endif /* __KOS_FS_H__ */