/*
 * KOS Network Stack Core Implementation
 * Main network stack initialization and management
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
#include <signal.h>
#include <stdio.h>
#include <time.h>

/* For older systems that might not have these defined */
#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC 1
#endif

/* Global network stack state */
static struct {
    bool initialized;
    pthread_mutex_t lock;
    
    /* Socket management */
    kos_socket_t* socket_list;
    int next_socket_fd;
    
    /* Network interfaces */
    kos_netif_t* netif_list;
    int next_netif_index;
    
    /* Routing table */
    kos_route_t* route_list;
    
    /* ARP cache */
    kos_arp_entry_t* arp_cache;
    
    /* Connection tracking */
    kos_conntrack_t* conntrack_list;
    
    /* Netfilter hooks */
    kos_nf_hook_entry_t* nf_hooks[KOS_NF_MAX_HOOKS];
    
    /* Statistics */
    uint64_t total_packets_sent;
    uint64_t total_packets_recv;
    uint64_t total_bytes_sent;
    uint64_t total_bytes_recv;
    
    /* Worker thread */
    pthread_t worker_thread;
    bool worker_running;
    
} netstack_state = {0};

/* Forward declarations */
static void* netstack_worker(void* arg);
static void netstack_process_timers(void);
static void netstack_cleanup_connections(void);

/*
 * Initialize the network stack
 */
int kos_netstack_init(void) {
    int ret = 0;
    
    if (netstack_state.initialized) {
        return 0; /* Already initialized */
    }
    
    /* Initialize mutex */
    if (pthread_mutex_init(&netstack_state.lock, NULL) != 0) {
        return -ENOMEM;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    /* Initialize socket management */
    netstack_state.socket_list = NULL;
    netstack_state.next_socket_fd = 1000; /* Start from 1000 */
    
    /* Initialize network interfaces */
    netstack_state.netif_list = NULL;
    netstack_state.next_netif_index = 1;
    
    /* Initialize routing table */
    netstack_state.route_list = NULL;
    
    /* Initialize ARP cache */
    netstack_state.arp_cache = NULL;
    
    /* Initialize connection tracking */
    netstack_state.conntrack_list = NULL;
    
    /* Initialize netfilter hooks */
    memset(netstack_state.nf_hooks, 0, sizeof(netstack_state.nf_hooks));
    
    /* Create loopback interface */
    kos_netif_t* lo = kos_netif_create("lo");
    if (lo) {
        lo->flags |= IFF_UP | IFF_LOOPBACK | IFF_RUNNING;
        lo->ip_addr = htonl(INADDR_LOOPBACK);
        lo->netmask = htonl(0xFF000000);
        lo->mtu = 65535; /* Max uint16_t value */
        memset(lo->hw_addr, 0, 6);
    }
    
    /* Add default routes */
    kos_route_add(htonl(INADDR_LOOPBACK), 0, htonl(0xFF000000), lo);
    
    /* Start worker thread */
    netstack_state.worker_running = true;
    if (pthread_create(&netstack_state.worker_thread, NULL, netstack_worker, NULL) != 0) {
        ret = -ENOMEM;
        netstack_state.worker_running = false;
        goto cleanup;
    }
    
    netstack_state.initialized = true;
    
cleanup:
    pthread_mutex_unlock(&netstack_state.lock);
    
    if (ret != 0) {
        pthread_mutex_destroy(&netstack_state.lock);
    }
    
    return ret;
}

/*
 * Shutdown the network stack
 */
void kos_netstack_shutdown(void) {
    if (!netstack_state.initialized) {
        return;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    /* Stop worker thread */
    netstack_state.worker_running = false;
    pthread_mutex_unlock(&netstack_state.lock);
    
    pthread_join(netstack_state.worker_thread, NULL);
    
    pthread_mutex_lock(&netstack_state.lock);
    
    /* Cleanup sockets */
    kos_socket_t* sock = netstack_state.socket_list;
    while (sock) {
        kos_socket_t* next = sock->next;
        
        /* Free socket buffers */
        kos_packet_t* pkt = sock->recv_buffer.head;
        while (pkt) {
            kos_packet_t* next_pkt = pkt->next;
            kos_packet_free(pkt);
            pkt = next_pkt;
        }
        
        pkt = sock->send_buffer.head;
        while (pkt) {
            kos_packet_t* next_pkt = pkt->next;
            kos_packet_free(pkt);
            pkt = next_pkt;
        }
        
        pthread_mutex_destroy(&sock->recv_buffer.lock);
        pthread_mutex_destroy(&sock->send_buffer.lock);
        free(sock);
        sock = next;
    }
    
    /* Cleanup network interfaces */
    kos_netif_t* netif = netstack_state.netif_list;
    while (netif) {
        kos_netif_t* next = netif->next;
        free(netif);
        netif = next;
    }
    
    /* Cleanup routing table */
    kos_route_t* route = netstack_state.route_list;
    while (route) {
        kos_route_t* next = route->next;
        free(route);
        route = next;
    }
    
    /* Cleanup ARP cache */
    kos_arp_entry_t* arp = netstack_state.arp_cache;
    while (arp) {
        kos_arp_entry_t* next = arp->next;
        free(arp);
        arp = next;
    }
    
    /* Cleanup connection tracking */
    kos_conntrack_t* conn = netstack_state.conntrack_list;
    while (conn) {
        kos_conntrack_t* next = conn->next;
        free(conn);
        conn = next;
    }
    
    /* Cleanup netfilter hooks */
    for (int i = 0; i < KOS_NF_MAX_HOOKS; i++) {
        kos_nf_hook_entry_t* hook = netstack_state.nf_hooks[i];
        while (hook) {
            kos_nf_hook_entry_t* next = hook->next;
            free(hook);
            hook = next;
        }
    }
    
    netstack_state.initialized = false;
    
    pthread_mutex_unlock(&netstack_state.lock);
    pthread_mutex_destroy(&netstack_state.lock);
}

/*
 * Allocate a packet buffer
 */
kos_packet_t* kos_packet_alloc(size_t size) {
    kos_packet_t* pkt = calloc(1, sizeof(kos_packet_t));
    if (!pkt) {
        return NULL;
    }
    
    pkt->data = malloc(size);
    if (!pkt->data) {
        free(pkt);
        return NULL;
    }
    
    pkt->size = 0;
    pkt->capacity = size;
    pkt->next = NULL;
    pkt->flags = 0;
    
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    pkt->timestamp = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    
    return pkt;
}

/*
 * Free a packet buffer
 */
void kos_packet_free(kos_packet_t* pkt) {
    if (!pkt) {
        return;
    }
    
    free(pkt->data);
    free(pkt);
}

/*
 * Put data into packet
 */
int kos_packet_put(kos_packet_t* pkt, const void* data, size_t len) {
    if (!pkt || !data || pkt->size + len > pkt->capacity) {
        return -EINVAL;
    }
    
    memcpy(pkt->data + pkt->size, data, len);
    pkt->size += len;
    return 0;
}

/*
 * Push header space
 */
int kos_packet_push(kos_packet_t* pkt, size_t len) {
    if (!pkt || len > pkt->capacity - pkt->size) {
        return -EINVAL;
    }
    
    memmove(pkt->data + len, pkt->data, pkt->size);
    pkt->size += len;
    return 0;
}

/*
 * Pull header space
 */
int kos_packet_pull(kos_packet_t* pkt, size_t len) {
    if (!pkt || len > pkt->size) {
        return -EINVAL;
    }
    
    memmove(pkt->data, pkt->data + len, pkt->size - len);
    pkt->size -= len;
    return 0;
}

/*
 * Create network interface
 */
kos_netif_t* kos_netif_create(const char* name) {
    if (!name || !netstack_state.initialized) {
        return NULL;
    }
    
    kos_netif_t* netif = calloc(1, sizeof(kos_netif_t));
    if (!netif) {
        return NULL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    strncpy(netif->name, name, sizeof(netif->name) - 1);
    netif->index = netstack_state.next_netif_index++;
    netif->flags = 0;
    netif->mtu = 1500; /* Default MTU */
    
    /* Add to interface list */
    netif->next = netstack_state.netif_list;
    netstack_state.netif_list = netif;
    
    pthread_mutex_unlock(&netstack_state.lock);
    
    return netif;
}

/*
 * Find network interface by name
 */
kos_netif_t* kos_netif_find(const char* name) {
    if (!name || !netstack_state.initialized) {
        return NULL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_netif_t* netif = netstack_state.netif_list;
    while (netif) {
        if (strcmp(netif->name, name) == 0) {
            break;
        }
        netif = netif->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
    
    return netif;
}

/*
 * Find network interface by index
 */
kos_netif_t* kos_netif_find_by_index(int index) {
    if (!netstack_state.initialized) {
        return NULL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_netif_t* netif = netstack_state.netif_list;
    while (netif) {
        if (netif->index == index) {
            break;
        }
        netif = netif->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
    
    return netif;
}

/*
 * Bring network interface up
 */
int kos_netif_up(kos_netif_t* netif) {
    if (!netif) {
        return -EINVAL;
    }
    
    netif->flags |= IFF_UP | IFF_RUNNING;
    return 0;
}

/*
 * Bring network interface down
 */
int kos_netif_down(kos_netif_t* netif) {
    if (!netif) {
        return -EINVAL;
    }
    
    netif->flags &= ~(IFF_UP | IFF_RUNNING);
    return 0;
}

/*
 * Set interface IP address
 */
int kos_netif_set_addr(kos_netif_t* netif, uint32_t addr, uint32_t netmask) {
    if (!netif) {
        return -EINVAL;
    }
    
    netif->ip_addr = addr;
    netif->netmask = netmask;
    netif->broadcast = addr | (~netmask);
    
    return 0;
}

/*
 * Set interface hardware address
 */
int kos_netif_set_hw_addr(kos_netif_t* netif, const uint8_t* hw_addr) {
    if (!netif || !hw_addr) {
        return -EINVAL;
    }
    
    memcpy(netif->hw_addr, hw_addr, 6);
    return 0;
}

/*
 * Worker thread for network stack processing
 */
static void* netstack_worker(void* arg) {
    (void)arg;
    
    while (netstack_state.worker_running) {
        /* Process timers and cleanup */
        netstack_process_timers();
        netstack_cleanup_connections();
        
        /* Sleep for 100ms */
        usleep(100000);
    }
    
    return NULL;
}

/*
 * Process network timers
 */
static void netstack_process_timers(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    uint64_t current_time = now.tv_sec * 1000000000ULL + now.tv_nsec;
    
    pthread_mutex_lock(&netstack_state.lock);
    
    /* Process TCP timers */
    kos_socket_t* sock = netstack_state.socket_list;
    while (sock) {
        if (sock->type == KOS_SOCK_STREAM && sock->tcp_state != KOS_TCP_CLOSED) {
            /* Handle TCP retransmission timers */
            /* Handle keep-alive timers */
            /* Handle TIME_WAIT timeout */
            if (sock->tcp_state == KOS_TCP_TIME_WAIT) {
                /* Simplified: close after 30 seconds */
                if (current_time - sock->recv_buffer.head->timestamp > 30000000000ULL) {
                    sock->tcp_state = KOS_TCP_CLOSED;
                    sock->state = KOS_SS_CLOSED;
                }
            }
        }
        sock = sock->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
}

/*
 * Cleanup old connections
 */
static void netstack_cleanup_connections(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    uint64_t current_time = now.tv_sec * 1000000000ULL + now.tv_nsec;
    const uint64_t timeout = 300000000000ULL; /* 5 minutes */
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_conntrack_t** conn_ptr = &netstack_state.conntrack_list;
    while (*conn_ptr) {
        kos_conntrack_t* conn = *conn_ptr;
        if (current_time - conn->timestamp > timeout) {
            *conn_ptr = conn->next;
            free(conn);
        } else {
            conn_ptr = &conn->next;
        }
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
}

/*
 * Utility functions
 */
uint16_t kos_ip_checksum(const void* data, size_t len) {
    const uint16_t* buf = (const uint16_t*)data;
    uint32_t sum = 0;
    
    /* Sum all 16-bit words */
    while (len > 1) {
        sum += *buf++;
        len -= 2;
    }
    
    /* Add odd byte if present */
    if (len) {
        sum += *(const uint8_t*)buf << 8;
    }
    
    /* Add carry */
    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }
    
    return ~sum;
}

/*
 * Statistics functions
 */
void kos_netstat_dump(void) {
    if (!netstack_state.initialized) {
        return;
    }
    
    printf("Network Statistics:\n");
    printf("  Total packets sent: %lu\n", netstack_state.total_packets_sent);
    printf("  Total packets received: %lu\n", netstack_state.total_packets_recv);
    printf("  Total bytes sent: %lu\n", netstack_state.total_bytes_sent);
    printf("  Total bytes received: %lu\n", netstack_state.total_bytes_recv);
}

void kos_socket_dump(void) {
    if (!netstack_state.initialized) {
        return;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    printf("Socket List:\n");
    kos_socket_t* sock = netstack_state.socket_list;
    while (sock) {
        printf("  FD %d: Type %d, State %d, TCP State %d\n",
               sock->fd, sock->type, sock->state, sock->tcp_state);
        sock = sock->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
}

void kos_netif_dump(void) {
    if (!netstack_state.initialized) {
        return;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    printf("Network Interfaces:\n");
    kos_netif_t* netif = netstack_state.netif_list;
    while (netif) {
        struct in_addr addr = { .s_addr = netif->ip_addr };
        printf("  %s: Index %d, IP %s, Flags 0x%x\n",
               netif->name, netif->index, inet_ntoa(addr), netif->flags);
        printf("    RX: %lu packets, %lu bytes\n", netif->rx_packets, netif->rx_bytes);
        printf("    TX: %lu packets, %lu bytes\n", netif->tx_packets, netif->tx_bytes);
        netif = netif->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
}

/* Internal accessor functions for other modules */
kos_socket_t* _kos_socket_find(int fd) {
    kos_socket_t* sock = netstack_state.socket_list;
    while (sock) {
        if (sock->fd == fd) {
            return sock;
        }
        sock = sock->next;
    }
    return NULL;
}

int _kos_socket_add(kos_socket_t* sock) {
    sock->next = netstack_state.socket_list;
    netstack_state.socket_list = sock;
    return 0;
}

int _kos_socket_remove(kos_socket_t* sock) {
    kos_socket_t** sock_ptr = &netstack_state.socket_list;
    while (*sock_ptr) {
        if (*sock_ptr == sock) {
            *sock_ptr = sock->next;
            return 0;
        }
        sock_ptr = &(*sock_ptr)->next;
    }
    return -ENOENT;
}

int _kos_get_next_socket_fd(void) {
    return netstack_state.next_socket_fd++;
}

pthread_mutex_t* _kos_get_netstack_lock(void) {
    return &netstack_state.lock;
}

/*
 * Routing functions (simple implementation)
 */
int kos_route_add(uint32_t dest, uint32_t gateway, uint32_t genmask, kos_netif_t* netif) {
    if (!netstack_state.initialized || !netif) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_route_t* route = calloc(1, sizeof(kos_route_t));
    if (!route) {
        pthread_mutex_unlock(&netstack_state.lock);
        return -ENOMEM;
    }
    
    route->dest = dest;
    route->gateway = gateway;
    route->genmask = genmask;
    route->flags = 0;
    route->metric = 0;
    route->ref = 0;
    route->use = 0;
    route->interface = netif;
    
    /* Add to route list */
    route->next = netstack_state.route_list;
    netstack_state.route_list = route;
    
    pthread_mutex_unlock(&netstack_state.lock);
    return 0;
}

int kos_route_del(uint32_t dest, uint32_t genmask) {
    if (!netstack_state.initialized) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_route_t** route_ptr = &netstack_state.route_list;
    while (*route_ptr) {
        kos_route_t* route = *route_ptr;
        if (route->dest == dest && route->genmask == genmask) {
            *route_ptr = route->next;
            free(route);
            pthread_mutex_unlock(&netstack_state.lock);
            return 0;
        }
        route_ptr = &route->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
    return -ENOENT;
}

kos_route_t* kos_route_lookup(uint32_t dest) {
    if (!netstack_state.initialized) {
        return NULL;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    kos_route_t* best_route = NULL;
    uint32_t best_match = 0;
    
    kos_route_t* route = netstack_state.route_list;
    while (route) {
        uint32_t masked_dest = dest & route->genmask;
        uint32_t masked_route = route->dest & route->genmask;
        
        if (masked_dest == masked_route) {
            /* Route matches, check if it's more specific */
            if (route->genmask > best_match) {
                best_match = route->genmask;
                best_route = route;
            }
        }
        route = route->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
    return best_route;
}

void kos_route_dump(void) {
    if (!netstack_state.initialized) {
        return;
    }
    
    pthread_mutex_lock(&netstack_state.lock);
    
    printf("Routing Table:\n");
    printf("Destination     Gateway         Genmask         Interface\n");
    
    kos_route_t* route = netstack_state.route_list;
    while (route) {
        struct in_addr dest = { .s_addr = htonl(route->dest) };
        struct in_addr gateway = { .s_addr = htonl(route->gateway) };
        struct in_addr genmask = { .s_addr = htonl(route->genmask) };
        
        printf("%-15s %-15s %-15s %s\n",
               inet_ntoa(dest),
               inet_ntoa(gateway),
               inet_ntoa(genmask),
               route->interface ? route->interface->name : "none");
        
        route = route->next;
    }
    
    pthread_mutex_unlock(&netstack_state.lock);
}

/*
 * Simple Ethernet output stub
 */
int kos_eth_output(kos_netif_t* netif, kos_packet_t* pkt, const uint8_t* dest) {
    if (!netif || !pkt) {
        return -EINVAL;
    }
    
    /* For simulation, just mark as sent */
    netif->tx_packets++;
    netif->tx_bytes += pkt->size;
    
    /* In a real implementation, this would send the packet to the network device */
    printf("ETH: Sending packet of %zu bytes on interface %s\n", pkt->size, netif->name);
    
    /* Free the packet after "sending" */
    kos_packet_free(pkt);
    
    return 0;
}

/*
 * Simple Ethernet input stub  
 */
int kos_eth_input(kos_netif_t* netif, kos_packet_t* pkt) {
    if (!netif || !pkt) {
        return -EINVAL;
    }
    
    /* Update interface statistics */
    netif->rx_packets++;
    netif->rx_bytes += pkt->size;
    
    /* Set L2 header */
    pkt->l2_header = pkt->data;
    
    /* Simple Ethernet frame parsing */
    if (pkt->size < sizeof(kos_eth_header_t)) {
        kos_packet_free(pkt);
        return -EINVAL;
    }
    
    kos_eth_header_t* eth = (kos_eth_header_t*)pkt->data;
    uint16_t ethertype = ntohs(eth->type);
    
    /* Set L3 header */
    pkt->l3_header = pkt->data + sizeof(kos_eth_header_t);
    
    /* Process based on ethertype */
    switch (ethertype) {
        case 0x0800: /* IPv4 */
            return kos_ip_input(netif, pkt);
            
        case 0x0806: /* ARP */
            /* ARP not implemented, just drop */
            kos_packet_free(pkt);
            return 0;
            
        default:
            /* Unknown protocol, drop */
            kos_packet_free(pkt);
            return 0;
    }
}