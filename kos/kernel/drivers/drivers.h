#ifndef KOS_DRIVERS_H
#define KOS_DRIVERS_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <sys/types.h>

/* Terminal flags for TTY */
#ifndef ICANON
#define ICANON    0000002
#define ECHO      0000010
#define ECHOE     0000020
#define ECHOK     0000040
#define ISIG      0000001
#define ICRNL     0000400
#define IXON      0002000
#define OPOST     0000001
#define ONLCR     0000004
#define CS8       0000060
#define CREAD     0000200
#define CLOCAL    0004000
#define B9600     0000015
#endif

/* Device types */
#define KOS_DEV_CHAR    1
#define KOS_DEV_BLOCK   2
#define KOS_DEV_NET     3
#define KOS_DEV_TTY     4

/* Device flags */
#define KOS_DEV_FLAG_READONLY   0x01
#define KOS_DEV_FLAG_WRITEONLY  0x02
#define KOS_DEV_FLAG_RDWR       0x03
#define KOS_DEV_FLAG_NONBLOCK   0x04
#define KOS_DEV_FLAG_DMA        0x08
#define KOS_DEV_FLAG_IRQ        0x10

/* IOCTL commands */
#define KOS_IOCTL_RESET         0x1000
#define KOS_IOCTL_GET_INFO      0x1001
#define KOS_IOCTL_SET_CONFIG    0x1002
#define KOS_IOCTL_GET_STATUS    0x1003
#define KOS_IOCTL_FLUSH         0x1004

/* Block device specific */
#define KOS_IOCTL_BLKGETSIZE    0x2000
#define KOS_IOCTL_BLKFLSBUF     0x2001
#define KOS_IOCTL_BLKRRPART     0x2002

/* Network device specific */
#define KOS_IOCTL_NETUP         0x3000
#define KOS_IOCTL_NETDOWN       0x3001
#define KOS_IOCTL_NETSETADDR    0x3002

/* TTY specific */
#define KOS_IOCTL_TTYSETRAW     0x4000
#define KOS_IOCTL_TTYSETCOOKED  0x4001
#define KOS_IOCTL_TTYGETATTR    0x4002

/* Error codes */
#define KOS_ERR_SUCCESS         0
#define KOS_ERR_INVALID_PARAM   -1
#define KOS_ERR_NO_MEMORY       -2
#define KOS_ERR_DEVICE_BUSY     -3
#define KOS_ERR_NOT_SUPPORTED   -4
#define KOS_ERR_IO_ERROR        -5
#define KOS_ERR_TIMEOUT         -6

/* Forward declarations */
struct kos_device;
struct kos_driver;
struct kos_file_ops;

/* DMA descriptor */
typedef struct kos_dma_desc {
    void *virt_addr;
    uint64_t phys_addr;
    size_t size;
    uint32_t flags;
    struct kos_dma_desc *next;
} kos_dma_desc_t;

/* IRQ handler function type */
typedef int (*kos_irq_handler_t)(int irq, void *dev_data);

/* Device file operations */
typedef struct kos_file_ops {
    int (*open)(struct kos_device *dev, int flags);
    int (*close)(struct kos_device *dev);
    ssize_t (*read)(struct kos_device *dev, void *buf, size_t count, off_t offset);
    ssize_t (*write)(struct kos_device *dev, const void *buf, size_t count, off_t offset);
    int (*ioctl)(struct kos_device *dev, unsigned int cmd, unsigned long arg);
    int (*mmap)(struct kos_device *dev, void **addr, size_t length, int prot, int flags, off_t offset);
    int (*flush)(struct kos_device *dev);
    int (*fsync)(struct kos_device *dev);
} kos_file_ops_t;

/* Block device specific operations */
typedef struct kos_block_ops {
    int (*read_block)(struct kos_device *dev, uint64_t block, void *buf);
    int (*write_block)(struct kos_device *dev, uint64_t block, const void *buf);
    int (*read_blocks)(struct kos_device *dev, uint64_t start_block, uint32_t count, void *buf);
    int (*write_blocks)(struct kos_device *dev, uint64_t start_block, uint32_t count, const void *buf);
    int (*format)(struct kos_device *dev);
    int (*get_geometry)(struct kos_device *dev, uint64_t *sectors, uint32_t *sector_size);
} kos_block_ops_t;

/* Network device specific operations */
typedef struct kos_net_ops {
    int (*send_packet)(struct kos_device *dev, const void *data, size_t len);
    int (*receive_packet)(struct kos_device *dev, void *buf, size_t *len);
    int (*set_mac_addr)(struct kos_device *dev, const uint8_t *mac);
    int (*get_mac_addr)(struct kos_device *dev, uint8_t *mac);
    int (*set_mtu)(struct kos_device *dev, uint32_t mtu);
    int (*get_mtu)(struct kos_device *dev, uint32_t *mtu);
    int (*up)(struct kos_device *dev);
    int (*down)(struct kos_device *dev);
    int (*get_stats)(struct kos_device *dev, void *stats);
} kos_net_ops_t;

/* TTY device specific operations */
typedef struct kos_tty_ops {
    int (*write_char)(struct kos_device *dev, char c);
    int (*read_char)(struct kos_device *dev, char *c);
    int (*set_termios)(struct kos_device *dev, const void *termios);
    int (*get_termios)(struct kos_device *dev, void *termios);
    int (*set_winsize)(struct kos_device *dev, uint16_t rows, uint16_t cols);
    int (*get_winsize)(struct kos_device *dev, uint16_t *rows, uint16_t *cols);
    int (*flush_input)(struct kos_device *dev);
    int (*flush_output)(struct kos_device *dev);
} kos_tty_ops_t;

/* Device structure */
typedef struct kos_device {
    char name[64];
    int type;
    int major;
    int minor;
    uint32_t flags;
    
    /* Reference counting */
    int ref_count;
    pthread_mutex_t ref_mutex;
    
    /* Device specific data */
    void *private_data;
    
    /* Operations */
    kos_file_ops_t *fops;
    union {
        kos_block_ops_t *block_ops;
        kos_net_ops_t *net_ops;
        kos_tty_ops_t *tty_ops;
    };
    
    /* DMA support */
    kos_dma_desc_t *dma_desc;
    pthread_mutex_t dma_mutex;
    
    /* IRQ support */
    int irq;
    kos_irq_handler_t irq_handler;
    
    /* Driver reference */
    struct kos_driver *driver;
    
    /* List management */
    struct kos_device *next;
} kos_device_t;

/* Driver structure */
typedef struct kos_driver {
    char name[64];
    int type;
    
    /* Driver operations */
    int (*probe)(kos_device_t *dev);
    int (*remove)(kos_device_t *dev);
    int (*suspend)(kos_device_t *dev);
    int (*resume)(kos_device_t *dev);
    
    /* List management */
    struct kos_driver *next;
} kos_driver_t;

/* Device manager structure */
typedef struct kos_device_manager {
    kos_device_t *devices;
    kos_driver_t *drivers;
    pthread_mutex_t lock;
    int next_major;
} kos_device_manager_t;

/* Base driver functions */
extern kos_device_manager_t *kos_device_manager;

/* Device management functions */
int kos_device_init(void);
void kos_device_cleanup(void);
int kos_device_register(kos_device_t *dev);
int kos_device_unregister(kos_device_t *dev);
kos_device_t *kos_device_find(const char *name);
kos_device_t *kos_device_find_by_major_minor(int major, int minor);

/* Driver management functions */
int kos_driver_register(kos_driver_t *driver);
int kos_driver_unregister(kos_driver_t *driver);
kos_driver_t *kos_driver_find(const char *name);

/* Device reference counting */
void kos_device_get(kos_device_t *dev);
void kos_device_put(kos_device_t *dev);

/* DMA functions */
kos_dma_desc_t *kos_dma_alloc(size_t size, uint32_t flags);
void kos_dma_free(kos_dma_desc_t *desc);
int kos_dma_map(kos_dma_desc_t *desc);
void kos_dma_unmap(kos_dma_desc_t *desc);

/* IRQ functions */
int kos_irq_request(int irq, kos_irq_handler_t handler, const char *name, void *dev_data);
void kos_irq_free(int irq, void *dev_data);
int kos_irq_enable(int irq);
int kos_irq_disable(int irq);

/* Character device functions */
int kos_char_device_create(const char *name, kos_file_ops_t *fops, void *private_data);
int kos_char_device_destroy(const char *name);

/* Block device functions */
int kos_block_device_create(const char *name, kos_file_ops_t *fops, kos_block_ops_t *block_ops, 
                           uint64_t size, uint32_t block_size, void *private_data);
int kos_block_device_destroy(const char *name);

/* Network device functions */
int kos_net_device_create(const char *name, kos_file_ops_t *fops, kos_net_ops_t *net_ops, 
                         const uint8_t *mac_addr, void *private_data);
int kos_net_device_destroy(const char *name);

/* TTY device functions */
int kos_tty_device_create(const char *name, kos_file_ops_t *fops, kos_tty_ops_t *tty_ops, 
                         void *private_data);
int kos_tty_device_destroy(const char *name);

/* Utility functions */
void kos_msleep(int msecs);
uint64_t kos_get_timestamp(void);
void *kos_kmalloc(size_t size);
void kos_kfree(void *ptr);

#endif /* KOS_DRIVERS_H */