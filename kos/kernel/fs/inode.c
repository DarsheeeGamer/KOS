#include "fs.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>

/* Global inode counter */
static uint64_t kos_next_ino = 1;
static pthread_mutex_t kos_ino_lock = PTHREAD_MUTEX_INITIALIZER;

/* Inode hash table functions */
static void kos_inode_hash_add(struct kos_inode *inode) {
    unsigned int hash = (unsigned int)(inode->ino % KOS_INODE_HASH_SIZE);
    
    pthread_rwlock_wrlock(&kos_inode_hash_lock);
    
    inode->i_hash_next = kos_inode_hashtbl[hash];
    inode->i_hash_prev = NULL;
    
    if (kos_inode_hashtbl[hash]) {
        kos_inode_hashtbl[hash]->i_hash_prev = inode;
    }
    
    kos_inode_hashtbl[hash] = inode;
    
    pthread_rwlock_unlock(&kos_inode_hash_lock);
}

static void kos_inode_hash_remove(struct kos_inode *inode) {
    unsigned int hash = (unsigned int)(inode->ino % KOS_INODE_HASH_SIZE);
    
    pthread_rwlock_wrlock(&kos_inode_hash_lock);
    
    if (inode->i_hash_prev) {
        inode->i_hash_prev->i_hash_next = inode->i_hash_next;
    } else {
        kos_inode_hashtbl[hash] = inode->i_hash_next;
    }
    
    if (inode->i_hash_next) {
        inode->i_hash_next->i_hash_prev = inode->i_hash_prev;
    }
    
    inode->i_hash_next = NULL;
    inode->i_hash_prev = NULL;
    
    pthread_rwlock_unlock(&kos_inode_hash_lock);
}

static struct kos_inode *kos_inode_hash_lookup(struct kos_super_block *sb, uint64_t ino) {
    unsigned int hash = (unsigned int)(ino % KOS_INODE_HASH_SIZE);
    struct kos_inode *inode = NULL;
    
    pthread_rwlock_rdlock(&kos_inode_hash_lock);
    
    struct kos_inode *current = kos_inode_hashtbl[hash];
    while (current) {
        if (current->ino == ino && current->i_sb == sb) {
            inode = current;
            break;
        }
        current = current->i_hash_next;
    }
    
    pthread_rwlock_unlock(&kos_inode_hash_lock);
    return inode;
}

/* Allocate a new inode number */
static uint64_t kos_get_next_ino(void) {
    pthread_mutex_lock(&kos_ino_lock);
    uint64_t ino = kos_next_ino++;
    pthread_mutex_unlock(&kos_ino_lock);
    return ino;
}

/* Initialize inode structure */
void kos_inode_init_once(struct kos_inode *inode) {
    if (!inode) return;
    
    memset(inode, 0, sizeof(struct kos_inode));
    pthread_rwlock_init(&inode->i_lock, NULL);
    inode->ref_count = 1;
    inode->nlink = 1;
    inode->blksize = 4096;
    
    /* Set default times */
    time_t now = time(NULL);
    inode->atime = now;
    inode->mtime = now;
    inode->ctime = now;
}

/* Allocate a new inode */
struct kos_inode *kos_alloc_inode(struct kos_super_block *sb) {
    if (!sb) {
        return NULL;
    }
    
    struct kos_inode *inode = NULL;
    
    /* Use super block's allocator if available */
    if (sb->s_op && sb->s_op->alloc_inode) {
        inode = sb->s_op->alloc_inode(sb);
    } else {
        /* Default allocation */
        inode = calloc(1, sizeof(struct kos_inode));
        if (inode) {
            kos_inode_init_once(inode);
        }
    }
    
    if (!inode) {
        return NULL;
    }
    
    /* Set basic properties */
    inode->ino = kos_get_next_ino();
    inode->i_sb = sb;
    
    /* Update super block statistics */
    pthread_rwlock_wrlock(&sb->s_lock);
    if (sb->free_inodes > 0) {
        sb->free_inodes--;
    }
    pthread_rwlock_unlock(&sb->s_lock);
    
    /* Add to hash table */
    kos_inode_hash_add(inode);
    
    return inode;
}

/* Free an inode */
void kos_free_inode(struct kos_inode *inode) {
    if (!inode) return;
    
    /* Remove from hash table */
    kos_inode_hash_remove(inode);
    
    /* Update super block statistics */
    if (inode->i_sb) {
        pthread_rwlock_wrlock(&inode->i_sb->s_lock);
        inode->i_sb->free_inodes++;
        pthread_rwlock_unlock(&inode->i_sb->s_lock);
    }
    
    /* Free extended attributes */
    struct kos_xattr *xattr = inode->xattrs;
    while (xattr) {
        struct kos_xattr *next = xattr->next;
        free(xattr->value);
        free(xattr);
        xattr = next;
    }
    
    /* Free ACLs */
    kos_free_acl(inode->acl_access);
    kos_free_acl(inode->acl_default);
    
    /* Free file locks */
    struct kos_file_lock *lock = inode->locks;
    while (lock) {
        struct kos_file_lock *next = lock->next;
        pthread_mutex_destroy(&lock->mutex);
        pthread_cond_destroy(&lock->cond);
        free(lock);
        lock = next;
    }
    
    /* Use super block's destroyer if available */
    if (inode->i_sb && inode->i_sb->s_op && inode->i_sb->s_op->destroy_inode) {
        inode->i_sb->s_op->destroy_inode(inode);
    } else {
        /* Default deallocation */
        pthread_rwlock_destroy(&inode->i_lock);
        free(inode->private_data);
        free(inode);
    }
}

/* Get inode by inode number */
struct kos_inode *kos_iget(struct kos_super_block *sb, uint64_t ino) {
    if (!sb) {
        return NULL;
    }
    
    /* First check hash table */
    struct kos_inode *inode = kos_inode_hash_lookup(sb, ino);
    if (inode) {
        /* Increment reference count */
        pthread_rwlock_wrlock(&inode->i_lock);
        inode->ref_count++;
        pthread_rwlock_unlock(&inode->i_lock);
        return inode;
    }
    
    /* Allocate new inode */
    inode = kos_alloc_inode(sb);
    if (!inode) {
        return NULL;
    }
    
    /* Set inode number */
    inode->ino = ino;
    
    /* Read inode from storage if super block has read operation */
    if (sb->s_op && sb->s_op->write_inode) {
        /* This would typically read from disk, but we'll set defaults */
        inode->mode = KOS_S_IFREG | 0644;
        inode->uid = getuid();
        inode->gid = getgid();
        inode->size = 0;
    }
    
    return inode;
}

/* Put inode (decrement reference count) */
void kos_iput(struct kos_inode *inode) {
    if (!inode) return;
    
    pthread_rwlock_wrlock(&inode->i_lock);
    inode->ref_count--;
    
    if (inode->ref_count <= 0) {
        pthread_rwlock_unlock(&inode->i_lock);
        
        /* Call super block's drop_inode if available */
        if (inode->i_sb && inode->i_sb->s_op && inode->i_sb->s_op->drop_inode) {
            inode->i_sb->s_op->drop_inode(inode);
        }
        
        /* If no links, delete the inode */
        if (inode->nlink == 0) {
            if (inode->i_sb && inode->i_sb->s_op && inode->i_sb->s_op->delete_inode) {
                inode->i_sb->s_op->delete_inode(inode);
            }
        }
        
        kos_free_inode(inode);
    } else {
        pthread_rwlock_unlock(&inode->i_lock);
    }
}

/* Check inode permissions */
int kos_inode_permission(struct kos_inode *inode, int mask) {
    if (!inode) {
        return -EINVAL;
    }
    
    /* Use inode's permission check if available */
    if (inode->i_op && inode->i_op->permission) {
        return inode->i_op->permission(inode, mask);
    }
    
    /* Use ACL permission check if ACLs are present */
    if (inode->acl_access) {
        return kos_acl_permission_check(inode, mask);
    }
    
    /* Default permission check */
    return kos_generic_permission(inode, mask);
}

/* Generic permission check */
int kos_generic_permission(struct kos_inode *inode, int mask) {
    if (!inode) {
        return -EINVAL;
    }
    
    uid_t uid = getuid();
    gid_t gid = getgid();
    mode_t mode = inode->mode;
    
    /* Root can do anything */
    if (uid == 0) {
        return 0;
    }
    
    /* Check owner permissions */
    if (uid == inode->uid) {
        if ((mask & MAY_READ) && !(mode & KOS_S_IRUSR)) return -EACCES;
        if ((mask & MAY_WRITE) && !(mode & KOS_S_IWUSR)) return -EACCES;
        if ((mask & MAY_EXEC) && !(mode & KOS_S_IXUSR)) return -EACCES;
        return 0;
    }
    
    /* Check group permissions */
    if (gid == inode->gid) {
        if ((mask & MAY_READ) && !(mode & KOS_S_IRGRP)) return -EACCES;
        if ((mask & MAY_WRITE) && !(mode & KOS_S_IWGRP)) return -EACCES;
        if ((mask & MAY_EXEC) && !(mode & KOS_S_IXGRP)) return -EACCES;
        return 0;
    }
    
    /* Check other permissions */
    if ((mask & MAY_READ) && !(mode & KOS_S_IROTH)) return -EACCES;
    if ((mask & MAY_WRITE) && !(mode & KOS_S_IWOTH)) return -EACCES;
    if ((mask & MAY_EXEC) && !(mode & KOS_S_IXOTH)) return -EACCES;
    
    return 0;
}

/* Update inode times */
void kos_update_time(struct kos_inode *inode, int flags) {
    if (!inode) return;
    
    time_t now = time(NULL);
    
    pthread_rwlock_wrlock(&inode->i_lock);
    
    if (flags & S_ATIME) {
        inode->atime = now;
    }
    if (flags & S_MTIME) {
        inode->mtime = now;
    }
    if (flags & S_CTIME) {
        inode->ctime = now;
    }
    
    pthread_rwlock_unlock(&inode->i_lock);
    
    /* Mark inode dirty for writeback */
    if (inode->i_sb && inode->i_sb->s_op && inode->i_sb->s_op->write_inode) {
        inode->i_sb->s_op->write_inode(inode, 0);
    }
}

/* Notify attribute change */
int kos_notify_change(struct kos_dentry *dentry, struct iattr *attr) {
    if (!dentry || !dentry->inode || !attr) {
        return -EINVAL;
    }
    
    struct kos_inode *inode = dentry->inode;
    
    /* Check permissions for attribute changes */
    uid_t uid = getuid();
    
    /* Only owner or root can change attributes */
    if (uid != 0 && uid != inode->uid) {
        return -EPERM;
    }
    
    pthread_rwlock_wrlock(&inode->i_lock);
    
    /* Update attributes */
    if (attr->ia_valid & ATTR_MODE) {
        inode->mode = (inode->mode & KOS_S_IFMT) | (attr->ia_mode & ~KOS_S_IFMT);
    }
    if (attr->ia_valid & ATTR_UID) {
        /* Only root can change ownership */
        if (uid == 0) {
            inode->uid = attr->ia_uid;
        } else {
            pthread_rwlock_unlock(&inode->i_lock);
            return -EPERM;
        }
    }
    if (attr->ia_valid & ATTR_GID) {
        /* Only root or owner can change group */
        if (uid == 0 || uid == inode->uid) {
            inode->gid = attr->ia_gid;
        } else {
            pthread_rwlock_unlock(&inode->i_lock);
            return -EPERM;
        }
    }
    if (attr->ia_valid & ATTR_SIZE) {
        inode->size = attr->ia_size;
        /* Update block count */
        inode->blocks = (inode->size + inode->blksize - 1) / inode->blksize;
    }
    if (attr->ia_valid & ATTR_ATIME) {
        inode->atime = attr->ia_atime.tv_sec;
    }
    if (attr->ia_valid & ATTR_MTIME) {
        inode->mtime = attr->ia_mtime.tv_sec;
    }
    if (attr->ia_valid & ATTR_CTIME) {
        inode->ctime = attr->ia_ctime.tv_sec;
    }
    
    pthread_rwlock_unlock(&inode->i_lock);
    
    /* Use inode's setattr if available */
    if (inode->i_op && inode->i_op->setattr) {
        return inode->i_op->setattr(dentry, attr);
    }
    
    /* Mark inode dirty */
    if (inode->i_sb && inode->i_sb->s_op && inode->i_sb->s_op->write_inode) {
        inode->i_sb->s_op->write_inode(inode, 0);
    }
    
    return 0;
}

/* Truncate inode to specified size */
int kos_inode_truncate(struct kos_inode *inode, off_t size) {
    if (!inode) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&inode->i_lock);
    
    off_t old_size = inode->size;
    inode->size = size;
    
    /* Update block count */
    inode->blocks = (size + inode->blksize - 1) / inode->blksize;
    
    /* Update times */
    time_t now = time(NULL);
    inode->mtime = now;
    inode->ctime = now;
    
    pthread_rwlock_unlock(&inode->i_lock);
    
    /* If shrinking, we might need to free blocks */
    if (size < old_size && inode->i_op && inode->i_op->setattr) {
        struct iattr attr;
        memset(&attr, 0, sizeof(attr));
        attr.ia_valid = ATTR_SIZE;
        attr.ia_size = size;
        return inode->i_op->setattr(NULL, &attr); /* Note: dentry can be NULL for truncate */
    }
    
    return 0;
}

/* Get inode statistics */
int kos_inode_getattr(struct kos_inode *inode, struct kstat *stat) {
    if (!inode || !stat) {
        return -EINVAL;
    }
    
    pthread_rwlock_rdlock(&inode->i_lock);
    
    memset(stat, 0, sizeof(struct kstat));
    stat->ino = inode->ino;
    stat->mode = inode->mode;
    stat->nlink = inode->nlink;
    stat->uid = inode->uid;
    stat->gid = inode->gid;
    stat->rdev = inode->rdev;
    stat->size = inode->size;
    stat->atime.tv_sec = inode->atime;
    stat->mtime.tv_sec = inode->mtime;
    stat->ctime.tv_sec = inode->ctime;
    stat->blksize = inode->blksize;
    stat->blocks = inode->blocks;
    
    pthread_rwlock_unlock(&inode->i_lock);
    
    return 0;
}

/* Create hard link */
int kos_inode_link(struct kos_inode *inode) {
    if (!inode) {
        return -EINVAL;
    }
    
    /* Can't link directories */
    if ((inode->mode & KOS_S_IFMT) == KOS_S_IFDIR) {
        return -EPERM;
    }
    
    pthread_rwlock_wrlock(&inode->i_lock);
    inode->nlink++;
    inode->ctime = time(NULL);
    pthread_rwlock_unlock(&inode->i_lock);
    
    return 0;
}

/* Remove hard link */
int kos_inode_unlink(struct kos_inode *inode) {
    if (!inode) {
        return -EINVAL;
    }
    
    pthread_rwlock_wrlock(&inode->i_lock);
    
    if (inode->nlink > 0) {
        inode->nlink--;
        inode->ctime = time(NULL);
    }
    
    int nlink = inode->nlink;
    pthread_rwlock_unlock(&inode->i_lock);
    
    /* If no more links, the inode should be deleted when last reference is dropped */
    return nlink;
}

/* Check if inode is a directory */
bool kos_inode_is_dir(struct kos_inode *inode) {
    if (!inode) {
        return false;
    }
    
    return (inode->mode & KOS_S_IFMT) == KOS_S_IFDIR;
}

/* Check if inode is a regular file */
bool kos_inode_is_reg(struct kos_inode *inode) {
    if (!inode) {
        return false;
    }
    
    return (inode->mode & KOS_S_IFMT) == KOS_S_IFREG;
}

/* Check if inode is a symbolic link */
bool kos_inode_is_lnk(struct kos_inode *inode) {
    if (!inode) {
        return false;
    }
    
    return (inode->mode & KOS_S_IFMT) == KOS_S_IFLNK;
}