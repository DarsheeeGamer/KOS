/*
 * KOS Security Error Handling and Edge Cases
 * Comprehensive security error recovery and validation
 */

#include "manager.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/capability.h>
#include <sys/prctl.h>

/* Security error types */
typedef enum {
    SEC_ERROR_NONE = 0,
    SEC_ERROR_ACCESS_DENIED,       /* Access denied */
    SEC_ERROR_PRIVILEGE_ESCALATION,/* Privilege escalation attempt */
    SEC_ERROR_INVALID_CREDENTIALS, /* Invalid credentials */
    SEC_ERROR_AUTHENTICATION_FAILED,/* Authentication failed */
    SEC_ERROR_AUTHORIZATION_FAILED,/* Authorization failed */
    SEC_ERROR_CAPABILITY_VIOLATION,/* Capability violation */
    SEC_ERROR_SELINUX_VIOLATION,   /* SELinux policy violation */
    SEC_ERROR_SECCOMP_VIOLATION,   /* Seccomp filter violation */
    SEC_ERROR_NAMESPACE_VIOLATION, /* Namespace boundary violation */  
    SEC_ERROR_CHROOT_ESCAPE,       /* Chroot escape attempt */
    SEC_ERROR_BUFFER_OVERFLOW,     /* Buffer overflow attack */
    SEC_ERROR_FORMAT_STRING,       /* Format string attack */
    SEC_ERROR_INJECTION_ATTACK,    /* Code injection attack */
    SEC_ERROR_TIMING_ATTACK,       /* Timing attack detected */
    SEC_ERROR_BRUTE_FORCE,         /* Brute force attack */
    SEC_ERROR_RATE_LIMIT_EXCEEDED, /* Rate limit exceeded */
    SEC_ERROR_SUSPICIOUS_ACTIVITY, /* Suspicious activity detected */
    SEC_ERROR_MALWARE_DETECTED,    /* Malware detected */
    SEC_ERROR_CRYPTO_ERROR,        /* Cryptographic error */
    SEC_ERROR_KEY_COMPROMISE,      /* Key compromise detected */
    SEC_ERROR_AUDIT_FAILURE,       /* Audit system failure */
    SEC_ERROR_POLICY_VIOLATION     /* Security policy violation */
} sec_error_type_t;

/* Error recovery strategies */
typedef enum {
    SEC_RECOVERY_IGNORE = 0,
    SEC_RECOVERY_LOG,
    SEC_RECOVERY_DENY_ACCESS,
    SEC_RECOVERY_KILL_PROCESS,
    SEC_RECOVERY_ISOLATE_PROCESS,
    SEC_RECOVERY_REVOKE_PRIVILEGES,
    SEC_RECOVERY_LOCKDOWN_SYSTEM,
    SEC_RECOVERY_ALERT_ADMIN,
    SEC_RECOVERY_EMERGENCY_SHUTDOWN,
    SEC_RECOVERY_PANIC
} sec_recovery_t;

/* Security error context */
typedef struct {
    sec_error_type_t type;
    const char *message;
    pid_t pid;
    uid_t uid;
    gid_t gid;
    const char *process_name;
    const char *resource;
    const char *operation;
    uint32_t capability;
    const char *selinux_context;
    uint64_t timestamp;
    const char *file;
    int line;
    const char *function;
    sec_recovery_t recovery;
    void *extra_data;
    uint32_t severity; /* 1-10 scale */
} sec_error_ctx_t;

/* Security error statistics */
static struct {
    uint64_t total_errors;
    uint64_t access_denied_errors;
    uint64_t privilege_escalation_errors;
    uint64_t invalid_credentials_errors;
    uint64_t authentication_failed_errors;
    uint64_t authorization_failed_errors;
    uint64_t capability_violation_errors;
    uint64_t selinux_violation_errors;
    uint64_t seccomp_violation_errors;
    uint64_t namespace_violation_errors;
    uint64_t chroot_escape_errors;
    uint64_t buffer_overflow_errors;
    uint64_t format_string_errors;
    uint64_t injection_attack_errors;
    uint64_t timing_attack_errors;
    uint64_t brute_force_errors;
    uint64_t rate_limit_exceeded_errors;
    uint64_t suspicious_activity_errors;
    uint64_t malware_detected_errors;
    uint64_t crypto_errors;
    uint64_t key_compromise_errors;
    uint64_t audit_failure_errors;
    uint64_t policy_violation_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t processes_killed;
    uint64_t processes_isolated;
    uint64_t privileges_revoked;
    uint64_t admin_alerts;
    uint64_t emergency_shutdowns;
    pthread_mutex_t lock;
} sec_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Attack detection patterns */
typedef struct attack_pattern {
    const char *name;
    const char *pattern;
    sec_error_type_t error_type;
    uint32_t severity;
} attack_pattern_t;

static attack_pattern_t attack_patterns[] = {
    {"Buffer Overflow", "%n%n%n%n", SEC_ERROR_BUFFER_OVERFLOW, 9},
    {"Format String", "%s%s%s%s", SEC_ERROR_FORMAT_STRING, 8},
    {"SQL Injection", "'; DROP TABLE", SEC_ERROR_INJECTION_ATTACK, 9},
    {"Command Injection", "; rm -rf", SEC_ERROR_INJECTION_ATTACK, 10},
    {"Path Traversal", "../../../", SEC_ERROR_INJECTION_ATTACK, 7},
    {"XSS", "<script>", SEC_ERROR_INJECTION_ATTACK, 6},
    {NULL, NULL, SEC_ERROR_NONE, 0}
};

/* Brute force tracking */
typedef struct brute_force_entry {
    uid_t uid;
    char source_ip[16];
    uint32_t attempt_count;
    uint64_t first_attempt;
    uint64_t last_attempt;
    bool blocked;
    struct brute_force_entry *next;
} brute_force_entry_t;

static brute_force_entry_t *brute_force_list = NULL;
static pthread_mutex_t brute_force_lock = PTHREAD_MUTEX_INITIALIZER;

/* Rate limiting */
typedef struct rate_limit_entry {
    pid_t pid;
    uid_t uid;
    const char *operation;
    uint32_t count;
    uint64_t window_start;
    struct rate_limit_entry *next;
} rate_limit_entry_t;

static rate_limit_entry_t *rate_limit_list = NULL;
static pthread_mutex_t rate_limit_lock = PTHREAD_MUTEX_INITIALIZER;

/* Validate process credentials */
static int validate_process_credentials(pid_t pid, const char *context)
{
    char proc_path[256];
    snprintf(proc_path, sizeof(proc_path), "/proc/%d/status", pid);
    
    FILE *fp = fopen(proc_path, "r");
    if (!fp) {
        sec_error_ctx_t ctx = {
            .type = SEC_ERROR_INVALID_CREDENTIALS,
            .message = "Cannot access process credentials",
            .pid = pid,
            .uid = getuid(),
            .gid = getgid(),
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .recovery = SEC_RECOVERY_LOG,
            .severity = 5
        };
        return handle_security_error(&ctx);
    }

    char line[256];
    uid_t real_uid = -1, effective_uid = -1;
    gid_t real_gid = -1, effective_gid = -1;

    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "Uid:", 4) == 0) {
            sscanf(line, "Uid:\t%d\t%d", &real_uid, &effective_uid);
        } else if (strncmp(line, "Gid:", 4) == 0) {
            sscanf(line, "Gid:\t%d\t%d", &real_gid, &effective_gid);
        }
    }
    fclose(fp);

    /* Check for suspicious UID changes */
    if (real_uid != effective_uid || real_gid != effective_gid) {
        /* Check if this is a legitimate setuid/setgid program */
        if (effective_uid == 0 && real_uid != 0) {
            sec_error_ctx_t ctx = {
                .type = SEC_ERROR_PRIVILEGE_ESCALATION,
                .message = "Potential privilege escalation detected",
                .pid = pid,
                .uid = real_uid,
                .gid = real_gid,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .recovery = SEC_RECOVERY_ALERT_ADMIN,
                .severity = 8
            };
            return handle_security_error(&ctx);
        }
    }

    return 0;
}

/* Check capability violations */
static int check_capability_violation(pid_t pid, uint32_t capability, const char *operation)
{
    cap_t caps = cap_get_pid(pid);
    if (!caps) {
        return 0; /* Cannot check, assume valid */
    }

    cap_flag_value_t value;
    if (cap_get_flag(caps, capability, CAP_EFFECTIVE, &value) == 0) {
        if (value != CAP_SET) {
            sec_error_ctx_t ctx = {
                .type = SEC_ERROR_CAPABILITY_VIOLATION,
                .message = "Process lacks required capability",
                .pid = pid,
                .uid = getuid(),
                .gid = getgid(),
                .operation = operation,
                .capability = capability,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = __func__,
                .recovery = SEC_RECOVERY_DENY_ACCESS,
                .severity = 7
            };
            
            cap_free(caps);
            return handle_security_error(&ctx);
        }
    }

    cap_free(caps);
    return 0;
}

/* Detect attack patterns in input */
static int detect_attack_patterns(const char *input, const char *context)
{
    if (!input) {
        return 0;
    }

    for (int i = 0; attack_patterns[i].name; i++) {
        if (strstr(input, attack_patterns[i].pattern)) {
            sec_error_ctx_t ctx = {
                .type = attack_patterns[i].error_type,
                .message = attack_patterns[i].name,
                .pid = getpid(),
                .uid = getuid(),
                .gid = getgid(),
                .resource = input,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .recovery = SEC_RECOVERY_KILL_PROCESS,
                .severity = attack_patterns[i].severity
            };
            return handle_security_error(&ctx);
        }
    }

    return 0;
}

/* Check rate limiting */
static int check_rate_limit(pid_t pid, uid_t uid, const char *operation, uint32_t limit_per_second)
{
    pthread_mutex_lock(&rate_limit_lock);

    uint64_t now = time(NULL);
    rate_limit_entry_t *entry = rate_limit_list;

    /* Find existing entry */
    while (entry && (entry->pid != pid || entry->uid != uid || 
                     strcmp(entry->operation, operation) != 0)) {
        entry = entry->next;
    }

    if (!entry) {
        /* Create new entry */
        entry = malloc(sizeof(rate_limit_entry_t));
        if (entry) {
            entry->pid = pid;
            entry->uid = uid;
            entry->operation = strdup(operation);
            entry->count = 1;
            entry->window_start = now;
            entry->next = rate_limit_list;
            rate_limit_list = entry;
        }
        pthread_mutex_unlock(&rate_limit_lock);
        return 0;
    }

    /* Reset window if needed */
    if (now - entry->window_start >= 1) {
        entry->count = 0;
        entry->window_start = now;
    }

    entry->count++;

    if (entry->count > limit_per_second) {
        sec_error_ctx_t ctx = {
            .type = SEC_ERROR_RATE_LIMIT_EXCEEDED,
            .message = "Rate limit exceeded",
            .pid = pid,
            .uid = uid,
            .operation = operation,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SEC_RECOVERY_DENY_ACCESS,
            .severity = 6
        };

        pthread_mutex_unlock(&rate_limit_lock);
        return handle_security_error(&ctx);
    }

    pthread_mutex_unlock(&rate_limit_lock);
    return 0;
}

/* Track brute force attempts */
static int track_brute_force(uid_t uid, const char *source_ip, bool success)
{
    pthread_mutex_lock(&brute_force_lock);

    uint64_t now = time(NULL);
    brute_force_entry_t *entry = brute_force_list;

    /* Find existing entry */
    while (entry && (entry->uid != uid || strcmp(entry->source_ip, source_ip) != 0)) {
        entry = entry->next;
    }

    if (!entry) {
        /* Create new entry */
        entry = malloc(sizeof(brute_force_entry_t));
        if (entry) {
            entry->uid = uid;
            strncpy(entry->source_ip, source_ip, sizeof(entry->source_ip) - 1);
            entry->source_ip[sizeof(entry->source_ip) - 1] = '\0';
            entry->attempt_count = 0;
            entry->first_attempt = now;
            entry->last_attempt = now;
            entry->blocked = false;
            entry->next = brute_force_list;
            brute_force_list = entry;
        } else {
            pthread_mutex_unlock(&brute_force_lock);
            return 0;
        }
    }

    if (success) {
        /* Reset on successful auth */
        entry->attempt_count = 0;
        entry->blocked = false;
    } else {
        entry->attempt_count++;
        entry->last_attempt = now;

        /* Check for brute force */
        if (entry->attempt_count >= MAX_AUTH_ATTEMPTS) {
            if (!entry->blocked) {
                entry->blocked = true;
                
                sec_error_ctx_t ctx = {
                    .type = SEC_ERROR_BRUTE_FORCE,
                    .message = "Brute force attack detected",
                    .uid = uid,
                    .resource = entry->source_ip,
                    .timestamp = time(NULL),
                    .file = __FILE__,
                    .line = __LINE__,
                    .function = __func__,
                    .recovery = SEC_RECOVERY_ALERT_ADMIN,
                    .severity = 9
                };

                pthread_mutex_unlock(&brute_force_lock);
                return handle_security_error(&ctx);
            }
        }
    }

    pthread_mutex_unlock(&brute_force_lock);
    return 0;
}

/* Validate SELinux context */
static int validate_selinux_context(pid_t pid, const char *required_context, const char *operation)
{
    char proc_path[256];
    snprintf(proc_path, sizeof(proc_path), "/proc/%d/attr/current", pid);
    
    FILE *fp = fopen(proc_path, "r");
    if (!fp) {
        return 0; /* SELinux not enabled or accessible */
    }

    char current_context[256];
    if (fgets(current_context, sizeof(current_context), fp)) {
        /* Remove newline */
        char *newline = strchr(current_context, '\n');
        if (newline) *newline = '\0';
        
        if (required_context && strcmp(current_context, required_context) != 0) {
            sec_error_ctx_t ctx = {
                .type = SEC_ERROR_SELINUX_VIOLATION,
                .message = "SELinux context violation",
                .pid = pid,
                .uid = getuid(),
                .gid = getgid(),
                .operation = operation,
                .selinux_context = current_context,
                .timestamp = time(NULL),
                .file = __FILE__,
                .line = __LINE__,
                .function = __func__,
                .recovery = SEC_RECOVERY_DENY_ACCESS,
                .severity = 8
            };
            
            fclose(fp);
            return handle_security_error(&ctx);
        }
    }
    
    fclose(fp);
    return 0;
}

/* Detect timing attacks */
static int detect_timing_attack(const char *operation, uint64_t start_time, uint64_t end_time)
{
    uint64_t duration = end_time - start_time;
    
    /* Check for suspiciously fast operations that might indicate timing attacks */
    if (duration < MIN_OPERATION_TIME_US) {
        sec_error_ctx_t ctx = {
            .type = SEC_ERROR_TIMING_ATTACK,
            .message = "Potential timing attack detected",
            .pid = getpid(),
            .uid = getuid(),
            .gid = getgid(),
            .operation = operation,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SEC_RECOVERY_LOG,
            .severity = 6
        };
        return handle_security_error(&ctx);
    }
    
    return 0;
}

/* Check for chroot escape attempts */
static int check_chroot_escape(const char *path)
{
    if (!path) {
        return 0;
    }

    /* Look for patterns that might indicate chroot escape attempts */
    if (strstr(path, "../") || strstr(path, "/proc/") || 
        strstr(path, "/sys/") || strstr(path, "/dev/")) {
        
        sec_error_ctx_t ctx = {
            .type = SEC_ERROR_CHROOT_ESCAPE,
            .message = "Potential chroot escape attempt",
            .pid = getpid(),
            .uid = getuid(),
            .gid = getgid(),
            .resource = path,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SEC_RECOVERY_KILL_PROCESS,
            .severity = 9
        };
        return handle_security_error(&ctx);
    }

    return 0;
}

/* Log security error */
static void log_security_error(const sec_error_ctx_t *ctx)
{
    pthread_mutex_lock(&sec_error_stats.lock);
    sec_error_stats.total_errors++;

    switch (ctx->type) {
        case SEC_ERROR_ACCESS_DENIED:
            sec_error_stats.access_denied_errors++;
            break;
        case SEC_ERROR_PRIVILEGE_ESCALATION:
            sec_error_stats.privilege_escalation_errors++;
            break;
        case SEC_ERROR_INVALID_CREDENTIALS:
            sec_error_stats.invalid_credentials_errors++;
            break;
        case SEC_ERROR_AUTHENTICATION_FAILED:
            sec_error_stats.authentication_failed_errors++;
            break;
        case SEC_ERROR_AUTHORIZATION_FAILED:
            sec_error_stats.authorization_failed_errors++;
            break;
        case SEC_ERROR_CAPABILITY_VIOLATION:
            sec_error_stats.capability_violation_errors++;
            break;
        case SEC_ERROR_SELINUX_VIOLATION:
            sec_error_stats.selinux_violation_errors++;
            break;
        case SEC_ERROR_SECCOMP_VIOLATION:
            sec_error_stats.seccomp_violation_errors++;
            break;
        case SEC_ERROR_NAMESPACE_VIOLATION:
            sec_error_stats.namespace_violation_errors++;
            break;
        case SEC_ERROR_CHROOT_ESCAPE:
            sec_error_stats.chroot_escape_errors++;
            break;
        case SEC_ERROR_BUFFER_OVERFLOW:
            sec_error_stats.buffer_overflow_errors++;
            break;
        case SEC_ERROR_FORMAT_STRING:
            sec_error_stats.format_string_errors++;
            break;
        case SEC_ERROR_INJECTION_ATTACK:
            sec_error_stats.injection_attack_errors++;
            break;
        case SEC_ERROR_TIMING_ATTACK:
            sec_error_stats.timing_attack_errors++;
            break;
        case SEC_ERROR_BRUTE_FORCE:
            sec_error_stats.brute_force_errors++;
            break;
        case SEC_ERROR_RATE_LIMIT_EXCEEDED:
            sec_error_stats.rate_limit_exceeded_errors++;
            break;
        case SEC_ERROR_SUSPICIOUS_ACTIVITY:
            sec_error_stats.suspicious_activity_errors++;
            break;
        case SEC_ERROR_MALWARE_DETECTED:
            sec_error_stats.malware_detected_errors++;
            break;
        case SEC_ERROR_CRYPTO_ERROR:
            sec_error_stats.crypto_errors++;
            break;
        case SEC_ERROR_KEY_COMPROMISE:
            sec_error_stats.key_compromise_errors++;
            break;
        case SEC_ERROR_AUDIT_FAILURE:
            sec_error_stats.audit_failure_errors++;
            break;
        case SEC_ERROR_POLICY_VIOLATION:
            sec_error_stats.policy_violation_errors++;
            break;
        default:
            break;
    }

    pthread_mutex_unlock(&sec_error_stats.lock);

    /* Log error details with severity indicator */
    const char *severity_str[] = {
        "INFO", "LOW", "LOW", "MEDIUM", "MEDIUM", 
        "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL", "EMERGENCY"
    };
    
    uint32_t sev_index = (ctx->severity < 11) ? ctx->severity : 10;
    
    printf("[SEC %s] Type: %d, Message: %s\n", severity_str[sev_index], ctx->type, ctx->message);
    printf("[SEC %s] PID: %d, UID: %d, GID: %d\n", severity_str[sev_index], ctx->pid, ctx->uid, ctx->gid);
    
    if (ctx->process_name) {
        printf("[SEC %s] Process: %s\n", severity_str[sev_index], ctx->process_name);
    }
    if (ctx->resource) {
        printf("[SEC %s] Resource: %s\n", severity_str[sev_index], ctx->resource);
    }
    if (ctx->operation) {
        printf("[SEC %s] Operation: %s\n", severity_str[sev_index], ctx->operation);
    }
    if (ctx->selinux_context) {
        printf("[SEC %s] SELinux Context: %s\n", severity_str[sev_index], ctx->selinux_context);
    }
    
    printf("[SEC %s] Location: %s:%d in %s()\n", severity_str[sev_index],
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle security error with recovery */
int handle_security_error(sec_error_ctx_t *ctx)
{
    log_security_error(ctx);

    pthread_mutex_lock(&sec_error_stats.lock);
    sec_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&sec_error_stats.lock);

    switch (ctx->recovery) {
        case SEC_RECOVERY_IGNORE:
            return 0;

        case SEC_RECOVERY_LOG:
            /* Already logged above */
            pthread_mutex_lock(&sec_error_stats.lock);
            sec_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&sec_error_stats.lock);
            return 0;

        case SEC_RECOVERY_DENY_ACCESS:
            printf("[SEC RECOVERY] Access denied for PID %d\n", ctx->pid);
            pthread_mutex_lock(&sec_error_stats.lock);
            sec_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&sec_error_stats.lock);
            return -EACCES;

        case SEC_RECOVERY_KILL_PROCESS:
            if (ctx->pid > 1) { /* Don't kill init */
                printf("[SEC RECOVERY] Killing malicious process PID %d\n", ctx->pid);
                kill(ctx->pid, SIGKILL);
                pthread_mutex_lock(&sec_error_stats.lock);
                sec_error_stats.processes_killed++;
                sec_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&sec_error_stats.lock);
            }
            return 0;

        case SEC_RECOVERY_ISOLATE_PROCESS:
            if (ctx->pid > 1) {
                printf("[SEC RECOVERY] Isolating process PID %d\n", ctx->pid);
                /* Move process to isolated cgroup/namespace */
                isolate_process(ctx->pid);
                pthread_mutex_lock(&sec_error_stats.lock);
                sec_error_stats.processes_isolated++;
                sec_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&sec_error_stats.lock);
            }
            return 0;

        case SEC_RECOVERY_REVOKE_PRIVILEGES:
            if (ctx->pid > 1) {
                printf("[SEC RECOVERY] Revoking privileges for PID %d\n", ctx->pid);
                /* Drop all capabilities */
                cap_t caps = cap_init();
                cap_set_proc(caps);
                cap_free(caps);
                pthread_mutex_lock(&sec_error_stats.lock);
                sec_error_stats.privileges_revoked++;
                sec_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&sec_error_stats.lock);
            }
            return 0;

        case SEC_RECOVERY_LOCKDOWN_SYSTEM:
            printf("[SEC RECOVERY] System lockdown initiated\n");
            /* Enable system-wide security lockdown */
            enable_security_lockdown();
            pthread_mutex_lock(&sec_error_stats.lock);
            sec_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&sec_error_stats.lock);
            return 0;

        case SEC_RECOVERY_ALERT_ADMIN:
            printf("[SEC ALERT] Security incident requires administrator attention\n");
            /* Send alert to system administrator */
            send_security_alert(ctx);
            pthread_mutex_lock(&sec_error_stats.lock);
            sec_error_stats.admin_alerts++;
            sec_error_stats.recoveries_successful++;
            pthread_mutex_unlock(&sec_error_stats.lock);
            return 0;

        case SEC_RECOVERY_EMERGENCY_SHUTDOWN:
            printf("[SEC EMERGENCY] Emergency system shutdown\n");
            /* Emergency system shutdown */
            pthread_mutex_lock(&sec_error_stats.lock);
            sec_error_stats.emergency_shutdowns++;
            pthread_mutex_unlock(&sec_error_stats.lock);
            system("shutdown -h now");
            return 0;

        case SEC_RECOVERY_PANIC:
            printf("[SEC PANIC] Critical security breach - system halting\n");
            abort();

        default:
            return -1;
    }
}

/* Safe security operations with error handling */
int safe_access_check(pid_t pid, const char *resource, const char *operation, uint32_t required_capability)
{
    /* Validate process credentials */
    if (validate_process_credentials(pid, "safe_access_check") != 0) {
        return -1;
    }

    /* Check capability requirements */
    if (required_capability != CAP_LAST_CAP) {
        if (check_capability_violation(pid, required_capability, operation) != 0) {
            return -1;
        }
    }

    /* Check rate limiting */
    if (check_rate_limit(pid, getuid(), operation, 100) != 0) {
        return -1;
    }

    /* Check for attack patterns in resource name */
    if (detect_attack_patterns(resource, "safe_access_check") != 0) {
        return -1;
    }

    /* Check for chroot escape attempts */
    if (check_chroot_escape(resource) != 0) {
        return -1;
    }

    return 0;
}

int safe_authenticate(uid_t uid, const char *password, const char *source_ip)
{
    uint64_t start_time = time(NULL) * 1000000 + 0; /* Simplified timing */
    
    /* Check for attack patterns in password */
    if (detect_attack_patterns(password, "safe_authenticate") != 0) {
        return -1;
    }

    /* Simulate authentication (in real implementation, this would check against database) */
    bool success = (uid > 0 && password && strlen(password) > 0);
    
    uint64_t end_time = time(NULL) * 1000000 + 1000; /* Simplified timing */
    
    /* Detect timing attacks */
    if (detect_timing_attack("authenticate", start_time, end_time) != 0) {
        return -1;
    }
    
    /* Track brute force attempts */
    if (track_brute_force(uid, source_ip, success) != 0) {
        return -1;
    }

    if (!success) {
        sec_error_ctx_t ctx = {
            .type = SEC_ERROR_AUTHENTICATION_FAILED,
            .message = "Authentication failed",
            .uid = uid,
            .resource = source_ip,
            .timestamp = time(NULL),
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .recovery = SEC_RECOVERY_LOG,
            .severity = 5
        };
        handle_security_error(&ctx);
        return -EACCES;
    }

    return 0;
}

/* Comprehensive security health check */
int security_health_check(void)
{
    int issues_found = 0;

    /* Check for blocked brute force attempts */
    pthread_mutex_lock(&brute_force_lock);
    brute_force_entry_t *entry = brute_force_list;
    while (entry) {
        if (entry->blocked) {
            issues_found++;
        }
        entry = entry->next;
    }
    pthread_mutex_unlock(&brute_force_lock);

    /* Check rate limiting violations */
    pthread_mutex_lock(&rate_limit_lock);
    rate_limit_entry_t *rate_entry = rate_limit_list;
    while (rate_entry) {
        if (rate_entry->count > 100) { /* Threshold */
            issues_found++;
        }
        rate_entry = rate_entry->next;
    }
    pthread_mutex_unlock(&rate_limit_lock);

    return issues_found;
}

/* Get security error statistics */
void sec_get_error_stats(void)
{
    pthread_mutex_lock(&sec_error_stats.lock);

    printf("\nSecurity Error Statistics:\n");
    printf("==========================\n");
    printf("Total errors:              %lu\n", sec_error_stats.total_errors);
    printf("Access denied errors:      %lu\n", sec_error_stats.access_denied_errors);
    printf("Privilege escalation:      %lu\n", sec_error_stats.privilege_escalation_errors);
    printf("Invalid credentials:       %lu\n", sec_error_stats.invalid_credentials_errors);
    printf("Authentication failed:     %lu\n", sec_error_stats.authentication_failed_errors);
    printf("Authorization failed:      %lu\n", sec_error_stats.authorization_failed_errors);
    printf("Capability violations:     %lu\n", sec_error_stats.capability_violation_errors);
    printf("SELinux violations:        %lu\n", sec_error_stats.selinux_violation_errors);
    printf("Seccomp violations:        %lu\n", sec_error_stats.seccomp_violation_errors);
    printf("Namespace violations:      %lu\n", sec_error_stats.namespace_violation_errors);
    printf("Chroot escape attempts:    %lu\n", sec_error_stats.chroot_escape_errors);
    printf("Buffer overflow attacks:   %lu\n", sec_error_stats.buffer_overflow_errors);
    printf("Format string attacks:     %lu\n", sec_error_stats.format_string_errors);
    printf("Injection attacks:         %lu\n", sec_error_stats.injection_attack_errors);
    printf("Timing attacks:            %lu\n", sec_error_stats.timing_attack_errors);
    printf("Brute force attacks:       %lu\n", sec_error_stats.brute_force_errors);
    printf("Rate limit exceeded:       %lu\n", sec_error_stats.rate_limit_exceeded_errors);
    printf("Suspicious activities:     %lu\n", sec_error_stats.suspicious_activity_errors);
    printf("Malware detected:          %lu\n", sec_error_stats.malware_detected_errors);
    printf("Crypto errors:             %lu\n", sec_error_stats.crypto_errors);
    printf("Key compromise:            %lu\n", sec_error_stats.key_compromise_errors);
    printf("Audit failures:            %lu\n", sec_error_stats.audit_failure_errors);
    printf("Policy violations:         %lu\n", sec_error_stats.policy_violation_errors);
    printf("Recovery attempts:         %lu\n", sec_error_stats.recoveries_attempted);
    printf("Recovery successes:        %lu\n", sec_error_stats.recoveries_successful);
    printf("Processes killed:          %lu\n", sec_error_stats.processes_killed);
    printf("Processes isolated:        %lu\n", sec_error_stats.processes_isolated);
    printf("Privileges revoked:        %lu\n", sec_error_stats.privileges_revoked);
    printf("Admin alerts:              %lu\n", sec_error_stats.admin_alerts);
    printf("Emergency shutdowns:       %lu\n", sec_error_stats.emergency_shutdowns);

    if (sec_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)sec_error_stats.recoveries_successful / 
                             sec_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate:     %.1f%%\n", success_rate);
    }

    pthread_mutex_unlock(&sec_error_stats.lock);
}

/* Initialize security error handling */
void sec_error_init(void)
{
    printf("Security error handling initialized\n");
}

/* Cleanup security error handling */
void sec_error_cleanup(void)
{
    pthread_mutex_lock(&brute_force_lock);
    
    brute_force_entry_t *bf_entry = brute_force_list;
    while (bf_entry) {
        brute_force_entry_t *next = bf_entry->next;
        free(bf_entry);
        bf_entry = next;
    }
    brute_force_list = NULL;
    
    pthread_mutex_unlock(&brute_force_lock);

    pthread_mutex_lock(&rate_limit_lock);
    
    rate_limit_entry_t *rl_entry = rate_limit_list;
    while (rl_entry) {
        rate_limit_entry_t *next = rl_entry->next;
        if (rl_entry->operation) {
            free((void*)rl_entry->operation);
        }
        free(rl_entry);
        rl_entry = next;
    }
    rate_limit_list = NULL;
    
    pthread_mutex_unlock(&rate_limit_lock);
}

/* Macros for easy security checking */
#define SEC_CHECK_ACCESS(pid, resource, operation, capability) \
    if (safe_access_check(pid, resource, operation, capability) != 0) return -EACCES

#define SEC_VALIDATE_INPUT(input, context) \
    if (detect_attack_patterns(input, context) != 0) return -EINVAL

#define SEC_CHECK_RATE_LIMIT(pid, uid, operation, limit) \
    if (check_rate_limit(pid, uid, operation, limit) != 0) return -EBUSY