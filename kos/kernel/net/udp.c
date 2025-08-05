/*
 * KOS UDP Protocol Implementation
 * Connectionless datagram service
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

/* UDP port management */
#define UDP_PORT_MIN        1024
#define UDP_PORT_MAX        65535
#define UDP_EPHEMERAL_MIN   32768
#define UDP_EPHEMERAL_MAX   65535

/* UDP socket hash table */
#define UDP_HASH_SIZE 256
static kos_socket_t* udp_hash[UDP_HASH_SIZE];
static pthread_mutex_t udp_hash_lock = PTHREAD_MUTEX_INITIALIZER;
static uint16_t next_ephemeral_port = UDP_EPHEMERAL_MIN;

/* External functions */
extern kos_socket_t* _kos_socket_find(int fd);
extern pthread_mutex_t* _kos_get_netstack_lock(void);

/* Forward declarations */
static uint32_t udp_hash_function(uint32_t ip, uint16_t port);
static kos_socket_t* udp_socket_find(uint32_t ip, uint16_t port);
static int udp_socket_add(kos_socket_t* sock);
static int udp_socket_remove(kos_socket_t* sock);
static uint16_t udp_allocate_port(void);
static int udp_bind_port(kos_socket_t* sock, uint16_t port);
static int udp_send_packet(kos_socket_t* sock, const void* data, size_t len,
                          uint32_t dst_ip, uint16_t dst_port);

/*
 * Process incoming UDP packet
 */
int kos_udp_input(kos_packet_t* pkt) {
    if (!pkt || !pkt->l3_header || !pkt->l4_header) {
        return -EINVAL;
    }
    
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    kos_udp_header_t* udph = (kos_udp_header_t*)pkt->l4_header;
    
    /* Convert from network byte order */
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    uint16_t src_port = ntohs(udph->src_port);
    uint16_t dst_port = ntohs(udph->dst_port);
    uint16_t udp_len = ntohs(udph->length);
    uint16_t checksum = ntohs(udph->checksum);
    
    /* Validate UDP length */
    if (udp_len < sizeof(kos_udp_header_t)) {
        return -EINVAL;
    }
    
    size_t data_len = udp_len - sizeof(kos_udp_header_t);
    
    /* Set data pointer */
    if (data_len > 0) {
        pkt->l7_data = (uint8_t*)udph + sizeof(kos_udp_header_t);
    }
    
    /* Verify checksum if present */
    if (checksum != 0) {
        uint16_t calc_checksum = kos_udp_checksum(iph, udph, pkt->l7_data, data_len);
        if (calc_checksum != checksum) {
            return -EINVAL; /* Checksum mismatch */
        }
    }
    
    pthread_mutex_lock(&udp_hash_lock);
    
    /* Find socket bound to destination port and IP */
    kos_socket_t* sock = udp_socket_find(dst_ip, dst_port);
    if (!sock) {
        /* Try wildcard address */
        sock = udp_socket_find(INADDR_ANY, dst_port);
    }
    
    if (!sock) {
        pthread_mutex_unlock(&udp_hash_lock);
        /* Port unreachable - should send ICMP error */
        return -ECONNREFUSED;
    }
    
    /* Update remote address for connected UDP sockets */
    if (sock->state == KOS_SS_CONNECTED) {
        struct sockaddr_in* remote = (struct sockaddr_in*)&sock->remote_addr;
        if (remote->sin_addr.s_addr != htonl(src_ip) ||
            remote->sin_port != htons(src_port)) {
            /* Packet from different source than connected to */
            pthread_mutex_unlock(&udp_hash_lock);
            return 0; /* Silently drop */
        }
    } else {
        /* Update remote address for unconnected socket */
        struct sockaddr_in* remote = (struct sockaddr_in*)&sock->remote_addr;
        remote->sin_family = AF_INET;
        remote->sin_addr.s_addr = htonl(src_ip);
        remote->sin_port = htons(src_port);
    }
    
    /* Add packet to receive buffer */
    pthread_mutex_lock(&sock->recv_buffer.lock);
    
    /* Check buffer space */
    if (sock->recv_buffer.total_size + pkt->size <= 65536) {
        /* Clone packet for socket buffer */
        kos_packet_t* clone = kos_packet_alloc(pkt->size);
        if (clone) {
            memcpy(clone->data, pkt->data, pkt->size);
            clone->size = pkt->size;
            clone->l2_header = clone->data + ((uint8_t*)pkt->l2_header - pkt->data);
            clone->l3_header = clone->data + ((uint8_t*)pkt->l3_header - pkt->data);
            clone->l4_header = clone->data + ((uint8_t*)pkt->l4_header - pkt->data);
            if (pkt->l7_data) {
                clone->l7_data = clone->data + ((uint8_t*)pkt->l7_data - pkt->data);
            }
            clone->timestamp = pkt->timestamp;
            clone->flags = pkt->flags;
            
            /* Add to receive buffer */
            if (!sock->recv_buffer.tail) {
                sock->recv_buffer.head = sock->recv_buffer.tail = clone;
            } else {
                sock->recv_buffer.tail->next = clone;
                sock->recv_buffer.tail = clone;
            }
            
            sock->recv_buffer.count++;
            sock->recv_buffer.total_size += clone->size;
            sock->bytes_recv += data_len;
            sock->packets_recv++;
        }
    }
    
    pthread_mutex_unlock(&sock->recv_buffer.lock);
    pthread_mutex_unlock(&udp_hash_lock);
    
    return 0;
}

/*
 * Send UDP data
 */
int kos_udp_output(kos_socket_t* sock, const void* data, size_t len) {
    if (!sock || !data || len == 0) {
        return -EINVAL;
    }
    
    if (sock->type != KOS_SOCK_DGRAM) {
        return -EINVAL;
    }
    
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    struct sockaddr_in* remote = (struct sockaddr_in*)&sock->remote_addr;
    
    uint32_t src_ip = ntohl(local->sin_addr.s_addr);
    uint32_t dst_ip = ntohl(remote->sin_addr.s_addr);
    uint16_t src_port = ntohs(local->sin_port);
    uint16_t dst_port = ntohs(remote->sin_port);
    
    /* Allocate ephemeral port if not bound */
    if (src_port == 0) {
        src_port = udp_allocate_port();
        if (src_port == 0) {
            return -EADDRNOTAVAIL;
        }
        
        /* Update socket address */
        local->sin_port = htons(src_port);
        
        /* Add to hash table */
        pthread_mutex_lock(&udp_hash_lock);
        udp_socket_add(sock);
        pthread_mutex_unlock(&udp_hash_lock);
    }
    
    /* Use default interface IP if not specified */
    if (src_ip == 0) {
        src_ip = INADDR_LOOPBACK; /* For now, use loopback */
        local->sin_addr.s_addr = htonl(src_ip);
    }
    
    int ret = udp_send_packet(sock, data, len, dst_ip, dst_port);
    
    if (ret > 0) {
        sock->bytes_sent += ret;
        sock->packets_sent++;
    }
    
    return ret;
}

/*
 * Send UDP packet
 */
static int udp_send_packet(kos_socket_t* sock, const void* data, size_t len,
                          uint32_t dst_ip, uint16_t dst_port) {
    /* Allocate packet */
    size_t pkt_size = sizeof(kos_eth_header_t) + sizeof(kos_ip_header_t) + 
                      sizeof(kos_udp_header_t) + len;
    kos_packet_t* pkt = kos_packet_alloc(pkt_size);
    if (!pkt) {
        return -ENOMEM;
    }
    
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    uint32_t src_ip = ntohl(local->sin_addr.s_addr);
    uint16_t src_port = ntohs(local->sin_port);
    
    /* Build Ethernet header */
    kos_eth_header_t* eth = (kos_eth_header_t*)pkt->data;
    memset(eth->dest, 0xFF, 6); /* Broadcast for now */
    memset(eth->src, 0x00, 6);  /* Our MAC */
    eth->type = htons(0x0800);  /* IPv4 */
    pkt->l2_header = eth;
    
    /* Build IP header */
    kos_ip_header_t* iph = (kos_ip_header_t*)(eth + 1);
    iph->version_ihl = 0x45; /* IPv4, 20 byte header */
    iph->tos = 0;
    iph->total_length = htons(sizeof(kos_ip_header_t) + sizeof(kos_udp_header_t) + len);
    iph->id = htons(rand());
    iph->flags_frag_offset = htons(0x4000); /* Don't fragment */
    iph->ttl = 64;
    iph->protocol = 17; /* UDP */
    iph->checksum = 0;
    iph->src_addr = htonl(src_ip);
    iph->dst_addr = htonl(dst_ip);
    iph->checksum = kos_ip_checksum(iph, sizeof(kos_ip_header_t));
    pkt->l3_header = iph;
    
    /* Build UDP header */
    kos_udp_header_t* udph = (kos_udp_header_t*)(iph + 1);
    udph->src_port = htons(src_port);
    udph->dst_port = htons(dst_port);
    udph->length = htons(sizeof(kos_udp_header_t) + len);
    udph->checksum = 0;
    pkt->l4_header = udph;
    
    /* Copy data */
    if (len > 0) {
        memcpy(udph + 1, data, len);
        pkt->l7_data = udph + 1;
    }
    
    /* Calculate UDP checksum */
    udph->checksum = kos_udp_checksum(iph, udph, data, len);
    
    pkt->size = pkt_size;
    
    /* Send via IP layer */
    int ret = kos_ip_output(pkt, dst_ip, 17);
    
    return ret < 0 ? ret : (int)len;
}

/*
 * Calculate UDP checksum
 */
uint16_t kos_udp_checksum(kos_ip_header_t* iph, kos_udp_header_t* udph,
                          const void* data, size_t len) {
    /* Create pseudo header */
    struct {
        uint32_t src_addr;
        uint32_t dst_addr;
        uint8_t zero;
        uint8_t protocol;
        uint16_t udp_length;
    } pseudo_header;
    
    pseudo_header.src_addr = iph->src_addr;
    pseudo_header.dst_addr = iph->dst_addr;
    pseudo_header.zero = 0;
    pseudo_header.protocol = 17;
    pseudo_header.udp_length = udph->length;
    
    /* Calculate checksum over pseudo header, UDP header, and data */
    uint32_t sum = 0;
    uint16_t* ptr;
    
    /* Pseudo header */
    ptr = (uint16_t*)&pseudo_header;
    for (int i = 0; i < sizeof(pseudo_header) / 2; i++) {
        sum += ntohs(*ptr++);
    }
    
    /* UDP header */
    uint16_t old_checksum = udph->checksum;
    udph->checksum = 0;
    ptr = (uint16_t*)udph;
    for (int i = 0; i < sizeof(kos_udp_header_t) / 2; i++) {
        sum += ntohs(*ptr++);
    }
    udph->checksum = old_checksum;
    
    /* Data */
    if (data && len > 0) {
        ptr = (uint16_t*)data;
        size_t words = len / 2;
        for (size_t i = 0; i < words; i++) {
            sum += ntohs(*ptr++);
        }
        if (len % 2) {
            sum += ((uint8_t*)data)[len - 1] << 8;
        }
    }
    
    /* Add carry */
    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }
    
    uint16_t checksum = ~sum;
    return checksum == 0 ? 0xFFFF : htons(checksum);
}

/*
 * Hash function for UDP sockets
 */
static uint32_t udp_hash_function(uint32_t ip, uint16_t port) {
    return (ip ^ port) % UDP_HASH_SIZE;
}

/*
 * Find UDP socket by IP and port
 */
static kos_socket_t* udp_socket_find(uint32_t ip, uint16_t port) {
    uint32_t hash = udp_hash_function(ip, port);
    kos_socket_t* sock = udp_hash[hash];
    
    while (sock) {
        struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
        if ((ntohl(local->sin_addr.s_addr) == ip || ip == INADDR_ANY) &&
            ntohs(local->sin_port) == port) {
            return sock;
        }
        sock = sock->next;
    }
    
    return NULL;
}

/*
 * Add UDP socket to hash table
 */
static int udp_socket_add(kos_socket_t* sock) {
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    uint32_t ip = ntohl(local->sin_addr.s_addr);
    uint16_t port = ntohs(local->sin_port);
    uint32_t hash = udp_hash_function(ip, port);
    
    sock->next = udp_hash[hash];
    udp_hash[hash] = sock;
    
    return 0;
}

/*
 * Remove UDP socket from hash table
 */
static int udp_socket_remove(kos_socket_t* sock) {
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    uint32_t ip = ntohl(local->sin_addr.s_addr);
    uint16_t port = ntohs(local->sin_port);
    uint32_t hash = udp_hash_function(ip, port);
    
    kos_socket_t** sock_ptr = &udp_hash[hash];
    while (*sock_ptr) {
        if (*sock_ptr == sock) {
            *sock_ptr = sock->next;
            return 0;
        }
        sock_ptr = &(*sock_ptr)->next;
    }
    
    return -ENOENT;
}

/*
 * Allocate ephemeral port
 */
static uint16_t udp_allocate_port(void) {
    pthread_mutex_lock(&udp_hash_lock);
    
    uint16_t start_port = next_ephemeral_port;
    uint16_t port = start_port;
    
    do {
        /* Check if port is in use */
        if (!udp_socket_find(INADDR_ANY, port)) {
            next_ephemeral_port = port + 1;
            if (next_ephemeral_port > UDP_EPHEMERAL_MAX) {
                next_ephemeral_port = UDP_EPHEMERAL_MIN;
            }
            pthread_mutex_unlock(&udp_hash_lock);
            return port;
        }
        
        port++;
        if (port > UDP_EPHEMERAL_MAX) {
            port = UDP_EPHEMERAL_MIN;
        }
    } while (port != start_port);
    
    pthread_mutex_unlock(&udp_hash_lock);
    return 0; /* No ports available */
}

/*
 * Bind UDP socket to port
 */
static int udp_bind_port(kos_socket_t* sock, uint16_t port) {
    pthread_mutex_lock(&udp_hash_lock);
    
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    uint32_t ip = ntohl(local->sin_addr.s_addr);
    
    /* Check if port is already in use */
    if (udp_socket_find(ip, port) || udp_socket_find(INADDR_ANY, port)) {
        pthread_mutex_unlock(&udp_hash_lock);
        return -EADDRINUSE;
    }
    
    /* Update socket port */
    local->sin_port = htons(port);
    
    /* Add to hash table */
    udp_socket_add(sock);
    
    pthread_mutex_unlock(&udp_hash_lock);
    return 0;
}

/*
 * UDP bind handler (called from socket layer)
 */
int kos_udp_bind(kos_socket_t* sock, const struct sockaddr* addr, socklen_t addrlen) {
    if (!sock || !addr || sock->type != KOS_SOCK_DGRAM) {
        return -EINVAL;
    }
    
    if (addr->sa_family != AF_INET) {
        return -EAFNOSUPPORT;
    }
    
    struct sockaddr_in* sin = (struct sockaddr_in*)addr;
    uint16_t port = ntohs(sin->sin_port);
    
    /* Allow binding to port 0 (ephemeral port allocation) */
    if (port == 0) {
        port = udp_allocate_port();
        if (port == 0) {
            return -EADDRNOTAVAIL;
        }
    }
    
    return udp_bind_port(sock, port);
}

/*
 * UDP close handler (called from socket layer)
 */
int kos_udp_close(kos_socket_t* sock) {
    if (!sock || sock->type != KOS_SOCK_DGRAM) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&udp_hash_lock);
    udp_socket_remove(sock);
    pthread_mutex_unlock(&udp_hash_lock);
    
    return 0;
}

/*
 * Get UDP statistics
 */
void kos_udp_stats(void) {
    pthread_mutex_lock(&udp_hash_lock);
    
    int socket_count = 0;
    uint64_t total_rx_packets = 0;
    uint64_t total_tx_packets = 0;
    uint64_t total_rx_bytes = 0;
    uint64_t total_tx_bytes = 0;
    
    for (int i = 0; i < UDP_HASH_SIZE; i++) {
        kos_socket_t* sock = udp_hash[i];
        while (sock) {
            socket_count++;
            total_rx_packets += sock->packets_recv;
            total_tx_packets += sock->packets_sent;
            total_rx_bytes += sock->bytes_recv;
            total_tx_bytes += sock->bytes_sent;
            sock = sock->next;
        }
    }
    
    printf("UDP Statistics:\n");
    printf("  Active sockets: %d\n", socket_count);
    printf("  RX packets: %lu\n", total_rx_packets);
    printf("  TX packets: %lu\n", total_tx_packets);
    printf("  RX bytes: %lu\n", total_rx_bytes);
    printf("  TX bytes: %lu\n", total_tx_bytes);
    
    pthread_mutex_unlock(&udp_hash_lock);
}