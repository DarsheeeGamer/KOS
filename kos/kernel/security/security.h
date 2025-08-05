#ifndef _KOS_SECURITY_H
#define _KOS_SECURITY_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Security framework constants */
#define KOS_MAX_CONTEXTS 1024
#define KOS_MAX_CAPABILITIES 64
#define KOS_MAX_AUDIT_ENTRIES 10000
#define KOS_MAX_SECCOMP_FILTERS 256
#define KOS_MAX_POLICY_SIZE (1024 * 1024)  // 1MB

/* Error codes */
#define KOS_SEC_SUCCESS 0
#define KOS_SEC_ERROR -1
#define KOS_SEC_EPERM -2
#define KOS_SEC_EACCES -3
#define KOS_SEC_EINVAL -4
#define KOS_SEC_ENOMEM -5

/* Forward declarations */
typedef struct kos_security_context kos_security_context_t;
typedef struct kos_capability_set kos_capability_set_t;
typedef struct kos_selinux_context kos_selinux_context_t;
typedef struct kos_seccomp_filter kos_seccomp_filter_t;
typedef struct kos_audit_event kos_audit_event_t;

/* Security operations structure */
typedef struct {
    int (*check_permission)(uint32_t pid, const char* object, const char* perm);
    int (*set_context)(uint32_t pid, const char* context);
    int (*get_context)(uint32_t pid, char* context, size_t size);
    int (*audit_log)(const char* event, uint32_t pid, const char* details);
} kos_security_ops_t;

/* Global security operations */
extern kos_security_ops_t kos_security_ops;

/* Core security functions */
int kos_security_init(void);
void kos_security_cleanup(void);
int kos_security_check_permission(uint32_t pid, const char* object, 
                                  const char* permission);
int kos_security_set_context(uint32_t pid, const char* context);
int kos_security_get_context(uint32_t pid, char* context, size_t size);

/* Capability system */
typedef enum {
    KOS_CAP_CHOWN = 0,
    KOS_CAP_DAC_OVERRIDE,
    KOS_CAP_DAC_READ_SEARCH,
    KOS_CAP_FOWNER,
    KOS_CAP_FSETID,
    KOS_CAP_KILL,
    KOS_CAP_SETGID,
    KOS_CAP_SETUID,
    KOS_CAP_SETPCAP,
    KOS_CAP_LINUX_IMMUTABLE,
    KOS_CAP_NET_BIND_SERVICE,
    KOS_CAP_NET_BROADCAST,
    KOS_CAP_NET_ADMIN,
    KOS_CAP_NET_RAW,
    KOS_CAP_IPC_LOCK,
    KOS_CAP_IPC_OWNER,
    KOS_CAP_SYS_MODULE,
    KOS_CAP_SYS_RAWIO,
    KOS_CAP_SYS_CHROOT,
    KOS_CAP_SYS_PTRACE,
    KOS_CAP_SYS_PACCT,
    KOS_CAP_SYS_ADMIN,
    KOS_CAP_SYS_BOOT,
    KOS_CAP_SYS_NICE,
    KOS_CAP_SYS_RESOURCE,
    KOS_CAP_SYS_TIME,
    KOS_CAP_SYS_TTY_CONFIG,
    KOS_CAP_MKNOD,
    KOS_CAP_LEASE,
    KOS_CAP_AUDIT_WRITE,
    KOS_CAP_AUDIT_CONTROL,
    KOS_CAP_SETFCAP,
    KOS_CAP_MAC_OVERRIDE,
    KOS_CAP_MAC_ADMIN,
    KOS_CAP_SYSLOG,
    KOS_CAP_WAKE_ALARM,
    KOS_CAP_BLOCK_SUSPEND,
    KOS_CAP_AUDIT_READ,
    KOS_CAP_PERFMON,
    KOS_CAP_BPF,
    KOS_CAP_CHECKPOINT_RESTORE,
    KOS_CAP_MAX
} kos_capability_t;

struct kos_capability_set {
    uint64_t effective;
    uint64_t permitted;
    uint64_t inheritable;
    uint64_t bounding;
    uint64_t ambient;
};

/* Capability functions */
int kos_cap_init(void);
int kos_cap_get(uint32_t pid, kos_capability_set_t* caps);
int kos_cap_set(uint32_t pid, const kos_capability_set_t* caps);
bool kos_cap_capable(uint32_t pid, kos_capability_t cap);
int kos_cap_drop(uint32_t pid, kos_capability_t cap);
int kos_cap_raise(uint32_t pid, kos_capability_t cap);

/* SELinux types */
typedef enum {
    KOS_SELINUX_UNCONFINED,
    KOS_SELINUX_CONFINED,
    KOS_SELINUX_ENFORCING,
    KOS_SELINUX_PERMISSIVE,
    KOS_SELINUX_DISABLED
} kos_selinux_mode_t;

struct kos_selinux_context {
    char user[64];
    char role[64];
    char type[64];
    char level[64];
    uint32_t sid;  /* Security identifier */
};

/* SELinux functions */
int kos_selinux_init(void);
void kos_selinux_cleanup(void);
int kos_selinux_set_mode(kos_selinux_mode_t mode);
kos_selinux_mode_t kos_selinux_get_mode(void);
int kos_selinux_check_access(const kos_selinux_context_t* scontext,
                             const kos_selinux_context_t* tcontext,
                             const char* tclass, const char* perm);
int kos_selinux_compute_av(const kos_selinux_context_t* scontext,
                           const kos_selinux_context_t* tcontext,
                           const char* tclass, uint32_t* allowed,
                           uint32_t* denied);
int kos_selinux_load_policy(const void* policy_data, size_t policy_size);

/* Seccomp types */
typedef enum {
    KOS_SECCOMP_MODE_DISABLED = 0,
    KOS_SECCOMP_MODE_STRICT,
    KOS_SECCOMP_MODE_FILTER
} kos_seccomp_mode_t;

struct kos_seccomp_filter {
    uint32_t syscall_nr;
    uint32_t action;
    uint32_t arg_count;
    struct {
        uint32_t arg;
        uint32_t op;
        uint64_t value;
    } args[6];
};

/* Seccomp actions */
#define KOS_SECCOMP_RET_KILL_PROCESS 0x80000000U
#define KOS_SECCOMP_RET_KILL_THREAD  0x00000000U
#define KOS_SECCOMP_RET_TRAP         0x00030000U
#define KOS_SECCOMP_RET_ERRNO        0x00050000U
#define KOS_SECCOMP_RET_TRACE        0x7ff00000U
#define KOS_SECCOMP_RET_LOG          0x7ffc0000U
#define KOS_SECCOMP_RET_ALLOW        0x7fff0000U

/* Seccomp functions */
int kos_seccomp_init(void);
int kos_seccomp_set_mode(uint32_t pid, kos_seccomp_mode_t mode);
kos_seccomp_mode_t kos_seccomp_get_mode(uint32_t pid);
int kos_seccomp_add_filter(uint32_t pid, const kos_seccomp_filter_t* filter);
int kos_seccomp_check_syscall(uint32_t pid, uint32_t syscall_nr,
                              uint64_t* args, size_t arg_count);

/* Audit types */
typedef enum {
    KOS_AUDIT_SYSCALL = 1,
    KOS_AUDIT_FS_WATCH,
    KOS_AUDIT_PATH,
    KOS_AUDIT_IPC,
    KOS_AUDIT_SOCKETCALL,
    KOS_AUDIT_CONFIG_CHANGE,
    KOS_AUDIT_SOCKADDR,
    KOS_AUDIT_CWD,
    KOS_AUDIT_EXECVE,
    KOS_AUDIT_USER,
    KOS_AUDIT_LOGIN,
    KOS_AUDIT_SELINUX_ERR,
    KOS_AUDIT_AVC
} kos_audit_type_t;

struct kos_audit_event {
    uint64_t timestamp;
    uint32_t pid;
    uint32_t uid;
    uint32_t gid;
    kos_audit_type_t type;
    char message[256];
    char comm[16];
    char exe[256];
};

/* Audit functions */
int kos_audit_init(void);
void kos_audit_cleanup(void);
int kos_audit_log_event(kos_audit_type_t type, uint32_t pid,
                        const char* message);
int kos_audit_set_enabled(bool enabled);
bool kos_audit_is_enabled(void);
int kos_audit_get_events(kos_audit_event_t* events, size_t max_events,
                         size_t* count);

/* Cryptographic functions */
typedef enum {
    KOS_HASH_SHA256,
    KOS_HASH_SHA512,
    KOS_HASH_MD5
} kos_hash_type_t;

typedef enum {
    KOS_CIPHER_AES128_CBC,
    KOS_CIPHER_AES256_CBC,
    KOS_CIPHER_AES128_GCM,
    KOS_CIPHER_AES256_GCM
} kos_cipher_type_t;

/* Crypto functions */
int kos_crypto_init(void);
void kos_crypto_cleanup(void);
int kos_crypto_hash(kos_hash_type_t type, const void* data, size_t len,
                    void* hash, size_t hash_len);
int kos_crypto_encrypt(kos_cipher_type_t type, const void* key, size_t key_len,
                       const void* iv, const void* plaintext, size_t pt_len,
                       void* ciphertext, size_t* ct_len);
int kos_crypto_decrypt(kos_cipher_type_t type, const void* key, size_t key_len,
                       const void* iv, const void* ciphertext, size_t ct_len,
                       void* plaintext, size_t* pt_len);
int kos_crypto_random(void* buffer, size_t len);

/* Security module registration */
typedef struct kos_security_module {
    const char* name;
    int (*init)(void);
    void (*cleanup)(void);
    int (*check_permission)(uint32_t pid, const char* object, const char* perm);
    struct kos_security_module* next;
} kos_security_module_t;

int kos_security_register_module(kos_security_module_t* module);
int kos_security_unregister_module(kos_security_module_t* module);

/* Utility macros */
#define KOS_CAP_SET(caps, cap) ((caps) |= (1ULL << (cap)))
#define KOS_CAP_CLEAR(caps, cap) ((caps) &= ~(1ULL << (cap)))
#define KOS_CAP_IS_SET(caps, cap) (((caps) & (1ULL << (cap))) != 0)

#define KOS_AUDIT_LOG(type, pid, fmt, ...) \
    do { \
        char __msg[256]; \
        snprintf(__msg, sizeof(__msg), fmt, ##__VA_ARGS__); \
        kos_audit_log_event(type, pid, __msg); \
    } while (0)

#ifdef __cplusplus
}
#endif

#endif /* _KOS_SECURITY_H */