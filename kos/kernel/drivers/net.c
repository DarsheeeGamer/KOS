#define _GNU_SOURCE
#include "drivers.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* Network device statistics */
typedef struct kos_net_stats {
    uint64_t rx_packets;
    uint64_t tx_packets;
    uint64_t rx_bytes;
    uint64_t tx_bytes;
    uint64_t rx_errors;
    uint64_t tx_errors;
    uint64_t rx_dropped;
    uint64_t tx_dropped;
    uint64_t collisions;
} kos_net_stats_t;

/* Network packet structure */
typedef struct kos_net_packet {
    void *data;
    size_t len;
    uint64_t timestamp;
    struct kos_net_packet *next;
} kos_net_packet_t;

/* Network device private data */
typedef struct kos_net_device_data {
    uint8_t mac_addr[6];
    uint32_t mtu;
    bool is_up;
    
    /* Packet queues */
    kos_net_packet_t *rx_queue_head;
    kos_net_packet_t *rx_queue_tail;
    kos_net_packet_t *tx_queue_head;
    kos_net_packet_t *tx_queue_tail;
    
    size_t rx_queue_size;
    size_t tx_queue_size;
    size_t max_queue_size;
    
    pthread_mutex_t rx_lock;
    pthread_mutex_t tx_lock;
    pthread_cond_t rx_cond;
    pthread_cond_t tx_cond;
    
    /* Statistics */
    kos_net_stats_t stats;
    pthread_mutex_t stats_lock;
    
    /* Network thread for packet processing */
    pthread_t net_thread;
    bool thread_running;
    
    /* Virtual network interface (for simulation) */
    int tap_fd;
    char tap_name[16];
} kos_net_device_data_t;

/* Forward declarations */
static int net_open(kos_device_t *dev, int flags);
static int net_close(kos_device_t *dev);
static ssize_t net_read(kos_device_t *dev, void *buf, size_t count, off_t offset);
static ssize_t net_write(kos_device_t *dev, const void *buf, size_t count, off_t offset);
static int net_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg);

static int default_send_packet(kos_device_t *dev, const void *data, size_t len);
static int default_receive_packet(kos_device_t *dev, void *buf, size_t *len);
static int default_set_mac_addr(kos_device_t *dev, const uint8_t *mac);
static int default_get_mac_addr(kos_device_t *dev, uint8_t *mac);
static int default_set_mtu(kos_device_t *dev, uint32_t mtu);
static int default_get_mtu(kos_device_t *dev, uint32_t *mtu);
static int default_up(kos_device_t *dev);
static int default_down(kos_device_t *dev);
static int default_get_stats(kos_device_t *dev, void *stats);

static void *net_thread_func(void *arg);

/* Default network device file operations */
static kos_file_ops_t default_net_fops = {
    .open = net_open,
    .close = net_close,
    .read = net_read,
    .write = net_write,
    .ioctl = net_ioctl,
    .flush = NULL,
    .fsync = NULL,
    .mmap = NULL
};

/* Default network device operations */
static kos_net_ops_t default_net_ops = {
    .send_packet = default_send_packet,
    .receive_packet = default_receive_packet,
    .set_mac_addr = default_set_mac_addr,
    .get_mac_addr = default_get_mac_addr,
    .set_mtu = default_set_mtu,
    .get_mtu = default_get_mtu,
    .up = default_up,
    .down = default_down,
    .get_stats = default_get_stats
};

/* Packet queue management */
static void net_packet_enqueue(kos_net_packet_t **head, kos_net_packet_t **tail, 
                              kos_net_packet_t *packet, size_t *queue_size) {
    packet->next = NULL;
    
    if (*tail) {
        (*tail)->next = packet;
        *tail = packet;
    } else {
        *head = *tail = packet;
    }
    
    (*queue_size)++;
}

static kos_net_packet_t *net_packet_dequeue(kos_net_packet_t **head, kos_net_packet_t **tail, 
                                           size_t *queue_size) {
    if (!*head) {
        return NULL;
    }
    
    kos_net_packet_t *packet = *head;
    *head = packet->next;
    
    if (!*head) {
        *tail = NULL;
    }
    
    (*queue_size)--;
    return packet;
}

static void net_packet_free(kos_net_packet_t *packet) {
    if (packet) {
        if (packet->data) {
            free(packet->data);
        }
        free(packet);
    }
}

/* Network thread for packet processing */
static void *net_thread_func(void *arg) {
    kos_device_t *dev = (kos_device_t *)arg;
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    
    while (data->thread_running) {
        /* Process TX queue */
        pthread_mutex_lock(&data->tx_lock);
        
        while (data->tx_queue_head && data->is_up) {
            kos_net_packet_t *packet = net_packet_dequeue(&data->tx_queue_head, &data->tx_queue_tail, 
                                                         &data->tx_queue_size);
            
            if (packet) {
                pthread_mutex_unlock(&data->tx_lock);
                
                /* Simulate sending packet */
                pthread_mutex_lock(&data->stats_lock);
                data->stats.tx_packets++;
                data->stats.tx_bytes += packet->len;
                pthread_mutex_unlock(&data->stats_lock);
                
                net_packet_free(packet);
                
                pthread_mutex_lock(&data->tx_lock);
            }
        }
        
        pthread_mutex_unlock(&data->tx_lock);
        
        /* Process actual received packets from network buffer */
        if (data->is_up) {
            /* In a real implementation, this would read from actual network hardware */
            /* For now, just check if we have any pending packets from the network stack */
            
            /* Check for packets from the physical network interface */
            /* This would be where we'd interface with real hardware drivers */
            
            /* Since we're in a virtualized environment, packets would come from */
            /* the host system's network stack or from other network processes */
        }
        
        usleep(1000); /* 1ms */
    }
    
    return NULL;
}

/* Network device open */
static int net_open(kos_device_t *dev, int flags) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    /* Start network thread if not running */
    if (!data->thread_running) {
        data->thread_running = true;
        if (pthread_create(&data->net_thread, NULL, net_thread_func, dev) != 0) {
            data->thread_running = false;
            return KOS_ERR_IO_ERROR;
        }
    }
    
    return KOS_ERR_SUCCESS;
}

/* Network device close */
static int net_close(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    /* Stop network thread */
    if (data->thread_running) {
        data->thread_running = false;
        pthread_join(data->net_thread, NULL);
    }
    
    return KOS_ERR_SUCCESS;
}

/* Network device read (receive packets) */
static ssize_t net_read(kos_device_t *dev, void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    if (!data->is_up) {
        return KOS_ERR_DEVICE_BUSY;
    }
    
    pthread_mutex_lock(&data->rx_lock);
    
    /* Wait for packets if blocking mode */
    while (!data->rx_queue_head) {
        if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
            pthread_mutex_unlock(&data->rx_lock);
            return 0; /* Would block */
        }
        
        pthread_cond_wait(&data->rx_cond, &data->rx_lock);
    }
    
    /* Get packet from queue */
    kos_net_packet_t *packet = net_packet_dequeue(&data->rx_queue_head, &data->rx_queue_tail, 
                                                 &data->rx_queue_size);
    
    pthread_mutex_unlock(&data->rx_lock);
    
    if (!packet) {
        return 0;
    }
    
    /* Copy packet data to user buffer */
    size_t to_copy = (packet->len < count) ? packet->len : count;
    memcpy(buf, packet->data, to_copy);
    
    ssize_t result = to_copy;
    net_packet_free(packet);
    
    return result;
}

/* Network device write (send packets) */
static ssize_t net_write(kos_device_t *dev, const void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    if (!data->is_up) {
        return KOS_ERR_DEVICE_BUSY;
    }
    
    if (count > data->mtu + 14) { /* MTU + Ethernet header */
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Create packet */
    kos_net_packet_t *packet = (kos_net_packet_t *)malloc(sizeof(kos_net_packet_t));
    if (!packet) {
        return KOS_ERR_NO_MEMORY;
    }
    
    packet->data = malloc(count);
    if (!packet->data) {
        free(packet);
        return KOS_ERR_NO_MEMORY;
    }
    
    memcpy(packet->data, buf, count);
    packet->len = count;
    packet->timestamp = kos_get_timestamp();
    
    pthread_mutex_lock(&data->tx_lock);
    
    /* Check queue space */
    if (data->tx_queue_size >= data->max_queue_size) {
        pthread_mutex_unlock(&data->tx_lock);
        net_packet_free(packet);
        
        if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
            return KOS_ERR_DEVICE_BUSY;
        }
        
        /* Wait for space */
        pthread_mutex_lock(&data->tx_lock);
        while (data->tx_queue_size >= data->max_queue_size) {
            pthread_cond_wait(&data->tx_cond, &data->tx_lock);
        }
    }
    
    /* Add to TX queue */
    net_packet_enqueue(&data->tx_queue_head, &data->tx_queue_tail, packet, &data->tx_queue_size);
    
    pthread_mutex_unlock(&data->tx_lock);
    
    return count;
}

/* Network device ioctl */
static int net_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    switch (cmd) {
        case KOS_IOCTL_NETUP:
            return default_up(dev);
            
        case KOS_IOCTL_NETDOWN:
            return default_down(dev);
            
        case KOS_IOCTL_NETSETADDR:
            if (arg) {
                return default_set_mac_addr(dev, (const uint8_t *)arg);
            }
            return KOS_ERR_INVALID_PARAM;
            
        case KOS_IOCTL_GET_INFO:
            if (arg) {
                struct {
                    uint8_t mac_addr[6];
                    uint32_t mtu;
                    bool is_up;
                    size_t rx_queue_size;
                    size_t tx_queue_size;
                    kos_net_stats_t stats;
                } *info = (void *)arg;
                
                memcpy(info->mac_addr, data->mac_addr, 6);
                info->mtu = data->mtu;
                info->is_up = data->is_up;
                info->rx_queue_size = data->rx_queue_size;
                info->tx_queue_size = data->tx_queue_size;
                
                pthread_mutex_lock(&data->stats_lock);
                info->stats = data->stats;
                pthread_mutex_unlock(&data->stats_lock);
            }
            break;
            
        default:
            return KOS_ERR_NOT_SUPPORTED;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Default network operations */
static int default_send_packet(kos_device_t *dev, const void *data, size_t len) {
    return net_write(dev, data, len, 0);
}

static int default_receive_packet(kos_device_t *dev, void *buf, size_t *len) {
    ssize_t result = net_read(dev, buf, *len, 0);
    if (result >= 0) {
        *len = result;
        return KOS_ERR_SUCCESS;
    }
    return result;
}

static int default_set_mac_addr(kos_device_t *dev, const uint8_t *mac) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data || !mac) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy(data->mac_addr, mac, 6);
    return KOS_ERR_SUCCESS;
}

static int default_get_mac_addr(kos_device_t *dev, uint8_t *mac) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data || !mac) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy(mac, data->mac_addr, 6);
    return KOS_ERR_SUCCESS;
}

static int default_set_mtu(kos_device_t *dev, uint32_t mtu) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data || mtu < 64 || mtu > 9000) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    data->mtu = mtu;
    return KOS_ERR_SUCCESS;
}

static int default_get_mtu(kos_device_t *dev, uint32_t *mtu) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data || !mtu) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    *mtu = data->mtu;
    return KOS_ERR_SUCCESS;
}

static int default_up(kos_device_t *dev) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    data->is_up = true;
    return KOS_ERR_SUCCESS;
}

static int default_down(kos_device_t *dev) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    data->is_up = false;
    
    /* Clear queues */
    pthread_mutex_lock(&data->rx_lock);
    while (data->rx_queue_head) {
        kos_net_packet_t *packet = net_packet_dequeue(&data->rx_queue_head, &data->rx_queue_tail, 
                                                     &data->rx_queue_size);
        net_packet_free(packet);
    }
    pthread_mutex_unlock(&data->rx_lock);
    
    pthread_mutex_lock(&data->tx_lock);
    while (data->tx_queue_head) {
        kos_net_packet_t *packet = net_packet_dequeue(&data->tx_queue_head, &data->tx_queue_tail, 
                                                     &data->tx_queue_size);
        net_packet_free(packet);
    }
    pthread_mutex_unlock(&data->tx_lock);
    
    return KOS_ERR_SUCCESS;
}

static int default_get_stats(kos_device_t *dev, void *stats) {
    kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
    if (!data || !stats) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&data->stats_lock);
    memcpy(stats, &data->stats, sizeof(kos_net_stats_t));
    pthread_mutex_unlock(&data->stats_lock);
    
    return KOS_ERR_SUCCESS;
}

/* Create a network device */
int kos_net_device_create(const char *name, kos_file_ops_t *fops, kos_net_ops_t *net_ops, 
                         const uint8_t *mac_addr, void *private_data) {
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
    dev->type = KOS_DEV_NET;
    dev->major = 0; /* Will be assigned by register function */
    dev->minor = 0;
    dev->flags = KOS_DEV_FLAG_RDWR | KOS_DEV_FLAG_NONBLOCK;
    dev->irq = -1;
    
    /* Use provided operations or default ones */
    dev->fops = fops ? fops : &default_net_fops;
    dev->net_ops = net_ops ? net_ops : &default_net_ops;
    
    /* Create private data */
    if (private_data) {
        dev->private_data = private_data;
    } else {
        kos_net_device_data_t *data = (kos_net_device_data_t *)malloc(sizeof(kos_net_device_data_t));
        if (!data) {
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data, 0, sizeof(kos_net_device_data_t));
        
        /* Set default MAC address or use provided one */
        if (mac_addr) {
            memcpy(data->mac_addr, mac_addr, 6);
        } else {
            /* Generate a random MAC address */
            data->mac_addr[0] = 0x02; /* Local bit set */
            for (int i = 1; i < 6; i++) {
                data->mac_addr[i] = rand() & 0xFF;
            }
        }
        
        data->mtu = 1500; /* Standard Ethernet MTU */
        data->is_up = false;
        data->max_queue_size = 256;
        data->tap_fd = -1;
        
        /* Initialize mutexes and conditions */
        if (pthread_mutex_init(&data->rx_lock, NULL) != 0 ||
            pthread_mutex_init(&data->tx_lock, NULL) != 0 ||
            pthread_mutex_init(&data->stats_lock, NULL) != 0 ||
            pthread_cond_init(&data->rx_cond, NULL) != 0 ||
            pthread_cond_init(&data->tx_cond, NULL) != 0) {
            
            pthread_mutex_destroy(&data->rx_lock);
            pthread_mutex_destroy(&data->tx_lock);
            pthread_mutex_destroy(&data->stats_lock);
            pthread_cond_destroy(&data->rx_cond);
            pthread_cond_destroy(&data->tx_cond);
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
            kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
            pthread_cond_destroy(&data->tx_cond);
            pthread_cond_destroy(&data->rx_cond);
            pthread_mutex_destroy(&data->stats_lock);
            pthread_mutex_destroy(&data->tx_lock);
            pthread_mutex_destroy(&data->rx_lock);
            free(data);
        }
        free(dev);
        return ret;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Destroy a network device */
int kos_net_device_destroy(const char *name) {
    if (!name) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_device_t *dev = kos_device_find(name);
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (dev->type != KOS_DEV_NET) {
        kos_device_put(dev);
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Bring interface down */
    if (dev->net_ops && dev->net_ops->down) {
        dev->net_ops->down(dev);
    }
    
    /* Stop network thread */
    net_close(dev);
    
    /* Unregister the device */
    int ret = kos_device_unregister(dev);
    if (ret != KOS_ERR_SUCCESS) {
        kos_device_put(dev);
        return ret;
    }
    
    /* Cleanup private data if it's the default type */
    if (dev->private_data && dev->fops == &default_net_fops) {
        kos_net_device_data_t *data = (kos_net_device_data_t *)dev->private_data;
        
        /* Free all packets */
        while (data->rx_queue_head) {
            kos_net_packet_t *packet = net_packet_dequeue(&data->rx_queue_head, &data->rx_queue_tail, 
                                                         &data->rx_queue_size);
            net_packet_free(packet);
        }
        
        while (data->tx_queue_head) {
            kos_net_packet_t *packet = net_packet_dequeue(&data->tx_queue_head, &data->tx_queue_tail, 
                                                         &data->tx_queue_size);
            net_packet_free(packet);
        }
        
        pthread_cond_destroy(&data->tx_cond);
        pthread_cond_destroy(&data->rx_cond);
        pthread_mutex_destroy(&data->stats_lock);
        pthread_mutex_destroy(&data->tx_lock);
        pthread_mutex_destroy(&data->rx_lock);
        free(data);
    }
    
    kos_device_put(dev);
    free(dev);
    
    return KOS_ERR_SUCCESS;
}