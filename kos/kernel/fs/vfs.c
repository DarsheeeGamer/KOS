#include "fs.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

/* Global VFS data structures */
struct kos_super_block *kos_super_blocks = NULL;
struct kos_file_system_type *kos_file_systems = NULL;
struct kos_mount *kos_root_mount = NULL;
pthread_rwlock_t kos_mount_lock = PTHREAD_RWLOCK_INITIALIZER;

/* Hash tables for inodes and dentries */
struct kos_inode *kos_inode_hashtbl[KOS_INODE_HASH_SIZE];
struct kos_dentry *kos_dentry_hashtbl[KOS_DENTRY_HASH_SIZE];
pthread_rwlock_t kos_inode_hash_lock = PTHREAD_RWLOCK_INITIALIZER;
pthread_rwlock_t kos_dentry_hash_lock = PTHREAD_RWLOCK_INITIALIZER;

/* File descriptor table */
#define KOS_MAX_FDS 1024
static struct kos_file *kos_fd_table[KOS_MAX_FDS];
static pthread_mutex_t kos_fd_lock = PTHREAD_MUTEX_INITIALIZER;

/* Hash functions */
static unsigned int kos_inode_hash(uint64_t ino) {
    return (unsigned int)(ino % KOS_INODE_HASH_SIZE);
}

static unsigned int kos_dentry_hash(const char *name) {
    unsigned int hash = 0;
    while (*name) {
        hash = hash * 31 + *name++;
    }
    return hash % KOS_DENTRY_HASH_SIZE;
}

/* Super block operations */
struct kos_super_block *kos_alloc_super_block(struct kos_file_system_type *type) {
    struct kos_super_block *sb = calloc(1, sizeof(struct kos_super_block));
    if (!sb) {
        return NULL;
    }
    
    sb->fs_type = type ? 0 : KOS_FS_TYPE_RAMFS; /* Default to RAMFS */
    sb->block_size = 4096;
    sb->total_blocks = 1000000;
    sb->free_blocks = 1000000;
    sb->total_inodes = 100000;
    sb->free_inodes = 100000;
    
    pthread_rwlock_init(&sb->s_lock, NULL);
    
    /* Add to global super block list */
    sb->next = kos_super_blocks;
    kos_super_blocks = sb;
    
    return sb;
}

void kos_free_super_block(struct kos_super_block *sb) {
    if (!sb) return;
    
    /* Remove from global list */
    struct kos_super_block **current = &kos_super_blocks;
    while (*current) {
        if (*current == sb) {
            *current = sb->next;
            break;
        }
        current = &(*current)->next;
    }
    
    pthread_rwlock_destroy(&sb->s_lock);
    free(sb->device_name);
    free(sb->mount_point);
    free(sb);
}

int kos_register_filesystem(struct kos_file_system_type *fs_type) {
    if (!fs_type || !fs_type->name) {
        return -EINVAL;
    }
    
    /* Check if already registered */
    struct kos_file_system_type *current = kos_file_systems;
    while (current) {
        if (strcmp(current->name, fs_type->name) == 0) {
            return -EEXIST;
        }
        current = current->next;
    }
    
    /* Add to list */
    fs_type->next = kos_file_systems;
    kos_file_systems = fs_type;
    
    return 0;
}

int kos_unregister_filesystem(struct kos_file_system_type *fs_type) {
    if (!fs_type) {
        return -EINVAL;
    }
    
    struct kos_file_system_type **current = &kos_file_systems;
    while (*current) {
        if (*current == fs_type) {
            *current = fs_type->next;
            return 0;
        }
        current = &(*current)->next;
    }
    
    return -ENOENT;
}

/* Mount operations */
int kos_mount(const char *source, const char *target, const char *filesystemtype,
              unsigned long mountflags, const void *data) {
    if (!target || !filesystemtype) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&kos_mount_lock);
    
    /* Find filesystem type */
    struct kos_file_system_type *fs_type = kos_file_systems;
    while (fs_type) {
        if (strcmp(fs_type->name, filesystemtype) == 0) {
            break;
        }
        fs_type = fs_type->next;
    }
    
    if (!fs_type) {
        pthread_rwlock_unlock(&kos_mount_lock);
        return -ENODEV;
    }
    
    /* Create super block */
    struct kos_super_block *sb = fs_type->mount ? 
        fs_type->mount(fs_type, mountflags, source, (void *)data) :
        kos_alloc_super_block(fs_type);
    
    if (!sb) {
        pthread_rwlock_unlock(&kos_mount_lock);
        return -ENOMEM;
    }
    
    /* Set mount information */
    sb->device_name = source ? strdup(source) : NULL;
    sb->mount_point = strdup(target);
    sb->mount_flags = mountflags;
    
    /* Create mount structure */
    struct kos_mount *mount = calloc(1, sizeof(struct kos_mount));
    if (!mount) {
        kos_free_super_block(sb);
        pthread_rwlock_unlock(&kos_mount_lock);
        return -ENOMEM;
    }
    
    mount->sb = sb;
    mount->device_name = sb->device_name ? strdup(sb->device_name) : NULL;
    mount->mount_point = strdup(target);
    mount->flags = mountflags;
    
    /* Add to mount list */
    mount->next = kos_root_mount;
    if (strcmp(target, "/") == 0) {
        kos_root_mount = mount;
    }
    
    pthread_rwlock_unlock(&kos_mount_lock);
    return 0;
}

int kos_umount(const char *target) {
    if (!target) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&kos_mount_lock);
    
    struct kos_mount **current = &kos_root_mount;
    while (*current) {
        if ((*current)->mount_point && strcmp((*current)->mount_point, target) == 0) {
            struct kos_mount *mount = *current;
            *current = mount->next;
            
            /* Clean up mount */
            if (mount->sb && mount->sb->s_op && mount->sb->s_op->put_super) {
                mount->sb->s_op->put_super(mount->sb);
            }
            kos_free_super_block(mount->sb);
            free(mount->device_name);
            free(mount->mount_point);
            free(mount);
            
            pthread_rwlock_unlock(&kos_mount_lock);
            return 0;
        }
        current = &(*current)->next;
    }
    
    pthread_rwlock_unlock(&kos_mount_lock);
    return -ENOENT;
}

struct kos_mount *kos_lookup_mount(const char *path) {
    if (!path) {
        return NULL;
    }
    
    pthread_rwlock_rdlock(&kos_mount_lock);
    
    struct kos_mount *best_mount = NULL;
    int best_len = 0;
    
    struct kos_mount *mount = kos_root_mount;
    while (mount) {
        if (mount->mount_point) {
            int len = strlen(mount->mount_point);
            if (strncmp(path, mount->mount_point, len) == 0 && len > best_len) {
                best_mount = mount;
                best_len = len;
            }
        }
        mount = mount->next;
    }
    
    pthread_rwlock_unlock(&kos_mount_lock);
    return best_mount;
}

/* File descriptor management */
static int kos_alloc_fd(void) {
    pthread_mutex_lock(&kos_fd_lock);
    
    for (int i = 0; i < KOS_MAX_FDS; i++) {
        if (kos_fd_table[i] == NULL) {
            pthread_mutex_unlock(&kos_fd_lock);
            return i;
        }
    }
    
    pthread_mutex_unlock(&kos_fd_lock);
    return -EMFILE;
}

static void kos_free_fd(int fd) {
    if (fd >= 0 && fd < KOS_MAX_FDS) {
        pthread_mutex_lock(&kos_fd_lock);
        kos_fd_table[fd] = NULL;
        pthread_mutex_unlock(&kos_fd_lock);
    }
}

static struct kos_file *kos_get_file(int fd) {
    if (fd < 0 || fd >= KOS_MAX_FDS) {
        return NULL;
    }
    
    pthread_mutex_lock(&kos_fd_lock);
    struct kos_file *file = kos_fd_table[fd];
    pthread_mutex_unlock(&kos_fd_lock);
    
    return file;
}

static void kos_set_file(int fd, struct kos_file *file) {
    if (fd >= 0 && fd < KOS_MAX_FDS) {
        pthread_mutex_lock(&kos_fd_lock);
        kos_fd_table[fd] = file;
        pthread_mutex_unlock(&kos_fd_lock);
    }
}

/* System call implementations */
int kos_sys_open(const char *pathname, int flags, mode_t mode) {
    if (!pathname) {
        return -EINVAL;
    }
    
    /* Allocate file descriptor */
    int fd = kos_alloc_fd();
    if (fd < 0) {
        return fd;
    }
    
    /* Lookup path */
    struct kos_dentry *dentry = kos_path_lookup(pathname, flags, NULL);
    if (!dentry) {
        kos_free_fd(fd);
        return -ENOENT;
    }
    
    /* Open file */
    struct kos_file *file = kos_dentry_open(dentry, flags);
    if (!file) {
        kos_dput(dentry);
        kos_free_fd(fd);
        return -ENOMEM;
    }
    
    /* Set file descriptor */
    kos_set_file(fd, file);
    
    return fd;
}

int kos_sys_close(int fd) {
    struct kos_file *file = kos_get_file(fd);
    if (!file) {
        return -EBADF;
    }
    
    int result = kos_file_close(file);
    kos_free_fd(fd);
    
    return result;
}

ssize_t kos_sys_read(int fd, void *buf, size_t count) {
    struct kos_file *file = kos_get_file(fd);
    if (!file) {
        return -EBADF;
    }
    
    if (!buf) {
        return -EINVAL;
    }
    
    if (file->f_op && file->f_op->read) {
        return file->f_op->read(file, (char *)buf, count, &file->position);
    }
    
    return -ENOSYS;
}

ssize_t kos_sys_write(int fd, const void *buf, size_t count) {
    struct kos_file *file = kos_get_file(fd);
    if (!file) {
        return -EBADF;
    }
    
    if (!buf) {
        return -EINVAL;
    }
    
    if (file->f_op && file->f_op->write) {
        return file->f_op->write(file, (const char *)buf, count, &file->position);
    }
    
    return -ENOSYS;
}

off_t kos_sys_lseek(int fd, off_t offset, int whence) {
    struct kos_file *file = kos_get_file(fd);
    if (!file) {
        return -EBADF;
    }
    
    if (file->f_op && file->f_op->lseek) {
        return file->f_op->lseek(file, offset, whence);
    }
    
    /* Default implementation */
    off_t new_pos;
    switch (whence) {
        case KOS_SEEK_SET:
            new_pos = offset;
            break;
        case KOS_SEEK_CUR:
            new_pos = file->position + offset;
            break;
        case KOS_SEEK_END:
            if (file->dentry && file->dentry->inode) {
                new_pos = file->dentry->inode->size + offset;
            } else {
                return -EINVAL;
            }
            break;
        default:
            return -EINVAL;
    }
    
    if (new_pos < 0) {
        return -EINVAL;
    }
    
    file->position = new_pos;
    return new_pos;
}

int kos_sys_stat(const char *pathname, struct stat *statbuf) {
    if (!pathname || !statbuf) {
        return -EINVAL;
    }
    
    struct kos_dentry *dentry = kos_path_lookup(pathname, 0, NULL);
    if (!dentry) {
        return -ENOENT;
    }
    
    struct kos_inode *inode = dentry->inode;
    if (!inode) {
        kos_dput(dentry);
        return -ENOENT;
    }
    
    /* Fill stat structure */
    memset(statbuf, 0, sizeof(struct stat));
    statbuf->st_ino = inode->ino;
    statbuf->st_mode = inode->mode;
    statbuf->st_nlink = inode->nlink;
    statbuf->st_uid = inode->uid;
    statbuf->st_gid = inode->gid;
    statbuf->st_rdev = inode->rdev;
    statbuf->st_size = inode->size;
    statbuf->st_atime = inode->atime;
    statbuf->st_mtime = inode->mtime;
    statbuf->st_ctime = inode->ctime;
    statbuf->st_blksize = inode->blksize;
    statbuf->st_blocks = inode->blocks;
    
    kos_dput(dentry);
    return 0;
}

int kos_sys_fstat(int fd, struct stat *statbuf) {
    struct kos_file *file = kos_get_file(fd);
    if (!file) {
        return -EBADF;
    }
    
    if (!statbuf) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -ENOENT;
    }
    
    struct kos_inode *inode = file->dentry->inode;
    
    /* Fill stat structure */
    memset(statbuf, 0, sizeof(struct stat));
    statbuf->st_ino = inode->ino;
    statbuf->st_mode = inode->mode;
    statbuf->st_nlink = inode->nlink;
    statbuf->st_uid = inode->uid;
    statbuf->st_gid = inode->gid;
    statbuf->st_rdev = inode->rdev;
    statbuf->st_size = inode->size;
    statbuf->st_atime = inode->atime;
    statbuf->st_mtime = inode->mtime;
    statbuf->st_ctime = inode->ctime;
    statbuf->st_blksize = inode->blksize;
    statbuf->st_blocks = inode->blocks;
    
    return 0;
}

int kos_sys_mkdir(const char *pathname, mode_t mode) {
    if (!pathname) {
        return -EINVAL;
    }
    
    /* Extract directory and filename */
    char *path_copy = strdup(pathname);
    char *dirname = path_copy;
    char *basename = strrchr(path_copy, '/');
    
    if (basename) {
        *basename = '\0';
        basename++;
    } else {
        basename = dirname;
        dirname = ".";
    }
    
    /* Lookup parent directory */
    struct kos_dentry *parent = kos_path_lookup(dirname, 0, NULL);
    if (!parent) {
        free(path_copy);
        return -ENOENT;
    }
    
    if (!parent->inode) {
        kos_dput(parent);
        free(path_copy);
        return -ENOENT;
    }
    
    /* Create new dentry */
    struct kos_dentry *dentry = kos_alloc_dentry(basename);
    if (!dentry) {
        kos_dput(parent);
        free(path_copy);
        return -ENOMEM;
    }
    
    /* Create directory */
    int result = -ENOSYS;
    if (parent->inode->i_op && parent->inode->i_op->mkdir) {
        result = parent->inode->i_op->mkdir(parent->inode, dentry, mode | KOS_S_IFDIR);
    }
    
    if (result == 0) {
        /* Add to dcache */
        dentry->parent = parent;
        kos_dcache_add(dentry);
    } else {
        kos_free_dentry(dentry);
    }
    
    kos_dput(parent);
    free(path_copy);
    return result;
}

int kos_sys_rmdir(const char *pathname) {
    if (!pathname) {
        return -EINVAL;
    }
    
    struct kos_dentry *dentry = kos_path_lookup(pathname, 0, NULL);
    if (!dentry) {
        return -ENOENT;
    }
    
    if (!dentry->inode) {
        kos_dput(dentry);
        return -ENOENT;
    }
    
    /* Check if it's a directory */
    if ((dentry->inode->mode & KOS_S_IFMT) != KOS_S_IFDIR) {
        kos_dput(dentry);
        return -ENOTDIR;
    }
    
    /* Remove directory */
    int result = -ENOSYS;
    if (dentry->parent && dentry->parent->inode && 
        dentry->parent->inode->i_op && dentry->parent->inode->i_op->rmdir) {
        result = dentry->parent->inode->i_op->rmdir(dentry->parent->inode, dentry);
    }
    
    if (result == 0) {
        kos_dcache_remove(dentry);
    }
    
    kos_dput(dentry);
    return result;
}

int kos_sys_unlink(const char *pathname) {
    if (!pathname) {
        return -EINVAL;
    }
    
    struct kos_dentry *dentry = kos_path_lookup(pathname, 0, NULL);
    if (!dentry) {
        return -ENOENT;
    }
    
    if (!dentry->inode) {
        kos_dput(dentry);
        return -ENOENT;
    }
    
    /* Check if it's not a directory */
    if ((dentry->inode->mode & KOS_S_IFMT) == KOS_S_IFDIR) {
        kos_dput(dentry);
        return -EISDIR;
    }
    
    /* Unlink file */
    int result = -ENOSYS;
    if (dentry->parent && dentry->parent->inode && 
        dentry->parent->inode->i_op && dentry->parent->inode->i_op->unlink) {
        result = dentry->parent->inode->i_op->unlink(dentry->parent->inode, dentry);
    }
    
    if (result == 0) {
        kos_dcache_remove(dentry);
    }
    
    kos_dput(dentry);
    return result;
}

/* Initialize VFS */
void kos_vfs_init(void) {
    /* Initialize hash tables */
    memset(kos_inode_hashtbl, 0, sizeof(kos_inode_hashtbl));
    memset(kos_dentry_hashtbl, 0, sizeof(kos_dentry_hashtbl));
    memset(kos_fd_table, 0, sizeof(kos_fd_table));
    
    /* Initialize dcache */
    kos_dcache_init();
}

/* Cleanup VFS */
void kos_vfs_cleanup(void) {
    /* Cleanup dcache */
    kos_dcache_cleanup();
    
    /* Cleanup file descriptors */
    for (int i = 0; i < KOS_MAX_FDS; i++) {
        if (kos_fd_table[i]) {
            kos_file_close(kos_fd_table[i]);
            kos_fd_table[i] = NULL;
        }
    }
    
    /* Cleanup mounts */
    while (kos_root_mount) {
        struct kos_mount *mount = kos_root_mount;
        kos_root_mount = mount->next;
        
        if (mount->sb && mount->sb->s_op && mount->sb->s_op->put_super) {
            mount->sb->s_op->put_super(mount->sb);
        }
        kos_free_super_block(mount->sb);
        free(mount->device_name);
        free(mount->mount_point);
        free(mount);
    }
    
    /* Cleanup super blocks */
    while (kos_super_blocks) {
        struct kos_super_block *sb = kos_super_blocks;
        kos_super_blocks = sb->next;
        kos_free_super_block(sb);
    }
}