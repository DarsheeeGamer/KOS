/*
 * KOS Netfilter Implementation
 * Handles packet filtering, netfilter hooks, and connection tracking
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>

/* Connection tracking states */
#define CT_STATE_NEW        0x01
#define CT_STATE_ESTABLISHED 0x02
#define CT_STATE_RELATED    0x04
#define CT_STATE_INVALID    0x08

/* Connection tracking timeouts (seconds) */
#define CT_TIMEOUT_TCP_ESTABLISHED  7200    /* 2 hours */
#define CT_TIMEOUT_TCP_SYN_SENT     120     /* 2 minutes */
#define CT_TIMEOUT_TCP_SYN_RECV     60      /* 1 minute */
#define CT_TIMEOUT_TCP_FIN_WAIT     120     /* 2 minutes */
#define CT_TIMEOUT_TCP_CLOSE_WAIT   60      /* 1 minute */
#define CT_TIMEOUT_TCP_TIME_WAIT    120     /* 2 minutes */
#define CT_TIMEOUT_UDP              30      /* 30 seconds */
#define CT_TIMEOUT_ICMP             30      /* 30 seconds */

/* Connection tracking table size */
#define CT_TABLE_SIZE       1024
#define CT_MAX_ENTRIES      4096

/* Netfilter hook tables */
static kos_nf_hook_entry_t* nf_hooks[KOS_NF_MAX_HOOKS] = {NULL};
static pthread_mutex_t nf_hooks_lock[KOS_NF_MAX_HOOKS];

/* Connection tracking table */
static kos_conntrack_t* ct_table[CT_TABLE_SIZE] = {NULL};
static pthread_mutex_t ct_table_lock = PTHREAD_MUTEX_INITIALIZER;
static uint32_t ct_count = 0;

/* Netfilter statistics */
static struct {
    uint64_t packets_total;
    uint64_t packets_accepted;
    uint64_t packets_dropped;
    uint64_t packets_stolen;
    uint64_t packets_queued;
    uint64_t hook_calls[KOS_NF_MAX_HOOKS];
    pthread_mutex_t lock;
} nf_stats = {0};

/* Connection tracking statistics */
static struct {
    uint64_t entries_created;
    uint64_t entries_destroyed;
    uint64_t entries_timeout;
    uint64_t lookups;
    uint64_t lookup_hits;
    uint64_t lookup_misses;
    pthread_mutex_t lock;
} ct_stats = {0};

/* Utility functions */
static uint64_t get_current_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec;
}

static uint32_t ct_hash(uint32_t src_ip, uint32_t dst_ip, uint16_t src_port, 
                        uint16_t dst_port, uint8_t protocol) {
    uint32_t hash = src_ip ^ dst_ip ^ ((uint32_t)src_port << 16) ^ dst_port ^ protocol;
    return hash % CT_TABLE_SIZE;
}

static void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

/* Connection tracking functions */
static kos_conntrack_t* ct_find_entry(uint32_t src_ip, uint32_t dst_ip,
                                      uint16_t src_port, uint16_t dst_port,
                                      uint8_t protocol) {
    uint32_t hash = ct_hash(src_ip, dst_ip, src_port, dst_port, protocol);
    kos_conntrack_t* entry = ct_table[hash];
    
    while (entry) {
        if (entry->src_ip == src_ip && entry->dst_ip == dst_ip &&
            entry->src_port == src_port && entry->dst_port == dst_port &&
            entry->protocol == protocol) {
            return entry;
        }
        /* Also check reverse direction */
        if (entry->src_ip == dst_ip && entry->dst_ip == src_ip &&
            entry->src_port == dst_port && entry->dst_port == src_port &&
            entry->protocol == protocol) {
            return entry;
        }
        entry = entry->next;
    }
    
    return NULL;
}

static kos_conntrack_t* ct_create_entry(uint32_t src_ip, uint32_t dst_ip,
                                        uint16_t src_port, uint16_t dst_port,
                                        uint8_t protocol) {
    if (ct_count >= CT_MAX_ENTRIES) {
        return NULL; /* Connection table full */
    }
    
    kos_conntrack_t* entry = malloc(sizeof(kos_conntrack_t));
    if (!entry) {
        return NULL;
    }
    
    entry->src_ip = src_ip;
    entry->dst_ip = dst_ip;
    entry->src_port = src_port;
    entry->dst_port = dst_port;
    entry->protocol = protocol;
    entry->state = CT_STATE_NEW;
    entry->timestamp = get_current_time();
    entry->packets = 0;
    entry->bytes = 0;
    entry->next = NULL;
    
    uint32_t hash = ct_hash(src_ip, dst_ip, src_port, dst_port, protocol);
    entry->next = ct_table[hash];
    ct_table[hash] = entry;
    ct_count++;
    
    pthread_mutex_lock(&ct_stats.lock);
    ct_stats.entries_created++;
    pthread_mutex_unlock(&ct_stats.lock);
    
    return entry;
}

static void ct_destroy_entry(kos_conntrack_t* target) {
    for (int i = 0; i < CT_TABLE_SIZE; i++) {
        kos_conntrack_t* entry = ct_table[i];
        kos_conntrack_t* prev = NULL;
        
        while (entry) {
            if (entry == target) {
                if (prev) {
                    prev->next = entry->next;
                } else {
                    ct_table[i] = entry->next;
                }
                free(entry);
                ct_count--;
                
                pthread_mutex_lock(&ct_stats.lock);
                ct_stats.entries_destroyed++;
                pthread_mutex_unlock(&ct_stats.lock);
                
                return;
            }
            prev = entry;
            entry = entry->next;
        }
    }
}

static void ct_cleanup_expired(void) {
    uint64_t current_time = get_current_time();
    
    for (int i = 0; i < CT_TABLE_SIZE; i++) {
        kos_conntrack_t* entry = ct_table[i];
        kos_conntrack_t* prev = NULL;
        
        while (entry) {
            kos_conntrack_t* next = entry->next;
            uint64_t timeout = 0;
            
            /* Determine timeout based on protocol and state */
            switch (entry->protocol) {
                case 6: /* TCP */
                    switch (entry->state) {
                        case CT_STATE_ESTABLISHED:
                            timeout = CT_TIMEOUT_TCP_ESTABLISHED;
                            break;
                        case CT_STATE_NEW:
                            timeout = CT_TIMEOUT_TCP_SYN_SENT;
                            break;
                        default:
                            timeout = CT_TIMEOUT_TCP_FIN_WAIT;
                            break;
                    }
                    break;
                case 17: /* UDP */
                    timeout = CT_TIMEOUT_UDP;
                    break;
                case 1: /* ICMP */
                    timeout = CT_TIMEOUT_ICMP;
                    break;
                default:
                    timeout = 300; /* 5 minutes default */
                    break;
            }
            
            if (current_time - entry->timestamp > timeout) {
                /* Remove expired entry */
                if (prev) {
                    prev->next = next;
                } else {
                    ct_table[i] = next;
                }
                free(entry);
                ct_count--;
                
                pthread_mutex_lock(&ct_stats.lock);
                ct_stats.entries_timeout++;
                pthread_mutex_unlock(&ct_stats.lock);
            } else {
                prev = entry;
            }
            
            entry = next;
        }
    }
}

/* Connection tracking interface */
kos_conntrack_t* kos_conntrack_find(uint32_t src_ip, uint32_t dst_ip,
                                    uint16_t src_port, uint16_t dst_port,
                                    uint8_t protocol) {
    pthread_mutex_lock(&ct_table_lock);
    pthread_mutex_lock(&ct_stats.lock);
    ct_stats.lookups++;
    pthread_mutex_unlock(&ct_stats.lock);
    
    kos_conntrack_t* entry = ct_find_entry(src_ip, dst_ip, src_port, dst_port, protocol);
    
    if (entry) {
        pthread_mutex_lock(&ct_stats.lock);
        ct_stats.lookup_hits++;
        pthread_mutex_unlock(&ct_stats.lock);
    } else {
        pthread_mutex_lock(&ct_stats.lock);
        ct_stats.lookup_misses++;
        pthread_mutex_unlock(&ct_stats.lock);
    }
    
    pthread_mutex_unlock(&ct_table_lock);
    return entry;
}

int kos_conntrack_add(kos_packet_t* pkt) {
    if (!pkt || !pkt->l3_header || !pkt->l4_header) {
        return -1;
    }
    
    kos_ip_header_t* ip_hdr = (kos_ip_header_t*)pkt->l3_header;
    uint32_t src_ip = ntohl(ip_hdr->src_addr);
    uint32_t dst_ip = ntohl(ip_hdr->dst_addr);
    uint8_t protocol = ip_hdr->protocol;
    uint16_t src_port = 0, dst_port = 0;
    
    /* Extract port information */
    if (protocol == 6) { /* TCP */
        kos_tcp_header_t* tcp_hdr = (kos_tcp_header_t*)pkt->l4_header;
        src_port = ntohs(tcp_hdr->src_port);
        dst_port = ntohs(tcp_hdr->dst_port);
    } else if (protocol == 17) { /* UDP */
        kos_udp_header_t* udp_hdr = (kos_udp_header_t*)pkt->l4_header;
        src_port = ntohs(udp_hdr->src_port);
        dst_port = ntohs(udp_hdr->dst_port);
    }
    
    pthread_mutex_lock(&ct_table_lock);
    
    /* Check if entry already exists */
    kos_conntrack_t* entry = ct_find_entry(src_ip, dst_ip, src_port, dst_port, protocol);
    if (entry) {
        pthread_mutex_unlock(&ct_table_lock);
        return 0; /* Entry already exists */
    }
    
    /* Create new entry */
    entry = ct_create_entry(src_ip, dst_ip, src_port, dst_port, protocol);
    
    pthread_mutex_unlock(&ct_table_lock);
    
    if (entry) {
        printf("New connection tracked: ");
        print_ip(src_ip);
        printf(":%u -> ", src_port);
        print_ip(dst_ip);
        printf(":%u (proto %u)\n", dst_port, protocol);
        return 0;
    }
    
    return -1;
}

int kos_conntrack_update(kos_packet_t* pkt) {
    if (!pkt || !pkt->l3_header) {
        return -1;
    }
    
    kos_ip_header_t* ip_hdr = (kos_ip_header_t*)pkt->l3_header;
    uint32_t src_ip = ntohl(ip_hdr->src_addr);
    uint32_t dst_ip = ntohl(ip_hdr->dst_addr);
    uint8_t protocol = ip_hdr->protocol;
    uint16_t src_port = 0, dst_port = 0;
    
    /* Extract port information */
    if (protocol == 6 && pkt->l4_header) { /* TCP */
        kos_tcp_header_t* tcp_hdr = (kos_tcp_header_t*)pkt->l4_header;
        src_port = ntohs(tcp_hdr->src_port);
        dst_port = ntohs(tcp_hdr->dst_port);
    } else if (protocol == 17 && pkt->l4_header) { /* UDP */
        kos_udp_header_t* udp_hdr = (kos_udp_header_t*)pkt->l4_header;
        src_port = ntohs(udp_hdr->src_port);
        dst_port = ntohs(udp_hdr->dst_port);
    }
    
    pthread_mutex_lock(&ct_table_lock);
    
    kos_conntrack_t* entry = ct_find_entry(src_ip, dst_ip, src_port, dst_port, protocol);
    if (entry) {
        entry->timestamp = get_current_time();
        entry->packets++;
        entry->bytes += pkt->size;
        
        /* Update connection state for TCP */
        if (protocol == 6 && pkt->l4_header) {
            kos_tcp_header_t* tcp_hdr = (kos_tcp_header_t*)pkt->l4_header;
            uint8_t flags = tcp_hdr->flags;
            
            if (flags & 0x02) { /* SYN */
                if (entry->state == CT_STATE_NEW) {
                    entry->state = CT_STATE_NEW; /* SYN_SENT */
                }
            } else if (flags & 0x10) { /* ACK */
                if (entry->state == CT_STATE_NEW) {
                    entry->state = CT_STATE_ESTABLISHED;
                }
            }
        } else if (entry->state == CT_STATE_NEW) {
            entry->state = CT_STATE_ESTABLISHED;
        }
    }
    
    pthread_mutex_unlock(&ct_table_lock);
    
    return entry ? 0 : -1;
}

void kos_conntrack_cleanup(void) {
    pthread_mutex_lock(&ct_table_lock);
    ct_cleanup_expired();
    pthread_mutex_unlock(&ct_table_lock);
}

/* Netfilter hook management */
int kos_nf_register_hook(kos_nf_hook_t hook, kos_nf_hook_fn fn, void* priv, int priority) {
    if (hook >= KOS_NF_MAX_HOOKS || !fn) {
        return -1;
    }
    
    kos_nf_hook_entry_t* entry = malloc(sizeof(kos_nf_hook_entry_t));
    if (!entry) {
        return -1;
    }
    
    entry->hook = fn;
    entry->priv = priv;
    entry->priority = priority;
    entry->next = NULL;
    
    pthread_mutex_lock(&nf_hooks_lock[hook]);
    
    /* Insert in priority order (lower numbers = higher priority) */
    if (!nf_hooks[hook] || nf_hooks[hook]->priority > priority) {
        entry->next = nf_hooks[hook];
        nf_hooks[hook] = entry;
    } else {
        kos_nf_hook_entry_t* current = nf_hooks[hook];
        while (current->next && current->next->priority <= priority) {
            current = current->next;
        }
        entry->next = current->next;
        current->next = entry;
    }
    
    pthread_mutex_unlock(&nf_hooks_lock[hook]);
    
    printf("Registered netfilter hook for point %d with priority %d\n", hook, priority);
    return 0;
}

int kos_nf_unregister_hook(kos_nf_hook_t hook, kos_nf_hook_fn fn) {
    if (hook >= KOS_NF_MAX_HOOKS || !fn) {
        return -1;
    }
    
    pthread_mutex_lock(&nf_hooks_lock[hook]);
    
    kos_nf_hook_entry_t* entry = nf_hooks[hook];
    kos_nf_hook_entry_t* prev = NULL;
    
    while (entry) {
        if (entry->hook == fn) {
            if (prev) {
                prev->next = entry->next;
            } else {
                nf_hooks[hook] = entry->next;
            }
            free(entry);
            pthread_mutex_unlock(&nf_hooks_lock[hook]);
            printf("Unregistered netfilter hook for point %d\n", hook);
            return 0;
        }
        prev = entry;
        entry = entry->next;
    }
    
    pthread_mutex_unlock(&nf_hooks_lock[hook]);
    return -1;
}

kos_nf_verdict_t kos_nf_hook_slow(kos_nf_hook_t hook, kos_packet_t* pkt,
                                  kos_netif_t* in, kos_netif_t* out) {
    if (hook >= KOS_NF_MAX_HOOKS || !pkt) {
        return KOS_NF_ACCEPT;
    }
    
    pthread_mutex_lock(&nf_stats.lock);
    nf_stats.packets_total++;
    nf_stats.hook_calls[hook]++;
    pthread_mutex_unlock(&nf_stats.lock);
    
    pthread_mutex_lock(&nf_hooks_lock[hook]);
    
    kos_nf_hook_entry_t* entry = nf_hooks[hook];
    kos_nf_verdict_t verdict = KOS_NF_ACCEPT;
    
    while (entry) {
        verdict = entry->hook(pkt, in, out, entry->priv);
        
        /* Stop if packet is dropped, stolen, or queued */
        if (verdict != KOS_NF_ACCEPT) {
            break;
        }
        
        entry = entry->next;
    }
    
    pthread_mutex_unlock(&nf_hooks_lock[hook]);
    
    /* Update statistics */
    pthread_mutex_lock(&nf_stats.lock);
    switch (verdict) {
        case KOS_NF_ACCEPT:
            nf_stats.packets_accepted++;
            break;
        case KOS_NF_DROP:
            nf_stats.packets_dropped++;
            break;
        case KOS_NF_STOLEN:
            nf_stats.packets_stolen++;
            break;
        case KOS_NF_QUEUE:
            nf_stats.packets_queued++;
            break;
        default:
            break;
    }
    pthread_mutex_unlock(&nf_stats.lock);
    
    return verdict;
}

/* Built-in netfilter hooks */

/* Connection tracking hook */
static kos_nf_verdict_t nf_conntrack_hook(kos_packet_t* pkt, kos_netif_t* in,
                                          kos_netif_t* out, void* priv) {
    /* Update existing connection or create new one */
    if (kos_conntrack_update(pkt) < 0) {
        kos_conntrack_add(pkt);
    }
    
    return KOS_NF_ACCEPT;
}

/* Basic firewall hook */
static kos_nf_verdict_t nf_firewall_hook(kos_packet_t* pkt, kos_netif_t* in,
                                         kos_netif_t* out, void* priv) {
    if (!pkt->l3_header) {
        return KOS_NF_ACCEPT;
    }
    
    kos_ip_header_t* ip_hdr = (kos_ip_header_t*)pkt->l3_header;
    
    /* Drop packets from private ranges going out (simple egress filter) */
    if (out && !in) {
        uint32_t src_ip = ntohl(ip_hdr->src_addr);
        
        /* Check for RFC 1918 private addresses */
        if (((src_ip & 0xFF000000) == 0x0A000000) ||      /* 10.0.0.0/8 */
            ((src_ip & 0xFFF00000) == 0xAC100000) ||      /* 172.16.0.0/12 */
            ((src_ip & 0xFFFF0000) == 0xC0A80000)) {      /* 192.168.0.0/16 */
            printf("Dropped private IP %d.%d.%d.%d in outgoing packet\n",
                   (src_ip >> 24) & 0xFF, (src_ip >> 16) & 0xFF,
                   (src_ip >> 8) & 0xFF, src_ip & 0xFF);
            return KOS_NF_DROP;
        }
    }
    
    return KOS_NF_ACCEPT;
}

/* Dump netfilter statistics */
void kos_nf_dump_stats(void) {
    pthread_mutex_lock(&nf_stats.lock);
    
    printf("Netfilter Statistics:\n");
    printf("  Total packets: %lu\n", nf_stats.packets_total);
    printf("  Accepted: %lu, Dropped: %lu\n", 
           nf_stats.packets_accepted, nf_stats.packets_dropped);
    printf("  Stolen: %lu, Queued: %lu\n",
           nf_stats.packets_stolen, nf_stats.packets_queued);
    
    printf("  Hook calls:\n");
    const char* hook_names[] = {
        "PRE_ROUTING", "LOCAL_IN", "FORWARD", "LOCAL_OUT", "POST_ROUTING"
    };
    for (int i = 0; i < KOS_NF_MAX_HOOKS; i++) {
        printf("    %s: %lu\n", hook_names[i], nf_stats.hook_calls[i]);
    }
    
    pthread_mutex_unlock(&nf_stats.lock);
}

/* Dump connection tracking statistics */
void kos_conntrack_dump_stats(void) {
    pthread_mutex_lock(&ct_stats.lock);
    
    printf("Connection Tracking Statistics:\n");
    printf("  Entries: %u active, %lu created, %lu destroyed\n",
           ct_count, ct_stats.entries_created, ct_stats.entries_destroyed);
    printf("  Timeouts: %lu\n", ct_stats.entries_timeout);
    printf("  Lookups: %lu total, %lu hits, %lu misses\n",
           ct_stats.lookups, ct_stats.lookup_hits, ct_stats.lookup_misses);
    
    pthread_mutex_unlock(&ct_stats.lock);
}

/* Dump connection tracking table */
void kos_conntrack_dump_table(void) {
    pthread_mutex_lock(&ct_table_lock);
    
    printf("Connection Tracking Table (%u entries):\n", ct_count);
    printf("%-15s %-6s %-15s %-6s %-5s %-8s %-8s %-8s\n",
           "Source", "Port", "Dest", "Port", "Proto", "State", "Packets", "Bytes");
    printf("--------------------------------------------------------------------------------\n");
    
    uint64_t current_time = get_current_time();
    
    for (int i = 0; i < CT_TABLE_SIZE; i++) {
        kos_conntrack_t* entry = ct_table[i];
        while (entry) {
            char src[16], dst[16];
            snprintf(src, sizeof(src), "%d.%d.%d.%d",
                     (entry->src_ip >> 24) & 0xFF, (entry->src_ip >> 16) & 0xFF,
                     (entry->src_ip >> 8) & 0xFF, entry->src_ip & 0xFF);
            snprintf(dst, sizeof(dst), "%d.%d.%d.%d",
                     (entry->dst_ip >> 24) & 0xFF, (entry->dst_ip >> 16) & 0xFF,
                     (entry->dst_ip >> 8) & 0xFF, entry->dst_ip & 0xFF);
            
            const char* state_str = "UNKNOWN";
            switch (entry->state) {
                case CT_STATE_NEW: state_str = "NEW"; break;
                case CT_STATE_ESTABLISHED: state_str = "ESTAB"; break;
                case CT_STATE_RELATED: state_str = "RELATED"; break;
                case CT_STATE_INVALID: state_str = "INVALID"; break;
            }
            
            printf("%-15s %-6u %-15s %-6u %-5u %-8s %-8lu %-8lu\n",
                   src, entry->src_port, dst, entry->dst_port,
                   entry->protocol, state_str, entry->packets, entry->bytes);
            
            entry = entry->next;
        }
    }
    
    pthread_mutex_unlock(&ct_table_lock);
}

/* Initialize netfilter subsystem */
int kos_netfilter_init(void) {
    /* Initialize hook tables */
    for (int i = 0; i < KOS_NF_MAX_HOOKS; i++) {
        nf_hooks[i] = NULL;
        if (pthread_mutex_init(&nf_hooks_lock[i], NULL) != 0) {
            return -1;
        }
    }
    
    /* Initialize connection tracking table */
    for (int i = 0; i < CT_TABLE_SIZE; i++) {
        ct_table[i] = NULL;
    }
    ct_count = 0;
    
    /* Initialize statistics */
    memset(&nf_stats, 0, sizeof(nf_stats));
    if (pthread_mutex_init(&nf_stats.lock, NULL) != 0) {
        return -1;
    }
    
    memset(&ct_stats, 0, sizeof(ct_stats));
    if (pthread_mutex_init(&ct_stats.lock, NULL) != 0) {
        return -1;
    }
    
    /* Register built-in hooks */
    kos_nf_register_hook(KOS_NF_PRE_ROUTING, nf_conntrack_hook, NULL, 100);
    kos_nf_register_hook(KOS_NF_LOCAL_IN, nf_firewall_hook, NULL, 0);
    kos_nf_register_hook(KOS_NF_LOCAL_OUT, nf_firewall_hook, NULL, 0);
    
    printf("Netfilter subsystem initialized\n");
    return 0;
}

/* Cleanup netfilter subsystem */
void kos_netfilter_cleanup(void) {
    /* Clean up hook tables */
    for (int i = 0; i < KOS_NF_MAX_HOOKS; i++) {
        pthread_mutex_lock(&nf_hooks_lock[i]);
        while (nf_hooks[i]) {
            kos_nf_hook_entry_t* entry = nf_hooks[i];
            nf_hooks[i] = entry->next;
            free(entry);
        }
        pthread_mutex_unlock(&nf_hooks_lock[i]);
        pthread_mutex_destroy(&nf_hooks_lock[i]);
    }
    
    /* Clean up connection tracking table */
    pthread_mutex_lock(&ct_table_lock);
    for (int i = 0; i < CT_TABLE_SIZE; i++) {
        while (ct_table[i]) {
            kos_conntrack_t* entry = ct_table[i];
            ct_table[i] = entry->next;
            free(entry);
        }
    }
    ct_count = 0;
    pthread_mutex_unlock(&ct_table_lock);
    
    /* Clean up mutexes */
    pthread_mutex_destroy(&nf_stats.lock);
    pthread_mutex_destroy(&ct_stats.lock);
    
    printf("Netfilter subsystem cleaned up\n");
}