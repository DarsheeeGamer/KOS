/*
 * hello_c - KOS C Application
 * 
 * This is a template KOS application written in C.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// KOS API headers (when available)
// #include <kos/api.h>
// #include <kos/system.h>

// Application headers
#include "hello_c.h"

// Function prototypes
void print_usage(const char *program_name);
int process_arguments(int argc, char *argv[]);

// Main entry point
int main(int argc, char *argv[]) {
    printf("hello_c - KOS C Application\n");
    printf("==========================\n\n");
    
    // Process command line arguments
    if (process_arguments(argc, argv) != 0) {
        print_usage(argv[0]);
        return 1;
    }
    
    // Initialize KOS runtime (when available)
    // kos_init();
    
    // Your application logic here
    printf("Hello from hello_c!\n");
    printf("This is a KOS C application template.\n");
    
    // Example: Get system information
    // KOSSystemInfo info;
    // if (kos_get_system_info(&info) == 0) {
    //     printf("KOS Version: %s\n", info.version);
    //     printf("Platform: %s\n", info.platform);
    // }
    
    // Cleanup
    // kos_cleanup();
    
    return 0;
}

void print_usage(const char *program_name) {
    printf("Usage: %s [options]\n", program_name);
    printf("Options:\n");
    printf("  -h, --help     Show this help message\n");
    printf("  -v, --version  Show version information\n");
}

int process_arguments(int argc, char *argv[]) {
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            exit(0);
        } else if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--version") == 0) {
            printf("hello_c version 1.0.0\n");
            exit(0);
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            return 1;
        }
    }
    return 0;
}
