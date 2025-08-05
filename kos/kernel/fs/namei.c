#include "fs.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <limits.h>

/* Maximum symlink recursion depth */
#define KOS_MAX_SYMLINK_DEPTH 40

/* Path lookup flags */
#define KOS_LOOKUP_FOLLOW    0x0001
#define KOS_LOOKUP_DIRECTORY 0x0002
#define KOS_LOOKUP_CREATE    0x0004
#define KOS_LOOKUP_EXCL      0x0008

/* Path component structure */
struct kos_nameidata {
    char *path;
    struct kos_dentry *dentry;
    struct kos_dentry *root;
    struct kos_mount *mnt;
    int flags;
    int symlink_depth;
    uid_t uid;
    gid_t gid;
};

/* Initialize nameidata structure */
static void kos_nameidata_init(struct kos_nameidata *nd, const char *path, int flags, struct kos_dentry *base) {
    memset(nd, 0, sizeof(struct kos_nameidata));
    nd->path = strdup(path);
    nd->flags = flags;
    nd->symlink_depth = 0;
    nd->uid = getuid();
    nd->gid = getgid();
    
    /* Set root directory */
    if (kos_root_mount && kos_root_mount->root) {
        nd->root = kos_dget(kos_root_mount->root);
    }
    
    /* Set starting point */
    if (base) {
        nd->dentry = kos_dget(base);
    } else if (path[0] == '/') {
        /* Absolute path - start from root */
        nd->dentry = nd->root ? kos_dget(nd->root) : NULL;
    } else {
        /* Relative path - start from current directory */
        /* For now, use root as current directory */
        nd->dentry = nd->root ? kos_dget(nd->root) : NULL;
    }
}

/* Cleanup nameidata structure */
static void kos_nameidata_cleanup(struct kos_nameidata *nd) {
    if (nd->path) {
        free(nd->path);
        nd->path = NULL;
    }
    if (nd->dentry) {
        kos_dput(nd->dentry);
        nd->dentry = NULL;
    }
    if (nd->root) {
        kos_dput(nd->root);
        nd->root = NULL;
    }
}

/* Get next path component */
static char *kos_get_next_component(char **path, char *component, size_t max_len) {
    char *start, *end;
    size_t len;
    
    if (!path || !*path || !component) {
        return NULL;
    }
    
    /* Skip leading slashes */
    while (**path == '/') {
        (*path)++;
    }
    
    /* Check for end of path */
    if (**path == '\0') {
        return NULL;
    }
    
    start = *path;
    
    /* Find end of component */
    end = strchr(start, '/');
    if (!end) {
        end = start + strlen(start);
    }
    
    len = end - start;
    if (len >= max_len) {
        return NULL; /* Component too long */
    }
    
    /* Copy component */
    strncpy(component, start, len);
    component[len] = '\0';
    
    /* Update path pointer */
    *path = end;
    
    return component;
}

/* Handle ".." (parent directory) */
static int kos_handle_dotdot(struct kos_nameidata *nd) {
    if (!nd->dentry || !nd->dentry->parent) {
        /* Already at root or no parent */
        return 0;
    }
    
    /* Don't go above root */
    if (nd->dentry == nd->root) {
        return 0;
    }
    
    struct kos_dentry *parent = kos_dget(nd->dentry->parent);
    kos_dput(nd->dentry);
    nd->dentry = parent;
    
    return 0;
}

/* Handle symbolic links */
static int kos_handle_symlink(struct kos_nameidata *nd) {
    if (!nd->dentry || !nd->dentry->inode) {
        return -ENOENT;
    }
    
    struct kos_inode *inode = nd->dentry->inode;
    
    /* Check if it's a symlink */
    if ((inode->mode & KOS_S_IFMT) != KOS_S_IFLNK) {
        return 0; /* Not a symlink */
    }
    
    /* Check recursion depth */
    if (nd->symlink_depth >= KOS_MAX_SYMLINK_DEPTH) {
        return -ELOOP;
    }
    
    nd->symlink_depth++;
    
    /* Read symlink target */
    char *target = malloc(PATH_MAX);
    if (!target) {
        return -ENOMEM;
    }
    
    ssize_t len = 0;
    if (inode->i_op && inode->i_op->readlink) {
        len = inode->i_op->readlink(nd->dentry, target, PATH_MAX - 1);
    } else {
        /* Default symlink reading - would read from inode data */
        strncpy(target, "/", PATH_MAX - 1);
        len = 1;
    }
    
    if (len < 0) {
        free(target);
        return len;
    }
    
    target[len] = '\0';
    
    /* Handle absolute vs relative symlinks */
    struct kos_dentry *base;
    if (target[0] == '/') {
        /* Absolute symlink - start from root */
        base = nd->root;
    } else {
        /* Relative symlink - start from parent directory */
        base = nd->dentry->parent;
    }
    
    /* Follow the symlink */
    struct kos_dentry *result = kos_path_lookup(target, nd->flags | KOS_LOOKUP_FOLLOW, base);
    
    free(target);
    
    if (!result) {
        return -ENOENT;
    }
    
    /* Replace current dentry with symlink target */
    kos_dput(nd->dentry);
    nd->dentry = result;
    
    return 0;
}

/* Perform single component lookup */
static struct kos_dentry *kos_lookup_component(struct kos_dentry *parent, const char *name) {
    if (!parent || !parent->inode || !name) {
        return NULL;
    }
    
    /* Handle special components */
    if (strcmp(name, ".") == 0) {
        return kos_dget(parent);
    }
    
    if (strcmp(name, "..") == 0) {
        if (parent->parent) {
            return kos_dget(parent->parent);
        } else {
            return kos_dget(parent); /* Root's parent is itself */
        }
    }
    
    /* Check if parent is a directory */
    if ((parent->inode->mode & KOS_S_IFMT) != KOS_S_IFDIR) {
        return NULL;
    }
    
    /* Check execute permission on parent directory */
    if (kos_inode_permission(parent->inode, MAY_EXEC) < 0) {
        return NULL;
    }
    
    /* Check dcache first */
    struct kos_dentry *dentry = kos_dcache_lookup(parent, name);
    if (dentry) {
        return dentry;
    }
    
    /* Not in cache - call filesystem lookup */
    if (!parent->inode->i_op || !parent->inode->i_op->lookup) {
        return NULL;
    }
    
    /* Create new dentry for lookup */
    dentry = kos_alloc_dentry(name);
    if (!dentry) {
        return NULL;
    }
    
    dentry->parent = kos_dget(parent);
    
    /* Call filesystem lookup */
    struct kos_dentry *result = parent->inode->i_op->lookup(parent->inode, dentry);
    
    if (!result) {
        /* Not found */
        kos_free_dentry(dentry);
        return NULL;
    }
    
    /* Add successful lookup to dcache */
    if (result == dentry) {
        kos_dcache_add(dentry);
    } else {
        /* Filesystem returned different dentry */
        kos_free_dentry(dentry);
        kos_dcache_add(result);
    }
    
    return result;
}

/* Walk path components */
static int kos_path_walk_components(struct kos_nameidata *nd) {
    char *path = nd->path;
    char component[KOS_MAX_FILENAME + 1];
    
    /* Skip leading slash for absolute paths */
    if (*path == '/') {
        path++;
    }
    
    while (kos_get_next_component(&path, component, sizeof(component))) {
        struct kos_dentry *next;
        
        /* Handle special cases */
        if (strcmp(component, "..") == 0) {
            int result = kos_handle_dotdot(nd);
            if (result < 0) {
                return result;
            }
            continue;
        }
        
        if (strcmp(component, ".") == 0) {
            continue; /* Stay in current directory */
        }
        
        /* Lookup component */
        next = kos_lookup_component(nd->dentry, component);
        if (!next) {
            /* Component not found */
            if (nd->flags & KOS_LOOKUP_CREATE) {
                /* Last component can be created */
                if (*path == '\0') {
                    return -ENOENT; /* Signal that last component should be created */
                }
            }
            return -ENOENT;
        }
        
        /* Move to next component */
        kos_dput(nd->dentry);
        nd->dentry = next;
        
        /* Handle symbolic links if not at end or FOLLOW is set */
        if (kos_inode_is_lnk(nd->dentry->inode)) {
            if (*path != '\0' || (nd->flags & KOS_LOOKUP_FOLLOW)) {
                int result = kos_handle_symlink(nd);
                if (result < 0) {
                    return result;
                }
            }
        }
        
        /* Handle mount points */
        struct kos_mount *mount = kos_lookup_mount(nd->path);
        if (mount && mount->root && nd->dentry == mount->sb->root) {
            /* Crossed into mounted filesystem */
            struct kos_dentry *mounted_root = kos_dget(mount->root);
            kos_dput(nd->dentry);
            nd->dentry = mounted_root;
            nd->mnt = mount;
        }
    }
    
    /* Check final result */
    if (nd->flags & KOS_LOOKUP_DIRECTORY) {
        if (!nd->dentry->inode || !kos_inode_is_dir(nd->dentry->inode)) {
            return -ENOTDIR;
        }
    }
    
    return 0;
}

/* Main path lookup function */
struct kos_dentry *kos_path_lookup(const char *path, int flags, struct kos_dentry *base) {
    if (!path) {
        return NULL;
    }
    
    /* Handle empty path */
    if (*path == '\0') {
        if (base) {
            return kos_dget(base);
        }
        return NULL;
    }
    
    struct kos_nameidata nd;
    kos_nameidata_init(&nd, path, flags, base);
    
    if (!nd.dentry) {
        kos_nameidata_cleanup(&nd);
        return NULL;
    }
    
    /* Walk the path */
    int result = kos_path_walk_components(&nd);
    
    struct kos_dentry *dentry = NULL;
    if (result == 0) {
        dentry = kos_dget(nd.dentry);
    }
    
    kos_nameidata_cleanup(&nd);
    return dentry;
}

/* Path walk with more control */
int kos_path_walk(const char *name, struct kos_dentry *base, struct kos_dentry **result) {
    if (!name || !result) {
        return -EINVAL;
    }
    
    *result = kos_path_lookup(name, 0, base);
    return *result ? 0 : -ENOENT;
}

/* Resolve parent directory and final component */
int kos_path_parent(const char *path, struct kos_dentry **parent, char **name) {
    if (!path || !parent || !name) {
        return -EINVAL;
    }
    
    *parent = NULL;
    *name = NULL;
    
    /* Make a copy of the path */
    char *path_copy = strdup(path);
    if (!path_copy) {
        return -ENOMEM;
    }
    
    /* Find the last slash */
    char *last_slash = strrchr(path_copy, '/');
    if (!last_slash) {
        /* No slash - relative path in current directory */
        *name = strdup(path);
        *parent = kos_path_lookup(".", 0, NULL);
        free(path_copy);
        return *parent ? 0 : -ENOENT;
    }
    
    /* Split path into directory and filename */
    *last_slash = '\0';
    char *filename = last_slash + 1;
    
    /* Handle root directory */
    if (path_copy[0] == '\0') {
        strcpy(path_copy, "/");
    }
    
    /* Lookup parent directory */
    *parent = kos_path_lookup(path_copy, KOS_LOOKUP_DIRECTORY, NULL);
    if (!*parent) {
        free(path_copy);
        return -ENOENT;
    }
    
    /* Copy filename */
    *name = strdup(filename);
    if (!*name) {
        kos_dput(*parent);
        *parent = NULL;
        free(path_copy);
        return -ENOMEM;
    }
    
    free(path_copy);
    return 0;
}

/* Create path with intermediate directories */
int kos_path_create(const char *path, mode_t mode, struct kos_dentry **result) {
    if (!path || !result) {
        return -EINVAL;
    }
    
    *result = NULL;
    
    struct kos_dentry *parent;
    char *name;
    
    int ret = kos_path_parent(path, &parent, &name);
    if (ret < 0) {
        return ret;
    }
    
    /* Check if file already exists */
    struct kos_dentry *existing = kos_lookup_component(parent, name);
    if (existing) {
        kos_dput(parent);
        free(name);
        kos_dput(existing);
        return -EEXIST;
    }
    
    /* Create new dentry */
    struct kos_dentry *dentry = kos_alloc_dentry(name);
    if (!dentry) {
        kos_dput(parent);
        free(name);
        return -ENOMEM;
    }
    
    dentry->parent = parent; /* Transfer reference */
    
    /* Create inode */
    if (parent->inode->i_op && parent->inode->i_op->create) {
        ret = parent->inode->i_op->create(parent->inode, dentry, mode);
        if (ret < 0) {
            kos_free_dentry(dentry);
            free(name);
            return ret;
        }
    } else {
        /* Default creation */
        struct kos_inode *inode = kos_alloc_inode(parent->inode->i_sb);
        if (!inode) {
            kos_free_dentry(dentry);
            free(name);
            return -ENOMEM;
        }
        
        inode->mode = mode;
        inode->uid = getuid();
        inode->gid = getgid();
        
        kos_d_instantiate(dentry, inode);
    }
    
    /* Add to dcache */
    kos_dcache_add(dentry);
    
    *result = dentry;
    free(name);
    return 0;
}

/* Remove path */
int kos_path_remove(const char *path) {
    if (!path) {
        return -EINVAL;
    }
    
    struct kos_dentry *parent;
    char *name;
    
    int ret = kos_path_parent(path, &parent, &name);
    if (ret < 0) {
        return ret;
    }
    
    /* Lookup the file to remove */
    struct kos_dentry *dentry = kos_lookup_component(parent, name);
    if (!dentry) {
        kos_dput(parent);
        free(name);
        return -ENOENT;
    }
    
    /* Remove the file */
    if (kos_inode_is_dir(dentry->inode)) {
        if (parent->inode->i_op && parent->inode->i_op->rmdir) {
            ret = parent->inode->i_op->rmdir(parent->inode, dentry);
        } else {
            ret = -ENOSYS;
        }
    } else {
        if (parent->inode->i_op && parent->inode->i_op->unlink) {
            ret = parent->inode->i_op->unlink(parent->inode, dentry);
        } else {
            ret = -ENOSYS;
        }
    }
    
    if (ret == 0) {
        kos_dcache_remove(dentry);
    }
    
    kos_dput(dentry);
    kos_dput(parent);
    free(name);
    
    return ret;
}

/* Rename path */
int kos_path_rename(const char *oldpath, const char *newpath) {
    if (!oldpath || !newpath) {
        return -EINVAL;
    }
    
    struct kos_dentry *old_parent, *new_parent;
    char *old_name, *new_name;
    
    int ret = kos_path_parent(oldpath, &old_parent, &old_name);
    if (ret < 0) {
        return ret;
    }
    
    ret = kos_path_parent(newpath, &new_parent, &new_name);
    if (ret < 0) {
        kos_dput(old_parent);
        free(old_name);
        return ret;
    }
    
    /* Lookup old file */
    struct kos_dentry *old_dentry = kos_lookup_component(old_parent, old_name);
    if (!old_dentry) {
        kos_dput(old_parent);
        kos_dput(new_parent);
        free(old_name);
        free(new_name);
        return -ENOENT;
    }
    
    /* Create new dentry */
    struct kos_dentry *new_dentry = kos_alloc_dentry(new_name);
    if (!new_dentry) {
        kos_dput(old_dentry);
        kos_dput(old_parent);
        kos_dput(new_parent);
        free(old_name);
        free(new_name);
        return -ENOMEM;
    }
    
    new_dentry->parent = kos_dget(new_parent);
    
    /* Perform rename */
    if (old_parent->inode->i_op && old_parent->inode->i_op->rename) {
        ret = old_parent->inode->i_op->rename(old_parent->inode, old_dentry,
                                              new_parent->inode, new_dentry);
    } else {
        ret = -ENOSYS;
    }
    
    if (ret == 0) {
        /* Update dcache */
        kos_dcache_remove(old_dentry);
        kos_dcache_add(new_dentry);
    } else {
        kos_free_dentry(new_dentry);
    }
    
    kos_dput(old_dentry);
    kos_dput(old_parent);
    kos_dput(new_parent);
    free(old_name);
    free(new_name);
    
    return ret;
}

/* Check if path exists */
bool kos_path_exists(const char *path) {
    if (!path) {
        return false;
    }
    
    struct kos_dentry *dentry = kos_path_lookup(path, 0, NULL);
    if (dentry) {
        kos_dput(dentry);
        return true;
    }
    
    return false;
}

/* Get absolute path from dentry */
char *kos_dentry_path(struct kos_dentry *dentry, char *buffer, size_t size) {
    if (!dentry || !buffer || size == 0) {
        return NULL;
    }
    
    char *end = buffer + size - 1;
    char *p = end;
    *p = '\0';
    
    struct kos_dentry *current = dentry;
    
    while (current && current->parent != current) {
        size_t name_len = strlen(current->name);
        
        if (p - buffer < name_len + 1) {
            return NULL; /* Buffer too small */
        }
        
        p -= name_len;
        memcpy(p, current->name, name_len);
        *(--p) = '/';
        
        current = current->parent;
    }
    
    if (p == end) {
        /* Root directory */
        if (size < 2) return NULL;
        buffer[0] = '/';
        buffer[1] = '\0';
        return buffer;
    }
    
    /* Move result to beginning of buffer */
    size_t len = end - p;
    memmove(buffer, p, len + 1);
    
    return buffer;
}