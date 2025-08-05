#include "security.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

/* Global security operations structure */
kos_security_ops_t kos_security_ops = {0};

/* Security module list */
static kos_security_module_t* security_modules = NULL;
static pthread_mutex_t security_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool security_initialized = false;

/* Core security functions */
int kos_security_init(void) {
    pthread_mutex_lock(&security_mutex);
    
    if (security_initialized) {
        pthread_mutex_unlock(&security_mutex);
        return KOS_SEC_SUCCESS;
    }
    
    /* Initialize default security operations */
    kos_security_ops.check_permission = NULL;
    kos_security_ops.set_context = NULL;
    kos_security_ops.get_context = NULL;
    kos_security_ops.audit_log = NULL;
    
    security_initialized = true;
    pthread_mutex_unlock(&security_mutex);
    
    printf("[KOS Security] Core security framework initialized\n");
    return KOS_SEC_SUCCESS;
}

void kos_security_cleanup(void) {
    pthread_mutex_lock(&security_mutex);
    
    /* Cleanup registered modules */
    kos_security_module_t* module = security_modules;
    while (module) {
        kos_security_module_t* next = module->next;
        if (module->cleanup) {
            module->cleanup();
        }
        module = next;
    }
    security_modules = NULL;
    
    security_initialized = false;
    pthread_mutex_unlock(&security_mutex);
    
    printf("[KOS Security] Core security framework cleanup completed\n");
}

int kos_security_check_permission(uint32_t pid, const char* object, 
                                  const char* permission) {
    if (!object || !permission) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&security_mutex);
    
    /* Check with registered modules */
    kos_security_module_t* module = security_modules;
    while (module) {
        if (module->check_permission) {
            int result = module->check_permission(pid, object, permission);
            if (result != KOS_SEC_SUCCESS) {
                pthread_mutex_unlock(&security_mutex);
                return result;
            }
        }
        module = module->next;
    }
    
    pthread_mutex_unlock(&security_mutex);
    return KOS_SEC_SUCCESS;
}

int kos_security_set_context(uint32_t pid, const char* context) {
    if (!context) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&security_mutex);
    
    if (kos_security_ops.set_context) {
        int result = kos_security_ops.set_context(pid, context);
        pthread_mutex_unlock(&security_mutex);
        return result;
    }
    
    pthread_mutex_unlock(&security_mutex);
    return KOS_SEC_SUCCESS;
}

int kos_security_get_context(uint32_t pid, char* context, size_t size) {
    if (!context) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&security_mutex);
    
    if (kos_security_ops.get_context) {
        int result = kos_security_ops.get_context(pid, context, size);
        pthread_mutex_unlock(&security_mutex);
        return result;
    }
    
    /* Default context */
    snprintf(context, size, "unconfined_u:unconfined_r:unconfined_t:s0");
    
    pthread_mutex_unlock(&security_mutex);
    return KOS_SEC_SUCCESS;
}

/* Security module registration */
int kos_security_register_module(kos_security_module_t* module) {
    if (!module || !module->name) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&security_mutex);
    
    /* Check if module is already registered */
    kos_security_module_t* existing = security_modules;
    while (existing) {
        if (strcmp(existing->name, module->name) == 0) {
            pthread_mutex_unlock(&security_mutex);
            return KOS_SEC_ERROR;
        }
        existing = existing->next;
    }
    
    /* Add to the front of the list */
    module->next = security_modules;
    security_modules = module;
    
    /* Initialize the module */
    if (module->init) {
        int result = module->init();
        if (result != KOS_SEC_SUCCESS) {
            /* Remove from list on initialization failure */
            security_modules = module->next;
            pthread_mutex_unlock(&security_mutex);
            return result;
        }
    }
    
    pthread_mutex_unlock(&security_mutex);
    
    printf("[KOS Security] Registered security module: %s\n", module->name);
    return KOS_SEC_SUCCESS;
}

int kos_security_unregister_module(kos_security_module_t* module) {
    if (!module) {
        return KOS_SEC_EINVAL;
    }
    
    pthread_mutex_lock(&security_mutex);
    
    /* Find and remove the module */
    kos_security_module_t** current = &security_modules;
    while (*current) {
        if (*current == module) {
            *current = module->next;
            
            /* Cleanup the module */
            if (module->cleanup) {
                module->cleanup();
            }
            
            pthread_mutex_unlock(&security_mutex);
            printf("[KOS Security] Unregistered security module: %s\n", module->name);
            return KOS_SEC_SUCCESS;
        }
        current = &(*current)->next;
    }
    
    pthread_mutex_unlock(&security_mutex);
    return KOS_SEC_ERROR;
}

/* Utility functions */
const char* kos_security_strerror(int error_code) {
    switch (error_code) {
        case KOS_SEC_SUCCESS:
            return "Success";
        case KOS_SEC_ERROR:
            return "General error";
        case KOS_SEC_EPERM:
            return "Operation not permitted";
        case KOS_SEC_EACCES:
            return "Access denied";
        case KOS_SEC_EINVAL:
            return "Invalid argument";
        case KOS_SEC_ENOMEM:
            return "Out of memory";
        default:
            return "Unknown error";
    }
}

void kos_security_print_status(void) {
    pthread_mutex_lock(&security_mutex);
    
    printf("KOS Security Framework Status:\n");
    printf("  Initialized: %s\n", security_initialized ? "yes" : "no");
    
    printf("  Registered modules:\n");
    kos_security_module_t* module = security_modules;
    int count = 0;
    while (module) {
        printf("    - %s\n", module->name);
        module = module->next;
        count++;
    }
    
    if (count == 0) {
        printf("    (none)\n");
    }
    
    pthread_mutex_unlock(&security_mutex);
}