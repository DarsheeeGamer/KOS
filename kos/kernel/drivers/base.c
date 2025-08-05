#define _GNU_SOURCE
#include "drivers.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mman.h>
#include <time.h>
#include <errno.h>
#include <signal.h>

/* Global device manager */
kos_device_manager_t *kos_device_manager = NULL;

/* IRQ management structures */
typedef struct kos_irq_entry {
    int irq;
    kos_irq_handler_t handler;
    char name[64];
    void *dev_data;
    bool enabled;
    struct kos_irq_entry *next;
} kos_irq_entry_t;

static kos_irq_entry_t *irq_handlers = NULL;
static pthread_mutex_t irq_mutex = PTHREAD_MUTEX_INITIALIZER;

/* Initialize the device subsystem */
int kos_device_init(void) {
    if (kos_device_manager != NULL) {
        return KOS_ERR_SUCCESS; /* Already initialized */
    }
    
    kos_device_manager = (kos_device_manager_t *)malloc(sizeof(kos_device_manager_t));
    if (!kos_device_manager) {
        return KOS_ERR_NO_MEMORY;
    }
    
    memset(kos_device_manager, 0, sizeof(kos_device_manager_t));
    
    if (pthread_mutex_init(&kos_device_manager->lock, NULL) != 0) {
        free(kos_device_manager);
        kos_device_manager = NULL;
        return KOS_ERR_IO_ERROR;
    }
    
    kos_device_manager->next_major = 1;
    
    return KOS_ERR_SUCCESS;
}

/* Cleanup the device subsystem */
void kos_device_cleanup(void) {
    if (!kos_device_manager) {
        return;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    /* Cleanup all devices */
    kos_device_t *dev = kos_device_manager->devices;
    while (dev) {
        kos_device_t *next = dev->next;
        
        /* Free DMA descriptors */
        if (dev->dma_desc) {
            kos_dma_free(dev->dma_desc);
        }
        
        /* Free IRQ if assigned */
        if (dev->irq >= 0 && dev->irq_handler) {
            kos_irq_free(dev->irq, dev);
        }
        
        pthread_mutex_destroy(&dev->ref_mutex);
        pthread_mutex_destroy(&dev->dma_mutex);
        free(dev);
        dev = next;
    }
    
    /* Cleanup all drivers */
    kos_driver_t *driver = kos_device_manager->drivers;
    while (driver) {
        kos_driver_t *next = driver->next;
        free(driver);
        driver = next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    pthread_mutex_destroy(&kos_device_manager->lock);
    
    free(kos_device_manager);
    kos_device_manager = NULL;
}

/* Register a device */
int kos_device_register(kos_device_t *dev) {
    if (!kos_device_manager || !dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    /* Check if device already exists */
    kos_device_t *existing = kos_device_manager->devices;
    while (existing) {
        if (strcmp(existing->name, dev->name) == 0) {
            pthread_mutex_unlock(&kos_device_manager->lock);
            return KOS_ERR_DEVICE_BUSY;
        }
        existing = existing->next;
    }
    
    /* Assign major number if not set */
    if (dev->major == 0) {
        dev->major = kos_device_manager->next_major++;
    }
    
    /* Initialize device mutexes */
    if (pthread_mutex_init(&dev->ref_mutex, NULL) != 0) {
        pthread_mutex_unlock(&kos_device_manager->lock);
        return KOS_ERR_IO_ERROR;
    }
    
    if (pthread_mutex_init(&dev->dma_mutex, NULL) != 0) {
        pthread_mutex_destroy(&dev->ref_mutex);
        pthread_mutex_unlock(&kos_device_manager->lock);
        return KOS_ERR_IO_ERROR;
    }
    
    /* Initialize reference count */
    dev->ref_count = 1;
    
    /* Add to device list */
    dev->next = kos_device_manager->devices;
    kos_device_manager->devices = dev;
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Unregister a device */
int kos_device_unregister(kos_device_t *dev) {
    if (!kos_device_manager || !dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    /* Find and remove from device list */
    kos_device_t **current = &kos_device_manager->devices;
    while (*current) {
        if (*current == dev) {
            *current = dev->next;
            break;
        }
        current = &(*current)->next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    
    /* Wait for all references to be released */
    pthread_mutex_lock(&dev->ref_mutex);
    while (dev->ref_count > 1) {
        pthread_mutex_unlock(&dev->ref_mutex);
        usleep(1000); /* Wait 1ms */
        pthread_mutex_lock(&dev->ref_mutex);
    }
    pthread_mutex_unlock(&dev->ref_mutex);
    
    /* Cleanup device resources */
    if (dev->dma_desc) {
        kos_dma_free(dev->dma_desc);
    }
    
    if (dev->irq >= 0 && dev->irq_handler) {
        kos_irq_free(dev->irq, dev);
    }
    
    pthread_mutex_destroy(&dev->ref_mutex);
    pthread_mutex_destroy(&dev->dma_mutex);
    
    return KOS_ERR_SUCCESS;
}

/* Find device by name */
kos_device_t *kos_device_find(const char *name) {
    if (!kos_device_manager || !name) {
        return NULL;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    kos_device_t *dev = kos_device_manager->devices;
    while (dev) {
        if (strcmp(dev->name, name) == 0) {
            kos_device_get(dev);
            pthread_mutex_unlock(&kos_device_manager->lock);
            return dev;
        }
        dev = dev->next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    return NULL;
}

/* Find device by major/minor numbers */
kos_device_t *kos_device_find_by_major_minor(int major, int minor) {
    if (!kos_device_manager) {
        return NULL;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    kos_device_t *dev = kos_device_manager->devices;
    while (dev) {
        if (dev->major == major && dev->minor == minor) {
            kos_device_get(dev);
            pthread_mutex_unlock(&kos_device_manager->lock);
            return dev;
        }
        dev = dev->next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    return NULL;
}

/* Register a driver */
int kos_driver_register(kos_driver_t *driver) {
    if (!kos_device_manager || !driver) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    /* Check if driver already exists */
    kos_driver_t *existing = kos_device_manager->drivers;
    while (existing) {
        if (strcmp(existing->name, driver->name) == 0) {
            pthread_mutex_unlock(&kos_device_manager->lock);
            return KOS_ERR_DEVICE_BUSY;
        }
        existing = existing->next;
    }
    
    /* Add to driver list */
    driver->next = kos_device_manager->drivers;
    kos_device_manager->drivers = driver;
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Unregister a driver */
int kos_driver_unregister(kos_driver_t *driver) {
    if (!kos_device_manager || !driver) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    /* Find and remove from driver list */
    kos_driver_t **current = &kos_device_manager->drivers;
    while (*current) {
        if (*current == driver) {
            *current = driver->next;
            break;
        }
        current = &(*current)->next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    
    return KOS_ERR_SUCCESS;
}

/* Find driver by name */
kos_driver_t *kos_driver_find(const char *name) {
    if (!kos_device_manager || !name) {
        return NULL;
    }
    
    pthread_mutex_lock(&kos_device_manager->lock);
    
    kos_driver_t *driver = kos_device_manager->drivers;
    while (driver) {
        if (strcmp(driver->name, name) == 0) {
            pthread_mutex_unlock(&kos_device_manager->lock);
            return driver;
        }
        driver = driver->next;
    }
    
    pthread_mutex_unlock(&kos_device_manager->lock);
    return NULL;
}

/* Increment device reference count */
void kos_device_get(kos_device_t *dev) {
    if (!dev) return;
    
    pthread_mutex_lock(&dev->ref_mutex);
    dev->ref_count++;
    pthread_mutex_unlock(&dev->ref_mutex);
}

/* Decrement device reference count */
void kos_device_put(kos_device_t *dev) {
    if (!dev) return;
    
    pthread_mutex_lock(&dev->ref_mutex);
    dev->ref_count--;
    pthread_mutex_unlock(&dev->ref_mutex);
}

/* Allocate DMA descriptor */
kos_dma_desc_t *kos_dma_alloc(size_t size, uint32_t flags) {
    kos_dma_desc_t *desc = (kos_dma_desc_t *)malloc(sizeof(kos_dma_desc_t));
    if (!desc) {
        return NULL;
    }
    
    memset(desc, 0, sizeof(kos_dma_desc_t));
    
    /* Allocate aligned memory for DMA */
    desc->virt_addr = aligned_alloc(4096, (size + 4095) & ~4095);
    if (!desc->virt_addr) {
        free(desc);
        return NULL;
    }
    
    desc->size = size;
    desc->flags = flags;
    desc->phys_addr = (uint64_t)desc->virt_addr; /* Simplified for userspace */
    
    return desc;
}

/* Free DMA descriptor */
void kos_dma_free(kos_dma_desc_t *desc) {
    if (!desc) return;
    
    kos_dma_desc_t *current = desc;
    while (current) {
        kos_dma_desc_t *next = current->next;
        
        if (current->virt_addr) {
            free(current->virt_addr);
        }
        
        free(current);
        current = next;
    }
}

/* Map DMA descriptor */
int kos_dma_map(kos_dma_desc_t *desc) {
    if (!desc || !desc->virt_addr) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* In userspace, memory is already mapped */
    return KOS_ERR_SUCCESS;
}

/* Unmap DMA descriptor */
void kos_dma_unmap(kos_dma_desc_t *desc) {
    /* In userspace, no special unmapping needed */
    (void)desc;
}

/* Request IRQ */
int kos_irq_request(int irq, kos_irq_handler_t handler, const char *name, void *dev_data) {
    if (!handler || !name) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&irq_mutex);
    
    /* Check if IRQ is already in use */
    kos_irq_entry_t *entry = irq_handlers;
    while (entry) {
        if (entry->irq == irq) {
            pthread_mutex_unlock(&irq_mutex);
            return KOS_ERR_DEVICE_BUSY;
        }
        entry = entry->next;
    }
    
    /* Create new IRQ entry */
    entry = (kos_irq_entry_t *)malloc(sizeof(kos_irq_entry_t));
    if (!entry) {
        pthread_mutex_unlock(&irq_mutex);
        return KOS_ERR_NO_MEMORY;
    }
    
    entry->irq = irq;
    entry->handler = handler;
    strncpy(entry->name, name, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';
    entry->dev_data = dev_data;
    entry->enabled = true;
    
    /* Add to list */
    entry->next = irq_handlers;
    irq_handlers = entry;
    
    pthread_mutex_unlock(&irq_mutex);
    
    return KOS_ERR_SUCCESS;
}

/* Free IRQ */
void kos_irq_free(int irq, void *dev_data) {
    pthread_mutex_lock(&irq_mutex);
    
    kos_irq_entry_t **current = &irq_handlers;
    while (*current) {
        if ((*current)->irq == irq && (*current)->dev_data == dev_data) {
            kos_irq_entry_t *to_free = *current;
            *current = (*current)->next;
            free(to_free);
            break;
        }
        current = &(*current)->next;
    }
    
    pthread_mutex_unlock(&irq_mutex);
}

/* Enable IRQ */
int kos_irq_enable(int irq) {
    pthread_mutex_lock(&irq_mutex);
    
    kos_irq_entry_t *entry = irq_handlers;
    while (entry) {
        if (entry->irq == irq) {
            entry->enabled = true;
            pthread_mutex_unlock(&irq_mutex);
            return KOS_ERR_SUCCESS;
        }
        entry = entry->next;
    }
    
    pthread_mutex_unlock(&irq_mutex);
    return KOS_ERR_INVALID_PARAM;
}

/* Disable IRQ */
int kos_irq_disable(int irq) {
    pthread_mutex_lock(&irq_mutex);
    
    kos_irq_entry_t *entry = irq_handlers;
    while (entry) {
        if (entry->irq == irq) {
            entry->enabled = false;
            pthread_mutex_unlock(&irq_mutex);
            return KOS_ERR_SUCCESS;
        }
        entry = entry->next;
    }
    
    pthread_mutex_unlock(&irq_mutex);
    return KOS_ERR_INVALID_PARAM;
}

/* Sleep function */
void kos_msleep(int msecs) {
    usleep(msecs * 1000);
}

/* Get timestamp */
uint64_t kos_get_timestamp(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

/* Kernel malloc */
void *kos_kmalloc(size_t size) {
    return malloc(size);
}

/* Kernel free */
void kos_kfree(void *ptr) {
    free(ptr);
}