/*
 * Simple KOS Network Stack Test
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include "netstack.h"

static volatile int running = 1;

void signal_handler(int sig) {
    (void)sig;
    running = 0;
}

int main(void) {
    printf("KOS Network Stack Simple Test\n");
    printf("=============================\n");
    
    signal(SIGINT, signal_handler);
    
    /* Initialize network stack */
    printf("Initializing network stack...\n");
    int ret = kos_netstack_init();
    if (ret < 0) {
        printf("Failed to initialize network stack: %d\n", ret);
        return 1;
    }
    printf("Network stack initialized successfully\n");
    
    /* Test socket creation */
    printf("\nTesting socket creation...\n");
    
    int tcp_fd = kos_socket(KOS_AF_INET, KOS_SOCK_STREAM, 0);
    if (tcp_fd >= 0) {
        printf("  TCP socket created: fd=%d\n", tcp_fd);
        kos_close_socket(tcp_fd);
    } else {
        printf("  TCP socket creation failed: %d\n", tcp_fd);
    }
    
    int udp_fd = kos_socket(KOS_AF_INET, KOS_SOCK_DGRAM, 0);
    if (udp_fd >= 0) {
        printf("  UDP socket created: fd=%d\n", udp_fd);
        kos_close_socket(udp_fd);
    } else {
        printf("  UDP socket creation failed: %d\n", udp_fd);
    }
    
    /* Test socket options */
    printf("\nTesting socket options...\n");
    tcp_fd = kos_socket(KOS_AF_INET, KOS_SOCK_STREAM, 0);
    if (tcp_fd >= 0) {
        int opt = 1;
        ret = kos_setsockopt(tcp_fd, KOS_SOL_SOCKET, KOS_SO_REUSEADDR, &opt, sizeof(opt));
        printf("  Set SO_REUSEADDR: %s\n", ret == 0 ? "OK" : "FAILED");
        
        ret = kos_setsockopt(tcp_fd, KOS_SOL_SOCKET, KOS_SO_KEEPALIVE, &opt, sizeof(opt));
        printf("  Set SO_KEEPALIVE: %s\n", ret == 0 ? "OK" : "FAILED");
        
        kos_close_socket(tcp_fd);
    }
    
    /* Test network interfaces */
    printf("\nNetwork interfaces:\n");
    kos_netif_dump();
    
    /* Test statistics */
    printf("\nNetwork statistics:\n");
    kos_netstat_dump();
    
    printf("\nIP statistics:\n");
    kos_ip_stats();
    
    printf("\nUDP statistics:\n");
    kos_udp_stats();
    
    printf("\nTest completed successfully!\n");
    printf("Press Ctrl+C to exit...\n");
    
    /* Keep running to show that the network stack is working */
    while (running) {
        sleep(1);
    }
    
    /* Shutdown network stack */
    printf("\nShutting down network stack...\n");
    kos_netstack_shutdown();
    
    printf("Test finished\n");
    return 0;
}