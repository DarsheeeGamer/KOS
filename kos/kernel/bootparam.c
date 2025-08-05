/*
 * KOS Boot Parameter Configuration
 * Handles kernel command line parameters
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <errno.h>

/* Boot parameter types */
typedef enum {
    BOOTPARAM_TYPE_STRING,
    BOOTPARAM_TYPE_INT,
    BOOTPARAM_TYPE_BOOL,
    BOOTPARAM_TYPE_CALLBACK
} bootparam_type_t;

/* Boot parameter handler */
typedef int (*bootparam_handler_t)(const char *param, const char *value);

/* Boot parameter entry */
typedef struct bootparam_entry {
    const char *name;
    const char *description;
    bootparam_type_t type;
    void *data;
    size_t data_size;
    bootparam_handler_t handler;
    struct bootparam_entry *next;
} bootparam_entry_t;

/* Global boot parameter list */
static bootparam_entry_t *bootparam_list = NULL;

/* Common boot parameters */
static bool boot_debug = false;
static bool boot_quiet = false;
static bool boot_single = false;
static char boot_init[256] = "/sbin/init";
static char boot_root[256] = "/dev/sda1";
static int boot_loglevel = 7;
static bool boot_nosmp = false;
static int boot_maxcpus = -1;
static bool boot_noacpi = false;
static bool boot_nokaslr = false;
static char boot_console[256] = "tty0";
static int boot_mem_limit = 0;

/* Register boot parameter */
int register_bootparam(const char *name, const char *desc,
                       bootparam_type_t type, void *data, size_t size,
                       bootparam_handler_t handler)
{
    bootparam_entry_t *entry = malloc(sizeof(bootparam_entry_t));
    if (!entry) {
        return -ENOMEM;
    }
    
    entry->name = name;
    entry->description = desc;
    entry->type = type;
    entry->data = data;
    entry->data_size = size;
    entry->handler = handler;
    entry->next = bootparam_list;
    bootparam_list = entry;
    
    return 0;
}

/* Parse single boot parameter */
static int parse_bootparam(const char *param)
{
    char *equals = strchr(param, '=');
    char *name;
    char *value = NULL;
    
    if (equals) {
        /* Parameter with value */
        size_t name_len = equals - param;
        name = malloc(name_len + 1);
        strncpy(name, param, name_len);
        name[name_len] = '\0';
        value = equals + 1;
    } else {
        /* Boolean parameter */
        name = strdup(param);
    }
    
    /* Search for registered parameter */
    bootparam_entry_t *entry = bootparam_list;
    while (entry) {
        if (strcmp(entry->name, name) == 0) {
            /* Found parameter */
            if (entry->handler) {
                /* Use custom handler */
                int ret = entry->handler(name, value);
                free(name);
                return ret;
            }
            
            /* Parse based on type */
            switch (entry->type) {
                case BOOTPARAM_TYPE_STRING:
                    if (value) {
                        strncpy((char *)entry->data, value, entry->data_size - 1);
                        ((char *)entry->data)[entry->data_size - 1] = '\0';
                    }
                    break;
                
                case BOOTPARAM_TYPE_INT:
                    if (value) {
                        *(int *)entry->data = atoi(value);
                    }
                    break;
                
                case BOOTPARAM_TYPE_BOOL:
                    if (!value || strcmp(value, "1") == 0 || 
                        strcmp(value, "true") == 0 || strcmp(value, "yes") == 0) {
                        *(bool *)entry->data = true;
                    } else {
                        *(bool *)entry->data = false;
                    }
                    break;
                
                default:
                    break;
            }
            
            free(name);
            return 0;
        }
        entry = entry->next;
    }
    
    /* Unknown parameter - might be handled elsewhere */
    free(name);
    return 0;
}

/* Parse kernel command line */
int parse_cmdline(const char *cmdline)
{
    if (!cmdline) {
        return -EINVAL;
    }
    
    char *cmdline_copy = strdup(cmdline);
    char *token = strtok(cmdline_copy, " ");
    
    while (token) {
        parse_bootparam(token);
        token = strtok(NULL, " ");
    }
    
    free(cmdline_copy);
    return 0;
}

/* Special handlers */
static int handle_mem(const char *param, const char *value)
{
    if (!value) return -EINVAL;
    
    char *end;
    long size = strtol(value, &end, 10);
    
    /* Handle suffixes */
    if (*end == 'K' || *end == 'k') {
        size *= 1024;
    } else if (*end == 'M' || *end == 'm') {
        size *= 1024 * 1024;
    } else if (*end == 'G' || *end == 'g') {
        size *= 1024 * 1024 * 1024;
    }
    
    boot_mem_limit = size;
    return 0;
}

static int handle_console(const char *param, const char *value)
{
    if (!value) return -EINVAL;
    
    /* Parse console parameters like console=ttyS0,115200n8 */
    strncpy(boot_console, value, sizeof(boot_console) - 1);
    boot_console[sizeof(boot_console) - 1] = '\0';
    
    /* TODO: Parse baud rate and settings */
    
    return 0;
}

/* Initialize boot parameters */
void bootparam_init(void)
{
    /* Register common boot parameters */
    register_bootparam("debug", "Enable debug mode",
                       BOOTPARAM_TYPE_BOOL, &boot_debug, sizeof(boot_debug), NULL);
    
    register_bootparam("quiet", "Quiet boot",
                       BOOTPARAM_TYPE_BOOL, &boot_quiet, sizeof(boot_quiet), NULL);
    
    register_bootparam("single", "Single user mode",
                       BOOTPARAM_TYPE_BOOL, &boot_single, sizeof(boot_single), NULL);
    
    register_bootparam("init", "Init program path",
                       BOOTPARAM_TYPE_STRING, boot_init, sizeof(boot_init), NULL);
    
    register_bootparam("root", "Root device",
                       BOOTPARAM_TYPE_STRING, boot_root, sizeof(boot_root), NULL);
    
    register_bootparam("loglevel", "Kernel log level (0-7)",
                       BOOTPARAM_TYPE_INT, &boot_loglevel, sizeof(boot_loglevel), NULL);
    
    register_bootparam("nosmp", "Disable SMP",
                       BOOTPARAM_TYPE_BOOL, &boot_nosmp, sizeof(boot_nosmp), NULL);
    
    register_bootparam("maxcpus", "Maximum CPUs",
                       BOOTPARAM_TYPE_INT, &boot_maxcpus, sizeof(boot_maxcpus), NULL);
    
    register_bootparam("noacpi", "Disable ACPI",
                       BOOTPARAM_TYPE_BOOL, &boot_noacpi, sizeof(boot_noacpi), NULL);
    
    register_bootparam("nokaslr", "Disable KASLR",
                       BOOTPARAM_TYPE_BOOL, &boot_nokaslr, sizeof(boot_nokaslr), NULL);
    
    register_bootparam("console", "Console device",
                       BOOTPARAM_TYPE_CALLBACK, NULL, 0, handle_console);
    
    register_bootparam("mem", "Memory limit",
                       BOOTPARAM_TYPE_CALLBACK, NULL, 0, handle_mem);
}

/* Get boot parameter values */
bool bootparam_get_debug(void) { return boot_debug; }
bool bootparam_get_quiet(void) { return boot_quiet; }
bool bootparam_get_single(void) { return boot_single; }
const char *bootparam_get_init(void) { return boot_init; }
const char *bootparam_get_root(void) { return boot_root; }
int bootparam_get_loglevel(void) { return boot_loglevel; }
bool bootparam_get_nosmp(void) { return boot_nosmp; }
int bootparam_get_maxcpus(void) { return boot_maxcpus; }
bool bootparam_get_noacpi(void) { return boot_noacpi; }
bool bootparam_get_nokaslr(void) { return boot_nokaslr; }
const char *bootparam_get_console(void) { return boot_console; }
int bootparam_get_mem_limit(void) { return boot_mem_limit; }

/* Print all boot parameters */
void bootparam_print_all(void)
{
    printf("Boot Parameters:\n");
    printf("================\n");
    
    bootparam_entry_t *entry = bootparam_list;
    while (entry) {
        printf("%-20s: ", entry->name);
        
        switch (entry->type) {
            case BOOTPARAM_TYPE_STRING:
                printf("%s", (char *)entry->data);
                break;
            case BOOTPARAM_TYPE_INT:
                printf("%d", *(int *)entry->data);
                break;
            case BOOTPARAM_TYPE_BOOL:
                printf("%s", *(bool *)entry->data ? "true" : "false");
                break;
            default:
                printf("<handler>");
                break;
        }
        
        if (entry->description[0]) {
            printf(" (%s)", entry->description);
        }
        printf("\n");
        
        entry = entry->next;
    }
}