/*
 * KOS Module Configuration System
 * Handles module parameters and configuration
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <pthread.h>
#include <errno.h>
#include <dirent.h>
#include <sys/stat.h>

/* Module parameter types */
typedef enum {
    MODPARAM_TYPE_INT,
    MODPARAM_TYPE_UINT,
    MODPARAM_TYPE_LONG,
    MODPARAM_TYPE_ULONG,
    MODPARAM_TYPE_STRING,
    MODPARAM_TYPE_BOOL,
    MODPARAM_TYPE_ARRAY
} modparam_type_t;

/* Module parameter flags */
#define MODPARAM_FLAG_RO    0x01  /* Read-only */
#define MODPARAM_FLAG_RW    0x02  /* Read-write */

/* Module parameter entry */
typedef struct modparam {
    char name[64];
    char description[256];
    modparam_type_t type;
    uint32_t flags;
    void *data;
    size_t size;
    int array_size;
    struct modparam *next;
} modparam_t;

/* Module configuration entry */
typedef struct module_config {
    char name[64];                    /* Module name */
    char path[256];                   /* Module path */
    modparam_t *params;              /* Parameter list */
    bool loaded;                     /* Is module loaded */
    void *handle;                    /* Module handle */
    struct module_config *next;       /* Next module */
} module_config_t;

/* Global module configuration */
static module_config_t *module_list = NULL;
static pthread_rwlock_t module_lock = PTHREAD_RWLOCK_INITIALIZER;

/* Configuration directories */
static const char *modprobe_dirs[] = {
    "/etc/modprobe.d",
    "/usr/lib/modprobe.d",
    "/run/modprobe.d",
    NULL
};

/* Module blacklist */
typedef struct blacklist_entry {
    char module_name[64];
    struct blacklist_entry *next;
} blacklist_entry_t;

static blacklist_entry_t *blacklist = NULL;

/* Module aliases */
typedef struct alias_entry {
    char alias[128];
    char module[64];
    struct alias_entry *next;
} alias_entry_t;

static alias_entry_t *aliases = NULL;

/* Module options */
typedef struct option_entry {
    char module[64];
    char options[256];
    struct option_entry *next;
} option_entry_t;

static option_entry_t *options = NULL;

/* Find module configuration */
static module_config_t *find_module_config(const char *name)
{
    module_config_t *mod = module_list;
    while (mod) {
        if (strcmp(mod->name, name) == 0) {
            return mod;
        }
        mod = mod->next;
    }
    return NULL;
}

/* Create module configuration */
static module_config_t *create_module_config(const char *name)
{
    module_config_t *mod = calloc(1, sizeof(module_config_t));
    if (!mod) {
        return NULL;
    }
    
    strncpy(mod->name, name, sizeof(mod->name) - 1);
    mod->next = module_list;
    module_list = mod;
    
    return mod;
}

/* Register module parameter */
int register_module_param(const char *module_name, const char *param_name,
                          const char *desc, modparam_type_t type,
                          uint32_t flags, void *data, size_t size)
{
    pthread_rwlock_wrlock(&module_lock);
    
    /* Find or create module config */
    module_config_t *mod = find_module_config(module_name);
    if (!mod) {
        mod = create_module_config(module_name);
        if (!mod) {
            pthread_rwlock_unlock(&module_lock);
            return -ENOMEM;
        }
    }
    
    /* Create parameter */
    modparam_t *param = calloc(1, sizeof(modparam_t));
    if (!param) {
        pthread_rwlock_unlock(&module_lock);
        return -ENOMEM;
    }
    
    strncpy(param->name, param_name, sizeof(param->name) - 1);
    strncpy(param->description, desc, sizeof(param->description) - 1);
    param->type = type;
    param->flags = flags;
    param->data = data;
    param->size = size;
    
    /* Link to module */
    param->next = mod->params;
    mod->params = param;
    
    pthread_rwlock_unlock(&module_lock);
    return 0;
}

/* Parse modprobe configuration line */
static void parse_modprobe_line(const char *line)
{
    char cmd[32], arg1[128], arg2[256];
    
    if (sscanf(line, "%31s %127s %255[^\n]", cmd, arg1, arg2) < 2) {
        return;
    }
    
    if (strcmp(cmd, "blacklist") == 0) {
        /* Add to blacklist */
        blacklist_entry_t *entry = malloc(sizeof(blacklist_entry_t));
        if (entry) {
            strncpy(entry->module_name, arg1, sizeof(entry->module_name) - 1);
            entry->next = blacklist;
            blacklist = entry;
        }
    }
    else if (strcmp(cmd, "alias") == 0) {
        /* Add alias */
        alias_entry_t *entry = malloc(sizeof(alias_entry_t));
        if (entry) {
            strncpy(entry->alias, arg1, sizeof(entry->alias) - 1);
            strncpy(entry->module, arg2, sizeof(entry->module) - 1);
            entry->next = aliases;
            aliases = entry;
        }
    }
    else if (strcmp(cmd, "options") == 0) {
        /* Add module options */
        option_entry_t *entry = malloc(sizeof(option_entry_t));
        if (entry) {
            strncpy(entry->module, arg1, sizeof(entry->module) - 1);
            strncpy(entry->options, arg2, sizeof(entry->options) - 1);
            entry->next = options;
            options = entry;
        }
    }
    else if (strcmp(cmd, "install") == 0) {
        /* Install command - store for later use */
        /* TODO: Implement install commands */
    }
    else if (strcmp(cmd, "remove") == 0) {
        /* Remove command - store for later use */
        /* TODO: Implement remove commands */
    }
}

/* Load modprobe configuration file */
static void load_modprobe_file(const char *filepath)
{
    FILE *f = fopen(filepath, "r");
    if (!f) {
        return;
    }
    
    char line[512];
    while (fgets(line, sizeof(line), f)) {
        /* Skip comments and empty lines */
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        
        if (*p == '#' || *p == '\n' || *p == '\0') {
            continue;
        }
        
        /* Remove trailing newline */
        char *nl = strchr(p, '\n');
        if (nl) *nl = '\0';
        
        parse_modprobe_line(p);
    }
    
    fclose(f);
}

/* Load all modprobe configuration */
void load_modprobe_config(void)
{
    pthread_rwlock_wrlock(&module_lock);
    
    /* Load configuration from all directories */
    for (int i = 0; modprobe_dirs[i]; i++) {
        DIR *dir = opendir(modprobe_dirs[i]);
        if (!dir) continue;
        
        struct dirent *entry;
        while ((entry = readdir(dir)) != NULL) {
            /* Only process .conf files */
            char *ext = strrchr(entry->d_name, '.');
            if (!ext || strcmp(ext, ".conf") != 0) {
                continue;
            }
            
            char filepath[512];
            snprintf(filepath, sizeof(filepath), "%s/%s", 
                     modprobe_dirs[i], entry->d_name);
            
            load_modprobe_file(filepath);
        }
        
        closedir(dir);
    }
    
    pthread_rwlock_unlock(&module_lock);
}

/* Check if module is blacklisted */
bool is_module_blacklisted(const char *module_name)
{
    pthread_rwlock_rdlock(&module_lock);
    
    blacklist_entry_t *entry = blacklist;
    while (entry) {
        if (strcmp(entry->module_name, module_name) == 0) {
            pthread_rwlock_unlock(&module_lock);
            return true;
        }
        entry = entry->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
    return false;
}

/* Resolve module alias */
const char *resolve_module_alias(const char *alias)
{
    pthread_rwlock_rdlock(&module_lock);
    
    alias_entry_t *entry = aliases;
    while (entry) {
        if (strcmp(entry->alias, alias) == 0) {
            pthread_rwlock_unlock(&module_lock);
            return entry->module;
        }
        entry = entry->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
    return alias; /* No alias found, return original */
}

/* Get module options */
const char *get_module_options(const char *module_name)
{
    pthread_rwlock_rdlock(&module_lock);
    
    option_entry_t *entry = options;
    while (entry) {
        if (strcmp(entry->module, module_name) == 0) {
            pthread_rwlock_unlock(&module_lock);
            return entry->options;
        }
        entry = entry->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
    return NULL;
}

/* Set module parameter value */
int set_module_param(const char *module_name, const char *param_name,
                     const char *value)
{
    pthread_rwlock_wrlock(&module_lock);
    
    module_config_t *mod = find_module_config(module_name);
    if (!mod) {
        pthread_rwlock_unlock(&module_lock);
        return -ENOENT;
    }
    
    /* Find parameter */
    modparam_t *param = mod->params;
    while (param) {
        if (strcmp(param->name, param_name) == 0) {
            /* Check if writable */
            if (!(param->flags & MODPARAM_FLAG_RW)) {
                pthread_rwlock_unlock(&module_lock);
                return -EPERM;
            }
            
            /* Set value based on type */
            switch (param->type) {
                case MODPARAM_TYPE_INT:
                    *(int *)param->data = atoi(value);
                    break;
                case MODPARAM_TYPE_UINT:
                    *(unsigned int *)param->data = strtoul(value, NULL, 0);
                    break;
                case MODPARAM_TYPE_LONG:
                    *(long *)param->data = strtol(value, NULL, 0);
                    break;
                case MODPARAM_TYPE_ULONG:
                    *(unsigned long *)param->data = strtoul(value, NULL, 0);
                    break;
                case MODPARAM_TYPE_STRING:
                    strncpy((char *)param->data, value, param->size - 1);
                    ((char *)param->data)[param->size - 1] = '\0';
                    break;
                case MODPARAM_TYPE_BOOL:
                    *(bool *)param->data = (strcmp(value, "1") == 0 ||
                                            strcmp(value, "true") == 0 ||
                                            strcmp(value, "yes") == 0);
                    break;
                default:
                    pthread_rwlock_unlock(&module_lock);
                    return -EINVAL;
            }
            
            pthread_rwlock_unlock(&module_lock);
            return 0;
        }
        param = param->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
    return -ENOENT;
}

/* Get module parameter value */
int get_module_param(const char *module_name, const char *param_name,
                     char *buffer, size_t size)
{
    pthread_rwlock_rdlock(&module_lock);
    
    module_config_t *mod = find_module_config(module_name);
    if (!mod) {
        pthread_rwlock_unlock(&module_lock);
        return -ENOENT;
    }
    
    /* Find parameter */
    modparam_t *param = mod->params;
    while (param) {
        if (strcmp(param->name, param_name) == 0) {
            /* Format value based on type */
            switch (param->type) {
                case MODPARAM_TYPE_INT:
                    snprintf(buffer, size, "%d", *(int *)param->data);
                    break;
                case MODPARAM_TYPE_UINT:
                    snprintf(buffer, size, "%u", *(unsigned int *)param->data);
                    break;
                case MODPARAM_TYPE_LONG:
                    snprintf(buffer, size, "%ld", *(long *)param->data);
                    break;
                case MODPARAM_TYPE_ULONG:
                    snprintf(buffer, size, "%lu", *(unsigned long *)param->data);
                    break;
                case MODPARAM_TYPE_STRING:
                    strncpy(buffer, (char *)param->data, size - 1);
                    buffer[size - 1] = '\0';
                    break;
                case MODPARAM_TYPE_BOOL:
                    snprintf(buffer, size, "%s", 
                             *(bool *)param->data ? "true" : "false");
                    break;
                default:
                    pthread_rwlock_unlock(&module_lock);
                    return -EINVAL;
            }
            
            pthread_rwlock_unlock(&module_lock);
            return 0;
        }
        param = param->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
    return -ENOENT;
}

/* List all modules and their parameters */
void list_module_params(void (*callback)(const char *module, const char *param,
                                         const char *value, const char *desc))
{
    if (!callback) return;
    
    pthread_rwlock_rdlock(&module_lock);
    
    module_config_t *mod = module_list;
    while (mod) {
        modparam_t *param = mod->params;
        while (param) {
            char value[256];
            
            /* Format value */
            switch (param->type) {
                case MODPARAM_TYPE_INT:
                    snprintf(value, sizeof(value), "%d", *(int *)param->data);
                    break;
                case MODPARAM_TYPE_UINT:
                    snprintf(value, sizeof(value), "%u", *(unsigned int *)param->data);
                    break;
                case MODPARAM_TYPE_LONG:
                    snprintf(value, sizeof(value), "%ld", *(long *)param->data);
                    break;
                case MODPARAM_TYPE_ULONG:
                    snprintf(value, sizeof(value), "%lu", *(unsigned long *)param->data);
                    break;
                case MODPARAM_TYPE_STRING:
                    strncpy(value, (char *)param->data, sizeof(value) - 1);
                    value[sizeof(value) - 1] = '\0';
                    break;
                case MODPARAM_TYPE_BOOL:
                    snprintf(value, sizeof(value), "%s",
                             *(bool *)param->data ? "true" : "false");
                    break;
                default:
                    strcpy(value, "<unknown>");
                    break;
            }
            
            callback(mod->name, param->name, value, param->description);
            param = param->next;
        }
        mod = mod->next;
    }
    
    pthread_rwlock_unlock(&module_lock);
}

/* Initialize module configuration system */
void modconfig_init(void)
{
    /* Load modprobe configuration */
    load_modprobe_config();
    
    /* TODO: Scan for available modules */
    /* TODO: Load module dependency information */
}