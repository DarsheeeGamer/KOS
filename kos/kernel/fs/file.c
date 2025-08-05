#include "fs.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>

/* File lock management */
static int kos_file_lock_conflicts(struct kos_file_lock *lock1, struct kos_file_lock *lock2) {
    /* Check if locks overlap */
    off_t end1 = (lock1->len == 0) ? OFF_MAX : lock1->start + lock1->len - 1;
    off_t end2 = (lock2->len == 0) ? OFF_MAX : lock2->start + lock2->len - 1;
    
    if (lock1->start > end2 || lock2->start > end1) {
        return 0; /* No overlap */
    }
    
    /* Check if lock types conflict */
    if (lock1->type == KOS_F_RDLCK && lock2->type == KOS_F_RDLCK) {
        return 0; /* Read locks don't conflict */
    }
    
    return 1; /* Conflict exists */
}

static struct kos_file_lock *kos_find_lock_conflict(struct kos_file *file, struct kos_file_lock *lock) {
    struct kos_file_lock *current = file->locks;
    
    while (current) {
        if (current->pid != lock->pid && kos_file_lock_conflicts(current, lock)) {
            return current;
        }
        current = current->next;
    }
    
    return NULL;
}

static void kos_add_file_lock(struct kos_file *file, struct kos_file_lock *lock) {
    lock->next = file->locks;
    file->locks = lock;
}

static void kos_remove_file_lock(struct kos_file *file, struct kos_file_lock *lock) {
    struct kos_file_lock **current = &file->locks;
    
    while (*current) {
        if (*current == lock) {
            *current = lock->next;
            break;
        }
        current = &(*current)->next;
    }
}

/* Allocate a new file structure */
struct kos_file *kos_alloc_file(void) {
    struct kos_file *file = calloc(1, sizeof(struct kos_file));
    if (!file) {
        return NULL;
    }
    
    file->ref_count = 1;
    file->position = 0;
    pthread_mutex_init(&file->f_lock, NULL);
    
    return file;
}

/* Free a file structure */
void kos_free_file(struct kos_file *file) {
    if (!file) return;
    
    /* Free file locks */
    struct kos_file_lock *lock = file->locks;
    while (lock) {
        struct kos_file_lock *next = lock->next;
        pthread_mutex_destroy(&lock->mutex);
        pthread_cond_destroy(&lock->cond);
        free(lock);
        lock = next;
    }
    
    /* Release dentry reference */
    if (file->dentry) {
        kos_dput(file->dentry);
    }
    
    pthread_mutex_destroy(&file->f_lock);
    free(file->private_data);
    free(file);
}

/* Open a file from dentry */
struct kos_file *kos_dentry_open(struct kos_dentry *dentry, int flags) {
    if (!dentry || !dentry->inode) {
        return NULL;
    }
    
    struct kos_file *file = kos_alloc_file();
    if (!file) {
        return NULL;
    }
    
    file->dentry = kos_dget(dentry);
    file->f_op = dentry->inode->i_fop;
    file->flags = flags;
    
    /* Check permissions */
    int mask = 0;
    if (flags & KOS_O_RDONLY || flags & KOS_O_RDWR) mask |= MAY_READ;
    if (flags & KOS_O_WRONLY || flags & KOS_O_RDWR) mask |= MAY_WRITE;
    
    int perm_result = kos_inode_permission(dentry->inode, mask);
    if (perm_result < 0) {
        kos_free_file(file);
        return NULL;
    }
    
    /* Truncate if requested */
    if (flags & KOS_O_TRUNC && (flags & (KOS_O_WRONLY | KOS_O_RDWR))) {
        kos_inode_truncate(dentry->inode, 0);
    }
    
    /* Call file system specific open */
    if (file->f_op && file->f_op->open) {
        int result = file->f_op->open(dentry->inode, file);
        if (result < 0) {
            kos_free_file(file);
            return NULL;
        }
    }
    
    /* Update access time */
    kos_update_time(dentry->inode, S_ATIME);
    
    return file;
}

/* Close a file */
int kos_file_close(struct kos_file *file) {
    if (!file) {
        return -EINVAL;
    }
    
    int result = 0;
    
    /* Call file system specific release */
    if (file->f_op && file->f_op->release && file->dentry && file->dentry->inode) {
        result = file->f_op->release(file->dentry->inode, file);
    }
    
    /* Remove all POSIX locks held by this file */
    kos_locks_remove_posix(file, getpid());
    
    kos_free_file(file);
    return result;
}

/* Read from file */
ssize_t kos_file_read(struct kos_file *file, char *buffer, size_t count, off_t *offset) {
    if (!file || !buffer) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -EBADF;
    }
    
    /* Check read permission */
    if (!(file->flags & KOS_O_RDONLY) && !(file->flags & KOS_O_RDWR)) {
        return -EBADF;
    }
    
    pthread_mutex_lock(&file->f_lock);
    
    off_t pos = offset ? *offset : file->position;
    
    /* Check file locks */
    struct kos_file_lock test_lock = {
        .type = KOS_F_RDLCK,
        .start = pos,
        .len = count,
        .pid = getpid()
    };
    
    struct kos_file_lock *conflict = kos_find_lock_conflict(file, &test_lock);
    if (conflict) {
        pthread_mutex_unlock(&file->f_lock);
        return -EAGAIN;
    }
    
    ssize_t result = 0;
    
    /* Call file system specific read */
    if (file->f_op && file->f_op->read) {
        result = file->f_op->read(file, buffer, count, &pos);
    } else {
        /* Default read implementation */
        struct kos_inode *inode = file->dentry->inode;
        
        if (pos >= inode->size) {
            result = 0; /* EOF */
        } else {
            size_t available = inode->size - pos;
            size_t to_read = (count < available) ? count : available;
            
            /* This is where actual data reading would happen */
            /* For now, we'll simulate reading zeros */
            memset(buffer, 0, to_read);
            result = to_read;
            pos += to_read;
        }
    }
    
    if (result > 0) {
        if (offset) {
            *offset = pos;
        } else {
            file->position = pos;
        }
        
        /* Update access time */
        kos_update_time(file->dentry->inode, S_ATIME);
    }
    
    pthread_mutex_unlock(&file->f_lock);
    return result;
}

/* Write to file */
ssize_t kos_file_write(struct kos_file *file, const char *buffer, size_t count, off_t *offset) {
    if (!file || !buffer) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -EBADF;
    }
    
    /* Check write permission */
    if (!(file->flags & KOS_O_WRONLY) && !(file->flags & KOS_O_RDWR)) {
        return -EBADF;
    }
    
    pthread_mutex_lock(&file->f_lock);
    
    off_t pos = offset ? *offset : file->position;
    
    /* Handle append mode */
    if (file->flags & KOS_O_APPEND) {
        pos = file->dentry->inode->size;
    }
    
    /* Check file locks */
    struct kos_file_lock test_lock = {
        .type = KOS_F_WRLCK,
        .start = pos,
        .len = count,
        .pid = getpid()
    };
    
    struct kos_file_lock *conflict = kos_find_lock_conflict(file, &test_lock);
    if (conflict) {
        pthread_mutex_unlock(&file->f_lock);
        return -EAGAIN;
    }
    
    ssize_t result = 0;
    
    /* Call file system specific write */
    if (file->f_op && file->f_op->write) {
        result = file->f_op->write(file, buffer, count, &pos);
    } else {
        /* Default write implementation */
        struct kos_inode *inode = file->dentry->inode;
        
        /* Update file size if writing beyond current size */
        pthread_rwlock_wrlock(&inode->i_lock);
        
        if (pos + count > inode->size) {
            inode->size = pos + count;
            inode->blocks = (inode->size + inode->blksize - 1) / inode->blksize;
        }
        
        pthread_rwlock_unlock(&inode->i_lock);
        
        /* Simulate writing data */
        result = count;
        pos += count;
    }
    
    if (result > 0) {
        if (offset) {
            *offset = pos;
        } else {
            file->position = pos;
        }
        
        /* Update modification time */
        kos_update_time(file->dentry->inode, S_MTIME | S_CTIME);
        
        /* Sync if O_SYNC is set */
        if (file->flags & KOS_O_SYNC && file->f_op && file->f_op->fsync) {
            file->f_op->fsync(file, 1);
        }
    }
    
    pthread_mutex_unlock(&file->f_lock);
    return result;
}

/* Seek in file */
off_t kos_file_lseek(struct kos_file *file, off_t offset, int whence) {
    if (!file) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -EBADF;
    }
    
    pthread_mutex_lock(&file->f_lock);
    
    off_t new_pos;
    
    /* Call file system specific lseek if available */
    if (file->f_op && file->f_op->lseek) {
        new_pos = file->f_op->lseek(file, offset, whence);
    } else {
        /* Default implementation */
        switch (whence) {
            case KOS_SEEK_SET:
                new_pos = offset;
                break;
            case KOS_SEEK_CUR:
                new_pos = file->position + offset;
                break;
            case KOS_SEEK_END:
                new_pos = file->dentry->inode->size + offset;
                break;
            default:
                new_pos = -EINVAL;
                break;
        }
        
        if (new_pos >= 0) {
            file->position = new_pos;
        }
    }
    
    pthread_mutex_unlock(&file->f_lock);
    return new_pos;
}

/* Synchronize file data */
int kos_file_fsync(struct kos_file *file, int datasync) {
    if (!file) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -EBADF;
    }
    
    /* Call file system specific fsync */
    if (file->f_op && file->f_op->fsync) {
        return file->f_op->fsync(file, datasync);
    }
    
    /* Default implementation - just update inode times */
    if (!datasync) {
        kos_update_time(file->dentry->inode, S_CTIME);
    }
    
    return 0;
}

/* File locking implementation */
int kos_file_lock(struct kos_file *file, int cmd, struct kos_file_lock *lock) {
    if (!file || !lock) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&file->f_lock);
    
    /* Call file system specific lock if available */
    if (file->f_op && file->f_op->lock) {
        int result = file->f_op->lock(file, cmd, lock);
        pthread_mutex_unlock(&file->f_lock);
        return result;
    }
    
    /* Default POSIX lock implementation */
    int result = 0;
    
    switch (cmd) {
        case F_SETLK:
        case F_SETLKW: {
            if (lock->type == KOS_F_UNLCK) {
                /* Remove existing locks */
                struct kos_file_lock **current = &file->locks;
                while (*current) {
                    struct kos_file_lock *existing = *current;
                    if (existing->pid == lock->pid &&
                        existing->start == lock->start &&
                        existing->len == lock->len) {
                        *current = existing->next;
                        pthread_mutex_destroy(&existing->mutex);
                        pthread_cond_destroy(&existing->cond);
                        free(existing);
                        break;
                    }
                    current = &(*current)->next;
                }
            } else {
                /* Check for conflicts */
                struct kos_file_lock *conflict = kos_find_lock_conflict(file, lock);
                if (conflict) {
                    if (cmd == F_SETLK) {
                        result = -EAGAIN;
                    } else {
                        /* F_SETLKW - wait for lock */
                        pthread_mutex_unlock(&file->f_lock);
                        
                        pthread_mutex_lock(&conflict->mutex);
                        while (kos_find_lock_conflict(file, lock)) {
                            pthread_cond_wait(&conflict->cond, &conflict->mutex);
                        }
                        pthread_mutex_unlock(&conflict->mutex);
                        
                        pthread_mutex_lock(&file->f_lock);
                    }
                }
                
                if (result == 0) {
                    /* Add new lock */
                    struct kos_file_lock *new_lock = calloc(1, sizeof(struct kos_file_lock));
                    if (!new_lock) {
                        result = -ENOMEM;
                    } else {
                        *new_lock = *lock;
                        new_lock->pid = getpid();
                        pthread_mutex_init(&new_lock->mutex, NULL);
                        pthread_cond_init(&new_lock->cond, NULL);
                        kos_add_file_lock(file, new_lock);
                    }
                }
            }
            break;
        }
        
        case F_GETLK: {
            struct kos_file_lock *conflict = kos_find_lock_conflict(file, lock);
            if (conflict) {
                lock->type = conflict->type;
                lock->start = conflict->start;
                lock->len = conflict->len;
                lock->pid = conflict->pid;
            } else {
                lock->type = KOS_F_UNLCK;
            }
            break;
        }
        
        default:
            result = -EINVAL;
            break;
    }
    
    pthread_mutex_unlock(&file->f_lock);
    return result;
}

/* Remove all POSIX locks for a process */
void kos_locks_remove_posix(struct kos_file *file, pid_t pid) {
    if (!file) return;
    
    pthread_mutex_lock(&file->f_lock);
    
    struct kos_file_lock **current = &file->locks;
    while (*current) {
        if ((*current)->pid == pid) {
            struct kos_file_lock *lock = *current;
            *current = lock->next;
            
            /* Wake up any waiters */
            pthread_cond_broadcast(&lock->cond);
            
            pthread_mutex_destroy(&lock->mutex);
            pthread_cond_destroy(&lock->cond);
            free(lock);
        } else {
            current = &(*current)->next;
        }
    }
    
    pthread_mutex_unlock(&file->f_lock);
}

/* File locking with flock semantics */
int kos_file_flock(struct kos_file *file, int operation) {
    if (!file) {
        return -EINVAL;
    }
    
    /* Call file system specific flock if available */
    if (file->f_op && file->f_op->flock) {
        return file->f_op->flock(file, operation);
    }
    
    /* Default implementation using POSIX locks */
    struct kos_file_lock lock = {0};
    lock.start = 0;
    lock.len = 0; /* Whole file */
    
    switch (operation & ~LOCK_NB) {
        case LOCK_SH:
            lock.type = KOS_F_RDLCK;
            break;
        case LOCK_EX:
            lock.type = KOS_F_WRLCK;
            break;
        case LOCK_UN:
            lock.type = KOS_F_UNLCK;
            break;
        default:
            return -EINVAL;
    }
    
    int cmd = (operation & LOCK_NB) ? F_SETLK : F_SETLKW;
    return kos_file_lock(file, cmd, &lock);
}

/* Get file status */
int kos_file_stat(struct kos_file *file, struct stat *statbuf) {
    if (!file || !statbuf) {
        return -EINVAL;
    }
    
    if (!file->dentry || !file->dentry->inode) {
        return -EBADF;
    }
    
    struct kos_inode *inode = file->dentry->inode;
    
    pthread_rwlock_rdlock(&inode->i_lock);
    
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
    
    pthread_rwlock_unlock(&inode->i_lock);
    
    return 0;
}

/* Check if file is readable */
bool kos_file_readable(struct kos_file *file) {
    if (!file) return false;
    return (file->flags & KOS_O_RDONLY) || (file->flags & KOS_O_RDWR);
}

/* Check if file is writable */
bool kos_file_writable(struct kos_file *file) {
    if (!file) return false;
    return (file->flags & KOS_O_WRONLY) || (file->flags & KOS_O_RDWR);
}

/* Get file position */
off_t kos_file_position(struct kos_file *file) {
    if (!file) return -1;
    
    pthread_mutex_lock(&file->f_lock);
    off_t pos = file->position;
    pthread_mutex_unlock(&file->f_lock);
    
    return pos;
}

/* Check if file has pending locks */
bool kos_file_has_locks(struct kos_file *file) {
    if (!file) return false;
    
    pthread_mutex_lock(&file->f_lock);
    bool has_locks = (file->locks != NULL);
    pthread_mutex_unlock(&file->f_lock);
    
    return has_locks;
}