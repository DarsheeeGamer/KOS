/*
 * KOS VLAN (802.1Q) Implementation
 * Virtual LAN tagging support
 */

#include "netstack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <arpa/inet.h>

/* VLAN constants */
#define VLAN_HLEN           4       /* VLAN header length */
#define VLAN_ETH_HLEN       18      /* Total Ethernet + VLAN header */
#define VLAN_ID_MASK        0x0FFF  /* VLAN ID is 12 bits */
#define VLAN_PRIO_MASK      0xE000  /* Priority is 3 bits */
#define VLAN_PRIO_SHIFT     13
#define VLAN_CFI_MASK       0x1000  /* Canonical Format Indicator */

/* VLAN header structure */
typedef struct kos_vlan_header {
    uint16_t tci;           /* Tag Control Information */
    uint16_t encap_proto;   /* Encapsulated protocol */
} __attribute__((packed)) kos_vlan_header_t;

/* VLAN interface structure */
typedef struct kos_vlan_if {
    kos_netif_t *parent;    /* Parent physical interface */
    uint16_t vlan_id;       /* VLAN ID */
    uint8_t priority;       /* Default priority */
    char name[16];          /* Interface name (e.g., eth0.100) */
    
    /* Statistics */
    uint64_t rx_packets;
    uint64_t tx_packets;
    uint64_t rx_bytes;
    uint64_t tx_bytes;
    uint64_t rx_errors;
    uint64_t tx_errors;
    
    struct kos_vlan_if *next;
} kos_vlan_if_t;

/* Global VLAN interfaces list */
static kos_vlan_if_t *vlan_interfaces = NULL;
static pthread_mutex_t vlan_lock = PTHREAD_MUTEX_INITIALIZER;

/* VLAN statistics */
static struct {
    uint64_t rx_packets;
    uint64_t tx_packets;
    uint64_t rx_tagged;
    uint64_t tx_tagged;
    uint64_t rx_untagged;
    uint64_t invalid_vid;
    uint64_t unknown_vid;
    pthread_mutex_t lock;
} vlan_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Find VLAN interface by ID and parent */
static kos_vlan_if_t *find_vlan_if(kos_netif_t *parent, uint16_t vlan_id)
{
    kos_vlan_if_t *vif;
    
    pthread_mutex_lock(&vlan_lock);
    for (vif = vlan_interfaces; vif; vif = vif->next) {
        if (vif->parent == parent && vif->vlan_id == vlan_id) {
            pthread_mutex_unlock(&vlan_lock);
            return vif;
        }
    }
    pthread_mutex_unlock(&vlan_lock);
    
    return NULL;
}

/* Process incoming VLAN packet */
int kos_vlan_input(kos_netif_t *netif, kos_packet_t *pkt)
{
    kos_vlan_header_t *vlan;
    kos_eth_header_t *eth;
    uint16_t vlan_tci, vlan_id, priority;
    uint16_t encap_proto;
    kos_vlan_if_t *vif;
    
    pthread_mutex_lock(&vlan_stats.lock);
    vlan_stats.rx_packets++;
    vlan_stats.rx_tagged++;
    pthread_mutex_unlock(&vlan_stats.lock);
    
    /* Check minimum size */
    if (pkt->size < sizeof(kos_vlan_header_t)) {
        printf("VLAN: Packet too small\n");
        return -1;
    }
    
    /* Get VLAN header */
    vlan = (kos_vlan_header_t *)pkt->data;
    vlan_tci = ntohs(vlan->tci);
    encap_proto = ntohs(vlan->encap_proto);
    
    /* Extract VLAN ID and priority */
    vlan_id = vlan_tci & VLAN_ID_MASK;
    priority = (vlan_tci & VLAN_PRIO_MASK) >> VLAN_PRIO_SHIFT;
    
    /* Validate VLAN ID (0 and 4095 are reserved) */
    if (vlan_id == 0 || vlan_id == 4095) {
        printf("VLAN: Invalid VID %u\n", vlan_id);
        pthread_mutex_lock(&vlan_stats.lock);
        vlan_stats.invalid_vid++;
        pthread_mutex_unlock(&vlan_stats.lock);
        return -1;
    }
    
    /* Find VLAN interface */
    vif = find_vlan_if(netif, vlan_id);
    if (!vif) {
        printf("VLAN: Unknown VID %u on %s\n", vlan_id, netif->name);
        pthread_mutex_lock(&vlan_stats.lock);
        vlan_stats.unknown_vid++;
        pthread_mutex_unlock(&vlan_stats.lock);
        return -1;
    }
    
    /* Update VLAN interface statistics */
    vif->rx_packets++;
    vif->rx_bytes += pkt->size;
    
    /* Remove VLAN header */
    if (kos_packet_pull(pkt, sizeof(kos_vlan_header_t)) < 0) {
        vif->rx_errors++;
        return -1;
    }
    
    /* Update Ethernet header to point after VLAN tag */
    eth = (kos_eth_header_t *)((uint8_t *)pkt->data - sizeof(kos_eth_header_t) - sizeof(kos_vlan_header_t));
    
    /* Process based on encapsulated protocol */
    switch (encap_proto) {
        case ETH_P_IP:
            return kos_ip_input(netif, pkt);
            
        case ETH_P_IPV6:
            return kos_ipv6_input(netif, pkt);
            
        case ETH_P_ARP:
            return kos_arp_input(netif, pkt);
            
        default:
            printf("VLAN: Unknown encapsulated protocol 0x%04x\n", encap_proto);
            vif->rx_errors++;
            return -1;
    }
}

/* Add VLAN tag to outgoing packet */
int kos_vlan_output(kos_vlan_if_t *vif, kos_packet_t *pkt, uint16_t proto)
{
    kos_vlan_header_t *vlan;
    uint16_t vlan_tci;
    
    pthread_mutex_lock(&vlan_stats.lock);
    vlan_stats.tx_packets++;
    vlan_stats.tx_tagged++;
    pthread_mutex_unlock(&vlan_stats.lock);
    
    /* Add space for VLAN header */
    if (kos_packet_push(pkt, sizeof(kos_vlan_header_t)) < 0) {
        vif->tx_errors++;
        return -1;
    }
    
    /* Fill VLAN header */
    vlan = (kos_vlan_header_t *)pkt->data;
    vlan_tci = (vif->priority << VLAN_PRIO_SHIFT) | vif->vlan_id;
    vlan->tci = htons(vlan_tci);
    vlan->encap_proto = htons(proto);
    
    /* Update statistics */
    vif->tx_packets++;
    vif->tx_bytes += pkt->size;
    
    /* Send via parent interface with VLAN ethertype */
    return kos_eth_output(vif->parent, pkt, NULL);
}

/* Create VLAN interface */
kos_vlan_if_t *kos_vlan_create(kos_netif_t *parent, uint16_t vlan_id, uint8_t priority)
{
    kos_vlan_if_t *vif;
    
    /* Validate parameters */
    if (!parent || vlan_id == 0 || vlan_id == 4095) {
        return NULL;
    }
    
    /* Check if already exists */
    if (find_vlan_if(parent, vlan_id)) {
        printf("VLAN: Interface %s.%u already exists\n", parent->name, vlan_id);
        return NULL;
    }
    
    /* Allocate VLAN interface */
    vif = calloc(1, sizeof(kos_vlan_if_t));
    if (!vif) {
        return NULL;
    }
    
    /* Initialize */
    vif->parent = parent;
    vif->vlan_id = vlan_id;
    vif->priority = priority & 0x7;
    snprintf(vif->name, sizeof(vif->name), "%s.%u", parent->name, vlan_id);
    
    /* Add to list */
    pthread_mutex_lock(&vlan_lock);
    vif->next = vlan_interfaces;
    vlan_interfaces = vif;
    pthread_mutex_unlock(&vlan_lock);
    
    printf("VLAN: Created interface %s (VID %u, priority %u)\n", 
           vif->name, vlan_id, priority);
    
    return vif;
}

/* Delete VLAN interface */
int kos_vlan_destroy(kos_vlan_if_t *vif)
{
    kos_vlan_if_t **pprev, *curr;
    
    if (!vif) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&vlan_lock);
    
    /* Find and remove from list */
    pprev = &vlan_interfaces;
    while ((curr = *pprev) != NULL) {
        if (curr == vif) {
            *pprev = curr->next;
            break;
        }
        pprev = &curr->next;
    }
    
    pthread_mutex_unlock(&vlan_lock);
    
    if (curr) {
        printf("VLAN: Destroyed interface %s\n", vif->name);
        free(vif);
        return 0;
    }
    
    return -ENOENT;
}

/* Set VLAN priority */
int kos_vlan_set_priority(kos_vlan_if_t *vif, uint8_t priority)
{
    if (!vif || priority > 7) {
        return -EINVAL;
    }
    
    vif->priority = priority;
    return 0;
}

/* Get VLAN statistics */
void kos_vlan_stats_dump(void)
{
    kos_vlan_if_t *vif;
    
    pthread_mutex_lock(&vlan_stats.lock);
    printf("\nVLAN Global Statistics:\n");
    printf("======================\n");
    printf("RX Packets:    %lu\n", vlan_stats.rx_packets);
    printf("TX Packets:    %lu\n", vlan_stats.tx_packets);
    printf("RX Tagged:     %lu\n", vlan_stats.rx_tagged);
    printf("TX Tagged:     %lu\n", vlan_stats.tx_tagged);
    printf("RX Untagged:   %lu\n", vlan_stats.rx_untagged);
    printf("Invalid VID:   %lu\n", vlan_stats.invalid_vid);
    printf("Unknown VID:   %lu\n", vlan_stats.unknown_vid);
    pthread_mutex_unlock(&vlan_stats.lock);
    
    printf("\nVLAN Interfaces:\n");
    printf("================\n");
    
    pthread_mutex_lock(&vlan_lock);
    for (vif = vlan_interfaces; vif; vif = vif->next) {
        printf("\nInterface: %s\n", vif->name);
        printf("  Parent: %s\n", vif->parent->name);
        printf("  VLAN ID: %u\n", vif->vlan_id);
        printf("  Priority: %u\n", vif->priority);
        printf("  RX Packets: %lu\n", vif->rx_packets);
        printf("  TX Packets: %lu\n", vif->tx_packets);
        printf("  RX Bytes: %lu\n", vif->rx_bytes);
        printf("  TX Bytes: %lu\n", vif->tx_bytes);
        printf("  RX Errors: %lu\n", vif->rx_errors);
        printf("  TX Errors: %lu\n", vif->tx_errors);
    }
    pthread_mutex_unlock(&vlan_lock);
}

/* Initialize VLAN subsystem */
int kos_vlan_init(void)
{
    printf("VLAN: 802.1Q support initialized\n");
    return 0;
}

/* Process untagged packet on VLAN-aware interface */
int kos_vlan_process_untagged(kos_netif_t *netif, kos_packet_t *pkt, uint16_t proto)
{
    pthread_mutex_lock(&vlan_stats.lock);
    vlan_stats.rx_packets++;
    vlan_stats.rx_untagged++;
    pthread_mutex_unlock(&vlan_stats.lock);
    
    /* For untagged packets, process normally on the physical interface */
    switch (proto) {
        case ETH_P_IP:
            return kos_ip_input(netif, pkt);
            
        case ETH_P_IPV6:
            return kos_ipv6_input(netif, pkt);
            
        case ETH_P_ARP:
            return kos_arp_input(netif, pkt);
            
        default:
            printf("VLAN: Unknown protocol 0x%04x on untagged packet\n", proto);
            return -1;
    }
}