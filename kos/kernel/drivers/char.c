#define _GNU_SOURCE
#include "drivers.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

/* Character device private data */
typedef struct kos_char_device_data {
    char *buffer;
    size_t buffer_size;
    size_t data_size;
    off_t read_pos;
    off_t write_pos;
    pthread_mutex_t lock;
    pthread_cond_t read_cond;
    pthread_cond_t write_cond;
    bool eof;
} kos_char_device_data_t;

/* Forward declarations */
static int char_open(kos_device_t *dev, int flags);
static int char_close(kos_device_t *dev);
static ssize_t char_read(kos_device_t *dev, void *buf, size_t count, off_t offset);
static ssize_t char_write(kos_device_t *dev, const void *buf, size_t count, off_t offset);
static int char_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg);
static int char_flush(kos_device_t *dev);

/* Default character device file operations */
static kos_file_ops_t default_char_fops = {
    .open = char_open,
    .close = char_close,
    .read = char_read,
    .write = char_write,
    .ioctl = char_ioctl,
    .flush = char_flush,
    .fsync = NULL,
    .mmap = NULL
};

/* Character device open */
static int char_open(kos_device_t *dev, int flags) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
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
    
    /* Reset positions if opening for write */
    if (flags & KOS_DEV_FLAG_WRITEONLY) {
        data->write_pos = 0;
        data->data_size = 0;
        data->eof = false;
    }
    
    /* Reset read position if opening for read */
    if (flags & KOS_DEV_FLAG_READONLY) {
        data->read_pos = 0;
    }
    
    pthread_mutex_unlock(&data->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Character device close */
static int char_close(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Character devices typically don't need special close handling */
    return KOS_ERR_SUCCESS;
}

/* Character device read */
static ssize_t char_read(kos_device_t *dev, void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    /* Wait for data if blocking mode */
    while (data->read_pos >= data->data_size && !data->eof) {
        if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
            pthread_mutex_unlock(&data->lock);
            return 0; /* Would block */
        }
        
        pthread_cond_wait(&data->read_cond, &data->lock);
    }
    
    /* Check for EOF */
    if (data->read_pos >= data->data_size && data->eof) {
        pthread_mutex_unlock(&data->lock);
        return 0; /* EOF */
    }
    
    /* Calculate available data */
    size_t available = data->data_size - data->read_pos;
    size_t to_read = (count < available) ? count : available;
    
    /* Copy data to user buffer */
    memcpy(buf, data->buffer + data->read_pos, to_read);
    data->read_pos += to_read;
    
    /* Signal writers that space is available */
    pthread_cond_signal(&data->write_cond);
    
    pthread_mutex_unlock(&data->lock);
    
    return to_read;
}

/* Character device write */
static ssize_t char_write(kos_device_t *dev, const void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    /* Wait for space if blocking mode */
    while (data->write_pos + count > data->buffer_size) {
        if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
            /* Try to write what we can */
            count = data->buffer_size - data->write_pos;
            if (count == 0) {
                pthread_mutex_unlock(&data->lock);
                return KOS_ERR_DEVICE_BUSY;
            }
            break;
        }
        
        pthread_cond_wait(&data->write_cond, &data->lock);
    }
    
    /* Copy data from user buffer */
    memcpy(data->buffer + data->write_pos, buf, count);
    data->write_pos += count;
    
    /* Update data size */
    if (data->write_pos > data->data_size) {
        data->data_size = data->write_pos;
    }
    
    /* Signal readers that data is available */
    pthread_cond_signal(&data->read_cond);
    
    pthread_mutex_unlock(&data->lock);
    
    return count;
}

/* Character device ioctl */
static int char_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    switch (cmd) {
        case KOS_IOCTL_RESET:
            data->read_pos = 0;
            data->write_pos = 0;
            data->data_size = 0;
            data->eof = false;
            memset(data->buffer, 0, data->buffer_size);
            break;
            
        case KOS_IOCTL_GET_INFO:
            if (arg) {
                struct {
                    size_t buffer_size;
                    size_t data_size;
                    off_t read_pos;
                    off_t write_pos;
                    bool eof;
                } *info = (void *)arg;
                
                info->buffer_size = data->buffer_size;
                info->data_size = data->data_size;
                info->read_pos = data->read_pos;
                info->write_pos = data->write_pos;
                info->eof = data->eof;
            }
            break;
            
        case KOS_IOCTL_FLUSH:
            data->read_pos = 0;
            data->data_size = 0;
            break;
            
        default:
            pthread_mutex_unlock(&data->lock);
            return KOS_ERR_NOT_SUPPORTED;
    }
    
    pthread_mutex_unlock(&data->lock);
    return KOS_ERR_SUCCESS;
}

/* Character device flush */
static int char_flush(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->lock);
    
    /* Mark EOF and signal waiting readers */
    data->eof = true;
    pthread_cond_broadcast(&data->read_cond);
    
    pthread_mutex_unlock(&data->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Create a character device */
int kos_char_device_create(const char *name, kos_file_ops_t *fops, void *private_data) {
    if (!name) {
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
    dev->type = KOS_DEV_CHAR;
    dev->major = 0; /* Will be assigned by register function */
    dev->minor = 0;
    dev->flags = KOS_DEV_FLAG_RDWR;
    dev->irq = -1;
    
    /* Use provided file operations or default ones */
    if (fops) {
        dev->fops = fops;
    } else {
        dev->fops = &default_char_fops;
    }
    
    /* Create default private data if none provided */
    if (private_data) {
        dev->private_data = private_data;
    } else {
        kos_char_device_data_t *data = (kos_char_device_data_t *)malloc(sizeof(kos_char_device_data_t));
        if (!data) {
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data, 0, sizeof(kos_char_device_data_t));
        
        /* Default buffer size of 4KB */
        data->buffer_size = 4096;
        data->buffer = (char *)malloc(data->buffer_size);
        if (!data->buffer) {
            free(data);
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data->buffer, 0, data->buffer_size);
        
        if (pthread_mutex_init(&data->lock, NULL) != 0) {
            free(data->buffer);
            free(data);
            free(dev);
            return KOS_ERR_IO_ERROR;
        }
        
        if (pthread_cond_init(&data->read_cond, NULL) != 0) {
            pthread_mutex_destroy(&data->lock);
            free(data->buffer);
            free(data);
            free(dev);
            return KOS_ERR_IO_ERROR;
        }
        
        if (pthread_cond_init(&data->write_cond, NULL) != 0) {
            pthread_cond_destroy(&data->read_cond);
            pthread_mutex_destroy(&data->lock);
            free(data->buffer);
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
            kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
            pthread_cond_destroy(&data->write_cond);
            pthread_cond_destroy(&data->read_cond);
            pthread_mutex_destroy(&data->lock);
            free(data->buffer);
            free(data);
        }
        free(dev);
        return ret;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Destroy a character device */
int kos_char_device_destroy(const char *name) {
    if (!name) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_device_t *dev = kos_device_find(name);
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (dev->type != KOS_DEV_CHAR) {
        kos_device_put(dev);
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Unregister the device */
    int ret = kos_device_unregister(dev);
    if (ret != KOS_ERR_SUCCESS) {
        kos_device_put(dev);
        return ret;
    }
    
    /* Cleanup private data if it's the default type */
    if (dev->private_data && dev->fops == &default_char_fops) {
        kos_char_device_data_t *data = (kos_char_device_data_t *)dev->private_data;
        
        pthread_mutex_lock(&data->lock);
        data->eof = true;
        pthread_cond_broadcast(&data->read_cond);
        pthread_cond_broadcast(&data->write_cond);
        pthread_mutex_unlock(&data->lock);
        
        pthread_cond_destroy(&data->write_cond);
        pthread_cond_destroy(&data->read_cond);
        pthread_mutex_destroy(&data->lock);
        free(data->buffer);
        free(data);
    }
    
    kos_device_put(dev);
    free(dev);
    
    return KOS_ERR_SUCCESS;
}