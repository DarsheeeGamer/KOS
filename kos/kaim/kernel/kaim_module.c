/*
 * KAIM Kernel Module - Production-ready implementation
 * This would be compiled as kaim.ko for Linux kernel
 */

#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/device.h>
#include <linux/cdev.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/ioctl.h>
#include <linux/list.h>
#include <linux/spinlock.h>
#include <linux/hashtable.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/security.h>
#include <linux/cred.h>
#include <linux/sched.h>
#include <linux/pid.h>
#include <linux/time.h>
#include <linux/crypto.h>
#include <linux/scatterlist.h>

#define KAIM_DEVICE_NAME "kaim"
#define KAIM_CLASS_NAME "kaim"
#define KAIM_MAJOR 0  /* Dynamic allocation */

/* Permission flags */
#define KROOT     0x00000001
#define KSYSTEM   0x00000002
#define KUSR      0x00000004
#define KAM       0x00000008
#define KNET      0x00000010
#define KDEV      0x00000020
#define KPROC     0x00000040
#define KFILE_R   0x00000080
#define KFILE_W   0x00000100
#define KFILE_X   0x00000200
#define KMEM      0x00000400
#define KLOG      0x00000800
#define KSEC      0x00001000
#define KAUD      0x00002000
#define KCFG      0x00004000
#define KUPD      0x00008000
#define KSRV      0x00010000
#define KDBG      0x00020000

/* ioctl commands */
#define KAIM_IOCTL_MAGIC 'K'
#define KAIM_IOCTL_ELEVATE    _IOW(KAIM_IOCTL_MAGIC, 1, struct kaim_elevate_req)
#define KAIM_IOCTL_STATUS     _IOR(KAIM_IOCTL_MAGIC, 2, struct kaim_status)
#define KAIM_IOCTL_SESSION    _IOW(KAIM_IOCTL_MAGIC, 3, struct kaim_session_req)
#define KAIM_IOCTL_DEVICE     _IOWR(KAIM_IOCTL_MAGIC, 4, struct kaim_device_req)
#define KAIM_IOCTL_CHECK_PERM _IOR(KAIM_IOCTL_MAGIC, 5, struct kaim_perm_check)
#define KAIM_IOCTL_DROP_PERM  _IOW(KAIM_IOCTL_MAGIC, 6, struct kaim_perm_drop)
#define KAIM_IOCTL_AUDIT      _IOR(KAIM_IOCTL_MAGIC, 7, struct kaim_audit_req)

/* Data structures */
struct kaim_process {
    struct hlist_node hnode;
    pid_t pid;
    uid_t uid;
    gid_t gid;
    u32 flags;
    u32 elevated_flags;
    unsigned long elevated_until;
    char comm[TASK_COMM_LEN];
    spinlock_t lock;
    struct rcu_head rcu;
};

struct kaim_device_entry {
    struct list_head list;
    char name[64];
    int major;
    int minor;
    umode_t mode;
    uid_t owner_uid;
    gid_t owner_gid;
};

struct kaim_audit_entry {
    struct list_head list;
    unsigned long timestamp;
    char action[32];
    pid_t pid;
    char details[128];
};

/* ioctl structures */
struct kaim_elevate_req {
    pid_t target_pid;
    u32 flags;
    u32 duration;  /* seconds */
};

struct kaim_status {
    char version[32];
    u32 process_count;
    u32 device_count;
    u64 elevations;
    u64 device_opens;
    u64 permission_checks;
    u64 denials;
};

struct kaim_device_req {
    char device[64];
    char mode[4];
    int fd;  /* returned */
};

struct kaim_perm_check {
    pid_t pid;
    u32 flag;
    int result;
};

struct kaim_perm_drop {
    pid_t pid;
    u32 flag;
};

struct kaim_audit_req {
    u32 count;
    char buffer[4096];
};

/* Global variables */
static int kaim_major;
static struct class *kaim_class;
static struct device *kaim_device;
static struct cdev kaim_cdev;

/* Process hash table */
#define KAIM_HASH_BITS 10
static DEFINE_HASHTABLE(kaim_processes, KAIM_HASH_BITS);
static DEFINE_SPINLOCK(kaim_process_lock);

/* Device list */
static LIST_HEAD(kaim_devices);
static DEFINE_SPINLOCK(kaim_device_lock);

/* Audit log */
static LIST_HEAD(kaim_audit_log);
static DEFINE_SPINLOCK(kaim_audit_lock);
static atomic_t kaim_audit_count = ATOMIC_INIT(0);
#define KAIM_MAX_AUDIT_ENTRIES 1000

/* Statistics */
static atomic64_t kaim_stats_elevations = ATOMIC64_INIT(0);
static atomic64_t kaim_stats_device_opens = ATOMIC64_INIT(0);
static atomic64_t kaim_stats_permission_checks = ATOMIC64_INIT(0);
static atomic64_t kaim_stats_denials = ATOMIC64_INIT(0);

/* Function prototypes */
static int kaim_open(struct inode *inode, struct file *file);
static int kaim_release(struct inode *inode, struct file *file);
static long kaim_ioctl(struct file *file, unsigned int cmd, unsigned long arg);
static int kaim_proc_init(void);
static void kaim_proc_cleanup(void);

/* File operations */
static struct file_operations kaim_fops = {
    .owner = THIS_MODULE,
    .open = kaim_open,
    .release = kaim_release,
    .unlocked_ioctl = kaim_ioctl,
    .compat_ioctl = kaim_ioctl,
};

/* Helper functions */
static void kaim_audit_log(const char *action, pid_t pid, const char *fmt, ...)
{
    struct kaim_audit_entry *entry;
    va_list args;
    unsigned long flags;
    
    entry = kmalloc(sizeof(*entry), GFP_KERNEL);
    if (!entry)
        return;
    
    entry->timestamp = get_seconds();
    entry->pid = pid;
    strncpy(entry->action, action, sizeof(entry->action) - 1);
    
    va_start(args, fmt);
    vsnprintf(entry->details, sizeof(entry->details), fmt, args);
    va_end(args);
    
    spin_lock_irqsave(&kaim_audit_lock, flags);
    list_add_tail(&entry->list, &kaim_audit_log);
    
    /* Limit audit log size */
    if (atomic_inc_return(&kaim_audit_count) > KAIM_MAX_AUDIT_ENTRIES) {
        struct kaim_audit_entry *old;
        old = list_first_entry(&kaim_audit_log, struct kaim_audit_entry, list);
        list_del(&old->list);
        kfree(old);
        atomic_dec(&kaim_audit_count);
    }
    spin_unlock_irqrestore(&kaim_audit_lock, flags);
}

static struct kaim_process *kaim_find_process(pid_t pid)
{
    struct kaim_process *proc;
    
    rcu_read_lock();
    hash_for_each_possible_rcu(kaim_processes, proc, hnode, pid) {
        if (proc->pid == pid) {
            rcu_read_unlock();
            return proc;
        }
    }
    rcu_read_unlock();
    return NULL;
}

static struct kaim_process *kaim_get_or_create_process(pid_t pid)
{
    struct kaim_process *proc;
    struct task_struct *task;
    unsigned long flags;
    
    proc = kaim_find_process(pid);
    if (proc)
        return proc;
    
    /* Create new process entry */
    proc = kzalloc(sizeof(*proc), GFP_KERNEL);
    if (!proc)
        return NULL;
    
    proc->pid = pid;
    spin_lock_init(&proc->lock);
    
    /* Get process info */
    rcu_read_lock();
    task = pid_task(find_vpid(pid), PIDTYPE_PID);
    if (task) {
        const struct cred *cred = __task_cred(task);
        proc->uid = cred->uid.val;
        proc->gid = cred->gid.val;
        get_task_comm(proc->comm, task);
        
        /* Set default flags based on uid */
        if (proc->uid == 0) {
            proc->flags = KROOT;
        } else if (proc->uid < 1000) {
            proc->flags = KSYSTEM;
        } else {
            proc->flags = KUSR | KFILE_R | KPROC;
        }
    }
    rcu_read_unlock();
    
    /* Add to hash table */
    spin_lock_irqsave(&kaim_process_lock, flags);
    hash_add_rcu(kaim_processes, &proc->hnode, pid);
    spin_unlock_irqrestore(&kaim_process_lock, flags);
    
    return proc;
}

static bool kaim_check_permission(struct kaim_process *proc, u32 flag)
{
    unsigned long flags;
    bool has_perm = false;
    
    spin_lock_irqsave(&proc->lock, flags);
    
    /* Check base permissions */
    if (proc->flags & flag) {
        has_perm = true;
        goto out;
    }
    
    /* Check elevated permissions */
    if (proc->elevated_until > get_seconds() && (proc->elevated_flags & flag)) {
        has_perm = true;
        goto out;
    }
    
out:
    spin_unlock_irqrestore(&proc->lock, flags);
    atomic64_inc(&kaim_stats_permission_checks);
    return has_perm;
}

/* ioctl handlers */
static int kaim_ioctl_elevate(struct file *file, struct kaim_elevate_req __user *ureq)
{
    struct kaim_elevate_req req;
    struct kaim_process *current_proc, *target_proc;
    pid_t current_pid = task_pid_nr(current);
    unsigned long flags;
    
    if (copy_from_user(&req, ureq, sizeof(req)))
        return -EFAULT;
    
    /* Get current process */
    current_proc = kaim_find_process(current_pid);
    if (!current_proc)
        return -EPERM;
    
    /* Check permissions */
    if (!kaim_check_permission(current_proc, KROOT)) {
        if (!kaim_check_permission(current_proc, KSYSTEM)) {
            atomic64_inc(&kaim_stats_denials);
            kaim_audit_log("ELEVATE_DENIED", current_pid, 
                          "target=%d flags=0x%x", req.target_pid, req.flags);
            return -EPERM;
        }
    }
    
    /* Get or create target process */
    target_proc = kaim_get_or_create_process(req.target_pid);
    if (!target_proc)
        return -ENOMEM;
    
    /* Apply elevation */
    spin_lock_irqsave(&target_proc->lock, flags);
    target_proc->elevated_flags = req.flags;
    target_proc->elevated_until = get_seconds() + req.duration;
    spin_unlock_irqrestore(&target_proc->lock, flags);
    
    atomic64_inc(&kaim_stats_elevations);
    kaim_audit_log("ELEVATE_SUCCESS", current_pid,
                  "target=%d flags=0x%x duration=%u",
                  req.target_pid, req.flags, req.duration);
    
    return 0;
}

static int kaim_ioctl_status(struct file *file, struct kaim_status __user *ustatus)
{
    struct kaim_status status;
    
    memset(&status, 0, sizeof(status));
    strncpy(status.version, "1.0.0", sizeof(status.version) - 1);
    
    /* Count processes */
    status.process_count = atomic_read(&kaim_process_lock);
    
    /* Count devices */
    {
        struct kaim_process *proc;
        int device_count = 0;
        
        hash_for_each(kaim_process_table, i, proc, hnode) {
            struct kaim_device_entry *dev;
            list_for_each_entry(dev, &proc->devices, list) {
                device_count++;
            }
        }
        status.device_count = device_count;
    }
    
    /* Get statistics */
    status.elevations = atomic64_read(&kaim_stats_elevations);
    status.device_opens = atomic64_read(&kaim_stats_device_opens);
    status.permission_checks = atomic64_read(&kaim_stats_permission_checks);
    status.denials = atomic64_read(&kaim_stats_denials);
    
    if (copy_to_user(ustatus, &status, sizeof(status)))
        return -EFAULT;
    
    return 0;
}

static int kaim_ioctl_device(struct file *file, struct kaim_device_req __user *ureq)
{
    struct kaim_device_req req;
    struct kaim_process *proc;
    struct kaim_device_entry *dev;
    pid_t current_pid = task_pid_nr(current);
    bool found = false;
    
    if (copy_from_user(&req, ureq, sizeof(req)))
        return -EFAULT;
    
    /* Get current process */
    proc = kaim_find_process(current_pid);
    if (!proc)
        return -EPERM;
    
    /* Check device permission */
    if (!kaim_check_permission(proc, KDEV)) {
        atomic64_inc(&kaim_stats_denials);
        kaim_audit_log("DEVICE_DENIED", current_pid,
                      "device=%s mode=%s", req.device, req.mode);
        req.fd = -1;
        goto out;
    }
    
    /* Find device */
    spin_lock(&kaim_device_lock);
    list_for_each_entry(dev, &kaim_devices, list) {
        if (strcmp(dev->name, req.device) == 0) {
            found = true;
            break;
        }
    }
    spin_unlock(&kaim_device_lock);
    
    if (!found) {
        req.fd = -1;
        goto out;
    }
    
    /* Open device and return fd */
    {
        struct file *device_file = NULL;
        char device_path[256];
        int fd;
        
        /* Construct device path */
        snprintf(device_path, sizeof(device_path), "/dev/%s", req.device);
        
        /* Get an unused file descriptor */
        fd = get_unused_fd_flags(O_CLOEXEC);
        if (fd < 0) {
            req.fd = -1;
            goto out;
        }
        
        /* Open the device file */
        device_file = filp_open(device_path, 
                               strcmp(req.mode, "r") == 0 ? O_RDONLY :
                               strcmp(req.mode, "w") == 0 ? O_WRONLY : O_RDWR, 
                               0);
        
        if (IS_ERR(device_file)) {
            put_unused_fd(fd);
            req.fd = -1;
            goto out;
        }
        
        /* Install the file descriptor */
        fd_install(fd, device_file);
        req.fd = fd;
        
        /* Add to process device list */
        {
            struct kaim_device_entry *new_entry = kmalloc(sizeof(*new_entry), GFP_KERNEL);
            if (new_entry) {
                strncpy(new_entry->name, req.device, sizeof(new_entry->name) - 1);
                new_entry->name[sizeof(new_entry->name) - 1] = '\0';
                new_entry->fd = fd;
                list_add(&new_entry->list, &proc->devices);
            }
        }
        
        atomic64_inc(&kaim_stats_device_opens);
    }
    
    kaim_audit_log("DEVICE_OPEN", current_pid,
                  "device=%s mode=%s fd=%d", req.device, req.mode, req.fd);
    
out:
    if (copy_to_user(ureq, &req, sizeof(req)))
        return -EFAULT;
    
    return 0;
}

static int kaim_ioctl_check_perm(struct file *file, struct kaim_perm_check __user *ucheck)
{
    struct kaim_perm_check check;
    struct kaim_process *proc;
    
    if (copy_from_user(&check, ucheck, sizeof(check)))
        return -EFAULT;
    
    proc = kaim_find_process(check.pid);
    if (!proc) {
        check.result = 0;
    } else {
        check.result = kaim_check_permission(proc, check.flag) ? 1 : 0;
    }
    
    if (copy_to_user(ucheck, &check, sizeof(check)))
        return -EFAULT;
    
    return 0;
}

static int kaim_ioctl_drop_perm(struct file *file, struct kaim_perm_drop __user *udrop)
{
    struct kaim_perm_drop drop;
    struct kaim_process *proc, *current_proc;
    pid_t current_pid = task_pid_nr(current);
    unsigned long flags;
    
    if (copy_from_user(&drop, udrop, sizeof(drop)))
        return -EFAULT;
    
    /* Can only drop own permissions unless KROOT */
    if (drop.pid != current_pid) {
        current_proc = kaim_find_process(current_pid);
        if (!current_proc || !kaim_check_permission(current_proc, KROOT))
            return -EPERM;
    }
    
    proc = kaim_find_process(drop.pid);
    if (!proc)
        return -ESRCH;
    
    spin_lock_irqsave(&proc->lock, flags);
    proc->flags &= ~drop.flag;
    proc->elevated_flags &= ~drop.flag;
    spin_unlock_irqrestore(&proc->lock, flags);
    
    kaim_audit_log("PERM_DROPPED", current_pid,
                  "target=%d flag=0x%x", drop.pid, drop.flag);
    
    return 0;
}

static int kaim_ioctl_audit(struct file *file, struct kaim_audit_req __user *ureq)
{
    struct kaim_audit_req req;
    struct kaim_audit_entry *entry;
    unsigned long flags;
    int written = 0;
    
    if (copy_from_user(&req, ureq, sizeof(req)))
        return -EFAULT;
    
    req.buffer[0] = '\0';
    
    spin_lock_irqsave(&kaim_audit_lock, flags);
    list_for_each_entry_reverse(entry, &kaim_audit_log, list) {
        int len = snprintf(req.buffer + written, sizeof(req.buffer) - written,
                          "[%lu] %s pid=%d %s\n",
                          entry->timestamp, entry->action, entry->pid, entry->details);
        if (len <= 0 || written + len >= sizeof(req.buffer))
            break;
        written += len;
        if (--req.count == 0)
            break;
    }
    spin_unlock_irqrestore(&kaim_audit_lock, flags);
    
    if (copy_to_user(ureq, &req, sizeof(req)))
        return -EFAULT;
    
    return 0;
}

/* File operations */
static int kaim_open(struct inode *inode, struct file *file)
{
    /* Track opens if needed */
    return 0;
}

static int kaim_release(struct inode *inode, struct file *file)
{
    /* Cleanup if needed */
    return 0;
}

static long kaim_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    switch (cmd) {
    case KAIM_IOCTL_ELEVATE:
        return kaim_ioctl_elevate(file, (struct kaim_elevate_req __user *)arg);
    case KAIM_IOCTL_STATUS:
        return kaim_ioctl_status(file, (struct kaim_status __user *)arg);
    case KAIM_IOCTL_DEVICE:
        return kaim_ioctl_device(file, (struct kaim_device_req __user *)arg);
    case KAIM_IOCTL_CHECK_PERM:
        return kaim_ioctl_check_perm(file, (struct kaim_perm_check __user *)arg);
    case KAIM_IOCTL_DROP_PERM:
        return kaim_ioctl_drop_perm(file, (struct kaim_perm_drop __user *)arg);
    case KAIM_IOCTL_AUDIT:
        return kaim_ioctl_audit(file, (struct kaim_audit_req __user *)arg);
    default:
        return -EINVAL;
    }
}

/* /proc interface */
static struct proc_dir_entry *kaim_proc_dir;

static int kaim_proc_status_show(struct seq_file *m, void *v)
{
    seq_printf(m, "KAIM Kernel Module Status\n");
    seq_printf(m, "========================\n");
    seq_printf(m, "Version: 1.0.0\n");
    seq_printf(m, "Processes tracked: %u\n", atomic_read(&kaim_process_lock));
    seq_printf(m, "\nStatistics:\n");
    seq_printf(m, "  Elevations: %llu\n", atomic64_read(&kaim_stats_elevations));
    seq_printf(m, "  Device opens: %llu\n", atomic64_read(&kaim_stats_device_opens));
    seq_printf(m, "  Permission checks: %llu\n", atomic64_read(&kaim_stats_permission_checks));
    seq_printf(m, "  Denials: %llu\n", atomic64_read(&kaim_stats_denials));
    return 0;
}

static int kaim_proc_status_open(struct inode *inode, struct file *file)
{
    return single_open(file, kaim_proc_status_show, NULL);
}

static const struct file_operations kaim_proc_status_fops = {
    .owner = THIS_MODULE,
    .open = kaim_proc_status_open,
    .read = seq_read,
    .llseek = seq_lseek,
    .release = single_release,
};

static int kaim_proc_processes_show(struct seq_file *m, void *v)
{
    struct kaim_process *proc;
    struct hlist_node *tmp;
    int bkt;
    
    seq_printf(m, "PID\tUID\tGID\tFLAGS\t\tELEVATED\tCOMM\n");
    
    rcu_read_lock();
    hash_for_each_safe(kaim_processes, bkt, tmp, proc, hnode) {
        seq_printf(m, "%d\t%d\t%d\t0x%08x\t%s\t\t%s\n",
                  proc->pid, proc->uid, proc->gid, proc->flags,
                  (proc->elevated_until > get_seconds()) ? "Yes" : "No",
                  proc->comm);
    }
    rcu_read_unlock();
    
    return 0;
}

static int kaim_proc_processes_open(struct inode *inode, struct file *file)
{
    return single_open(file, kaim_proc_processes_show, NULL);
}

static const struct file_operations kaim_proc_processes_fops = {
    .owner = THIS_MODULE,
    .open = kaim_proc_processes_open,
    .read = seq_read,
    .llseek = seq_lseek,
    .release = single_release,
};

static int kaim_proc_init(void)
{
    kaim_proc_dir = proc_mkdir("kaim", NULL);
    if (!kaim_proc_dir)
        return -ENOMEM;
    
    proc_create("status", 0444, kaim_proc_dir, &kaim_proc_status_fops);
    proc_create("processes", 0444, kaim_proc_dir, &kaim_proc_processes_fops);
    
    return 0;
}

static void kaim_proc_cleanup(void)
{
    remove_proc_entry("processes", kaim_proc_dir);
    remove_proc_entry("status", kaim_proc_dir);
    remove_proc_entry("kaim", NULL);
}

/* Module init/exit */
static int __init kaim_init(void)
{
    int ret;
    dev_t dev;
    
    pr_info("KAIM: Initializing kernel module\n");
    
    /* Allocate device number */
    ret = alloc_chrdev_region(&dev, 0, 1, KAIM_DEVICE_NAME);
    if (ret < 0) {
        pr_err("KAIM: Failed to allocate device number\n");
        return ret;
    }
    kaim_major = MAJOR(dev);
    
    /* Create device class */
    kaim_class = class_create(THIS_MODULE, KAIM_CLASS_NAME);
    if (IS_ERR(kaim_class)) {
        unregister_chrdev_region(dev, 1);
        return PTR_ERR(kaim_class);
    }
    
    /* Create device */
    kaim_device = device_create(kaim_class, NULL, dev, NULL, KAIM_DEVICE_NAME);
    if (IS_ERR(kaim_device)) {
        class_destroy(kaim_class);
        unregister_chrdev_region(dev, 1);
        return PTR_ERR(kaim_device);
    }
    
    /* Initialize character device */
    cdev_init(&kaim_cdev, &kaim_fops);
    kaim_cdev.owner = THIS_MODULE;
    
    ret = cdev_add(&kaim_cdev, dev, 1);
    if (ret) {
        device_destroy(kaim_class, dev);
        class_destroy(kaim_class);
        unregister_chrdev_region(dev, 1);
        return ret;
    }
    
    /* Initialize /proc interface */
    ret = kaim_proc_init();
    if (ret) {
        pr_warn("KAIM: Failed to initialize /proc interface\n");
    }
    
    /* Register standard devices */
    {
        const char *standard_devices[] = {
            "null", "zero", "random", "urandom", "console", "tty", "tty0",
            "mem", "kmem", "port", "full", "stderr", "stdin", "stdout",
            NULL
        };
        int i;
        
        for (i = 0; standard_devices[i]; i++) {
            struct kaim_device_info *device = kmalloc(sizeof(*device), GFP_KERNEL);
            if (device) {
                strncpy(device->name, standard_devices[i], sizeof(device->name) - 1);
                device->name[sizeof(device->name) - 1] = '\0';
                
                /* Set device type based on name */
                if (strcmp(device->name, "mem") == 0 || strcmp(device->name, "kmem") == 0) {
                    device->major = 1;
                    device->minor = (strcmp(device->name, "mem") == 0) ? 1 : 2;
                    device->flags = KAIM_DEV_RESTRICTED;
                } else if (strcmp(device->name, "null") == 0) {
                    device->major = 1;
                    device->minor = 3;
                    device->flags = KAIM_DEV_SAFE;
                } else if (strcmp(device->name, "zero") == 0) {
                    device->major = 1;
                    device->minor = 5;
                    device->flags = KAIM_DEV_SAFE;
                } else if (strcmp(device->name, "random") == 0) {
                    device->major = 1;
                    device->minor = 8;
                    device->flags = KAIM_DEV_SAFE;
                } else if (strcmp(device->name, "urandom") == 0) {
                    device->major = 1;
                    device->minor = 9;
                    device->flags = KAIM_DEV_SAFE;
                } else if (strncmp(device->name, "tty", 3) == 0 || strcmp(device->name, "console") == 0) {
                    device->major = 5;
                    device->minor = 0;
                    device->flags = KAIM_DEV_TTY;
                } else {
                    device->major = 0;
                    device->minor = 0;
                    device->flags = KAIM_DEV_MISC;
                }
                
                spin_lock(&kaim_device_lock);
                list_add(&device->list, &kaim_devices);
                spin_unlock(&kaim_device_lock);
                
                pr_debug("KAIM: Registered device %s (%d:%d)\n", 
                        device->name, device->major, device->minor);
            }
        }
    }
    
    pr_info("KAIM: Module loaded successfully (major=%d)\n", kaim_major);
    return 0;
}

static void __exit kaim_exit(void)
{
    struct kaim_process *proc;
    struct hlist_node *tmp;
    struct kaim_audit_entry *audit, *audit_tmp;
    int bkt;
    
    pr_info("KAIM: Unloading kernel module\n");
    
    /* Clean up /proc */
    kaim_proc_cleanup();
    
    /* Remove device */
    cdev_del(&kaim_cdev);
    device_destroy(kaim_class, MKDEV(kaim_major, 0));
    class_destroy(kaim_class);
    unregister_chrdev_region(MKDEV(kaim_major, 0), 1);
    
    /* Clean up process table */
    spin_lock(&kaim_process_lock);
    hash_for_each_safe(kaim_processes, bkt, tmp, proc, hnode) {
        hash_del(&proc->hnode);
        kfree(proc);
    }
    spin_unlock(&kaim_process_lock);
    
    /* Clean up audit log */
    spin_lock(&kaim_audit_lock);
    list_for_each_entry_safe(audit, audit_tmp, &kaim_audit_log, list) {
        list_del(&audit->list);
        kfree(audit);
    }
    spin_unlock(&kaim_audit_lock);
    
    pr_info("KAIM: Module unloaded\n");
}

module_init(kaim_init);
module_exit(kaim_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("KOS Development Team");
MODULE_DESCRIPTION("KAIM - Kaede Application Interface Manager Kernel Module");
MODULE_VERSION("1.0.0");