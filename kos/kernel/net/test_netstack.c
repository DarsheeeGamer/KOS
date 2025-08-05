/*
 * KOS Network Stack Test Program
 * Demonstrates usage of the network protocol implementations
 */

#include "netstack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

static bool running = true;

void signal_handler(int sig) {
    printf("\nReceived signal %d, shutting down...\n", sig);
    running = false;
}

void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

void test_ethernet(void) {
    printf("\n=== Testing Ethernet Layer ===\n");
    
    /* Initialize Ethernet */
    if (kos_eth_init() < 0) {
        printf("Failed to initialize Ethernet layer\n");
        return;
    }
    
    /* Create test network interface */
    kos_netif_t* netif = kos_netif_create("eth0");
    if (!netif) {
        printf("Failed to create network interface\n");
        return;
    }
    
    /* Initialize interface with random MAC */
    kos_eth_init_interface(netif);
    
    /* Set IP address */
    uint32_t ip = 0xC0A80101; /* 192.168.1.1 */
    uint32_t mask = 0xFFFFFF00; /* 255.255.255.0 */
    kos_netif_set_addr(netif, ip, mask);
    
    printf("Created interface %s with IP ", netif->name);
    print_ip(netif->ip_addr);
    printf("/%u\n", __builtin_popcount(netif->netmask));
    
    /* Dump Ethernet statistics */
    kos_eth_dump_stats();
    
    kos_eth_cleanup();
}

void test_arp(void) {
    printf("\n=== Testing ARP Protocol ===\n");
    
    /* Initialize ARP */
    if (kos_arp_init() < 0) {
        printf("Failed to initialize ARP subsystem\n");
        return;
    }
    
    /* Create test network interface */
    kos_netif_t* netif = kos_netif_create("eth0");
    if (!netif) {
        printf("Failed to create network interface\n");
        kos_arp_cleanup();
        return;
    }
    
    kos_eth_init_interface(netif);
    kos_netif_set_addr(netif, 0xC0A80101, 0xFFFFFF00); /* 192.168.1.1/24 */
    
    /* Add some test ARP entries */
    uint8_t mac1[6] = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55};
    uint8_t mac2[6] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};
    
    kos_arp_add(0xC0A80102, mac1); /* 192.168.1.2 */
    kos_arp_add(0xC0A80103, mac2); /* 192.168.1.3 */
    
    /* Test ARP lookup */
    kos_arp_entry_t* entry = kos_arp_lookup(0xC0A80102);
    if (entry) {
        printf("ARP lookup successful for ");
        print_ip(entry->ip_addr);
        printf("\n");
    }
    
    /* Send gratuitous ARP */
    kos_arp_send_gratuitous(netif);
    
    /* Dump ARP cache and statistics */
    kos_arp_dump_cache();
    kos_arp_dump_stats();
    
    kos_netif_destroy(netif);
    kos_arp_cleanup();
}

void test_routing(void) {
    printf("\n=== Testing Routing Subsystem ===\n");
    
    /* Initialize routing */
    if (kos_route_init() < 0) {
        printf("Failed to initialize routing subsystem\n");
        return;
    }
    
    /* Create test network interfaces */
    kos_netif_t* eth0 = kos_netif_create("eth0");
    kos_netif_t* eth1 = kos_netif_create("eth1");
    
    if (!eth0 || !eth1) {
        printf("Failed to create network interfaces\n");
        kos_route_cleanup();
        return;
    }
    
    /* Configure interfaces */
    kos_netif_set_addr(eth0, 0xC0A80101, 0xFFFFFF00); /* 192.168.1.1/24 */
    kos_netif_set_addr(eth1, 0x0A000001, 0xFF000000);   /* 10.0.0.1/8 */
    
    /* Add interface routes */
    kos_route_add_interface_route(eth0);
    kos_route_add_interface_route(eth1);
    
    /* Add default gateway */
    kos_route_set_default_gw(0xC0A80101, eth0); /* 192.168.1.1 via eth0 */
    
    /* Add specific route */
    kos_route_add(0xAC100000, 0x0A000001, 0xFFF00000, eth1); /* 172.16.0.0/12 via 10.0.0.1 */
    
    /* Test route lookup */
    kos_route_t* route = kos_route_lookup(0xAC100101); /* 172.16.1.1 */
    if (route) {
        printf("Route found for 172.16.1.1: gateway ");
        if (route->gateway != 0) {
            print_ip(route->gateway);
        } else {
            printf("direct");
        }
        printf(" dev %s\n", route->interface->name);
    }
    
    /* Dump routing table and statistics */
    kos_route_dump();
    kos_route_dump_stats();
    
    kos_netif_destroy(eth0);
    kos_netif_destroy(eth1);
    kos_route_cleanup();
}

void test_netfilter(void) {
    printf("\n=== Testing Netfilter Subsystem ===\n");
    
    /* Initialize netfilter */
    if (kos_netfilter_init() < 0) {
        printf("Failed to initialize netfilter subsystem\n");
        return;
    }
    
    /* Create test packet */
    kos_packet_t* pkt = kos_packet_alloc(64);
    if (pkt) {
        /* Simulate packet processing through hooks */
        kos_nf_verdict_t verdict = kos_nf_hook_slow(KOS_NF_LOCAL_IN, pkt, NULL, NULL);
        printf("Packet verdict: %s\n", 
               (verdict == KOS_NF_ACCEPT) ? "ACCEPT" :
               (verdict == KOS_NF_DROP) ? "DROP" : "OTHER");
        
        kos_packet_free(pkt);
    }
    
    /* Dump netfilter and connection tracking statistics */
    kos_nf_dump_stats();
    kos_conntrack_dump_stats();
    kos_conntrack_dump_table();
    
    kos_netfilter_cleanup();
}

void test_dns(void) {
    printf("\n=== Testing DNS Resolver ===\n");
    
    /* Initialize DNS */
    if (kos_dns_init() < 0) {
        printf("Failed to initialize DNS subsystem\n");
        return;
    }
    
    /* Add custom DNS server */
    kos_dns_add_server(0x01010101); /* 1.1.1.1 - Cloudflare DNS */
    
    /* Test hostname validation */
    const char* test_hostnames[] = {
        "www.google.com",
        "github.com",
        "invalid..hostname",
        "toolonglabell23456789012345678901234567890123456789012345678901234567890.com",
        NULL
    };
    
    for (int i = 0; test_hostnames[i]; i++) {
        uint32_t ip;
        printf("Testing hostname: %s\n", test_hostnames[i]);
        int result = kos_dns_resolve(test_hostnames[i], &ip);
        if (result == 0) {
            printf("  Resolved to: ");
            print_ip(ip);
            printf("\n");
        } else {
            printf("  Resolution failed\n");
        }
    }
    
    /* Dump DNS cache and statistics */
    kos_dns_dump_cache();
    kos_dns_dump_stats();
    
    kos_dns_cleanup();
}

void test_dhcp(void) {
    printf("\n=== Testing DHCP Client ===\n");
    
    /* Initialize DHCP */
    if (kos_dhcp_init() < 0) {
        printf("Failed to initialize DHCP subsystem\n");
        return;
    }
    
    /* Create test network interface */
    kos_netif_t* netif = kos_netif_create("eth0");
    if (!netif) {
        printf("Failed to create network interface\n");
        kos_dhcp_cleanup();
        return;
    }
    
    kos_eth_init_interface(netif);
    
    /* Start DHCP client */
    printf("Starting DHCP client on %s...\n", netif->name);
    if (kos_dhcp_start_client(netif, "kos-test") == 0) {
        printf("DHCP client started successfully\n");
        
        /* Let it run for a few seconds */
        sleep(5);
        
        /* Stop DHCP client */
        kos_dhcp_stop_client(netif);
    } else {
        printf("Failed to start DHCP client\n");
    }
    
    /* Dump DHCP statistics */
    kos_dhcp_dump_stats();
    
    kos_netif_destroy(netif);
    kos_dhcp_cleanup();
}

int main(int argc, char* argv[]) {
    printf("KOS Network Stack Test Program\n");
    printf("==============================\n");
    
    /* Set up signal handling */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    /* Initialize random number generator */
    srand(time(NULL));
    
    /* Run tests based on arguments */
    if (argc > 1) {
        for (int i = 1; i < argc; i++) {
            if (strcmp(argv[i], "ethernet") == 0) {
                test_ethernet();
            } else if (strcmp(argv[i], "arp") == 0) {
                test_arp();
            } else if (strcmp(argv[i], "route") == 0) {
                test_routing();
            } else if (strcmp(argv[i], "netfilter") == 0) {
                test_netfilter();
            } else if (strcmp(argv[i], "dns") == 0) {
                test_dns();
            } else if (strcmp(argv[i], "dhcp") == 0) {
                test_dhcp();
            } else {
                printf("Unknown test: %s\n", argv[i]);
                printf("Available tests: ethernet, arp, route, netfilter, dns, dhcp\n");
            }
        }
    } else {
        /* Run all tests */
        test_ethernet();
        test_arp();
        test_routing();
        test_netfilter();
        test_dns();
        test_dhcp();
    }
    
    printf("\nAll tests completed.\n");
    return 0;
}