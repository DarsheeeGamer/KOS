#include "fs.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>

/* Directory entry cache configuration */
#define KOS_DCACHE_MAX_ENTRIES 10000
#define KOS_DCACHE_TIMEOUT 300  /* 5 minutes */

/* Global dcache statistics */
struct kos_dcache_stats {
    unsigned long lookups;
    unsigned long hits;
    unsigned long misses;
    unsigned long allocations;
    unsigned long deallocations;
    unsigned long active_entries;
};

static struct kos_dcache_stats kos_dcache_stats = {0};
static pthread_mutex_t kos_dcache_stats_lock = PTHREAD_MUTEX_INITIALIZER;

/* LRU list for cache eviction */
struct kos_dcache_lru {
    struct kos_dentry *head;
    struct kos_dentry *tail;
    pthread_mutex_t lock;
    unsigned long count;
};

static struct kos_dcache_lru kos_dcache_lru = {NULL, NULL, PTHREAD_MUTEX_INITIALIZER, 0};

/* Hash function for dentry names */
static unsigned int kos_dentry_hash_fn(struct kos_dentry *parent, const char *name) {
    unsigned int hash = 0;
    unsigned long parent_hash = parent ? (unsigned long)parent : 0;
    
    /* Combine parent pointer and name */
    hash = (unsigned int)(parent_hash % 1000);
    
    while (*name) {
        hash = hash * 31 + *name++;
    }
    
    return hash % KOS_DENTRY_HASH_SIZE;
}

/* Add dentry to LRU list */
static void kos_dcache_lru_add(struct kos_dentry *dentry) {
    pthread_mutex_lock(&kos_dcache_lru.lock);
    
    /* Remove from current position if already in list */
    if (dentry->d_hash_next || dentry->d_hash_prev || kos_dcache_lru.head == dentry) {
        if (dentry->d_hash_prev) {
            dentry->d_hash_prev->d_hash_next = dentry->d_hash_next;
        } else {
            kos_dcache_lru.head = dentry->d_hash_next;
        }
        
        if (dentry->d_hash_next) {
            dentry->d_hash_next->d_hash_prev = dentry->d_hash_prev;
        } else {
            kos_dcache_lru.tail = dentry->d_hash_prev;
        }
    } else {
        kos_dcache_lru.count++;
    }
    
    /* Add to head of LRU list */
    dentry->d_hash_next = kos_dcache_lru.head;
    dentry->d_hash_prev = NULL;
    
    if (kos_dcache_lru.head) {
        kos_dcache_lru.head->d_hash_prev = dentry;
    } else {
        kos_dcache_lru.tail = dentry;
    }
    
    kos_dcache_lru.head = dentry;
    
    pthread_mutex_unlock(&kos_dcache_lru.lock);
}

/* Remove dentry from LRU list */
static void kos_dcache_lru_remove(struct kos_dentry *dentry) {
    pthread_mutex_lock(&kos_dcache_lru.lock);
    
    if (dentry->d_hash_prev) {
        dentry->d_hash_prev->d_hash_next = dentry->d_hash_next;
    } else {
        kos_dcache_lru.head = dentry->d_hash_next;
    }
    
    if (dentry->d_hash_next) {
        dentry->d_hash_next->d_hash_prev = dentry->d_hash_prev;
    } else {
        kos_dcache_lru.tail = dentry->d_hash_prev;
    }
    
    dentry->d_hash_next = NULL;
    dentry->d_hash_prev = NULL;
    
    if (kos_dcache_lru.count > 0) {
        kos_dcache_lru.count--;
    }
    
    pthread_mutex_unlock(&kos_dcache_lru.lock);
}

/* Get LRU victim for eviction */
static struct kos_dentry *kos_dcache_lru_victim(void) {
    struct kos_dentry *victim = NULL;
    
    pthread_mutex_lock(&kos_dcache_lru.lock);
    
    /* Find a dentry with ref_count == 0 from tail */
    struct kos_dentry *current = kos_dcache_lru.tail;
    while (current) {
        pthread_mutex_lock(&current->d_lock);
        if (current->ref_count == 0) {
            victim = current;
            pthread_mutex_unlock(&current->d_lock);
            break;
        }
        pthread_mutex_unlock(&current->d_lock);
        current = current->d_hash_prev;
    }
    
    pthread_mutex_unlock(&kos_dcache_lru.lock);
    return victim;
}

/* Allocate a new dentry */
struct kos_dentry *kos_alloc_dentry(const char *name) {
    if (!name || strlen(name) > KOS_MAX_FILENAME) {
        return NULL;
    }
    
    struct kos_dentry *dentry = calloc(1, sizeof(struct kos_dentry));
    if (!dentry) {
        return NULL;
    }
    
    /* Initialize dentry */
    strncpy(dentry->name, name, KOS_MAX_FILENAME);
    dentry->name[KOS_MAX_FILENAME] = '\0';
    dentry->ref_count = 1;
    dentry->cache_time = time(NULL);
    
    pthread_mutex_init(&dentry->d_lock, NULL);
    
    /* Update statistics */
    pthread_mutex_lock(&kos_dcache_stats_lock);
    kos_dcache_stats.allocations++;
    kos_dcache_stats.active_entries++;
    pthread_mutex_unlock(&kos_dcache_stats_lock);
    
    return dentry;
}

/* Free a dentry */
void kos_free_dentry(struct kos_dentry *dentry) {
    if (!dentry) return;
    
    /* Remove from hash table and LRU list */
    kos_dcache_remove(dentry);
    
    /* Free resources */
    if (dentry->inode) {
        kos_iput(dentry->inode);
    }
    
    pthread_mutex_destroy(&dentry->d_lock);
    
    /* Update statistics */
    pthread_mutex_lock(&kos_dcache_stats_lock);
    kos_dcache_stats.deallocations++;
    if (kos_dcache_stats.active_entries > 0) {
        kos_dcache_stats.active_entries--;
    }
    pthread_mutex_unlock(&kos_dcache_stats_lock);
    
    free(dentry);
}

/* Get reference to dentry */
struct kos_dentry *kos_dget(struct kos_dentry *dentry) {
    if (!dentry) return NULL;
    
    pthread_mutex_lock(&dentry->d_lock);
    dentry->ref_count++;
    pthread_mutex_unlock(&dentry->d_lock);
    
    /* Move to head of LRU list */
    kos_dcache_lru_add(dentry);
    
    return dentry;
}

/* Put reference to dentry */
void kos_dput(struct kos_dentry *dentry) {
    if (!dentry) return;
    
    pthread_mutex_lock(&dentry->d_lock);
    dentry->ref_count--;
    int ref_count = dentry->ref_count;
    pthread_mutex_unlock(&dentry->d_lock);
    
    /* If no more references and not in use, free it */
    if (ref_count == 0) {
        /* Don't immediately free - let cache pruning handle it */
        /* This allows for quick re-access to recently used dentries */
    }
}

/* Instantiate dentry with inode */
void kos_d_instantiate(struct kos_dentry *dentry, struct kos_inode *inode) {
    if (!dentry) return;
    
    pthread_mutex_lock(&dentry->d_lock);
    
    if (dentry->inode) {
        kos_iput(dentry->inode);
    }
    
    dentry->inode = inode;
    
    if (inode) {
        /* Increment inode reference count */
        pthread_rwlock_wrlock(&inode->i_lock);
        inode->ref_count++;
        pthread_rwlock_unlock(&inode->i_lock);
    }
    
    pthread_mutex_unlock(&dentry->d_lock);
}

/* Initialize directory cache */
void kos_dcache_init(void) {
    /* Initialize hash table */
    memset(kos_dentry_hashtbl, 0, sizeof(kos_dentry_hashtbl));
    
    /* Initialize statistics */
    memset(&kos_dcache_stats, 0, sizeof(kos_dcache_stats));
    
    /* Initialize LRU list */
    kos_dcache_lru.head = NULL;
    kos_dcache_lru.tail = NULL;
    kos_dcache_lru.count = 0;
}

/* Cleanup directory cache */
void kos_dcache_cleanup(void) {
    /* Remove all entries from hash table */
    pthread_rwlock_wrlock(&kos_dentry_hash_lock);
    
    for (int i = 0; i < KOS_DENTRY_HASH_SIZE; i++) {
        struct kos_dentry *dentry = kos_dentry_hashtbl[i];
        while (dentry) {
            struct kos_dentry *next = dentry->d_hash_next;
            kos_free_dentry(dentry);
            dentry = next;
        }
        kos_dentry_hashtbl[i] = NULL;
    }
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
    
    /* Clear LRU list */
    pthread_mutex_lock(&kos_dcache_lru.lock);
    kos_dcache_lru.head = NULL;
    kos_dcache_lru.tail = NULL;
    kos_dcache_lru.count = 0;
    pthread_mutex_unlock(&kos_dcache_lru.lock);
}

/* Lookup dentry in cache */
struct kos_dentry *kos_dcache_lookup(struct kos_dentry *parent, const char *name) {
    if (!name) {
        return NULL;
    }
    
    unsigned int hash = kos_dentry_hash_fn(parent, name);
    struct kos_dentry *dentry = NULL;
    
    /* Update statistics */
    pthread_mutex_lock(&kos_dcache_stats_lock);
    kos_dcache_stats.lookups++;
    pthread_mutex_unlock(&kos_dcache_stats_lock);
    
    pthread_rwlock_rdlock(&kos_dentry_hash_lock);
    
    struct kos_dentry *current = kos_dentry_hashtbl[hash];
    while (current) {
        if (current->parent == parent && strcmp(current->name, name) == 0) {
            /* Check if cache entry is still valid */
            time_t now = time(NULL);
            if (now - current->cache_time < KOS_DCACHE_TIMEOUT) {
                dentry = kos_dget(current);
                
                /* Update statistics */
                pthread_mutex_lock(&kos_dcache_stats_lock);
                kos_dcache_stats.hits++;
                pthread_mutex_unlock(&kos_dcache_stats_lock);
                
                break;
            } else {
                /* Cache entry expired, remove it */
                pthread_rwlock_unlock(&kos_dentry_hash_lock);
                kos_dcache_remove(current);
                pthread_rwlock_rdlock(&kos_dentry_hash_lock);
                
                /* Restart search as hash table may have changed */
                current = kos_dentry_hashtbl[hash];
                continue;
            }
        }
        current = current->d_hash_next;
    }
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
    
    if (!dentry) {
        /* Update statistics */
        pthread_mutex_lock(&kos_dcache_stats_lock);
        kos_dcache_stats.misses++;
        pthread_mutex_unlock(&kos_dcache_stats_lock);
    }
    
    return dentry;
}

/* Add dentry to cache */
void kos_dcache_add(struct kos_dentry *dentry) {
    if (!dentry) return;
    
    unsigned int hash = kos_dentry_hash_fn(dentry->parent, dentry->name);
    
    /* Check if we need to evict entries */
    if (kos_dcache_lru.count >= KOS_DCACHE_MAX_ENTRIES) {
        struct kos_dentry *victim = kos_dcache_lru_victim();
        if (victim) {
            kos_free_dentry(victim);
        }
    }
    
    pthread_rwlock_wrlock(&kos_dentry_hash_lock);
    
    /* Add to hash table */
    dentry->d_hash_next = kos_dentry_hashtbl[hash];
    dentry->d_hash_prev = NULL;
    
    if (kos_dentry_hashtbl[hash]) {
        kos_dentry_hashtbl[hash]->d_hash_prev = dentry;
    }
    
    kos_dentry_hashtbl[hash] = dentry;
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
    
    /* Add to LRU list */
    kos_dcache_lru_add(dentry);
    
    /* Update cache time */
    dentry->cache_time = time(NULL);
}

/* Remove dentry from cache */
void kos_dcache_remove(struct kos_dentry *dentry) {
    if (!dentry) return;
    
    unsigned int hash = kos_dentry_hash_fn(dentry->parent, dentry->name);
    
    pthread_rwlock_wrlock(&kos_dentry_hash_lock);
    
    /* Remove from hash table */
    if (dentry->d_hash_prev) {
        dentry->d_hash_prev->d_hash_next = dentry->d_hash_next;
    } else {
        kos_dentry_hashtbl[hash] = dentry->d_hash_next;
    }
    
    if (dentry->d_hash_next) {
        dentry->d_hash_next->d_hash_prev = dentry->d_hash_prev;
    }
    
    dentry->d_hash_next = NULL;
    dentry->d_hash_prev = NULL;
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
    
    /* Remove from LRU list */
    kos_dcache_lru_remove(dentry);
}

/* Prune expired cache entries */
void kos_dcache_prune(void) {
    time_t now = time(NULL);
    struct kos_dentry **victims = NULL;
    int victim_count = 0;
    int victim_capacity = 100;
    
    /* Allocate temporary array for victims */
    victims = malloc(victim_capacity * sizeof(struct kos_dentry *));
    if (!victims) {
        return;
    }
    
    pthread_rwlock_rdlock(&kos_dentry_hash_lock);
    
    /* Find expired entries */
    for (int i = 0; i < KOS_DENTRY_HASH_SIZE; i++) {
        struct kos_dentry *dentry = kos_dentry_hashtbl[i];
        while (dentry) {
            pthread_mutex_lock(&dentry->d_lock);
            
            /* Check if expired and not in use */
            if (dentry->ref_count == 0 && (now - dentry->cache_time) >= KOS_DCACHE_TIMEOUT) {
                /* Add to victim list */
                if (victim_count >= victim_capacity) {
                    victim_capacity *= 2;
                    victims = realloc(victims, victim_capacity * sizeof(struct kos_dentry *));
                    if (!victims) {
                        pthread_mutex_unlock(&dentry->d_lock);
                        break;
                    }
                }
                victims[victim_count++] = dentry;
            }
            
            pthread_mutex_unlock(&dentry->d_lock);
            dentry = dentry->d_hash_next;
        }
    }
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
    
    /* Free victim entries */
    for (int i = 0; i < victim_count; i++) {
        kos_free_dentry(victims[i]);
    }
    
    free(victims);
}

/* Get cache statistics */
void kos_dcache_get_stats(struct kos_dcache_stats *stats) {
    if (!stats) return;
    
    pthread_mutex_lock(&kos_dcache_stats_lock);
    *stats = kos_dcache_stats;
    pthread_mutex_unlock(&kos_dcache_stats_lock);
}

/* Invalidate cache entry */
void kos_dcache_invalidate(struct kos_dentry *dentry) {
    if (!dentry) return;
    
    pthread_mutex_lock(&dentry->d_lock);
    dentry->cache_time = 0; /* Mark as expired */
    pthread_mutex_unlock(&dentry->d_lock);
}

/* Invalidate all cache entries for a directory */
void kos_dcache_invalidate_dir(struct kos_dentry *dir) {
    if (!dir) return;
    
    pthread_rwlock_rdlock(&kos_dentry_hash_lock);
    
    for (int i = 0; i < KOS_DENTRY_HASH_SIZE; i++) {
        struct kos_dentry *dentry = kos_dentry_hashtbl[i];
        while (dentry) {
            if (dentry->parent == dir) {
                kos_dcache_invalidate(dentry);
            }
            dentry = dentry->d_hash_next;
        }
    }
    
    pthread_rwlock_unlock(&kos_dentry_hash_lock);
}

/* Shrink cache to target size */
void kos_dcache_shrink(unsigned long target_count) {
    struct kos_dentry **victims = NULL;
    int victim_count = 0;
    int victim_capacity = 100;
    
    if (kos_dcache_lru.count <= target_count) {
        return;
    }
    
    victims = malloc(victim_capacity * sizeof(struct kos_dentry *));
    if (!victims) {
        return;
    }
    
    pthread_mutex_lock(&kos_dcache_lru.lock);
    
    /* Collect victims from tail of LRU list */
    struct kos_dentry *current = kos_dcache_lru.tail;
    while (current && kos_dcache_lru.count > target_count) {
        pthread_mutex_lock(&current->d_lock);
        
        if (current->ref_count == 0) {
            if (victim_count >= victim_capacity) {
                victim_capacity *= 2;
                victims = realloc(victims, victim_capacity * sizeof(struct kos_dentry *));
                if (!victims) {
                    pthread_mutex_unlock(&current->d_lock);
                    break;
                }
            }
            victims[victim_count++] = current;
        }
        
        pthread_mutex_unlock(&current->d_lock);
        current = current->d_hash_prev;
    }
    
    pthread_mutex_unlock(&kos_dcache_lru.lock);
    
    /* Free victim entries */
    for (int i = 0; i < victim_count; i++) {
        kos_free_dentry(victims[i]);
    }
    
    free(victims);
}