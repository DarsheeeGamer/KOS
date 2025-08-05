#define _GNU_SOURCE
#include "drivers.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

/* Block device private data */
typedef struct kos_block_device_data {
    void *storage;
    uint64_t total_blocks;
    uint32_t block_size;
    uint64_t total_size;
    pthread_mutex_t lock;
    pthread_rwlock_t rw_lock;
    
    /* Statistics */
    uint64_t read_count;
    uint64_t write_count;
    uint64_t read_bytes;
    uint64_t write_bytes;
    
    /* Cache (simple write-through) */
    struct {
        uint64_t block_num;
        void *data;
        bool valid;
        bool dirty;
    } cache[16]; /* Simple 16-block cache */
    
    int cache_size;
} kos_block_device_data_t;

/* Forward declarations */
static int block_open(kos_device_t *dev, int flags);
static int block_close(kos_device_t *dev);
static ssize_t block_read(kos_device_t *dev, void *buf, size_t count, off_t offset);
static ssize_t block_write(kos_device_t *dev, const void *buf, size_t count, off_t offset);
static int block_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg);
static int block_fsync(kos_device_t *dev);

static int default_read_block(kos_device_t *dev, uint64_t block, void *buf);
static int default_write_block(kos_device_t *dev, uint64_t block, const void *buf);
static int default_read_blocks(kos_device_t *dev, uint64_t start_block, uint32_t count, void *buf);
static int default_write_blocks(kos_device_t *dev, uint64_t start_block, uint32_t count, const void *buf);
static int default_get_geometry(kos_device_t *dev, uint64_t *sectors, uint32_t *sector_size);

/* Default block device file operations */
static kos_file_ops_t default_block_fops = {
    .open = block_open,
    .close = block_close,
    .read = block_read,
    .write = block_write,
    .ioctl = block_ioctl,
    .flush = NULL,
    .fsync = block_fsync,
    .mmap = NULL
};

/* Default block device operations */
static kos_block_ops_t default_block_ops = {
    .read_block = default_read_block,
    .write_block = default_write_block,
    .read_blocks = default_read_blocks,
    .write_blocks = default_write_blocks,
    .format = NULL,
    .get_geometry = default_get_geometry
};

/* Cache management */
static int block_cache_find(kos_block_device_data_t *data, uint64_t block_num) {
    for (int i = 0; i < data->cache_size; i++) {
        if (data->cache[i].valid && data->cache[i].block_num == block_num) {
            return i;
        }
    }
    return -1;
}

static int block_cache_get_free(kos_block_device_data_t *data) {
    for (int i = 0; i < data->cache_size; i++) {
        if (!data->cache[i].valid) {
            return i;
        }
    }
    /* Find least recently used (simple implementation) */
    return 0;
}

static int block_cache_flush(kos_device_t *dev, int cache_idx) {
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    
    if (cache_idx < 0 || cache_idx >= data->cache_size || !data->cache[cache_idx].valid) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (data->cache[cache_idx].dirty) {
        /* Write to storage */
        uint64_t offset = data->cache[cache_idx].block_num * data->block_size;
        memcpy((char *)data->storage + offset, data->cache[cache_idx].data, data->block_size);
        data->cache[cache_idx].dirty = false;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Block device open */
static int block_open(kos_device_t *dev, int flags) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    /* Check access permissions */
    if ((flags & KOS_DEV_FLAG_WRITEONLY) && (dev->flags & KOS_DEV_FLAG_READONLY)) {
        pthread_mutex_unlock(&data->lock);
        return KOS_ERR_NOT_SUPPORTED;
    }
    
    if ((flags & KOS_DEV_FLAG_READONLY) && (dev->flags & KOS_DEV_FLAG_WRITEONLY)) {
        pthread_mutex_unlock(&data->lock);
        return KOS_ERR_NOT_SUPPORTED;
    }
    
    pthread_mutex_unlock(&data->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Block device close */
static int block_close(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Flush all cached data */
    return block_fsync(dev);
}

/* Block device read */
static ssize_t block_read(kos_device_t *dev, void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    if (offset < 0 || offset >= data->total_size) {
        return 0; /* EOF */
    }
    
    if (offset + count > data->total_size) {
        count = data->total_size - offset;
    }
    
    pthread_rwlock_rdlock(&data->rw_lock);
    
    uint64_t start_block = offset / data->block_size;
    uint64_t end_block = (offset + count - 1) / data->block_size;
    size_t bytes_read = 0;
    
    for (uint64_t block = start_block; block <= end_block; block++) {
        size_t block_offset = (block == start_block) ? (offset % data->block_size) : 0;
        size_t block_count = data->block_size - block_offset;
        
        if (bytes_read + block_count > count) {
            block_count = count - bytes_read;
        }
        
        /* Check cache first */
        pthread_mutex_lock(&data->lock);
        int cache_idx = block_cache_find(data, block);
        
        if (cache_idx >= 0) {
            /* Cache hit */
            memcpy((char *)buf + bytes_read, 
                   (char *)data->cache[cache_idx].data + block_offset, 
                   block_count);
        } else {
            /* Cache miss - read from storage */
            void *block_buf = malloc(data->block_size);
            if (!block_buf) {
                pthread_mutex_unlock(&data->lock);
                pthread_rwlock_unlock(&data->rw_lock);
                return KOS_ERR_NO_MEMORY;
            }
            
            if (dev->block_ops && dev->block_ops->read_block) {
                int ret = dev->block_ops->read_block(dev, block, block_buf);
                if (ret != KOS_ERR_SUCCESS) {
                    free(block_buf);
                    pthread_mutex_unlock(&data->lock);
                    pthread_rwlock_unlock(&data->rw_lock);
                    return ret;
                }
            } else {
                /* Default read from storage */
                memcpy(block_buf, (char *)data->storage + block * data->block_size, data->block_size);
            }
            
            memcpy((char *)buf + bytes_read, (char *)block_buf + block_offset, block_count);
            
            /* Add to cache */
            int free_idx = block_cache_get_free(data);
            if (data->cache[free_idx].valid && data->cache[free_idx].dirty) {
                block_cache_flush(dev, free_idx);
            }
            
            if (data->cache[free_idx].data) {
                free(data->cache[free_idx].data);
            }
            
            data->cache[free_idx].block_num = block;
            data->cache[free_idx].data = block_buf;
            data->cache[free_idx].valid = true;
            data->cache[free_idx].dirty = false;
        }
        
        pthread_mutex_unlock(&data->lock);
        bytes_read += block_count;
    }
    
    /* Update statistics */
    data->read_count++;
    data->read_bytes += bytes_read;
    
    pthread_rwlock_unlock(&data->rw_lock);
    
    return bytes_read;
}

/* Block device write */
static ssize_t block_write(kos_device_t *dev, const void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    if (offset < 0 || offset >= data->total_size) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (offset + count > data->total_size) {
        count = data->total_size - offset;
    }
    
    pthread_rwlock_wrlock(&data->rw_lock);
    
    uint64_t start_block = offset / data->block_size;
    uint64_t end_block = (offset + count - 1) / data->block_size;
    size_t bytes_written = 0;
    
    for (uint64_t block = start_block; block <= end_block; block++) {
        size_t block_offset = (block == start_block) ? (offset % data->block_size) : 0;
        size_t block_count = data->block_size - block_offset;
        
        if (bytes_written + block_count > count) {
            block_count = count - bytes_written;
        }
        
        pthread_mutex_lock(&data->lock);
        
        /* Check if we need to read the block first (partial write) */
        void *block_buf = NULL;
        bool need_read = (block_offset != 0 || block_count != data->block_size);
        
        int cache_idx = block_cache_find(data, block);
        if (cache_idx >= 0) {
            /* Cache hit */
            block_buf = data->cache[cache_idx].data;
        } else {
            /* Allocate new block buffer */
            block_buf = malloc(data->block_size);
            if (!block_buf) {
                pthread_mutex_unlock(&data->lock);
                pthread_rwlock_unlock(&data->rw_lock);
                return KOS_ERR_NO_MEMORY;
            }
            
            if (need_read) {
                /* Read existing data */
                if (dev->block_ops && dev->block_ops->read_block) {
                    int ret = dev->block_ops->read_block(dev, block, block_buf);
                    if (ret != KOS_ERR_SUCCESS) {
                        free(block_buf);
                        pthread_mutex_unlock(&data->lock);
                        pthread_rwlock_unlock(&data->rw_lock);
                        return ret;
                    }
                } else {
                    memcpy(block_buf, (char *)data->storage + block * data->block_size, data->block_size);
                }
            }
            
            /* Add to cache */
            cache_idx = block_cache_get_free(data);
            if (data->cache[cache_idx].valid && data->cache[cache_idx].dirty) {
                block_cache_flush(dev, cache_idx);
            }
            
            if (data->cache[cache_idx].data) {
                free(data->cache[cache_idx].data);
            }
            
            data->cache[cache_idx].block_num = block;
            data->cache[cache_idx].data = block_buf;
            data->cache[cache_idx].valid = true;
            data->cache[cache_idx].dirty = false;
        }
        
        /* Update block data */
        memcpy((char *)block_buf + block_offset, (char *)buf + bytes_written, block_count);
        data->cache[cache_idx].dirty = true;
        
        /* Write-through: immediately write to storage */
        if (dev->block_ops && dev->block_ops->write_block) {
            int ret = dev->block_ops->write_block(dev, block, block_buf);
            if (ret != KOS_ERR_SUCCESS) {
                pthread_mutex_unlock(&data->lock);
                pthread_rwlock_unlock(&data->rw_lock);
                return ret;
            }
        } else {
            memcpy((char *)data->storage + block * data->block_size, block_buf, data->block_size);
        }
        
        data->cache[cache_idx].dirty = false;
        
        pthread_mutex_unlock(&data->lock);
        bytes_written += block_count;
    }
    
    /* Update statistics */
    data->write_count++;
    data->write_bytes += bytes_written;
    
    pthread_rwlock_unlock(&data->rw_lock);
    
    return bytes_written;
}

/* Block device ioctl */
static int block_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    switch (cmd) {
        case KOS_IOCTL_BLKGETSIZE:
            if (arg) {
                *(uint64_t *)arg = data->total_blocks;
            }
            break;
            
        case KOS_IOCTL_BLKFLSBUF:
            return block_fsync(dev);
            
        case KOS_IOCTL_GET_INFO:
            if (arg) {
                struct {
                    uint64_t total_blocks;
                    uint32_t block_size;
                    uint64_t total_size;
                    uint64_t read_count;
                    uint64_t write_count;
                    uint64_t read_bytes;
                    uint64_t write_bytes;
                } *info = (void *)arg;
                
                pthread_mutex_lock(&data->lock);
                info->total_blocks = data->total_blocks;
                info->block_size = data->block_size;
                info->total_size = data->total_size;
                info->read_count = data->read_count;
                info->write_count = data->write_count;
                info->read_bytes = data->read_bytes;
                info->write_bytes = data->write_bytes;
                pthread_mutex_unlock(&data->lock);
            }
            break;
            
        default:
            return KOS_ERR_NOT_SUPPORTED;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Block device fsync */
static int block_fsync(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    /* Flush all dirty cache entries */
    for (int i = 0; i < data->cache_size; i++) {
        if (data->cache[i].valid && data->cache[i].dirty) {
            block_cache_flush(dev, i);
        }
    }
    
    pthread_mutex_unlock(&data->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Default block operations */
static int default_read_block(kos_device_t *dev, uint64_t block, void *buf) {
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data || block >= data->total_blocks) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy(buf, (char *)data->storage + block * data->block_size, data->block_size);
    return KOS_ERR_SUCCESS;
}

static int default_write_block(kos_device_t *dev, uint64_t block, const void *buf) {
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data || block >= data->total_blocks) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy((char *)data->storage + block * data->block_size, buf, data->block_size);
    return KOS_ERR_SUCCESS;
}

static int default_read_blocks(kos_device_t *dev, uint64_t start_block, uint32_t count, void *buf) {
    for (uint32_t i = 0; i < count; i++) {
        int ret = default_read_block(dev, start_block + i, (char *)buf + i * ((kos_block_device_data_t *)dev->private_data)->block_size);
        if (ret != KOS_ERR_SUCCESS) {
            return ret;
        }
    }
    return KOS_ERR_SUCCESS;
}

static int default_write_blocks(kos_device_t *dev, uint64_t start_block, uint32_t count, const void *buf) {
    for (uint32_t i = 0; i < count; i++) {
        int ret = default_write_block(dev, start_block + i, (char *)buf + i * ((kos_block_device_data_t *)dev->private_data)->block_size);
        if (ret != KOS_ERR_SUCCESS) {
            return ret;
        }
    }
    return KOS_ERR_SUCCESS;
}

static int default_get_geometry(kos_device_t *dev, uint64_t *sectors, uint32_t *sector_size) {
    kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (sectors) *sectors = data->total_blocks;
    if (sector_size) *sector_size = data->block_size;
    
    return KOS_ERR_SUCCESS;
}

/* Create a block device */
int kos_block_device_create(const char *name, kos_file_ops_t *fops, kos_block_ops_t *block_ops, 
                           uint64_t size, uint32_t block_size, void *private_data) {
    if (!name || size == 0 || block_size == 0) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Allocate device structure */
    kos_device_t *dev = (kos_device_t *)malloc(sizeof(kos_device_t));
    if (!dev) {
        return KOS_ERR_NO_MEMORY;
    }
    
    memset(dev, 0, sizeof(kos_device_t));
    
    /* Set device properties */
    strncpy(dev->name, name, sizeof(dev->name) - 1);
    dev->name[sizeof(dev->name) - 1] = '\0';
    dev->type = KOS_DEV_BLOCK;
    dev->major = 0; /* Will be assigned by register function */
    dev->minor = 0;
    dev->flags = KOS_DEV_FLAG_RDWR;
    dev->irq = -1;
    
    /* Use provided file operations or default ones */
    dev->fops = fops ? fops : &default_block_fops;
    dev->block_ops = block_ops ? block_ops : &default_block_ops;
    
    /* Create private data */
    if (private_data) {
        dev->private_data = private_data;
    } else {
        kos_block_device_data_t *data = (kos_block_device_data_t *)malloc(sizeof(kos_block_device_data_t));
        if (!data) {
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data, 0, sizeof(kos_block_device_data_t));
        
        data->block_size = block_size;
        data->total_blocks = (size + block_size - 1) / block_size;
        data->total_size = data->total_blocks * block_size;
        data->cache_size = 16;
        
        /* Allocate storage */
        data->storage = malloc(data->total_size);
        if (!data->storage) {
            free(data);
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data->storage, 0, data->total_size);
        
        if (pthread_mutex_init(&data->lock, NULL) != 0) {
            free(data->storage);
            free(data);
            free(dev);
            return KOS_ERR_IO_ERROR;
        }
        
        if (pthread_rwlock_init(&data->rw_lock, NULL) != 0) {
            pthread_mutex_destroy(&data->lock);
            free(data->storage);
            free(data);
            free(dev);
            return KOS_ERR_IO_ERROR;
        }
        
        dev->private_data = data;
    }
    
    /* Register the device */
    int ret = kos_device_register(dev);
    if (ret != KOS_ERR_SUCCESS) {
        if (!private_data) {
            kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
            pthread_rwlock_destroy(&data->rw_lock);
            pthread_mutex_destroy(&data->lock);
            free(data->storage);
            free(data);
        }
        free(dev);
        return ret;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Destroy a block device */
int kos_block_device_destroy(const char *name) {
    if (!name) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_device_t *dev = kos_device_find(name);
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (dev->type != KOS_DEV_BLOCK) {
        kos_device_put(dev);
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Flush all data */
    block_fsync(dev);
    
    /* Unregister the device */
    int ret = kos_device_unregister(dev);
    if (ret != KOS_ERR_SUCCESS) {
        kos_device_put(dev);
        return ret;
    }
    
    /* Cleanup private data if it's the default type */
    if (dev->private_data && dev->fops == &default_block_fops) {
        kos_block_device_data_t *data = (kos_block_device_data_t *)dev->private_data;
        
        /* Free cache entries */
        for (int i = 0; i < data->cache_size; i++) {
            if (data->cache[i].data) {
                free(data->cache[i].data);
            }
        }
        
        pthread_rwlock_destroy(&data->rw_lock);
        pthread_mutex_destroy(&data->lock);
        free(data->storage);
        free(data);
    }
    
    kos_device_put(dev);
    free(dev);
    
    return KOS_ERR_SUCCESS;
}