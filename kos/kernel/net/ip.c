/*
 * KOS IP Layer Implementation
 * IP packet routing, fragmentation, and ICMP handling
 */

#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200112L

#include "netstack.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <sys/time.h>
#include <stdio.h>

/* IP constants */
#define IP_VERSION          4
#define IP_MIN_HLEN         20
#define IP_MAX_HLEN         60
#define IP_DEFAULT_TTL      64
#define IP_MAX_PACKET_SIZE  65535
#define IP_FRAG_TIMEOUT     30000  /* 30 seconds in milliseconds */

/* IP flags */
#define IP_FLAG_RESERVED    0x8000
#define IP_FLAG_DF          0x4000  /* Don't fragment */
#define IP_FLAG_MF          0x2000  /* More fragments */
#define IP_FRAG_OFFSET_MASK 0x1FFF

/* ICMP types */
#define ICMP_ECHO_REPLY     0
#define ICMP_DEST_UNREACH   3
#define ICMP_SOURCE_QUENCH  4
#define ICMP_REDIRECT       5
#define ICMP_ECHO_REQUEST   8
#define ICMP_TIME_EXCEEDED  11
#define ICMP_PARAM_PROBLEM  12
#define ICMP_TIMESTAMP      13
#define ICMP_TIMESTAMP_REPLY 14
#define ICMP_INFO_REQUEST   15
#define ICMP_INFO_REPLY     16

/* Fragment tracking */
/* Fragment hole descriptor for reassembly */
typedef struct ip_frag_hole {
    uint16_t first;         /* First byte of hole */
    uint16_t last;          /* Last byte of hole */
    struct ip_frag_hole *next;
} ip_frag_hole_t;

/* IP fragment tracking */
typedef struct ip_fragment {
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t id;
    uint8_t protocol;
    uint64_t timestamp;
    uint8_t *buffer;        /* Reassembly buffer */
    uint16_t total_len;     /* Total length when complete */
    uint16_t received_len;  /* Bytes received so far */
    ip_frag_hole_t *holes;  /* List of holes in reassembly */
    int complete;           /* Reassembly complete flag */
    struct ip_fragment* next;
} ip_fragment_t;

/* Global IP state */
static struct {
    pthread_mutex_t lock;
    uint16_t next_id;
    ip_fragment_t* fragment_list;
    
    /* Statistics */
    uint64_t packets_received;
    uint64_t packets_sent;
    uint64_t packets_forwarded;
    uint64_t packets_dropped;
    uint64_t fragments_created;
    uint64_t fragments_reassembled;
    uint64_t checksum_errors;
    uint64_t ttl_expired;
    
} ip_state = {
    .lock = PTHREAD_MUTEX_INITIALIZER,
    .next_id = 1
};

/* External functions */
extern kos_netif_t* kos_netif_find_by_index(int index);
extern kos_route_t* kos_route_lookup(uint32_t dest);

/* Forward declarations */
static int ip_fragment_packet(kos_packet_t* pkt, kos_netif_t* netif);
static kos_packet_t* ip_reassemble_fragments(kos_ip_header_t* iph, uint8_t *data, size_t data_len);
static void ip_cleanup_fragments(void);
static int ip_forward_packet(kos_packet_t* pkt, kos_netif_t* in_netif);
static int ip_send_icmp(uint32_t src_ip, uint32_t dst_ip, uint8_t type, 
                       uint8_t code, uint32_t data);
static int ip_handle_icmp(kos_packet_t* pkt);
static bool ip_is_local_address(uint32_t addr);
static kos_netif_t* ip_route_output(uint32_t dest);

/*
 * Process incoming IP packet
 */
int kos_ip_input(kos_netif_t* netif, kos_packet_t* pkt) {
    if (!netif || !pkt || !pkt->l3_header) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&ip_state.lock);
    ip_state.packets_received++;
    
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    
    /* Validate basic IP header */
    uint8_t version = (iph->version_ihl >> 4) & 0x0F;
    uint8_t hlen = (iph->version_ihl & 0x0F) * 4;
    
    if (version != IP_VERSION || hlen < IP_MIN_HLEN || hlen > IP_MAX_HLEN) {
        ip_state.packets_dropped++;
        pthread_mutex_unlock(&ip_state.lock);
        return -EINVAL;
    }
    
    /* Verify checksum */
    uint16_t orig_checksum = iph->checksum;
    iph->checksum = 0;
    uint16_t calc_checksum = kos_ip_checksum(iph, hlen);
    iph->checksum = orig_checksum;
    
    if (calc_checksum != orig_checksum) {
        ip_state.checksum_errors++;
        ip_state.packets_dropped++;
        pthread_mutex_unlock(&ip_state.lock);
        return -EINVAL;
    }
    
    /* Convert header fields from network byte order */
    uint16_t total_len = ntohs(iph->total_length);
    uint16_t id = ntohs(iph->id);
    uint16_t flags_frag = ntohs(iph->flags_frag_offset);
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    
    /* Check if packet is for us */
    bool for_us = ip_is_local_address(dst_ip) || dst_ip == INADDR_BROADCAST;
    
    /* Check TTL */
    if (iph->ttl <= 1) {
        if (for_us) {
            /* Packet is for us but TTL expired - still process */
        } else {
            /* Send ICMP Time Exceeded */
            ip_send_icmp(netif->ip_addr, src_ip, ICMP_TIME_EXCEEDED, 0, 0);
            ip_state.ttl_expired++;
            ip_state.packets_dropped++;
            pthread_mutex_unlock(&ip_state.lock);
            return -ETIMEDOUT;
        }
    }
    
    /* Handle fragmentation */
    bool is_fragment = (flags_frag & IP_FLAG_MF) || (flags_frag & IP_FRAG_OFFSET_MASK);
    
    if (is_fragment) {
        /* Reassemble fragments */
        /* Get fragment data and length */
        uint16_t hlen = (iph->version_ihl & 0x0F) * 4;
        uint8_t *frag_data = (uint8_t *)iph + hlen;
        size_t frag_data_len = total_len - hlen;
        
        kos_packet_t* reassembled = ip_reassemble_fragments(iph, frag_data, frag_data_len);
        if (!reassembled) {
            /* Fragment not complete yet */
            pthread_mutex_unlock(&ip_state.lock);
            return 0;
        }
        
        pkt = reassembled;
        iph = (kos_ip_header_t*)pkt->l3_header;
        total_len = ntohs(iph->total_length);
        ip_state.fragments_reassembled++;
    }
    
    /* Set L4 header pointer */
    pkt->l4_header = (uint8_t*)iph + hlen;
    
    if (for_us) {
        /* Packet is for local delivery */
        int ret = 0;
        
        switch (iph->protocol) {
            case 1: /* ICMP */
                ret = ip_handle_icmp(pkt);
                break;
                
            case 6: /* TCP */
                ret = kos_tcp_input(pkt);
                break;
                
            case 17: /* UDP */
                ret = kos_udp_input(pkt);
                break;
                
            default:
                /* Protocol not supported */
                ip_send_icmp(dst_ip, src_ip, ICMP_DEST_UNREACH, 2, 0);
                ret = -EPROTONOSUPPORT;
                break;
        }
        
        pthread_mutex_unlock(&ip_state.lock);
        return ret;
        
    } else {
        /* Forward packet */
        int ret = ip_forward_packet(pkt, netif);
        pthread_mutex_unlock(&ip_state.lock);
        return ret;
    }
}

/*
 * Send IP packet
 */
int kos_ip_output(kos_packet_t* pkt, uint32_t dest, uint8_t protocol) {
    if (!pkt || !pkt->l3_header) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&ip_state.lock);
    
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    
    /* Find route to destination */
    kos_route_t* route = kos_route_lookup(dest);
    kos_netif_t* netif = route ? route->interface : NULL;
    
    if (!netif) {
        /* No route to destination */
        ip_state.packets_dropped++;
        pthread_mutex_unlock(&ip_state.lock);
        return -EHOSTUNREACH;
    }
    
    /* Update IP header */
    iph->version_ihl = 0x45; /* IPv4, 20 byte header */
    iph->tos = 0;
    /* total_length should already be set */
    iph->id = htons(ip_state.next_id++);
    iph->flags_frag_offset = htons(IP_FLAG_DF); /* Don't fragment for now */
    iph->ttl = IP_DEFAULT_TTL;
    iph->protocol = protocol;
    iph->checksum = 0;
    iph->src_addr = htonl(netif->ip_addr);
    iph->dst_addr = htonl(dest);
    
    /* Calculate checksum */
    iph->checksum = kos_ip_checksum(iph, 20);
    
    /* Check if fragmentation is needed */
    if (pkt->size > netif->mtu) {
        if (ntohs(iph->flags_frag_offset) & IP_FLAG_DF) {
            /* Don't fragment flag is set */
            ip_send_icmp(netif->ip_addr, ntohl(iph->src_addr), 
                        ICMP_DEST_UNREACH, 4, netif->mtu);
            ip_state.packets_dropped++;
            pthread_mutex_unlock(&ip_state.lock);
            return -EMSGSIZE;
        }
        
        int ret = ip_fragment_packet(pkt, netif);
        pthread_mutex_unlock(&ip_state.lock);
        return ret;
    }
    
    /* Send packet */
    int ret = kos_eth_output(netif, pkt, NULL);
    
    if (ret >= 0) {
        ip_state.packets_sent++;
        netif->tx_packets++;
        netif->tx_bytes += pkt->size;
    } else {
        ip_state.packets_dropped++;
        netif->tx_errors++;
    }
    
    pthread_mutex_unlock(&ip_state.lock);
    return ret;
}

/*
 * Fragment IP packet
 */
static int ip_fragment_packet(kos_packet_t* pkt, kos_netif_t* netif) {
    kos_ip_header_t* orig_iph = (kos_ip_header_t*)pkt->l3_header;
    uint16_t total_len = ntohs(orig_iph->total_length);
    uint16_t hlen = (orig_iph->version_ihl & 0x0F) * 4;
    uint16_t data_len = total_len - hlen;
    uint16_t mtu = netif->mtu - sizeof(kos_eth_header_t);
    uint16_t max_frag_data = ((mtu - hlen) / 8) * 8; /* Must be multiple of 8 */
    
    if (max_frag_data <= 0) {
        return -EMSGSIZE;
    }
    
    uint8_t* data = (uint8_t*)orig_iph + hlen;
    uint16_t offset = 0;
    uint16_t sent = 0;
    
    while (offset < data_len) {
        uint16_t frag_data_len = (data_len - offset > max_frag_data) ? 
                                 max_frag_data : (data_len - offset);
        
        /* Create fragment packet */
        kos_packet_t* frag = kos_packet_alloc(sizeof(kos_eth_header_t) + hlen + frag_data_len);
        if (!frag) {
            return -ENOMEM;
        }
        
        /* Copy Ethernet header */
        memcpy(frag->data, pkt->data, sizeof(kos_eth_header_t));
        frag->l2_header = frag->data;
        
        /* Copy and modify IP header */
        kos_ip_header_t* frag_iph = (kos_ip_header_t*)(frag->data + sizeof(kos_eth_header_t));
        memcpy(frag_iph, orig_iph, hlen);
        frag->l3_header = frag_iph;
        
        frag_iph->total_length = htons(hlen + frag_data_len);
        
        uint16_t flags = ntohs(orig_iph->flags_frag_offset) & 0xE000;
        if (offset + frag_data_len < data_len) {
            flags |= IP_FLAG_MF; /* More fragments */
        }
        frag_iph->flags_frag_offset = htons(flags | (offset / 8));
        
        frag_iph->checksum = 0;
        frag_iph->checksum = kos_ip_checksum(frag_iph, hlen);
        
        /* Copy fragment data */
        memcpy((uint8_t*)frag_iph + hlen, data + offset, frag_data_len);
        frag->l4_header = (uint8_t*)frag_iph + hlen;
        frag->size = sizeof(kos_eth_header_t) + hlen + frag_data_len;
        
        /* Send fragment */
        int ret = kos_eth_output(netif, frag, NULL);
        if (ret < 0) {
            kos_packet_free(frag);
            return ret;
        }
        
        sent += frag_data_len;
        offset += frag_data_len;
        ip_state.fragments_created++;
    }
    
    ip_state.packets_sent++;
    return sent;
}

/*
 * Reassemble IP fragments
 */
static kos_packet_t* ip_reassemble_fragments(kos_ip_header_t* iph, uint8_t *data, size_t data_len) {
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    uint16_t id = ntohs(iph->id);
    uint8_t protocol = iph->protocol;
    uint16_t flags_frag = ntohs(iph->flags_frag_offset);
    uint16_t frag_offset = (flags_frag & IP_FRAG_OFFSET_MASK) * 8;
    bool more_frags = (flags_frag & IP_FLAG_MF) != 0;
    
    /* Find existing fragment entry */
    ip_fragment_t* frag_entry = ip_state.fragment_list;
    while (frag_entry) {
        if (frag_entry->src_ip == src_ip && frag_entry->dst_ip == dst_ip &&
            frag_entry->id == id && frag_entry->protocol == protocol) {
            break;
        }
        frag_entry = frag_entry->next;
    }
    
    /* Create new fragment entry if not found */
    if (!frag_entry) {
        frag_entry = calloc(1, sizeof(ip_fragment_t));
        if (!frag_entry) {
            return NULL;
        }
        
        frag_entry->src_ip = src_ip;
        frag_entry->dst_ip = dst_ip;
        frag_entry->id = id;
        frag_entry->protocol = protocol;
        frag_entry->timestamp = time(NULL) * 1000; /* Current time in ms */
        
        /* Add to fragment list */
        frag_entry->next = ip_state.fragment_list;
        ip_state.fragment_list = frag_entry;
    }
    
    /* Initialize reassembly buffer if this is the first fragment */
    if (!frag_entry->buffer) {
        frag_entry->buffer = calloc(1, IP_MAX_PACKET_SIZE);
        if (!frag_entry->buffer) {
            return NULL;
        }
        
        /* Initialize with one big hole */
        frag_entry->holes = malloc(sizeof(ip_frag_hole_t));
        if (!frag_entry->holes) {
            free(frag_entry->buffer);
            return NULL;
        }
        frag_entry->holes->first = 0;
        frag_entry->holes->last = IP_MAX_PACKET_SIZE - 1;
        frag_entry->holes->next = NULL;
        frag_entry->total_len = 0;
        frag_entry->received_len = 0;
        frag_entry->complete = 0;
    }
    
    /* Calculate fragment boundaries */
    uint16_t frag_first = frag_offset;
    uint16_t frag_last = frag_offset + data_len - 1;
    
    /* If this is the last fragment, we know the total length */
    if (!more_frags) {
        frag_entry->total_len = frag_last + 1;
    }
    
    /* Copy fragment data to reassembly buffer */
    memcpy(frag_entry->buffer + frag_first, data, data_len);
    frag_entry->received_len += data_len;
    
    /* Update hole list */
    ip_frag_hole_t **hole_ptr = &frag_entry->holes;
    ip_frag_hole_t *hole = frag_entry->holes;
    
    while (hole) {
        /* Check if this fragment fills any part of this hole */
        if (frag_first > hole->last || frag_last < hole->first) {
            /* No overlap with this hole */
            hole_ptr = &hole->next;
            hole = hole->next;
            continue;
        }
        
        /* Fragment overlaps with hole */
        if (frag_first <= hole->first && frag_last >= hole->last) {
            /* Fragment completely fills this hole */
            *hole_ptr = hole->next;
            free(hole);
            hole = *hole_ptr;
        } else if (frag_first > hole->first && frag_last < hole->last) {
            /* Fragment splits hole in two */
            ip_frag_hole_t *new_hole = malloc(sizeof(ip_frag_hole_t));
            if (new_hole) {
                new_hole->first = frag_last + 1;
                new_hole->last = hole->last;
                new_hole->next = hole->next;
                hole->last = frag_first - 1;
                hole->next = new_hole;
            }
            break;
        } else if (frag_first <= hole->first) {
            /* Fragment fills beginning of hole */
            hole->first = frag_last + 1;
            break;
        } else {
            /* Fragment fills end of hole */
            hole->last = frag_first - 1;
            hole_ptr = &hole->next;
            hole = hole->next;
        }
    }
    
    /* Check if reassembly is complete */
    if (!frag_entry->holes && frag_entry->total_len > 0) {
        /* All holes filled and we know the total length */
        frag_entry->complete = 1;
        
        /* Create reassembled packet */
        kos_packet_t *reassembled = kos_packet_alloc(frag_entry->total_len);
        if (reassembled) {
            kos_packet_put(reassembled, frag_entry->buffer, frag_entry->total_len);
        }
        
        /* Remove from fragment list */
        ip_fragment_t **frag_ptr = &ip_state.fragment_list;
        while (*frag_ptr) {
            if (*frag_ptr == frag_entry) {
                *frag_ptr = frag_entry->next;
                break;
            }
            frag_ptr = &(*frag_ptr)->next;
        }
        
        /* Free fragment entry */
        free(frag_entry->buffer);
        ip_frag_hole_t *h = frag_entry->holes;
        while (h) {
            ip_frag_hole_t *next = h->next;
            free(h);
            h = next;
        }
        free(frag_entry);
        
        return reassembled;
    }
    
    return NULL; /* Reassembly not complete */
}

/*
 * Forward IP packet
 */
static int ip_forward_packet(kos_packet_t* pkt, kos_netif_t* in_netif) {
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    uint32_t dest = ntohl(iph->dst_addr);
    
    /* Decrement TTL */
    if (--iph->ttl <= 0) {
        ip_send_icmp(in_netif->ip_addr, ntohl(iph->src_addr), ICMP_TIME_EXCEEDED, 0, 0);
        ip_state.ttl_expired++;
        ip_state.packets_dropped++;
        return -ETIMEDOUT;
    }
    
    /* Recalculate checksum */
    iph->checksum = 0;
    iph->checksum = kos_ip_checksum(iph, (iph->version_ihl & 0x0F) * 4);
    
    /* Find route */
    kos_route_t* route = kos_route_lookup(dest);
    if (!route || !route->interface) {
        ip_send_icmp(in_netif->ip_addr, ntohl(iph->src_addr), ICMP_DEST_UNREACH, 0, 0);
        ip_state.packets_dropped++;
        return -EHOSTUNREACH;
    }
    
    /* Don't forward back to same interface */
    if (route->interface == in_netif) {
        ip_state.packets_dropped++;
        return -EINVAL;
    }
    
    /* Forward packet */
    int ret = kos_eth_output(route->interface, pkt, NULL);
    
    if (ret >= 0) {
        ip_state.packets_forwarded++;
        route->interface->tx_packets++;
        route->interface->tx_bytes += pkt->size;
    } else {
        ip_state.packets_dropped++;
        route->interface->tx_errors++;
    }
    
    return ret;
}

/*
 * Send ICMP packet
 */
static int ip_send_icmp(uint32_t src_ip, uint32_t dst_ip, uint8_t type, 
                       uint8_t code, uint32_t data) {
    /* Allocate packet for ICMP */
    size_t pkt_size = sizeof(kos_eth_header_t) + sizeof(kos_ip_header_t) + 8;
    kos_packet_t* pkt = kos_packet_alloc(pkt_size);
    if (!pkt) {
        return -ENOMEM;
    }
    
    /* Build Ethernet header */
    kos_eth_header_t* eth = (kos_eth_header_t*)pkt->data;
    memset(eth->dest, 0xFF, 6); /* Broadcast for now */
    memset(eth->src, 0x00, 6);  /* Our MAC */
    eth->type = htons(0x0800);  /* IPv4 */
    pkt->l2_header = eth;
    
    /* Build IP header */
    kos_ip_header_t* iph = (kos_ip_header_t*)(eth + 1);
    iph->version_ihl = 0x45;
    iph->tos = 0;
    iph->total_length = htons(sizeof(kos_ip_header_t) + 8);
    iph->id = htons(ip_state.next_id++);
    iph->flags_frag_offset = htons(IP_FLAG_DF);
    iph->ttl = IP_DEFAULT_TTL;
    iph->protocol = 1; /* ICMP */
    iph->checksum = 0;
    iph->src_addr = htonl(src_ip);
    iph->dst_addr = htonl(dst_ip);
    iph->checksum = kos_ip_checksum(iph, 20);
    pkt->l3_header = iph;
    
    /* Build ICMP header */
    struct {
        uint8_t type;
        uint8_t code;
        uint16_t checksum;
        uint32_t data;
    } *icmp = (void*)(iph + 1);
    
    icmp->type = type;
    icmp->code = code;
    icmp->checksum = 0;
    icmp->data = htonl(data);
    icmp->checksum = kos_ip_checksum(icmp, 8);
    
    pkt->l4_header = icmp;
    pkt->size = pkt_size;
    
    /* Send packet */
    return kos_ip_output(pkt, dst_ip, 1);
}

/*
 * Handle ICMP packet
 */
static int ip_handle_icmp(kos_packet_t* pkt) {
    struct {
        uint8_t type;
        uint8_t code;
        uint16_t checksum;
        uint32_t data;
    } *icmp = (void*)pkt->l4_header;
    
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    
    switch (icmp->type) {
        case ICMP_ECHO_REQUEST:
            /* Send echo reply */
            return ip_send_icmp(dst_ip, src_ip, ICMP_ECHO_REPLY, 0, ntohl(icmp->data));
            
        case ICMP_ECHO_REPLY:
            /* Handle ping reply */
            return 0;
            
        default:
            /* Other ICMP types */
            return 0;
    }
}

/*
 * Check if address is local
 */
static bool ip_is_local_address(uint32_t addr) {
    if (addr == INADDR_LOOPBACK || addr == INADDR_BROADCAST) {
        return true;
    }
    
    /* Check all network interfaces */
    kos_netif_t* netif = kos_netif_find_by_index(1); /* Start from first interface */
    while (netif) {
        if (netif->ip_addr == addr || netif->broadcast == addr) {
            return true;
        }
        netif = netif->next;
    }
    
    return false;
}

/*
 * Find output interface for destination
 */
static kos_netif_t* ip_route_output(uint32_t dest) {
    kos_route_t* route = kos_route_lookup(dest);
    return route ? route->interface : NULL;
}

/*
 * Cleanup old fragments
 */
static void ip_cleanup_fragments(void) {
    uint64_t current_time = time(NULL) * 1000;
    
    ip_fragment_t** frag_ptr = &ip_state.fragment_list;
    while (*frag_ptr) {
        ip_fragment_t* frag = *frag_ptr;
        if (current_time - frag->timestamp > IP_FRAG_TIMEOUT) {
            /* Remove expired fragment */
            *frag_ptr = frag->next;
            
            /* Free fragment resources */
            if (frag->buffer)
                free(frag->buffer);
            
            /* Free hole list */
            ip_frag_hole_t *hole = frag->holes;
            while (hole) {
                ip_frag_hole_t *next = hole->next;
                free(hole);
                hole = next;
            }
            
            free(frag);
        } else {
            frag_ptr = &frag->next;
        }
    }
}

/*
 * Get IP statistics
 */
void kos_ip_stats(void) {
    pthread_mutex_lock(&ip_state.lock);
    
    printf("IP Statistics:\n");
    printf("  Packets received: %lu\n", ip_state.packets_received);
    printf("  Packets sent: %lu\n", ip_state.packets_sent);
    printf("  Packets forwarded: %lu\n", ip_state.packets_forwarded);
    printf("  Packets dropped: %lu\n", ip_state.packets_dropped);
    printf("  Fragments created: %lu\n", ip_state.fragments_created);
    printf("  Fragments reassembled: %lu\n", ip_state.fragments_reassembled);
    printf("  Checksum errors: %lu\n", ip_state.checksum_errors);
    printf("  TTL expired: %lu\n", ip_state.ttl_expired);
    
    pthread_mutex_unlock(&ip_state.lock);
    
    /* Cleanup old fragments */
    ip_cleanup_fragments();
}