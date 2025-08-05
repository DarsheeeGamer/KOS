/*
 * KOS ARP (Address Resolution Protocol) Implementation
 * Handles ARP request/reply, cache management, and gratuitous ARP
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <sys/time.h>

#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC 1
#endif

/* ARP constants */
#define ARP_HTYPE_ETHERNET  1       /* Ethernet hardware type */
#define ARP_PTYPE_IP        0x0800  /* IP protocol type */
#define ARP_HLEN_ETHERNET   6       /* Ethernet address length */
#define ARP_PLEN_IP         4       /* IP address length */

/* ARP opcodes */
#define ARP_OP_REQUEST      1       /* ARP request */
#define ARP_OP_REPLY        2       /* ARP reply */
#define ARP_OP_RREQUEST     3       /* RARP request */
#define ARP_OP_RREPLY       4       /* RARP reply */

/* ARP cache constants */
#define ARP_CACHE_SIZE      256     /* Maximum ARP cache entries */
#define ARP_CACHE_TIMEOUT   300     /* ARP cache timeout in seconds */
#define ARP_MAX_RETRIES     3       /* Maximum ARP request retries */

/* ARP flags */
#define ARP_FLAG_COMPLETE   0x01    /* Entry is complete */
#define ARP_FLAG_PERMANENT  0x02    /* Entry is permanent */
#define ARP_FLAG_PUBLISHED  0x04    /* Entry is published */
#define ARP_FLAG_PROXY      0x08    /* Proxy ARP entry */

/* ARP header */
typedef struct kos_arp_header {
    uint16_t htype;     /* Hardware type */
    uint16_t ptype;     /* Protocol type */
    uint8_t hlen;       /* Hardware address length */
    uint8_t plen;       /* Protocol address length */
    uint16_t opcode;    /* ARP opcode */
    uint8_t sha[6];     /* Sender hardware address */
    uint32_t spa;       /* Sender protocol address */
    uint8_t tha[6];     /* Target hardware address */
    uint32_t tpa;       /* Target protocol address */
} __attribute__((packed)) kos_arp_header_t;

/* ARP cache */
static kos_arp_entry_t* arp_cache = NULL;
static pthread_mutex_t arp_cache_lock = PTHREAD_MUTEX_INITIALIZER;
static uint32_t arp_cache_count = 0;

/* ARP statistics */
static struct {
    uint64_t requests_sent;
    uint64_t requests_recv;
    uint64_t replies_sent;
    uint64_t replies_recv;
    uint64_t gratuitous_recv;
    uint64_t cache_hits;
    uint64_t cache_misses;
    uint64_t timeouts;
    pthread_mutex_t lock;
} arp_stats = {0};

/* Utility functions */
static uint64_t get_current_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

static void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

static void print_mac(const uint8_t* mac) {
    printf("%02x:%02x:%02x:%02x:%02x:%02x",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

/* ARP cache management */
static kos_arp_entry_t* arp_cache_find(uint32_t ip_addr) {
    kos_arp_entry_t* entry = arp_cache;
    while (entry) {
        if (entry->ip_addr == ip_addr) {
            return entry;
        }
        entry = entry->next;
    }
    return NULL;
}

static int arp_cache_add_entry(uint32_t ip_addr, const uint8_t* hw_addr, uint16_t flags) {
    kos_arp_entry_t* entry;
    
    /* Check if entry already exists */
    entry = arp_cache_find(ip_addr);
    if (entry) {
        /* Update existing entry */
        memcpy(entry->hw_addr, hw_addr, 6);
        entry->timestamp = get_current_time();
        entry->flags = flags;
        return 0;
    }
    
    /* Check cache size limit */
    if (arp_cache_count >= ARP_CACHE_SIZE) {
        /* Remove oldest entry */
        kos_arp_entry_t* oldest = arp_cache;
        kos_arp_entry_t* prev = NULL;
        kos_arp_entry_t* oldest_prev = NULL;
        uint64_t oldest_time = oldest->timestamp;
        
        entry = arp_cache;
        while (entry) {
            if (entry->timestamp < oldest_time && !(entry->flags & ARP_FLAG_PERMANENT)) {
                oldest = entry;
                oldest_prev = prev;
                oldest_time = entry->timestamp;
            }
            prev = entry;
            entry = entry->next;
        }
        
        if (oldest_prev) {
            oldest_prev->next = oldest->next;
        } else {
            arp_cache = oldest->next;
        }
        free(oldest);
        arp_cache_count--;
    }
    
    /* Create new entry */
    entry = malloc(sizeof(kos_arp_entry_t));
    if (!entry) {
        return -1;
    }
    
    entry->ip_addr = ip_addr;
    memcpy(entry->hw_addr, hw_addr, 6);
    entry->timestamp = get_current_time();
    entry->flags = flags;
    entry->next = arp_cache;
    arp_cache = entry;
    arp_cache_count++;
    
    return 0;
}

static int arp_cache_remove_entry(uint32_t ip_addr) {
    kos_arp_entry_t* entry = arp_cache;
    kos_arp_entry_t* prev = NULL;
    
    while (entry) {
        if (entry->ip_addr == ip_addr) {
            if (prev) {
                prev->next = entry->next;
            } else {
                arp_cache = entry->next;
            }
            free(entry);
            arp_cache_count--;
            return 0;
        }
        prev = entry;
        entry = entry->next;
    }
    
    return -1;
}

static void arp_cache_cleanup(void) {
    uint64_t current_time = get_current_time();
    uint64_t timeout_ns = ARP_CACHE_TIMEOUT * 1000000000ULL;
    
    kos_arp_entry_t* entry = arp_cache;
    kos_arp_entry_t* prev = NULL;
    
    while (entry) {
        kos_arp_entry_t* next = entry->next;
        
        if (!(entry->flags & ARP_FLAG_PERMANENT) && 
            (current_time - entry->timestamp) > timeout_ns) {
            
            /* Remove expired entry */
            if (prev) {
                prev->next = next;
            } else {
                arp_cache = next;
            }
            
            pthread_mutex_lock(&arp_stats.lock);
            arp_stats.timeouts++;
            pthread_mutex_unlock(&arp_stats.lock);
            
            free(entry);
            arp_cache_count--;
        } else {
            prev = entry;
        }
        
        entry = next;
    }
}

/* ARP packet creation */
static kos_packet_t* create_arp_packet(uint16_t opcode, kos_netif_t* netif,
                                       uint32_t spa, const uint8_t* sha,
                                       uint32_t tpa, const uint8_t* tha) {
    kos_packet_t* pkt = kos_packet_alloc(sizeof(kos_arp_header_t));
    if (!pkt) {
        return NULL;
    }
    
    kos_arp_header_t* arp_hdr = (kos_arp_header_t*)pkt->data;
    
    arp_hdr->htype = htons(ARP_HTYPE_ETHERNET);
    arp_hdr->ptype = htons(ARP_PTYPE_IP);
    arp_hdr->hlen = ARP_HLEN_ETHERNET;
    arp_hdr->plen = ARP_PLEN_IP;
    arp_hdr->opcode = htons(opcode);
    
    memcpy(arp_hdr->sha, sha, 6);
    arp_hdr->spa = htonl(spa);
    memcpy(arp_hdr->tha, tha, 6);
    arp_hdr->tpa = htonl(tpa);
    
    pkt->size = sizeof(kos_arp_header_t);
    return pkt;
}

/* Send ARP request */
int kos_arp_request(kos_netif_t* netif, uint32_t ip_addr) {
    if (!netif) {
        return -1;
    }
    
    /* Don't send ARP for broadcast or our own IP */
    if (ip_addr == INADDR_BROADCAST || ip_addr == netif->ip_addr) {
        return -1;
    }
    
    uint8_t zero_mac[6] = {0};
    uint8_t broadcast_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    
    kos_packet_t* pkt = create_arp_packet(ARP_OP_REQUEST, netif,
                                          netif->ip_addr, netif->hw_addr,
                                          ip_addr, zero_mac);
    if (!pkt) {
        return -1;
    }
    
    printf("Sending ARP request for ");
    print_ip(ip_addr);
    printf(" on interface %s\n", netif->name);
    
    /* Send as Ethernet frame with broadcast MAC */
    int result = kos_eth_output(netif, pkt, broadcast_mac);
    
    pthread_mutex_lock(&arp_stats.lock);
    arp_stats.requests_sent++;
    pthread_mutex_unlock(&arp_stats.lock);
    
    if (result < 0) {
        kos_packet_free(pkt);
    }
    
    return result;
}

/* Send ARP reply */
int kos_arp_reply(kos_netif_t* netif, kos_packet_t* req_pkt) {
    if (!netif || !req_pkt) {
        return -1;
    }
    
    kos_arp_header_t* req_hdr = (kos_arp_header_t*)req_pkt->data;
    
    /* Validate request */
    if (ntohs(req_hdr->htype) != ARP_HTYPE_ETHERNET ||
        ntohs(req_hdr->ptype) != ARP_PTYPE_IP ||
        req_hdr->hlen != ARP_HLEN_ETHERNET ||
        req_hdr->plen != ARP_PLEN_IP ||
        ntohs(req_hdr->opcode) != ARP_OP_REQUEST) {
        return -1;
    }
    
    uint32_t target_ip = ntohl(req_hdr->tpa);
    
    /* Check if request is for our IP */
    if (target_ip != netif->ip_addr) {
        return -1;
    }
    
    uint32_t sender_ip = ntohl(req_hdr->spa);
    
    kos_packet_t* pkt = create_arp_packet(ARP_OP_REPLY, netif,
                                          netif->ip_addr, netif->hw_addr,
                                          sender_ip, req_hdr->sha);
    if (!pkt) {
        return -1;
    }
    
    printf("Sending ARP reply to ");
    print_ip(sender_ip);
    printf(" (");
    print_mac(req_hdr->sha);
    printf(")\n");
    
    /* Send as Ethernet frame to requester */
    int result = kos_eth_output(netif, pkt, req_hdr->sha);
    
    pthread_mutex_lock(&arp_stats.lock);
    arp_stats.replies_sent++;
    pthread_mutex_unlock(&arp_stats.lock);
    
    if (result < 0) {
        kos_packet_free(pkt);
    }
    
    return result;
}

/* Process incoming ARP packet */
int kos_arp_input(kos_netif_t* netif, kos_packet_t* pkt) {
    if (!netif || !pkt || pkt->size < sizeof(kos_arp_header_t)) {
        return -1;
    }
    
    kos_arp_header_t* arp_hdr = (kos_arp_header_t*)pkt->data;
    
    /* Validate ARP header */
    if (ntohs(arp_hdr->htype) != ARP_HTYPE_ETHERNET ||
        ntohs(arp_hdr->ptype) != ARP_PTYPE_IP ||
        arp_hdr->hlen != ARP_HLEN_ETHERNET ||
        arp_hdr->plen != ARP_PLEN_IP) {
        return -1;
    }
    
    uint16_t opcode = ntohs(arp_hdr->opcode);
    uint32_t sender_ip = ntohl(arp_hdr->spa);
    uint32_t target_ip = ntohl(arp_hdr->tpa);
    
    /* Ignore our own packets */
    if (sender_ip == netif->ip_addr) {
        return 0;
    }
    
    pthread_mutex_lock(&arp_cache_lock);
    
    /* Update ARP cache with sender information */
    if (sender_ip != 0) {
        arp_cache_add_entry(sender_ip, arp_hdr->sha, ARP_FLAG_COMPLETE);
    }
    
    pthread_mutex_unlock(&arp_cache_lock);
    
    switch (opcode) {
        case ARP_OP_REQUEST:
            pthread_mutex_lock(&arp_stats.lock);
            arp_stats.requests_recv++;
            pthread_mutex_unlock(&arp_stats.lock);
            
            printf("Received ARP request from ");
            print_ip(sender_ip);
            printf(" for ");
            print_ip(target_ip);
            printf("\n");
            
            /* Send reply if request is for our IP */
            if (target_ip == netif->ip_addr) {
                return kos_arp_reply(netif, pkt);
            }
            break;
            
        case ARP_OP_REPLY:
            pthread_mutex_lock(&arp_stats.lock);
            arp_stats.replies_recv++;
            pthread_mutex_unlock(&arp_stats.lock);
            
            printf("Received ARP reply from ");
            print_ip(sender_ip);
            printf(" (");
            print_mac(arp_hdr->sha);
            printf(")\n");
            
            /* Check for gratuitous ARP */
            if (sender_ip == target_ip) {
                pthread_mutex_lock(&arp_stats.lock);
                arp_stats.gratuitous_recv++;
                pthread_mutex_unlock(&arp_stats.lock);
                
                printf("Gratuitous ARP detected\n");
            }
            break;
            
        default:
            printf("Unknown ARP opcode: %d\n", opcode);
            return -1;
    }
    
    return 0;
}

/* Lookup ARP entry */
kos_arp_entry_t* kos_arp_lookup(uint32_t ip_addr) {
    pthread_mutex_lock(&arp_cache_lock);
    
    kos_arp_entry_t* entry = arp_cache_find(ip_addr);
    
    if (entry) {
        pthread_mutex_lock(&arp_stats.lock);
        arp_stats.cache_hits++;
        pthread_mutex_unlock(&arp_stats.lock);
    } else {
        pthread_mutex_lock(&arp_stats.lock);
        arp_stats.cache_misses++;
        pthread_mutex_unlock(&arp_stats.lock);
    }
    
    pthread_mutex_unlock(&arp_cache_lock);
    return entry;
}

/* Add ARP entry */
int kos_arp_add(uint32_t ip_addr, const uint8_t* hw_addr) {
    if (!hw_addr) {
        return -1;
    }
    
    pthread_mutex_lock(&arp_cache_lock);
    int result = arp_cache_add_entry(ip_addr, hw_addr, ARP_FLAG_COMPLETE);
    pthread_mutex_unlock(&arp_cache_lock);
    
    if (result == 0) {
        printf("Added ARP entry: ");
        print_ip(ip_addr);
        printf(" -> ");
        print_mac(hw_addr);
        printf("\n");
    }
    
    return result;
}

/* Delete ARP entry */
int kos_arp_delete(uint32_t ip_addr) {
    pthread_mutex_lock(&arp_cache_lock);
    int result = arp_cache_remove_entry(ip_addr);
    pthread_mutex_unlock(&arp_cache_lock);
    
    if (result == 0) {
        printf("Deleted ARP entry for ");
        print_ip(ip_addr);
        printf("\n");
    }
    
    return result;
}

/* Send gratuitous ARP */
int kos_arp_send_gratuitous(kos_netif_t* netif) {
    if (!netif || netif->ip_addr == 0) {
        return -1;
    }
    
    uint8_t broadcast_mac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    
    kos_packet_t* pkt = create_arp_packet(ARP_OP_REQUEST, netif,
                                          netif->ip_addr, netif->hw_addr,
                                          netif->ip_addr, broadcast_mac);
    if (!pkt) {
        return -1;
    }
    
    printf("Sending gratuitous ARP for ");
    print_ip(netif->ip_addr);
    printf(" on interface %s\n", netif->name);
    
    int result = kos_eth_output(netif, pkt, broadcast_mac);
    
    pthread_mutex_lock(&arp_stats.lock);
    arp_stats.requests_sent++;
    pthread_mutex_unlock(&arp_stats.lock);
    
    if (result < 0) {
        kos_packet_free(pkt);
    }
    
    return result;
}

/* Dump ARP cache */
void kos_arp_dump_cache(void) {
    pthread_mutex_lock(&arp_cache_lock);
    
    printf("ARP Cache (%u entries):\n", arp_cache_count);
    printf("%-15s %-18s %-8s %-10s\n", "IP Address", "HW Address", "Flags", "Age");
    printf("--------------------------------------------------------\n");
    
    uint64_t current_time = get_current_time();
    kos_arp_entry_t* entry = arp_cache;
    
    while (entry) {
        printf("%-15s ", "");
        print_ip(entry->ip_addr);
        printf(" ");
        print_mac(entry->hw_addr);
        
        printf(" %c%c%c%c ",
               (entry->flags & ARP_FLAG_COMPLETE) ? 'C' : '-',
               (entry->flags & ARP_FLAG_PERMANENT) ? 'P' : '-',
               (entry->flags & ARP_FLAG_PUBLISHED) ? 'M' : '-',
               (entry->flags & ARP_FLAG_PROXY) ? 'R' : '-');
        
        uint64_t age = (current_time - entry->timestamp) / 1000000000ULL;
        printf("%lus\n", age);
        
        entry = entry->next;
    }
    
    pthread_mutex_unlock(&arp_cache_lock);
}

/* Dump ARP statistics */
void kos_arp_dump_stats(void) {
    pthread_mutex_lock(&arp_stats.lock);
    
    printf("ARP Statistics:\n");
    printf("  Requests: %lu sent, %lu received\n", 
           arp_stats.requests_sent, arp_stats.requests_recv);
    printf("  Replies: %lu sent, %lu received\n",
           arp_stats.replies_sent, arp_stats.replies_recv);
    printf("  Gratuitous: %lu received\n", arp_stats.gratuitous_recv);
    printf("  Cache: %lu hits, %lu misses, %lu timeouts\n",
           arp_stats.cache_hits, arp_stats.cache_misses, arp_stats.timeouts);
    
    pthread_mutex_unlock(&arp_stats.lock);
}

/* Initialize ARP subsystem */
int kos_arp_init(void) {
    arp_cache = NULL;
    arp_cache_count = 0;
    
    memset(&arp_stats, 0, sizeof(arp_stats));
    if (pthread_mutex_init(&arp_stats.lock, NULL) != 0) {
        return -1;
    }
    
    printf("ARP subsystem initialized\n");
    return 0;
}

/* Cleanup ARP subsystem */
void kos_arp_cleanup(void) {
    pthread_mutex_lock(&arp_cache_lock);
    
    /* Free all ARP entries */
    while (arp_cache) {
        kos_arp_entry_t* entry = arp_cache;
        arp_cache = entry->next;
        free(entry);
    }
    arp_cache_count = 0;
    
    pthread_mutex_unlock(&arp_cache_lock);
    pthread_mutex_destroy(&arp_stats.lock);
    
    printf("ARP subsystem cleaned up\n");
}

/* Periodic ARP cache maintenance */
void kos_arp_timer(void) {
    pthread_mutex_lock(&arp_cache_lock);
    arp_cache_cleanup();
    pthread_mutex_unlock(&arp_cache_lock);
}