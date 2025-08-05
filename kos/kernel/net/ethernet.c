/*
 * KOS Ethernet Layer Implementation
 * Handles Ethernet frame processing, MAC address operations, and Ethernet type handling
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>

/* External protocol functions */
extern int kos_ipv6_input(kos_netif_t *netif, kos_packet_t *pkt);
extern int kos_vlan_input(kos_netif_t *netif, kos_packet_t *pkt);

/* Ethernet types */
#define ETH_P_IP        0x0800  /* IPv4 */
#define ETH_P_ARP       0x0806  /* ARP */
#define ETH_P_IPV6      0x86DD  /* IPv6 */
#define ETH_P_VLAN      0x8100  /* VLAN */

/* Ethernet frame constants */
#define ETH_ALEN        6       /* MAC address length */
#define ETH_HLEN        14      /* Ethernet header length */
#define ETH_ZLEN        60      /* Minimum frame length */
#define ETH_DATA_LEN    1500    /* Maximum data length */
#define ETH_FRAME_LEN   1514    /* Maximum frame length */

/* Special MAC addresses */
static const uint8_t broadcast_mac[ETH_ALEN] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static const uint8_t zero_mac[ETH_ALEN] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

/* Global Ethernet statistics */
static struct {
    uint64_t rx_frames;
    uint64_t tx_frames;
    uint64_t rx_bytes;
    uint64_t tx_bytes;
    uint64_t rx_errors;
    uint64_t tx_errors;
    uint64_t rx_dropped;
    uint64_t tx_dropped;
    uint64_t collisions;
    uint64_t multicast;
    pthread_mutex_t lock;
} eth_stats = {0};

/* MAC address operations */
static bool is_multicast_mac(const uint8_t* mac) {
    return (mac[0] & 0x01) != 0;
}

static bool is_broadcast_mac(const uint8_t* mac) {
    return memcmp(mac, broadcast_mac, ETH_ALEN) == 0;
}

static bool is_zero_mac(const uint8_t* mac) {
    return memcmp(mac, zero_mac, ETH_ALEN) == 0;
}

static bool is_valid_mac(const uint8_t* mac) {
    return !is_zero_mac(mac);
}

static void copy_mac(uint8_t* dest, const uint8_t* src) {
    memcpy(dest, src, ETH_ALEN);
}

static bool compare_mac(const uint8_t* mac1, const uint8_t* mac2) {
    return memcmp(mac1, mac2, ETH_ALEN) == 0;
}

static void print_mac(const uint8_t* mac) {
    printf("%02x:%02x:%02x:%02x:%02x:%02x",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

/* Generate random MAC address */
static void generate_random_mac(uint8_t* mac) {
    for (int i = 0; i < ETH_ALEN; i++) {
        mac[i] = rand() & 0xFF;
    }
    /* Set locally administered bit and clear multicast bit */
    mac[0] = (mac[0] & 0xFE) | 0x02;
}

/* Ethernet frame validation */
static int validate_ethernet_frame(kos_packet_t* pkt) {
    if (!pkt || !pkt->data) {
        return -1;
    }
    
    if (pkt->size < ETH_HLEN) {
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.rx_errors++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    kos_eth_header_t* eth_hdr = (kos_eth_header_t*)pkt->data;
    
    /* Validate destination MAC */
    if (!is_valid_mac(eth_hdr->dest) && !is_broadcast_mac(eth_hdr->dest) && 
        !is_multicast_mac(eth_hdr->dest)) {
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.rx_errors++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    /* Validate source MAC */
    if (!is_valid_mac(eth_hdr->src) || is_multicast_mac(eth_hdr->src)) {
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.rx_errors++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    return 0;
}

/* Process incoming Ethernet frame */
int kos_eth_input(kos_netif_t* netif, kos_packet_t* pkt) {
    if (!netif || !pkt) {
        return -1;
    }
    
    /* Validate frame */
    if (validate_ethernet_frame(pkt) < 0) {
        return -1;
    }
    
    kos_eth_header_t* eth_hdr = (kos_eth_header_t*)pkt->data;
    pkt->l2_header = eth_hdr;
    
    /* Convert network byte order to host byte order */
    uint16_t eth_type = ntohs(eth_hdr->type);
    
    /* Check if frame is for us */
    bool for_us = false;
    if (is_broadcast_mac(eth_hdr->dest)) {
        for_us = true;
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.multicast++;
        pthread_mutex_unlock(&eth_stats.lock);
    } else if (is_multicast_mac(eth_hdr->dest)) {
        for_us = true; /* Accept all multicast for now */
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.multicast++;
        pthread_mutex_unlock(&eth_stats.lock);
    } else if (compare_mac(eth_hdr->dest, netif->hw_addr)) {
        for_us = true;
    }
    
    if (!for_us) {
        /* Frame not for us, drop it */
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.rx_dropped++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    /* Update statistics */
    pthread_mutex_lock(&eth_stats.lock);
    eth_stats.rx_frames++;
    eth_stats.rx_bytes += pkt->size;
    pthread_mutex_unlock(&eth_stats.lock);
    
    netif->rx_packets++;
    netif->rx_bytes += pkt->size;
    
    /* Remove Ethernet header */
    if (kos_packet_pull(pkt, ETH_HLEN) < 0) {
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.rx_errors++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    /* Process based on Ethernet type */
    switch (eth_type) {
        case ETH_P_IP:
            return kos_ip_input(netif, pkt);
            
        case ETH_P_ARP:
            return kos_arp_input(netif, pkt);
            
        case ETH_P_IPV6:
            /* Process IPv6 packet */
            pthread_mutex_lock(&eth_stats.lock);
            eth_stats.ipv6_packets++;
            pthread_mutex_unlock(&eth_stats.lock);
            return kos_ipv6_input(netif, pkt);
            
        case ETH_P_VLAN:
            /* Process VLAN tagged packet */
            pthread_mutex_lock(&eth_stats.lock);
            eth_stats.vlan_packets++;
            pthread_mutex_unlock(&eth_stats.lock);
            return kos_vlan_input(netif, pkt);
            
        default:
            printf("Unknown Ethernet type: 0x%04x\n", eth_type);
            pthread_mutex_lock(&eth_stats.lock);
            eth_stats.rx_dropped++;
            pthread_mutex_unlock(&eth_stats.lock);
            return -1;
    }
}

/* Send Ethernet frame */
int kos_eth_output(kos_netif_t* netif, kos_packet_t* pkt, const uint8_t* dest) {
    if (!netif || !pkt || !dest) {
        return -1;
    }
    
    /* Check if we have enough space for Ethernet header */
    if (kos_packet_push(pkt, ETH_HLEN) < 0) {
        pthread_mutex_lock(&eth_stats.lock);
        eth_stats.tx_errors++;
        pthread_mutex_unlock(&eth_stats.lock);
        return -1;
    }
    
    /* Fill Ethernet header */
    kos_eth_header_t* eth_hdr = (kos_eth_header_t*)pkt->data;
    copy_mac(eth_hdr->dest, dest);
    copy_mac(eth_hdr->src, netif->hw_addr);
    
    /* Determine Ethernet type based on packet content */
    uint16_t eth_type;
    if (pkt->l3_header) {
        kos_ip_header_t* ip_hdr = (kos_ip_header_t*)pkt->l3_header;
        uint8_t version = (ip_hdr->version_ihl >> 4) & 0x0F;
        if (version == 4) {
            eth_type = ETH_P_IP;
        } else if (version == 6) {
            eth_type = ETH_P_IPV6;
        } else {
            eth_type = ETH_P_IP; /* Default to IPv4 */
        }
    } else {
        eth_type = ETH_P_IP; /* Default to IPv4 */
    }
    
    eth_hdr->type = htons(eth_type);
    pkt->l2_header = eth_hdr;
    
    /* Pad frame if too small */
    if (pkt->size < ETH_ZLEN) {
        size_t pad_len = ETH_ZLEN - pkt->size;
        if (pkt->size + pad_len > pkt->capacity) {
            pthread_mutex_lock(&eth_stats.lock);
            eth_stats.tx_errors++;
            pthread_mutex_unlock(&eth_stats.lock);
            return -1;
        }
        memset(pkt->data + pkt->size, 0, pad_len);
        pkt->size += pad_len;
    }
    
    /* Update statistics */
    pthread_mutex_lock(&eth_stats.lock);
    eth_stats.tx_frames++;
    eth_stats.tx_bytes += pkt->size;
    pthread_mutex_unlock(&eth_stats.lock);
    
    netif->tx_packets++;
    netif->tx_bytes += pkt->size;
    
    /* Send frame through network interface */
    if (netif->send) {
        return netif->send(netif, pkt);
    }
    
    return 0;
}

/* Set MAC address for network interface */
int kos_eth_set_mac_addr(kos_netif_t* netif, const uint8_t* mac) {
    if (!netif || !mac) {
        return -1;
    }
    
    if (!is_valid_mac(mac) || is_multicast_mac(mac)) {
        return -1;
    }
    
    copy_mac(netif->hw_addr, mac);
    printf("MAC address set to ");
    print_mac(netif->hw_addr);
    printf(" for interface %s\n", netif->name);
    
    return 0;
}

/* Get MAC address from network interface */
int kos_eth_get_mac_addr(kos_netif_t* netif, uint8_t* mac) {
    if (!netif || !mac) {
        return -1;
    }
    
    copy_mac(mac, netif->hw_addr);
    return 0;
}

/* Initialize network interface with random MAC */
int kos_eth_init_interface(kos_netif_t* netif) {
    if (!netif) {
        return -1;
    }
    
    /* Generate random MAC if not set */
    if (is_zero_mac(netif->hw_addr)) {
        generate_random_mac(netif->hw_addr);
        printf("Generated random MAC address ");
        print_mac(netif->hw_addr);
        printf(" for interface %s\n", netif->name);
    }
    
    return 0;
}

/* Ethernet address resolution */
int kos_eth_resolve_addr(kos_netif_t* netif, uint32_t ip_addr, uint8_t* mac) {
    if (!netif || !mac) {
        return -1;
    }
    
    /* Check if it's broadcast */
    if (ip_addr == INADDR_BROADCAST || 
        ip_addr == (netif->ip_addr | ~netif->netmask)) {
        copy_mac(mac, broadcast_mac);
        return 0;
    }
    
    /* Check if it's on the same subnet */
    if ((ip_addr & netif->netmask) != (netif->ip_addr & netif->netmask)) {
        /* Need to go through gateway, resolve gateway MAC */
        kos_route_t* route = kos_route_lookup(ip_addr);
        if (route && route->gateway != 0) {
            ip_addr = route->gateway;
        } else {
            return -1; /* No route */
        }
    }
    
    /* Look up in ARP cache */
    kos_arp_entry_t* arp_entry = kos_arp_lookup(ip_addr);
    if (arp_entry) {
        copy_mac(mac, arp_entry->hw_addr);
        return 0;
    }
    
    /* Send ARP request */
    return kos_arp_request(netif, ip_addr);
}

/* Dump Ethernet statistics */
void kos_eth_dump_stats(void) {
    pthread_mutex_lock(&eth_stats.lock);
    
    printf("Ethernet Statistics:\n");
    printf("  RX: %lu frames, %lu bytes\n", eth_stats.rx_frames, eth_stats.rx_bytes);
    printf("  TX: %lu frames, %lu bytes\n", eth_stats.tx_frames, eth_stats.tx_bytes);
    printf("  RX Errors: %lu, Dropped: %lu\n", eth_stats.rx_errors, eth_stats.rx_dropped);
    printf("  TX Errors: %lu, Dropped: %lu\n", eth_stats.tx_errors, eth_stats.tx_dropped);
    printf("  Collisions: %lu, Multicast: %lu\n", eth_stats.collisions, eth_stats.multicast);
    
    pthread_mutex_unlock(&eth_stats.lock);
}

/* Initialize Ethernet layer */
int kos_eth_init(void) {
    memset(&eth_stats, 0, sizeof(eth_stats));
    if (pthread_mutex_init(&eth_stats.lock, NULL) != 0) {
        return -1;
    }
    
    printf("Ethernet layer initialized\n");
    return 0;
}

/* Cleanup Ethernet layer */
void kos_eth_cleanup(void) {
    pthread_mutex_destroy(&eth_stats.lock);
    printf("Ethernet layer cleaned up\n");
}