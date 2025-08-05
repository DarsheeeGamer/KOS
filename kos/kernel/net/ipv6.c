/*
 * KOS IPv6 Protocol Implementation
 * Basic IPv6 support with ICMPv6
 */

#include "netstack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <arpa/inet.h>

/* IPv6 constants */
#define IPV6_VERSION        6
#define IPV6_MIN_MTU        1280
#define IPV6_ADDR_LEN       16
#define IPV6_HDR_LEN        40

/* IPv6 address types */
#define IPV6_ADDR_UNICAST       0x00
#define IPV6_ADDR_MULTICAST     0xFF
#define IPV6_ADDR_LINKLOCAL     0xFE80
#define IPV6_ADDR_SITELOCAL     0xFEC0
#define IPV6_ADDR_GLOBAL        0x2000

/* ICMPv6 types */
#define ICMPV6_ECHO_REQUEST     128
#define ICMPV6_ECHO_REPLY       129
#define ICMPV6_ROUTER_SOLICIT   133
#define ICMPV6_ROUTER_ADVERT    134
#define ICMPV6_NEIGHBOR_SOLICIT 135
#define ICMPV6_NEIGHBOR_ADVERT  136

/* IPv6 header structure */
typedef struct kos_ipv6_header {
    uint32_t version_class_flow;    /* Version (4), Traffic class (8), Flow label (20) */
    uint16_t payload_length;
    uint8_t next_header;
    uint8_t hop_limit;
    uint8_t src_addr[16];
    uint8_t dst_addr[16];
} __attribute__((packed)) kos_ipv6_header_t;

/* ICMPv6 header */
typedef struct kos_icmpv6_header {
    uint8_t type;
    uint8_t code;
    uint16_t checksum;
    union {
        struct {
            uint16_t identifier;
            uint16_t sequence;
        } echo;
        uint32_t mtu;
        uint32_t reserved;
    } un;
} __attribute__((packed)) kos_icmpv6_header_t;

/* IPv6 address structure */
typedef struct kos_ipv6_addr {
    uint8_t addr[16];
} kos_ipv6_addr_t;

/* IPv6 statistics */
static struct {
    uint64_t in_receives;
    uint64_t in_hdr_errors;
    uint64_t in_addr_errors;
    uint64_t in_discards;
    uint64_t in_delivers;
    uint64_t out_requests;
    uint64_t out_discards;
    uint64_t out_no_routes;
    pthread_mutex_t lock;
} ipv6_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* IPv6 routing table */
typedef struct kos_ipv6_route {
    kos_ipv6_addr_t dest;
    uint8_t prefix_len;
    kos_ipv6_addr_t gateway;
    kos_netif_t *interface;
    uint32_t flags;
    int metric;
    struct kos_ipv6_route *next;
} kos_ipv6_route_t;

static kos_ipv6_route_t *ipv6_routes = NULL;
static pthread_mutex_t ipv6_route_lock = PTHREAD_MUTEX_INITIALIZER;

/* Check if address is all zeros */
static int ipv6_addr_is_zero(const kos_ipv6_addr_t *addr)
{
    for (int i = 0; i < 16; i++) {
        if (addr->addr[i] != 0)
            return 0;
    }
    return 1;
}

/* Compare IPv6 addresses */
static int ipv6_addr_equal(const kos_ipv6_addr_t *a, const kos_ipv6_addr_t *b)
{
    return memcmp(a->addr, b->addr, 16) == 0;
}

/* Get address type */
static int ipv6_addr_type(const kos_ipv6_addr_t *addr)
{
    if (addr->addr[0] == 0xFF)
        return IPV6_ADDR_MULTICAST;
    
    if (addr->addr[0] == 0xFE && (addr->addr[1] & 0xC0) == 0x80)
        return IPV6_ADDR_LINKLOCAL;
    
    if (addr->addr[0] == 0xFE && (addr->addr[1] & 0xC0) == 0xC0)
        return IPV6_ADDR_SITELOCAL;
    
    if ((addr->addr[0] & 0xE0) == 0x20)
        return IPV6_ADDR_GLOBAL;
    
    return IPV6_ADDR_UNICAST;
}

/* Calculate ICMPv6 checksum */
static uint16_t icmpv6_checksum(const kos_ipv6_addr_t *src, const kos_ipv6_addr_t *dst,
                               const void *data, size_t len, uint8_t next_hdr)
{
    /* Pseudo header for checksum */
    struct {
        uint8_t src[16];
        uint8_t dst[16];
        uint32_t length;
        uint8_t zeros[3];
        uint8_t next_header;
    } __attribute__((packed)) pseudo;
    
    memcpy(pseudo.src, src->addr, 16);
    memcpy(pseudo.dst, dst->addr, 16);
    pseudo.length = htonl(len);
    memset(pseudo.zeros, 0, 3);
    pseudo.next_header = next_hdr;
    
    /* Calculate checksum over pseudo header and data */
    uint32_t sum = 0;
    const uint16_t *p;
    
    /* Add pseudo header */
    p = (const uint16_t *)&pseudo;
    for (size_t i = 0; i < sizeof(pseudo)/2; i++) {
        sum += ntohs(p[i]);
    }
    
    /* Add data */
    p = (const uint16_t *)data;
    for (size_t i = 0; i < len/2; i++) {
        sum += ntohs(p[i]);
    }
    
    /* Add odd byte if present */
    if (len & 1) {
        sum += ((const uint8_t *)data)[len-1] << 8;
    }
    
    /* Fold to 16 bits */
    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }
    
    return htons(~sum);
}

/* Handle ICMPv6 packet */
static int kos_icmpv6_input(kos_netif_t *netif, kos_packet_t *pkt,
                           const kos_ipv6_addr_t *src, const kos_ipv6_addr_t *dst)
{
    kos_icmpv6_header_t *icmp;
    
    if (pkt->size < sizeof(kos_icmpv6_header_t)) {
        printf("ICMPv6: Packet too small\n");
        return -1;
    }
    
    icmp = (kos_icmpv6_header_t *)pkt->data;
    
    /* Verify checksum */
    uint16_t checksum = icmp->checksum;
    icmp->checksum = 0;
    uint16_t calc_checksum = icmpv6_checksum(src, dst, icmp, pkt->size, IPPROTO_ICMPV6);
    if (checksum != calc_checksum) {
        printf("ICMPv6: Checksum error\n");
        return -1;
    }
    icmp->checksum = checksum;
    
    switch (icmp->type) {
    case ICMPV6_ECHO_REQUEST:
        printf("ICMPv6: Echo request received\n");
        /* Send echo reply */
        icmp->type = ICMPV6_ECHO_REPLY;
        icmp->checksum = 0;
        icmp->checksum = icmpv6_checksum(dst, src, icmp, pkt->size, IPPROTO_ICMPV6);
        
        /* Send reply (swap src/dst) */
        kos_ipv6_output(pkt, src, IPPROTO_ICMPV6);
        break;
        
    case ICMPV6_ECHO_REPLY:
        printf("ICMPv6: Echo reply received\n");
        break;
        
    case ICMPV6_NEIGHBOR_SOLICIT:
        printf("ICMPv6: Neighbor solicitation received\n");
        /* TODO: Send neighbor advertisement */
        break;
        
    case ICMPV6_NEIGHBOR_ADVERT:
        printf("ICMPv6: Neighbor advertisement received\n");
        /* TODO: Update neighbor cache */
        break;
        
    case ICMPV6_ROUTER_SOLICIT:
        printf("ICMPv6: Router solicitation received\n");
        break;
        
    case ICMPV6_ROUTER_ADVERT:
        printf("ICMPv6: Router advertisement received\n");
        /* TODO: Process router advertisement */
        break;
        
    default:
        printf("ICMPv6: Unknown type %d\n", icmp->type);
        return -1;
    }
    
    return 0;
}

/* Process IPv6 input */
int kos_ipv6_input(kos_netif_t *netif, kos_packet_t *pkt)
{
    kos_ipv6_header_t *ip6;
    kos_ipv6_addr_t src, dst;
    
    pthread_mutex_lock(&ipv6_stats.lock);
    ipv6_stats.in_receives++;
    pthread_mutex_unlock(&ipv6_stats.lock);
    
    /* Check minimum size */
    if (pkt->size < sizeof(kos_ipv6_header_t)) {
        printf("IPv6: Packet too small\n");
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.in_hdr_errors++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    ip6 = (kos_ipv6_header_t *)pkt->data;
    
    /* Check version */
    uint32_t ver_class_flow = ntohl(ip6->version_class_flow);
    if ((ver_class_flow >> 28) != IPV6_VERSION) {
        printf("IPv6: Invalid version\n");
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.in_hdr_errors++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    /* Extract addresses */
    memcpy(src.addr, ip6->src_addr, 16);
    memcpy(dst.addr, ip6->dst_addr, 16);
    
    /* Check payload length */
    uint16_t payload_len = ntohs(ip6->payload_length);
    if (pkt->size < sizeof(kos_ipv6_header_t) + payload_len) {
        printf("IPv6: Invalid payload length\n");
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.in_hdr_errors++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    /* Check if packet is for us */
    int for_us = 0;
    /* TODO: Check against our IPv6 addresses */
    
    /* For now, accept all packets */
    for_us = 1;
    
    if (!for_us) {
        /* Try to forward */
        printf("IPv6: Packet not for us, dropping\n");
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.in_addr_errors++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    /* Decrement hop limit for forwarding */
    if (ip6->hop_limit <= 1 && !for_us) {
        printf("IPv6: Hop limit exceeded\n");
        /* TODO: Send ICMPv6 time exceeded */
        return -1;
    }
    
    /* Process based on next header */
    pkt->data += sizeof(kos_ipv6_header_t);
    pkt->size = payload_len;
    
    pthread_mutex_lock(&ipv6_stats.lock);
    ipv6_stats.in_delivers++;
    pthread_mutex_unlock(&ipv6_stats.lock);
    
    switch (ip6->next_header) {
    case IPPROTO_ICMPV6:
        return kos_icmpv6_input(netif, pkt, &src, &dst);
        
    case IPPROTO_TCP:
        printf("IPv6: TCP not yet implemented\n");
        return -1;
        
    case IPPROTO_UDP:
        printf("IPv6: UDP not yet implemented\n");
        return -1;
        
    default:
        printf("IPv6: Unknown next header %d\n", ip6->next_header);
        return -1;
    }
}

/* Send IPv6 packet */
int kos_ipv6_output(kos_packet_t *pkt, const kos_ipv6_addr_t *dest, uint8_t next_header)
{
    kos_ipv6_header_t *ip6;
    kos_ipv6_route_t *route;
    kos_netif_t *netif;
    kos_ipv6_addr_t src;
    
    pthread_mutex_lock(&ipv6_stats.lock);
    ipv6_stats.out_requests++;
    pthread_mutex_unlock(&ipv6_stats.lock);
    
    /* Find route */
    pthread_mutex_lock(&ipv6_route_lock);
    route = ipv6_routes;  /* TODO: Implement proper route lookup */
    pthread_mutex_unlock(&ipv6_route_lock);
    
    if (!route) {
        printf("IPv6: No route to destination\n");
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.out_no_routes++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    netif = route->interface;
    if (!netif) {
        return -1;
    }
    
    /* Get source address - for now use link-local */
    memset(src.addr, 0, 16);
    src.addr[0] = 0xFE;
    src.addr[1] = 0x80;
    /* Use MAC address for interface ID */
    memcpy(&src.addr[8], netif->hw_addr, 6);
    
    /* Add IPv6 header */
    if (kos_packet_push(pkt, sizeof(kos_ipv6_header_t)) < 0) {
        pthread_mutex_lock(&ipv6_stats.lock);
        ipv6_stats.out_discards++;
        pthread_mutex_unlock(&ipv6_stats.lock);
        return -1;
    }
    
    ip6 = (kos_ipv6_header_t *)pkt->data;
    
    /* Fill header */
    ip6->version_class_flow = htonl((IPV6_VERSION << 28));
    ip6->payload_length = htons(pkt->size - sizeof(kos_ipv6_header_t));
    ip6->next_header = next_header;
    ip6->hop_limit = 64;
    memcpy(ip6->src_addr, src.addr, 16);
    memcpy(ip6->dst_addr, dest->addr, 16);
    
    /* Send via Ethernet */
    uint8_t eth_dest[6];
    
    /* For multicast, use multicast MAC */
    if (ipv6_addr_type(dest) == IPV6_ADDR_MULTICAST) {
        eth_dest[0] = 0x33;
        eth_dest[1] = 0x33;
        memcpy(&eth_dest[2], &dest->addr[12], 4);
    } else {
        /* For unicast, would need neighbor discovery */
        /* For now, use broadcast */
        memset(eth_dest, 0xFF, 6);
    }
    
    return kos_eth_output(netif, pkt, eth_dest);
}

/* Add IPv6 route */
int kos_ipv6_route_add(const kos_ipv6_addr_t *dest, uint8_t prefix_len,
                      const kos_ipv6_addr_t *gateway, kos_netif_t *netif)
{
    kos_ipv6_route_t *route;
    
    route = malloc(sizeof(kos_ipv6_route_t));
    if (!route)
        return -ENOMEM;
    
    memcpy(&route->dest, dest, sizeof(kos_ipv6_addr_t));
    route->prefix_len = prefix_len;
    if (gateway && !ipv6_addr_is_zero(gateway)) {
        memcpy(&route->gateway, gateway, sizeof(kos_ipv6_addr_t));
    } else {
        memset(&route->gateway, 0, sizeof(kos_ipv6_addr_t));
    }
    route->interface = netif;
    route->flags = 0;
    route->metric = 1;
    
    pthread_mutex_lock(&ipv6_route_lock);
    route->next = ipv6_routes;
    ipv6_routes = route;
    pthread_mutex_unlock(&ipv6_route_lock);
    
    return 0;
}

/* Initialize IPv6 */
int kos_ipv6_init(void)
{
    printf("IPv6: Initializing\n");
    
    /* Add default route */
    kos_ipv6_addr_t any_addr;
    memset(&any_addr, 0, sizeof(kos_ipv6_addr_t));
    
    /* Find first interface */
    kos_netif_t *netif = kos_netif_find_by_index(0);
    if (netif) {
        kos_ipv6_route_add(&any_addr, 0, NULL, netif);
    }
    
    return 0;
}

/* Get IPv6 statistics */
void kos_ipv6_stats_dump(void)
{
    pthread_mutex_lock(&ipv6_stats.lock);
    printf("\nIPv6 Statistics:\n");
    printf("================\n");
    printf("In Receives:    %lu\n", ipv6_stats.in_receives);
    printf("In Hdr Errors:  %lu\n", ipv6_stats.in_hdr_errors);
    printf("In Addr Errors: %lu\n", ipv6_stats.in_addr_errors);
    printf("In Discards:    %lu\n", ipv6_stats.in_discards);
    printf("In Delivers:    %lu\n", ipv6_stats.in_delivers);
    printf("Out Requests:   %lu\n", ipv6_stats.out_requests);
    printf("Out Discards:   %lu\n", ipv6_stats.out_discards);
    printf("Out No Routes:  %lu\n", ipv6_stats.out_no_routes);
    pthread_mutex_unlock(&ipv6_stats.lock);
}