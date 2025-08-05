#define _GNU_SOURCE
#include "drivers.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>

/* TTY modes */
#define KOS_TTY_MODE_RAW     0
#define KOS_TTY_MODE_COOKED  1
#define KOS_TTY_MODE_CBREAK  2

/* TTY control characters */
#define KOS_TTY_CTRL_C       0x03
#define KOS_TTY_CTRL_D       0x04
#define KOS_TTY_CTRL_Z       0x1A
#define KOS_TTY_BACKSPACE    0x08
#define KOS_TTY_DELETE       0x7F
#define KOS_TTY_NEWLINE      0x0A
#define KOS_TTY_CARRIAGE_RETURN 0x0D

/* TTY buffer sizes */
#define KOS_TTY_INPUT_BUFFER_SIZE   4096
#define KOS_TTY_OUTPUT_BUFFER_SIZE  4096
#define KOS_TTY_LINE_BUFFER_SIZE    1024

/* TTY termios structure */
typedef struct kos_termios {
    uint32_t c_iflag;    /* input modes */
    uint32_t c_oflag;    /* output modes */
    uint32_t c_cflag;    /* control modes */
    uint32_t c_lflag;    /* local modes */
    uint8_t c_cc[32];    /* control characters */
    uint32_t c_ispeed;   /* input speed */
    uint32_t c_ospeed;   /* output speed */
} kos_termios_t;

/* TTY window size */
typedef struct kos_winsize {
    uint16_t ws_row;     /* rows */
    uint16_t ws_col;     /* columns */
    uint16_t ws_xpixel;  /* horizontal size, pixels */
    uint16_t ws_ypixel;  /* vertical size, pixels */
} kos_winsize_t;

/* TTY device private data */
typedef struct kos_tty_device_data {
    int mode;                              /* TTY mode */
    kos_termios_t termios;                 /* Terminal settings */
    kos_winsize_t winsize;                 /* Window size */
    
    /* Input processing */
    char input_buffer[KOS_TTY_INPUT_BUFFER_SIZE];
    size_t input_head;
    size_t input_tail;
    size_t input_count;
    
    /* Output processing */
    char output_buffer[KOS_TTY_OUTPUT_BUFFER_SIZE];
    size_t output_head;
    size_t output_tail;
    size_t output_count;
    
    /* Line editing */
    char line_buffer[KOS_TTY_LINE_BUFFER_SIZE];
    size_t line_pos;
    size_t line_len;
    bool line_ready;
    
    /* Synchronization */
    pthread_mutex_t input_lock;
    pthread_mutex_t output_lock;
    pthread_cond_t input_cond;
    pthread_cond_t output_cond;
    
    /* Process group management */
    pid_t pgrp;                            /* Process group */
    pid_t session;                         /* Session ID */
    
    /* Flags */
    bool echo;                             /* Echo input */
    bool canonical;                        /* Canonical mode */
    bool isig;                             /* Signal processing */
    bool blocked;                          /* Blocked for input */
    
    /* Statistics */
    uint64_t chars_in;
    uint64_t chars_out;
    uint64_t lines_in;
    uint64_t lines_out;
} kos_tty_device_data_t;

/* Forward declarations */
static int tty_open(kos_device_t *dev, int flags);
static int tty_close(kos_device_t *dev);
static ssize_t tty_read(kos_device_t *dev, void *buf, size_t count, off_t offset);
static ssize_t tty_write(kos_device_t *dev, const void *buf, size_t count, off_t offset);
static int tty_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg);

static int default_write_char(kos_device_t *dev, char c);
static int default_read_char(kos_device_t *dev, char *c);
static int default_set_termios(kos_device_t *dev, const void *termios);
static int default_get_termios(kos_device_t *dev, void *termios);
static int default_set_winsize(kos_device_t *dev, uint16_t rows, uint16_t cols);
static int default_get_winsize(kos_device_t *dev, uint16_t *rows, uint16_t *cols);
static int default_flush_input(kos_device_t *dev);
static int default_flush_output(kos_device_t *dev);

static void tty_process_input_char(kos_device_t *dev, char c);
static void tty_process_output_char(kos_device_t *dev, char c);
static void tty_echo_char(kos_device_t *dev, char c);
static void tty_handle_signal_char(kos_device_t *dev, char c);

/* Default TTY device file operations */
static kos_file_ops_t default_tty_fops = {
    .open = tty_open,
    .close = tty_close,
    .read = tty_read,
    .write = tty_write,
    .ioctl = tty_ioctl,
    .flush = NULL,
    .fsync = NULL,
    .mmap = NULL
};

/* Default TTY device operations */
static kos_tty_ops_t default_tty_ops = {
    .write_char = default_write_char,
    .read_char = default_read_char,
    .set_termios = default_set_termios,
    .get_termios = default_get_termios,
    .set_winsize = default_set_winsize,
    .get_winsize = default_get_winsize,
    .flush_input = default_flush_input,
    .flush_output = default_flush_output
};

/* Circular buffer operations */
static void tty_buffer_put(char *buf, size_t size, size_t *head, size_t *count, char c) {
    if (*count < size) {
        buf[*head] = c;
        *head = (*head + 1) % size;
        (*count)++;
    }
}

static bool tty_buffer_get(char *buf, size_t size, size_t *tail, size_t *count, char *c) {
    if (*count > 0) {
        *c = buf[*tail];
        *tail = (*tail + 1) % size;
        (*count)--;
        return true;
    }
    return false;
}

/* Process input character */
static void tty_process_input_char(kos_device_t *dev, char c) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    
    pthread_mutex_lock(&data->input_lock);
    
    /* Handle special characters in canonical mode */
    if (data->canonical) {
        switch (c) {
            case KOS_TTY_BACKSPACE:
            case KOS_TTY_DELETE:
                if (data->line_len > 0) {
                    data->line_len--;
                    if (data->echo) {
                        tty_echo_char(dev, '\b');
                        tty_echo_char(dev, ' ');
                        tty_echo_char(dev, '\b');
                    }
                }
                pthread_mutex_unlock(&data->input_lock);
                return;
                
            case KOS_TTY_NEWLINE:
            case KOS_TTY_CARRIAGE_RETURN:
                if (data->line_len < KOS_TTY_LINE_BUFFER_SIZE - 1) {
                    data->line_buffer[data->line_len++] = '\n';
                    data->line_buffer[data->line_len] = '\0';
                    data->line_ready = true;
                    data->lines_in++;
                    
                    if (data->echo) {
                        tty_echo_char(dev, '\n');
                    }
                    
                    pthread_cond_signal(&data->input_cond);
                }
                pthread_mutex_unlock(&data->input_lock);
                return;
        }
        
        /* Add to line buffer */
        if (data->line_len < KOS_TTY_LINE_BUFFER_SIZE - 1) {
            data->line_buffer[data->line_len++] = c;
            
            if (data->echo) {
                tty_echo_char(dev, c);
            }
        }
    } else {
        /* Raw mode - add directly to input buffer */
        tty_buffer_put(data->input_buffer, KOS_TTY_INPUT_BUFFER_SIZE, 
                      &data->input_head, &data->input_count, c);
        pthread_cond_signal(&data->input_cond);
    }
    
    data->chars_in++;
    
    /* Handle signal characters */
    if (data->isig) {
        tty_handle_signal_char(dev, c);
    }
    
    pthread_mutex_unlock(&data->input_lock);
}

/* Process output character */
static void tty_process_output_char(kos_device_t *dev, char c) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    
    pthread_mutex_lock(&data->output_lock);
    
    /* Output processing */
    if (c == '\n' && (data->termios.c_oflag & ONLCR)) {
        /* Convert LF to CRLF */
        tty_buffer_put(data->output_buffer, KOS_TTY_OUTPUT_BUFFER_SIZE, 
                      &data->output_head, &data->output_count, '\r');
        data->chars_out++;
    }
    
    tty_buffer_put(data->output_buffer, KOS_TTY_OUTPUT_BUFFER_SIZE, 
                  &data->output_head, &data->output_count, c);
    data->chars_out++;
    
    if (c == '\n') {
        data->lines_out++;
    }
    
    pthread_cond_signal(&data->output_cond);
    pthread_mutex_unlock(&data->output_lock);
}

/* Echo character */
static void tty_echo_char(kos_device_t *dev, char c) {
    if (dev->tty_ops && dev->tty_ops->write_char) {
        dev->tty_ops->write_char(dev, c);
    } else {
        tty_process_output_char(dev, c);
    }
}

/* Handle signal characters */
static void tty_handle_signal_char(kos_device_t *dev, char c) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    
    switch (c) {
        case KOS_TTY_CTRL_C:
            if (data->pgrp > 0) {
                kill(-data->pgrp, SIGINT);
            }
            break;
            
        case KOS_TTY_CTRL_Z:
            if (data->pgrp > 0) {
                kill(-data->pgrp, SIGTSTP);
            }
            break;
            
        case KOS_TTY_CTRL_D:
            /* EOF - handle in read */
            break;
    }
}

/* TTY device open */
static int tty_open(kos_device_t *dev, int flags) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    /* Set session and process group if not already set */
    if (data->session == 0) {
        data->session = getsid(0);
        data->pgrp = getpgrp();
    }
    
    return KOS_ERR_SUCCESS;
}

/* TTY device close */
static int tty_close(kos_device_t *dev) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Flush output */
    if (dev->tty_ops && dev->tty_ops->flush_output) {
        dev->tty_ops->flush_output(dev);
    }
    
    return KOS_ERR_SUCCESS;
}

/* TTY device read */
static ssize_t tty_read(kos_device_t *dev, void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    pthread_mutex_lock(&data->input_lock);
    
    size_t bytes_read = 0;
    
    if (data->canonical) {
        /* Canonical mode - wait for complete line */
        while (!data->line_ready && bytes_read == 0) {
            if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
                pthread_mutex_unlock(&data->input_lock);
                return 0; /* Would block */
            }
            
            pthread_cond_wait(&data->input_cond, &data->input_lock);
        }
        
        if (data->line_ready) {
            size_t to_copy = (data->line_len < count) ? data->line_len : count;
            memcpy(buf, data->line_buffer, to_copy);
            bytes_read = to_copy;
            
            /* Remove copied data from line buffer */
            if (to_copy < data->line_len) {
                memmove(data->line_buffer, data->line_buffer + to_copy, data->line_len - to_copy);
                data->line_len -= to_copy;
            } else {
                data->line_len = 0;
                data->line_ready = false;
            }
        }
    } else {
        /* Raw mode - read available characters */
        while (data->input_count == 0 && bytes_read == 0) {
            if (dev->flags & KOS_DEV_FLAG_NONBLOCK) {
                pthread_mutex_unlock(&data->input_lock);
                return 0; /* Would block */
            }
            
            pthread_cond_wait(&data->input_cond, &data->input_lock);
        }
        
        /* Copy available characters */
        char *cbuf = (char *)buf;
        while (bytes_read < count && data->input_count > 0) {
            char c;
            if (tty_buffer_get(data->input_buffer, KOS_TTY_INPUT_BUFFER_SIZE, 
                              &data->input_tail, &data->input_count, &c)) {
                cbuf[bytes_read++] = c;
            }
        }
    }
    
    pthread_mutex_unlock(&data->input_lock);
    
    return bytes_read;
}

/* TTY device write */
static ssize_t tty_write(kos_device_t *dev, const void *buf, size_t count, off_t offset) {
    if (!dev || !buf) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    const char *cbuf = (const char *)buf;
    
    for (size_t i = 0; i < count; i++) {
        if (dev->tty_ops && dev->tty_ops->write_char) {
            int ret = dev->tty_ops->write_char(dev, cbuf[i]);
            if (ret != KOS_ERR_SUCCESS) {
                return (i > 0) ? i : ret;
            }
        } else {
            tty_process_output_char(dev, cbuf[i]);
        }
    }
    
    return count;
}

/* TTY device ioctl */
static int tty_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg) {
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_IO_ERROR;
    }
    
    switch (cmd) {
        case KOS_IOCTL_TTYSETRAW:
            data->mode = KOS_TTY_MODE_RAW;
            data->canonical = false;
            data->echo = false;
            data->isig = false;
            break;
            
        case KOS_IOCTL_TTYSETCOOKED:
            data->mode = KOS_TTY_MODE_COOKED;
            data->canonical = true;
            data->echo = true;
            data->isig = true;
            break;
            
        case KOS_IOCTL_TTYGETATTR:
            if (arg && dev->tty_ops && dev->tty_ops->get_termios) {
                return dev->tty_ops->get_termios(dev, (void *)arg);
            }
            return KOS_ERR_NOT_SUPPORTED;
            
        case KOS_IOCTL_GET_INFO:
            if (arg) {
                struct {
                    int mode;
                    kos_winsize_t winsize;
                    uint64_t chars_in;
                    uint64_t chars_out;
                    uint64_t lines_in;
                    uint64_t lines_out;
                    bool canonical;
                    bool echo;
                    bool isig;
                } *info = (void *)arg;
                
                pthread_mutex_lock(&data->input_lock);
                pthread_mutex_lock(&data->output_lock);
                
                info->mode = data->mode;
                info->winsize = data->winsize;
                info->chars_in = data->chars_in;
                info->chars_out = data->chars_out;
                info->lines_in = data->lines_in;
                info->lines_out = data->lines_out;
                info->canonical = data->canonical;
                info->echo = data->echo;
                info->isig = data->isig;
                
                pthread_mutex_unlock(&data->output_lock);
                pthread_mutex_unlock(&data->input_lock);
            }
            break;
            
        default:
            return KOS_ERR_NOT_SUPPORTED;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Default TTY operations */
static int default_write_char(kos_device_t *dev, char c) {
    tty_process_output_char(dev, c);
    return KOS_ERR_SUCCESS;
}

static int default_read_char(kos_device_t *dev, char *c) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data || !c) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&data->output_lock);
    
    bool got_char = tty_buffer_get(data->output_buffer, KOS_TTY_OUTPUT_BUFFER_SIZE, 
                                  &data->output_tail, &data->output_count, c);
    
    pthread_mutex_unlock(&data->output_lock);
    
    return got_char ? KOS_ERR_SUCCESS : KOS_ERR_IO_ERROR;
}

static int default_set_termios(kos_device_t *dev, const void *termios) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data || !termios) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy(&data->termios, termios, sizeof(kos_termios_t));
    
    /* Update flags based on termios */
    data->canonical = (data->termios.c_lflag & ICANON) != 0;
    data->echo = (data->termios.c_lflag & ECHO) != 0;
    data->isig = (data->termios.c_lflag & ISIG) != 0;
    
    return KOS_ERR_SUCCESS;
}

static int default_get_termios(kos_device_t *dev, void *termios) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data || !termios) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    memcpy(termios, &data->termios, sizeof(kos_termios_t));
    return KOS_ERR_SUCCESS;
}

static int default_set_winsize(kos_device_t *dev, uint16_t rows, uint16_t cols) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    data->winsize.ws_row = rows;
    data->winsize.ws_col = cols;
    
    /* Send SIGWINCH to process group */
    if (data->pgrp > 0) {
        kill(-data->pgrp, SIGWINCH);
    }
    
    return KOS_ERR_SUCCESS;
}

static int default_get_winsize(kos_device_t *dev, uint16_t *rows, uint16_t *cols) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (rows) *rows = data->winsize.ws_row;
    if (cols) *cols = data->winsize.ws_col;
    
    return KOS_ERR_SUCCESS;
}

static int default_flush_input(kos_device_t *dev) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&data->input_lock);
    
    data->input_head = 0;
    data->input_tail = 0;
    data->input_count = 0;
    data->line_len = 0;
    data->line_ready = false;
    
    pthread_mutex_unlock(&data->input_lock);
    
    return KOS_ERR_SUCCESS;
}

static int default_flush_output(kos_device_t *dev) {
    kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
    if (!data) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&data->output_lock);
    
    /* Wait for output buffer to empty */
    while (data->output_count > 0) {
        pthread_cond_wait(&data->output_cond, &data->output_lock);
    }
    
    pthread_mutex_unlock(&data->output_lock);
    
    return KOS_ERR_SUCCESS;
}

/* Public function to inject input into TTY */
int kos_tty_input_char(kos_device_t *dev, char c) {
    if (!dev || dev->type != KOS_DEV_TTY) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    tty_process_input_char(dev, c);
    return KOS_ERR_SUCCESS;
}

/* Create a TTY device */
int kos_tty_device_create(const char *name, kos_file_ops_t *fops, kos_tty_ops_t *tty_ops, 
                         void *private_data) {
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
    dev->type = KOS_DEV_TTY;
    dev->major = 0; /* Will be assigned by register function */
    dev->minor = 0;
    dev->flags = KOS_DEV_FLAG_RDWR;
    dev->irq = -1;
    
    /* Use provided operations or default ones */
    dev->fops = fops ? fops : &default_tty_fops;
    dev->tty_ops = tty_ops ? tty_ops : &default_tty_ops;
    
    /* Create private data */
    if (private_data) {
        dev->private_data = private_data;
    } else {
        kos_tty_device_data_t *data = (kos_tty_device_data_t *)malloc(sizeof(kos_tty_device_data_t));
        if (!data) {
            free(dev);
            return KOS_ERR_NO_MEMORY;
        }
        
        memset(data, 0, sizeof(kos_tty_device_data_t));
        
        /* Initialize TTY data */
        data->mode = KOS_TTY_MODE_COOKED;
        data->canonical = true;
        data->echo = true;
        data->isig = true;
        
        /* Default window size */
        data->winsize.ws_row = 24;
        data->winsize.ws_col = 80;
        
        /* Initialize termios with default settings */
        data->termios.c_iflag = ICRNL | IXON;
        data->termios.c_oflag = OPOST | ONLCR;
        data->termios.c_cflag = CS8 | CREAD | CLOCAL;
        data->termios.c_lflag = ISIG | ICANON | ECHO | ECHOE | ECHOK;
        data->termios.c_ispeed = data->termios.c_ospeed = B9600;
        
        /* Initialize mutexes and conditions */
        if (pthread_mutex_init(&data->input_lock, NULL) != 0 ||
            pthread_mutex_init(&data->output_lock, NULL) != 0 ||
            pthread_cond_init(&data->input_cond, NULL) != 0 ||
            pthread_cond_init(&data->output_cond, NULL) != 0) {
            
            pthread_mutex_destroy(&data->input_lock);
            pthread_mutex_destroy(&data->output_lock);
            pthread_cond_destroy(&data->input_cond);
            pthread_cond_destroy(&data->output_cond);
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
            kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
            pthread_cond_destroy(&data->output_cond);
            pthread_cond_destroy(&data->input_cond);
            pthread_mutex_destroy(&data->output_lock);
            pthread_mutex_destroy(&data->input_lock);
            free(data);
        }
        free(dev);
        return ret;
    }
    
    return KOS_ERR_SUCCESS;
}

/* Destroy a TTY device */
int kos_tty_device_destroy(const char *name) {
    if (!name) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    kos_device_t *dev = kos_device_find(name);
    if (!dev) {
        return KOS_ERR_INVALID_PARAM;
    }
    
    if (dev->type != KOS_DEV_TTY) {
        kos_device_put(dev);
        return KOS_ERR_INVALID_PARAM;
    }
    
    /* Flush output */
    if (dev->tty_ops && dev->tty_ops->flush_output) {
        dev->tty_ops->flush_output(dev);
    }
    
    /* Unregister the device */
    int ret = kos_device_unregister(dev);
    if (ret != KOS_ERR_SUCCESS) {
        kos_device_put(dev);
        return ret;
    }
    
    /* Cleanup private data if it's the default type */
    if (dev->private_data && dev->fops == &default_tty_fops) {
        kos_tty_device_data_t *data = (kos_tty_device_data_t *)dev->private_data;
        
        pthread_cond_destroy(&data->output_cond);
        pthread_cond_destroy(&data->input_cond);
        pthread_mutex_destroy(&data->output_lock);
        pthread_mutex_destroy(&data->input_lock);
        free(data);
    }
    
    kos_device_put(dev);
    free(dev);
    
    return KOS_ERR_SUCCESS;
}