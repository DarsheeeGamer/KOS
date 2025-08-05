#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include <sys/syscall.h>
#include "security.h"

/* Test helper macros */
#define TEST_ASSERT(condition, message) \
    do { \
        if (!(condition)) { \
            printf("FAIL: %s\n", message); \
            return -1; \
        } else { \
            printf("PASS: %s\n", message); \
        } \
    } while (0)

#define TEST_EXPECT_SUCCESS(call, message) \
    TEST_ASSERT((call) == KOS_SEC_SUCCESS, message)

#define TEST_EXPECT_ERROR(call, expected_error, message) \
    TEST_ASSERT((call) == (expected_error), message)

/* Test functions */
static int test_capabilities(void) {
    printf("\n=== Testing Capability System ===\n");
    
    uint32_t pid = getpid();
    kos_capability_set_t caps;
    
    /* Test capability retrieval */
    TEST_EXPECT_SUCCESS(kos_cap_get(pid, &caps), 
                       "Get initial capabilities");
    
    printf("Initial capabilities:\n");
    printf("  Effective: 0x%016llx\n", (unsigned long long)caps.effective);
    printf("  Permitted: 0x%016llx\n", (unsigned long long)caps.permitted);
    
    /* Test capability checking */
    bool has_kill = kos_cap_capable(pid, KOS_CAP_KILL);
    printf("Has KILL capability: %s\n", has_kill ? "yes" : "no");
    
    /* Test capability modification */
    if (has_kill) {
        TEST_EXPECT_SUCCESS(kos_cap_drop(pid, KOS_CAP_KILL),
                           "Drop KILL capability");
        
        TEST_ASSERT(!kos_cap_capable(pid, KOS_CAP_KILL),
                   "KILL capability should be dropped");
    }
    
    /* Test invalid capability */
    TEST_ASSERT(!kos_cap_capable(pid, KOS_CAP_MAX),
               "Invalid capability should return false");
    
    return 0;
}

static int test_selinux(void) {
    printf("\n=== Testing SELinux System ===\n");
    
    /* Test mode operations */
    kos_selinux_mode_t initial_mode = kos_selinux_get_mode();
    printf("Initial SELinux mode: %d\n", initial_mode);
    
    TEST_EXPECT_SUCCESS(kos_selinux_set_mode(KOS_SELINUX_PERMISSIVE),
                       "Set SELinux to permissive mode");
    
    TEST_ASSERT(kos_selinux_get_mode() == KOS_SELINUX_PERMISSIVE,
               "SELinux mode should be permissive");
    
    /* Test context operations */
    kos_selinux_context_t scontext = {
        .user = "system_u",
        .role = "system_r", 
        .type = "init_t",
        .level = "s0",
        .sid = 1
    };
    
    kos_selinux_context_t tcontext = {
        .user = "system_u",
        .role = "object_r",
        .type = "tmp_t", 
        .level = "s0",
        .sid = 2
    };
    
    /* Test access check */
    int access_result = kos_selinux_check_access(&scontext, &tcontext, 
                                                 "file", "read");
    printf("SELinux access check result: %d\n", access_result);
    
    /* Test simple policy loading */
    const char* test_policy = 
        "allow init_t tmp_t:file { read write create }\n"
        "deny user_t system_t:process { ptrace }\n";
    
    TEST_EXPECT_SUCCESS(kos_selinux_load_policy(test_policy, strlen(test_policy)),
                       "Load test SELinux policy");
    
    return 0;
}

static int test_seccomp(void) {
    printf("\n=== Testing Seccomp System ===\n");
    
    uint32_t pid = getpid();
    
    /* Test initial mode */
    kos_seccomp_mode_t initial_mode = kos_seccomp_get_mode(pid);
    TEST_ASSERT(initial_mode == KOS_SECCOMP_MODE_DISABLED,
               "Initial seccomp mode should be disabled");
    
    /* Test mode setting */
    TEST_EXPECT_SUCCESS(kos_seccomp_set_mode(pid, KOS_SECCOMP_MODE_FILTER),
                       "Set seccomp to filter mode");
    
    TEST_ASSERT(kos_seccomp_get_mode(pid) == KOS_SECCOMP_MODE_FILTER,
               "Seccomp mode should be filter");
    
    /* Test filter addition */
    kos_seccomp_filter_t filter = {
        .syscall_nr = SYS_write,
        .action = KOS_SECCOMP_RET_ALLOW,
        .arg_count = 0
    };
    
    TEST_EXPECT_SUCCESS(kos_seccomp_add_filter(pid, &filter),
                       "Add seccomp filter for write syscall");
    
    /* Test syscall checking */
    uint64_t args[6] = {1, 0, 0, 0, 0, 0}; /* stdout */
    int check_result = kos_seccomp_check_syscall(pid, SYS_write, args, 1);
    TEST_ASSERT(check_result == KOS_SEC_SUCCESS,
               "Write syscall should be allowed");
    
    /* Test denied syscall */
    check_result = kos_seccomp_check_syscall(pid, SYS_execve, args, 0);
    printf("Execve syscall check result: 0x%x\n", check_result);
    
    return 0;
}

static int test_audit(void) {
    printf("\n=== Testing Audit System ===\n");
    
    /* Test audit state */
    bool initial_state = kos_audit_is_enabled();
    printf("Audit initially enabled: %s\n", initial_state ? "yes" : "no");
    
    /* Test enabling audit */
    TEST_EXPECT_SUCCESS(kos_audit_set_enabled(true),
                       "Enable audit system");
    
    TEST_ASSERT(kos_audit_is_enabled(),
               "Audit should be enabled");
    
    /* Test event logging */
    TEST_EXPECT_SUCCESS(kos_audit_log_event(KOS_AUDIT_SYSCALL, getpid(),
                                           "test syscall event"),
                       "Log syscall audit event");
    
    TEST_EXPECT_SUCCESS(kos_audit_log_event(KOS_AUDIT_USER, getpid(),
                                           "test user event"),
                       "Log user audit event");
    
    /* Test event retrieval */
    kos_audit_event_t events[10];
    size_t count;
    
    TEST_EXPECT_SUCCESS(kos_audit_get_events(events, 10, &count),
                       "Retrieve audit events");
    
    printf("Retrieved %zu audit events\n", count);
    for (size_t i = 0; i < count; i++) {
        printf("  Event %zu: type=%d pid=%u msg='%s'\n", 
               i, events[i].type, events[i].pid, events[i].message);
    }
    
    return 0;
}

static int test_crypto(void) {
    printf("\n=== Testing Cryptographic Functions ===\n");
    
    /* Test random number generation */
    uint8_t random_data[32];
    TEST_EXPECT_SUCCESS(kos_crypto_random(random_data, sizeof(random_data)),
                       "Generate random data");
    
    printf("Random data: ");
    for (size_t i = 0; i < sizeof(random_data); i++) {
        printf("%02x", random_data[i]);
    }
    printf("\n");
    
    /* Test SHA-256 hashing */
    const char* test_string = "Hello, KOS Security Framework!";
    uint8_t hash[32];
    
    TEST_EXPECT_SUCCESS(kos_crypto_hash(KOS_HASH_SHA256, test_string, 
                                       strlen(test_string), hash, sizeof(hash)),
                       "Compute SHA-256 hash");
    
    printf("SHA-256 of '%s': ", test_string);
    for (size_t i = 0; i < sizeof(hash); i++) {
        printf("%02x", hash[i]);
    }
    printf("\n");
    
    /* Test hash consistency */
    uint8_t hash2[32];
    TEST_EXPECT_SUCCESS(kos_crypto_hash(KOS_HASH_SHA256, test_string,
                                       strlen(test_string), hash2, sizeof(hash2)),
                       "Compute second SHA-256 hash");
    
    TEST_ASSERT(memcmp(hash, hash2, sizeof(hash)) == 0,
               "Hash results should be consistent");
    
    /* Test encryption (basic) */
    const char* plaintext = "This is a test message for encryption!";
    uint8_t key[32];
    uint8_t ciphertext[64];
    size_t ct_len = sizeof(ciphertext);
    
    /* Generate a random key */
    TEST_EXPECT_SUCCESS(kos_crypto_random(key, sizeof(key)),
                       "Generate encryption key");
    
    /* Pad plaintext to 16-byte boundary */
    char padded_plaintext[48];
    size_t pt_len = strlen(plaintext);
    size_t padded_len = ((pt_len + 15) / 16) * 16;
    
    memcpy(padded_plaintext, plaintext, pt_len);
    memset(padded_plaintext + pt_len, 0, padded_len - pt_len);
    
    int encrypt_result = kos_crypto_encrypt(KOS_CIPHER_AES256_CBC, key, sizeof(key),
                                           NULL, padded_plaintext, padded_len,
                                           ciphertext, &ct_len);
    
    if (encrypt_result == KOS_SEC_SUCCESS) {
        printf("Encryption successful, ciphertext length: %zu\n", ct_len);
        printf("Ciphertext: ");
        for (size_t i = 0; i < ct_len && i < 32; i++) {
            printf("%02x", ciphertext[i]);
        }
        printf("%s\n", ct_len > 32 ? "..." : "");
    } else {
        printf("Encryption not implemented or failed: %d\n", encrypt_result);
    }
    
    return 0;
}

static int test_integration(void) {
    printf("\n=== Testing Integration Scenarios ===\n");
    
    uint32_t pid = getpid();
    
    /* Scenario 1: Secure a process */
    printf("Scenario 1: Securing current process\n");
    
    /* Drop dangerous capabilities */
    kos_cap_drop(pid, KOS_CAP_SYS_ADMIN);
    kos_cap_drop(pid, KOS_CAP_SYS_MODULE);
    
    /* Enable seccomp filtering */
    kos_seccomp_set_mode(pid, KOS_SECCOMP_MODE_FILTER);
    
    /* Allow basic syscalls */
    kos_seccomp_filter_t filters[] = {
        { .syscall_nr = SYS_read, .action = KOS_SECCOMP_RET_ALLOW, .arg_count = 0 },
        { .syscall_nr = SYS_write, .action = KOS_SECCOMP_RET_ALLOW, .arg_count = 0 },
        { .syscall_nr = SYS_exit, .action = KOS_SECCOMP_RET_ALLOW, .arg_count = 0 },
        { .syscall_nr = SYS_exit_group, .action = KOS_SECCOMP_RET_ALLOW, .arg_count = 0 }
    };
    
    for (size_t i = 0; i < sizeof(filters) / sizeof(filters[0]); i++) {
        kos_seccomp_add_filter(pid, &filters[i]);
    }
    
    /* Audit the security changes */
    kos_audit_log_event(KOS_AUDIT_CONFIG_CHANGE, pid, 
                        "Applied restrictive security profile");
    
    printf("Process secured successfully\n");
    
    /* Scenario 2: Policy enforcement check */
    printf("Scenario 2: Policy enforcement\n");
    
    kos_selinux_context_t user_ctx = {
        .user = "user_u", .role = "user_r", .type = "user_t", .level = "s0"
    };
    
    kos_selinux_context_t admin_ctx = {
        .user = "root", .role = "sysadm_r", .type = "sysadm_t", .level = "s0"
    };
    
    /* Check if user can access admin files */
    int user_access = kos_selinux_check_access(&user_ctx, &admin_ctx, 
                                               "file", "read");
    printf("User access to admin files: %s\n", 
           user_access == KOS_SEC_SUCCESS ? "allowed" : "denied");
    
    if (user_access != KOS_SEC_SUCCESS) {
        kos_audit_log_event(KOS_AUDIT_AVC, pid, 
                            "denied { read } for user_t sysadm_t:file");
    }
    
    return 0;
}

int main(int argc, char* argv[]) {
    printf("KOS Security Framework Test Suite\n");
    printf("==================================\n");
    
    /* Initialize security framework */
    if (kos_security_init() != KOS_SEC_SUCCESS) {
        printf("FATAL: Failed to initialize security framework\n");
        return 1;
    }
    
    /* Initialize individual subsystems */
    kos_cap_init();
    kos_selinux_init();
    kos_seccomp_init();
    kos_audit_init(); 
    kos_crypto_init();
    
    int failed_tests = 0;
    
    /* Run test suites */
    if (test_capabilities() != 0) failed_tests++;
    if (test_selinux() != 0) failed_tests++;
    if (test_seccomp() != 0) failed_tests++;
    if (test_audit() != 0) failed_tests++;
    if (test_crypto() != 0) failed_tests++;
    if (test_integration() != 0) failed_tests++;
    
    /* Print summary */
    printf("\n=== Test Summary ===\n");
    if (failed_tests == 0) {
        printf("All tests PASSED!\n");
    } else {
        printf("%d test suite(s) FAILED!\n", failed_tests);
    }
    
    /* Cleanup */
    kos_security_cleanup();
    kos_selinux_cleanup();
    kos_audit_cleanup();
    kos_crypto_cleanup();
    
    printf("\nTest suite completed.\n");
    return failed_tests > 0 ? 1 : 0;
}