/*
 * KOS Device Driver Error Handling and Edge Cases
 * Comprehensive device driver error recovery and validation
 */

#include "drivers.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>
#include <fcntl.h>
#include <unistd.h>

/* Device driver error types */
typedef enum {
    DRV_ERROR_NONE = 0,
    DRV_ERROR_INVALID_DEVICE,      /* Invalid device pointer */
    DRV_ERROR_DEVICE_NOT_FOUND,    /* Device not found */
    DRV_ERROR_DEVICE_BUSY,         /* Device busy */
    DRV_ERROR_DEVICE_TIMEOUT,      /* Device timeout */
    DRV_ERROR_DEVICE_OFFLINE,      /* Device offline */
    DRV_ERROR_INVALID_OPERATION,   /* Invalid operation */
    DRV_ERROR_PERMISSION_DENIED,   /* Permission denied */
    DRV_ERROR_RESOURCE_EXHAUSTED,  /* Resource exhaustion */
    DRV_ERROR_HARDWARE_FAILURE,    /* Hardware failure */
    DRV_ERROR_FIRMWARE_ERROR,      /* Firmware error */
    DRV_ERROR_DRIVER_MISMATCH,     /* Driver version mismatch */
    DRV_ERROR_INTERRUPT_STORM,     /* Interrupt storm */
    DRV_ERROR_DMA_ERROR,           /* DMA error */
    DRV_ERROR_POWER_FAILURE,       /* Power failure */
    DRV_ERROR_THERMAL_SHUTDOWN,    /* Thermal shutdown */
    DRV_ERROR_BUS_ERROR,           /* Bus error */
    DRV_ERROR_PROTOCOL_ERROR,      /* Protocol error */
    DRV_ERROR_CALIBRATION_FAILED,  /* Calibration failed */
    DRV_ERROR_SECURITY_VIOLATION   /* Security violation */
} drv_error_type_t;

/* Error recovery strategies */
typedef enum {
    DRV_RECOVERY_IGNORE = 0,
    DRV_RECOVERY_LOG,
    DRV_RECOVERY_RETRY,
    DRV_RECOVERY_RESET_DEVICE,
    DRV_RECOVERY_REINITIALIZE,
    DRV_RECOVERY_DISABLE_DEVICE,
    DRV_RECOVERY_FALLBACK_DRIVER,
    DRV_RECOVERY_POWER_CYCLE,
    DRV_RECOVERY_FIRMWARE_RELOAD,
    DRV_RECOVERY_PANIC
} drv_recovery_t;

/* Device driver error context */
typedef struct {
    drv_error_type_t type;
    const char *message;
    kos_device_t *device;
    const char *driver_name;
    uint32_t error_code;
    uint64_t timestamp;
    const char *file;
    int line;
    const char *function;
    drv_recovery_t recovery;
    void *extra_data;
    uint32_t retry_count;
} drv_error_ctx_t;

/* Device driver error statistics */
static struct {
    uint64_t total_errors;
    uint64_t invalid_device_errors;
    uint64_t device_not_found_errors;
    uint64_t device_busy_errors;
    uint64_t device_timeout_errors;
    uint64_t device_offline_errors;
    uint64_t invalid_operation_errors;
    uint64_t permission_denied_errors;
    uint64_t resource_exhausted_errors;
    uint64_t hardware_failure_errors;
    uint64_t firmware_error_errors;
    uint64_t driver_mismatch_errors;
    uint64_t interrupt_storm_errors;
    uint64_t dma_error_errors;
    uint64_t power_failure_errors;
    uint64_t thermal_shutdown_errors;
    uint64_t bus_error_errors;
    uint64_t protocol_error_errors;
    uint64_t calibration_failed_errors;
    uint64_t security_violation_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t devices_reset;
    uint64_t devices_disabled;
    uint64_t firmware_reloads;
    uint64_t power_cycles;
    pthread_mutex_t lock;
} drv_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Device health monitoring */
typedef struct device_health {
    kos_device_t *device;
    uint64_t last_activity;
    uint32_t error_count;
    uint32_t consecutive_errors;
    bool quarantined;
    struct device_health *next;
} device_health_t;

static device_health_t *device_health_list = NULL;
static pthread_mutex_t health_lock = PTHREAD_MUTEX_INITIALIZER;

/* Interrupt storm detection */
typedef struct {
    uint32_t irq;
    uint64_t last_reset_time;
    uint32_t interrupt_count;
    uint32_t max_per_second;
    bool storm_detected;
} interrupt_monitor_t;

static interrupt_monitor_t interrupt_monitors[MAX_IRQ_LINES];
static pthread_mutex_t interrupt_lock = PTHREAD_MUTEX_INITIALIZER;

/* Validate device structure */
static int validate_device_struct(kos_device_t *dev, const char *context)
{
    if (!dev) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_DEVICE,
            .message = "NULL device pointer",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    /* Check device name */
    if (!dev->name[0]) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_DEVICE,
            .message = "Device has no name",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    /* Check device type */
    if (dev->type >= KOS_DEV_MAX) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_DEVICE,
            .message = "Invalid device type",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_DISABLE_DEVICE
        };
        return handle_device_error(&ctx);
    }

    /* Check file operations */
    if (!dev->fops) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_DEVICE,
            .message = "Device has no file operations",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_DISABLE_DEVICE
        };
        return handle_device_error(&ctx);
    }

    return 0;
}

/* Validate device operation parameters */
static int validate_device_operation(kos_device_t *dev, const char *operation, 
                                    void *buffer, size_t size, const char *context)
{
    if (validate_device_struct(dev, context) != 0) {
        return -1;
    }

    /* Check if device is online */
    if (dev->flags & KOS_DEV_FLAG_OFFLINE) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_DEVICE_OFFLINE,
            .message = "Device is offline",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_REINITIALIZE
        };
        return handle_device_error(&ctx);
    }

    /* Check buffer validity for read/write operations */
    if ((strcmp(operation, "read") == 0 || strcmp(operation, "write") == 0) && 
        (!buffer || size == 0)) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_OPERATION,
            .message = "Invalid buffer for I/O operation",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    /* Check for excessive I/O size */
    if (size > MAX_IO_SIZE) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_OPERATION,
            .message = "I/O size too large",
            .device = dev,
            .error_code = size,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    return 0;
}

/* Detect interrupt storms */
static int detect_interrupt_storm(uint32_t irq)
{
    if (irq >= MAX_IRQ_LINES) {
        return 0;
    }

    pthread_mutex_lock(&interrupt_lock);

    interrupt_monitor_t *monitor = &interrupt_monitors[irq];
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;

    /* Reset counter every second */
    if (now_us - monitor->last_reset_time >= 1000000) {
        monitor->interrupt_count = 0;
        monitor->last_reset_time = now_us;
        monitor->storm_detected = false;
    }

    monitor->interrupt_count++;

    /* Check for storm */
    if (monitor->interrupt_count > monitor->max_per_second && !monitor->storm_detected) {
        monitor->storm_detected = true;
        
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INTERRUPT_STORM,
            .message = "Interrupt storm detected",
            .device = NULL, /* IRQ-based, not device-specific */
            .error_code = irq,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_DISABLE_DEVICE
        };

        pthread_mutex_unlock(&interrupt_lock);
        return handle_device_error(&ctx);
    }

    pthread_mutex_unlock(&interrupt_lock);
    return 0;
}

/* Monitor device health */
static void update_device_health(kos_device_t *dev, bool error_occurred)
{
    pthread_mutex_lock(&health_lock);

    /* Find or create health entry */
    device_health_t *health = device_health_list;
    while (health && health->device != dev) {
        health = health->next;
    }

    if (!health) {
        health = malloc(sizeof(device_health_t));
        if (health) {
            health->device = dev;
            health->last_activity = time(NULL);
            health->error_count = 0;
            health->consecutive_errors = 0;
            health->quarantined = false;
            health->next = device_health_list;
            device_health_list = health;
        } else {
            pthread_mutex_unlock(&health_lock);
            return;
        }
    }

    health->last_activity = time(NULL);

    if (error_occurred) {
        health->error_count++;
        health->consecutive_errors++;

        /* Quarantine device if too many consecutive errors */
        if (health->consecutive_errors >= MAX_CONSECUTIVE_ERRORS && !health->quarantined) {
            health->quarantined = true;
            dev->flags |= KOS_DEV_FLAG_OFFLINE;

            drv_error_ctx_t ctx = {
                .type = DRV_ERROR_HARDWARE_FAILURE,
                .message = "Device quarantined due to excessive errors",
                .device = dev,
                .error_code = health->consecutive_errors,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = __func__,
                .recovery = DRV_RECOVERY_DISABLE_DEVICE
            };
            
            pthread_mutex_unlock(&health_lock);
            handle_device_error(&ctx);
            return;
        }
    } else {
        health->consecutive_errors = 0;
    }

    pthread_mutex_unlock(&health_lock);
}

/* Check device timeout */
static int check_device_timeout(kos_device_t *dev, uint64_t start_time, uint32_t timeout_ms)
{
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t elapsed_ms = (now.tv_sec * 1000ULL + now.tv_usec / 1000) - start_time;

    if (elapsed_ms > timeout_ms) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_DEVICE_TIMEOUT,
            .message = "Device operation timeout",
            .device = dev,
            .error_code = elapsed_ms,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_RESET_DEVICE
        };
        return handle_device_error(&ctx);
    }

    return 0;
}

/* Validate DMA operation */
static int validate_dma_operation(kos_device_t *dev, void *buffer, size_t size, int direction)
{
    if (!buffer || size == 0) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_DMA_ERROR,
            .message = "Invalid DMA buffer",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    /* Check buffer alignment */
    if (((uintptr_t)buffer & (DMA_ALIGNMENT - 1)) != 0) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_DMA_ERROR,
            .message = "DMA buffer not aligned",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    /* Check DMA size limits */
    if (size > MAX_DMA_SIZE) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_DMA_ERROR,
            .message = "DMA size too large",
            .device = dev,
            .error_code = size,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_LOG
        };
        return handle_device_error(&ctx);
    }

    return 0;
}

/* Log device driver error */
static void log_device_error(const drv_error_ctx_t *ctx)
{
    pthread_mutex_lock(&drv_error_stats.lock);
    drv_error_stats.total_errors++;

    switch (ctx->type) {
        case DRV_ERROR_INVALID_DEVICE:
            drv_error_stats.invalid_device_errors++;
            break;
        case DRV_ERROR_DEVICE_NOT_FOUND:
            drv_error_stats.device_not_found_errors++;
            break;
        case DRV_ERROR_DEVICE_BUSY:
            drv_error_stats.device_busy_errors++;
            break;
        case DRV_ERROR_DEVICE_TIMEOUT:
            drv_error_stats.device_timeout_errors++;
            break;
        case DRV_ERROR_DEVICE_OFFLINE:
            drv_error_stats.device_offline_errors++;
            break;
        case DRV_ERROR_INVALID_OPERATION:
            drv_error_stats.invalid_operation_errors++;
            break;
        case DRV_ERROR_PERMISSION_DENIED:
            drv_error_stats.permission_denied_errors++;
            break;
        case DRV_ERROR_RESOURCE_EXHAUSTED:
            drv_error_stats.resource_exhausted_errors++;
            break;
        case DRV_ERROR_HARDWARE_FAILURE:
            drv_error_stats.hardware_failure_errors++;
            break;
        case DRV_ERROR_FIRMWARE_ERROR:
            drv_error_stats.firmware_error_errors++;
            break;
        case DRV_ERROR_DRIVER_MISMATCH:
            drv_error_stats.driver_mismatch_errors++;
            break;
        case DRV_ERROR_INTERRUPT_STORM:
            drv_error_stats.interrupt_storm_errors++;
            break;
        case DRV_ERROR_DMA_ERROR:
            drv_error_stats.dma_error_errors++;
            break;
        case DRV_ERROR_POWER_FAILURE:
            drv_error_stats.power_failure_errors++;
            break;
        case DRV_ERROR_THERMAL_SHUTDOWN:
            drv_error_stats.thermal_shutdown_errors++;
            break;
        case DRV_ERROR_BUS_ERROR:
            drv_error_stats.bus_error_errors++;
            break;
        case DRV_ERROR_PROTOCOL_ERROR:
            drv_error_stats.protocol_error_errors++;
            break;
        case DRV_ERROR_CALIBRATION_FAILED:
            drv_error_stats.calibration_failed_errors++;
            break;
        case DRV_ERROR_SECURITY_VIOLATION:
            drv_error_stats.security_violation_errors++;
            break;
        default:
            break;
    }

    pthread_mutex_unlock(&drv_error_stats.lock);

    /* Log error details */
    printf("[DRV ERROR] Type: %d, Message: %s\n", ctx->type, ctx->message);
    if (ctx->device) {
        printf("[DRV ERROR] Device: %s (Type: %d, Major: %d, Minor: %d)\n",
               ctx->device->name, ctx->device->type, ctx->device->major, ctx->device->minor);
    }
    if (ctx->driver_name) {
        printf("[DRV ERROR] Driver: %s\n", ctx->driver_name);
    }
    if (ctx->error_code) {
        printf("[DRV ERROR] Error code: %u\n", ctx->error_code);
    }
    printf("[DRV ERROR] Location: %s:%d in %s()\n",
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle device driver error with recovery */
int handle_device_error(drv_error_ctx_t *ctx)
{
    log_device_error(ctx);

    pthread_mutex_lock(&drv_error_stats.lock);
    drv_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&drv_error_stats.lock);

    /* Update device health */
    if (ctx->device) {
        update_device_health(ctx->device, true);
    }

    switch (ctx->recovery) {
        case DRV_RECOVERY_IGNORE:
            return 0;

        case DRV_RECOVERY_LOG:
            /* Already logged above */
            return 0;

        case DRV_RECOVERY_RETRY:
            if (ctx->retry_count < MAX_RETRY_COUNT) {
                ctx->retry_count++;
                usleep(1000 * ctx->retry_count); /* Exponential backoff */
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
                return -EAGAIN; /* Signal retry */
            }
            return -1; /* Give up */

        case DRV_RECOVERY_RESET_DEVICE:
            if (ctx->device) {
                printf("[DRV RECOVERY] Resetting device %s\n", ctx->device->name);
                /* Reset device hardware state */
                if (ctx->device->fops && ctx->device->fops->ioctl) {
                    ctx->device->fops->ioctl(ctx->device, KOS_IOCTL_RESET, 0);
                }
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.devices_reset++;
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_REINITIALIZE:
            if (ctx->device) {
                printf("[DRV RECOVERY] Reinitializing device %s\n", ctx->device->name);
                /* Reinitialize device */
                device_reinitialize(ctx->device);
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_DISABLE_DEVICE:
            if (ctx->device) {
                printf("[DRV RECOVERY] Disabling device %s\n", ctx->device->name);
                ctx->device->flags |= KOS_DEV_FLAG_OFFLINE;
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.devices_disabled++;
                drv_error_stats.recoveries_successful++;  
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_FALLBACK_DRIVER:
            if (ctx->device) {
                printf("[DRV RECOVERY] Switching to fallback driver for %s\n", ctx->device->name);
                /* Load fallback driver */
                load_fallback_driver(ctx->device);
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_POWER_CYCLE:
            if (ctx->device) {
                printf("[DRV RECOVERY] Power cycling device %s\n", ctx->device->name);
                /* Power cycle device */
                device_power_cycle(ctx->device);
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.power_cycles++;
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_FIRMWARE_RELOAD:
            if (ctx->device) {
                printf("[DRV RECOVERY] Reloading firmware for device %s\n", ctx->device->name);
                /* Reload device firmware */
                device_reload_firmware(ctx->device);
                pthread_mutex_lock(&drv_error_stats.lock);
                drv_error_stats.firmware_reloads++;
                drv_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&drv_error_stats.lock);
            }
            return 0;

        case DRV_RECOVERY_PANIC:
            printf("[DRV PANIC] Unrecoverable device error - system halting\n");
            abort();

        default:
            return -1;
    }
}

/* Safe device I/O operations with error handling */
ssize_t safe_device_read(kos_device_t *dev, void *buffer, size_t count, off_t offset)
{
    if (validate_device_operation(dev, "read", buffer, count, "safe_device_read") != 0) {
        return -1;
    }

    struct timeval start_time;
    gettimeofday(&start_time, NULL);
    uint64_t start_ms = start_time.tv_sec * 1000ULL + start_time.tv_usec / 1000;

    ssize_t result = dev->fops->read(dev, buffer, count, offset);

    /* Check for timeout */
    if (check_device_timeout(dev, start_ms, DEFAULT_IO_TIMEOUT_MS) != 0) {
        return -ETIME;
    }

    /* Update health on successful operation */
    if (result >= 0) {
        update_device_health(dev, false);
    } else {
        update_device_health(dev, true);
    }

    return result;
}

ssize_t safe_device_write(kos_device_t *dev, const void *buffer, size_t count, off_t offset)
{
    if (validate_device_operation(dev, "write", (void*)buffer, count, "safe_device_write") != 0) {
        return -1;
    }

    struct timeval start_time;
    gettimeofday(&start_time, NULL);
    uint64_t start_ms = start_time.tv_sec * 1000ULL + start_time.tv_usec / 1000;

    ssize_t result = dev->fops->write(dev, buffer, count, offset);

    /* Check for timeout */
    if (check_device_timeout(dev, start_ms, DEFAULT_IO_TIMEOUT_MS) != 0) {
        return -ETIME;
    }

    /* Update health on successful operation */
    if (result >= 0) {
        update_device_health(dev, false);
    } else {
        update_device_health(dev, true);
    }

    return result;
}

int safe_device_ioctl(kos_device_t *dev, unsigned int cmd, unsigned long arg)
{
    if (validate_device_struct(dev, "safe_device_ioctl") != 0) {
        return -1;
    }

    if (!dev->fops->ioctl) {
        drv_error_ctx_t ctx = {
            .type = DRV_ERROR_INVALID_OPERATION,
            .message = "Device does not support ioctl",
            .device = dev,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = DRV_RECOVERY_LOG
        };
        handle_device_error(&ctx);
        return -ENOTTY;
    }

    int result = dev->fops->ioctl(dev, cmd, arg);

    /* Update health on operation result */
    update_device_health(dev, result < 0);

    return result;
}

/* Comprehensive device health check */
int device_health_check(void)
{
    int unhealthy_devices = 0;

    pthread_mutex_lock(&health_lock);

    device_health_t *health = device_health_list;
    while (health) {
        /* Check for devices that haven't been active */
        uint64_t now = time(NULL);
        if (now - health->last_activity > DEVICE_INACTIVITY_THRESHOLD) {
            if (!health->quarantined) {
                drv_error_ctx_t ctx = {
                    .type = DRV_ERROR_DEVICE_OFFLINE,
                    .message = "Device inactive for too long",
                    .device = health->device,
                    .error_code = now - health->last_activity,
                    .timestamp = time(NULL),
                    .file = __FILE__,
                    .line = __LINE__,
                    .function = __func__,
                    .recovery = DRV_RECOVERY_REINITIALIZE
                };
                handle_device_error(&ctx);
                unhealthy_devices++;
            }
        }

        /* Check error rates */
        if (health->error_count > MAX_ERROR_RATE) {
            unhealthy_devices++;
        }

        health = health->next;
    }

    pthread_mutex_unlock(&health_lock);

    return unhealthy_devices;
}

/* Get device driver error statistics */
void drv_get_error_stats(void)
{
    pthread_mutex_lock(&drv_error_stats.lock);

    printf("\nDevice Driver Error Statistics:\n");
    printf("===============================\n");
    printf("Total errors:              %lu\n", drv_error_stats.total_errors);
    printf("Invalid device errors:     %lu\n", drv_error_stats.invalid_device_errors);
    printf("Device not found errors:   %lu\n", drv_error_stats.device_not_found_errors);
    printf("Device busy errors:        %lu\n", drv_error_stats.device_busy_errors);
    printf("Device timeout errors:     %lu\n", drv_error_stats.device_timeout_errors);
    printf("Device offline errors:     %lu\n", drv_error_stats.device_offline_errors);
    printf("Invalid operation errors:  %lu\n", drv_error_stats.invalid_operation_errors);
    printf("Permission denied errors:  %lu\n", drv_error_stats.permission_denied_errors);
    printf("Resource exhausted errors: %lu\n", drv_error_stats.resource_exhausted_errors);
    printf("Hardware failure errors:   %lu\n", drv_error_stats.hardware_failure_errors);
    printf("Firmware error errors:     %lu\n", drv_error_stats.firmware_error_errors);
    printf("Driver mismatch errors:    %lu\n", drv_error_stats.driver_mismatch_errors);
    printf("Interrupt storm errors:    %lu\n", drv_error_stats.interrupt_storm_errors);
    printf("DMA error errors:          %lu\n", drv_error_stats.dma_error_errors);
    printf("Power failure errors:      %lu\n", drv_error_stats.power_failure_errors);
    printf("Thermal shutdown errors:   %lu\n", drv_error_stats.thermal_shutdown_errors);
    printf("Bus error errors:          %lu\n", drv_error_stats.bus_error_errors);
    printf("Protocol error errors:     %lu\n", drv_error_stats.protocol_error_errors);
    printf("Calibration failed errors: %lu\n", drv_error_stats.calibration_failed_errors);
    printf("Security violation errors: %lu\n", drv_error_stats.security_violation_errors);
    printf("Recovery attempts:         %lu\n", drv_error_stats.recoveries_attempted);
    printf("Recovery successes:        %lu\n", drv_error_stats.recoveries_successful);
    printf("Devices reset:             %lu\n", drv_error_stats.devices_reset);
    printf("Devices disabled:          %lu\n", drv_error_stats.devices_disabled);
    printf("Firmware reloads:          %lu\n", drv_error_stats.firmware_reloads);
    printf("Power cycles:              %lu\n", drv_error_stats.power_cycles);

    if (drv_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)drv_error_stats.recoveries_successful / 
                             drv_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate:     %.1f%%\n", success_rate);
    }

    pthread_mutex_unlock(&drv_error_stats.lock);
}

/* Initialize device driver error handling */
void drv_error_init(void)
{
    /* Initialize interrupt monitors */
    for (int i = 0; i < MAX_IRQ_LINES; i++) {
        interrupt_monitors[i].irq = i;
        interrupt_monitors[i].max_per_second = 1000; /* Default threshold */
        interrupt_monitors[i].storm_detected = false;
        interrupt_monitors[i].interrupt_count = 0;
        interrupt_monitors[i].last_reset_time = 0;
    }

    printf("Device driver error handling initialized\n");
}

/* Cleanup device driver error handling */
void drv_error_cleanup(void)
{
    pthread_mutex_lock(&health_lock);
    
    device_health_t *health = device_health_list;
    while (health) {
        device_health_t *next = health->next;
        free(health);
        health = next;
    }
    device_health_list = NULL;
    
    pthread_mutex_unlock(&health_lock);
}

/* Macros for easy error checking */
#define DRV_VALIDATE_DEVICE(dev, context) \
    if (validate_device_struct(dev, context) != 0) return -1

#define DRV_CHECK_DEVICE_ONLINE(dev) \
    if (dev->flags & KOS_DEV_FLAG_OFFLINE) { \
        drv_error_ctx_t ctx = { \
            .type = DRV_ERROR_DEVICE_OFFLINE, \
            .message = "Device is offline", \
            .device = dev, \
            .timestamp = time(NULL), \
            .file = __FILE__, \
            .line = __LINE__, \
            .function = __func__, \
            .recovery = DRV_RECOVERY_REINITIALIZE \
        }; \
        handle_device_error(&ctx); \
        return -ENODEV; \
    }

#define DRV_UPDATE_HEALTH(dev, error) \
    update_device_health(dev, error)