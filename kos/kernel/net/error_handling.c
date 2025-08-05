/*
 * KOS Network Stack Error Handling and Edge Cases
 * Comprehensive network error recovery and validation
 */

#include "netstack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/time.h>
#include <netinet/in.h>

/* Network error types */
typedef enum {
    NET_ERROR_NONE = 0,
    NET_ERROR_INVALID_PACKET,   /* Malformed packet */
    NET_ERROR_CHECKSUM,         /* Checksum mismatch */
    NET_ERROR_BUFFER_OVERFLOW,  /* Buffer overflow */
    NET_ERROR_QUEUE_FULL,       /* Queue is full */
    NET_ERROR_INTERFACE_DOWN,   /* Interface is down */
    NET_ERROR_ROUTE_MISSING,    /* No route to destination */
    NET_ERROR_CONGESTION,       /* Network congestion */
    NET_ERROR_TIMEOUT,          /* Operation timeout */
    NET_ERROR_CONNECTION_RESET, /* Connection reset */
    NET_ERROR_PROTOCOL,         /* Protocol error */
    NET_ERROR_SECURITY,         /* Security violation */
    NET_ERROR_RESOURCE,         /* Resource exhaustion */
    NET_ERROR_FRAGMENTATION     /* Fragmentation error */
} net_error_type_t;

/* Error recovery strategies */
typedef enum {
    NET_RECOVERY_DROP = 0,      /* Drop packet/connection */
    NET_RECOVERY_RETRY,         /* Retry operation */
    NET_RECOVERY_FALLBACK,      /* Use fallback method */
    NET_RECOVERY_THROTTLE,      /* Apply rate limiting */
    NET_RECOVERY_RESET,         /* Reset connection/interface */
    NET_RECOVERY_ISOLATE        /* Isolate problematic component */
} net_recovery_t;

/* Network error context */
typedef struct {
    net_error_type_t type;
    const char *message;
    void *packet;
    size_t packet_size;
    kos_netif_t *interface;
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t src_port;
    uint16_t dst_port;
    uint8_t protocol;
    const char *file;
    int line;
    const char *function;
    uint64_t timestamp;
    net_recovery_t recovery;
    int retry_count;
} net_error_ctx_t;

/* Network error statistics */
static struct {
    uint64_t total_errors;
    uint64_t packet_errors;
    uint64_t checksum_errors;
    uint64_t buffer_overflows;
    uint64_t queue_full_errors;
    uint64_t interface_errors;
    uint64_t routing_errors;
    uint64_t congestion_errors;
    uint64_t timeout_errors;
    uint64_t protocol_errors;
    uint64_t security_errors;
    uint64_t recoveries_attempted;
    uint64_t recoveries_successful;
    uint64_t packets_dropped;
    uint64_t connections_reset;
    pthread_mutex_t lock;
} net_error_stats = { .lock = PTHREAD_MUTEX_INITIALIZER };

/* Rate limiting for error recovery */
typedef struct {
    uint64_t last_error_time;
    uint32_t error_count;
    uint32_t max_errors_per_second;
    uint32_t backoff_multiplier;
} net_rate_limiter_t;

static net_rate_limiter_t global_rate_limiter = {
    .max_errors_per_second = 100,
    .backoff_multiplier = 2
};

/* Packet validation functions */
static int validate_ethernet_packet(kos_packet_t *pkt)
{
    if (!pkt || pkt->size < sizeof(kos_eth_header_t)) {
        return 0;
    }
    
    kos_eth_header_t *eth = (kos_eth_header_t *)pkt->data;
    uint16_t eth_type = ntohs(eth->type);
    
    /* Check for valid Ethernet types */
    switch (eth_type) {
        case ETH_P_IP:
        case ETH_P_IPV6:
        case ETH_P_ARP:
        case ETH_P_VLAN:
            return 1;
        default:
            if (eth_type < 0x0600) {
                return 0; /* Invalid length/type field */
            }
            return 1; /* Unknown but potentially valid */
    }
}

static int validate_ip_packet(kos_packet_t *pkt)
{
    if (!pkt || pkt->size < sizeof(kos_ip_header_t)) {
        return 0;
    }
    
    kos_ip_header_t *iph = (kos_ip_header_t *)pkt->data;
    
    /* Check version */
    uint8_t version = (iph->version_ihl >> 4) & 0x0F;
    if (version != 4) {
        return 0;
    }
    
    /* Check header length */
    uint8_t ihl = iph->version_ihl & 0x0F;
    if (ihl < 5 || ihl > 15) {
        return 0;
    }
    
    /* Check total length */
    uint16_t total_len = ntohs(iph->total_length);
    if (total_len < (ihl * 4) || total_len > pkt->size) {
        return 0;
    }
    
    /* Validate checksum */
    uint16_t orig_checksum = iph->checksum;
    iph->checksum = 0;
    uint16_t calc_checksum = kos_ip_checksum(iph, ihl * 4);
    iph->checksum = orig_checksum;
    
    if (orig_checksum != calc_checksum) {
        return 0;
    }
    
    return 1;
}

static int validate_tcp_packet(kos_packet_t *pkt, kos_ip_header_t *iph)
{
    if (!pkt || !iph) {
        return 0;
    }
    
    uint8_t ihl = (iph->version_ihl & 0x0F) * 4;
    if (pkt->size < ihl + sizeof(kos_tcp_header_t)) {
        return 0;
    }
    
    kos_tcp_header_t *tcph = (kos_tcp_header_t *)((uint8_t *)iph + ihl);
    
    /* Check data offset */
    uint8_t doff = (tcph->data_offset >> 4) & 0x0F;
    if (doff < 5 || doff > 15) {
        return 0;
    }
    
    /* Validate ports */
    if (ntohs(tcph->src_port) == 0 || ntohs(tcph->dst_port) == 0) {
        return 0;
    }
    
    /* Validate checksum */
    uint16_t orig_checksum = tcph->checksum;
    tcph->checksum = 0;
    uint16_t calc_checksum = kos_tcp_checksum(iph, tcph, 
                                             (uint8_t *)tcph + (doff * 4),
                                             ntohs(iph->total_length) - ihl - (doff * 4));
    tcph->checksum = orig_checksum;
    
    if (orig_checksum != calc_checksum) {
        return 0;
    }
    
    return 1;
}

/* Rate limiting check */
static int check_rate_limit(net_rate_limiter_t *limiter)
{
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_us = now.tv_sec * 1000000ULL + now.tv_usec;
    
    if (now_us - limiter->last_error_time > 1000000) { /* 1 second */
        limiter->error_count = 0;
        limiter->last_error_time = now_us;
    }
    
    if (limiter->error_count >= limiter->max_errors_per_second) {
        return 0; /* Rate limited */
    }
    
    limiter->error_count++;
    return 1;
}

/* Log network error */
static void log_network_error(const net_error_ctx_t *ctx)
{
    pthread_mutex_lock(&net_error_stats.lock);
    net_error_stats.total_errors++;
    
    switch (ctx->type) {
        case NET_ERROR_INVALID_PACKET:
            net_error_stats.packet_errors++;
            break;
        case NET_ERROR_CHECKSUM:
            net_error_stats.checksum_errors++;
            break;
        case NET_ERROR_BUFFER_OVERFLOW:
            net_error_stats.buffer_overflows++;
            break;
        case NET_ERROR_QUEUE_FULL:
            net_error_stats.queue_full_errors++;
            break;
        case NET_ERROR_INTERFACE_DOWN:
            net_error_stats.interface_errors++;
            break;
        case NET_ERROR_ROUTE_MISSING:
            net_error_stats.routing_errors++;
            break;
        case NET_ERROR_CONGESTION:
            net_error_stats.congestion_errors++;
            break;
        case NET_ERROR_TIMEOUT:
            net_error_stats.timeout_errors++;
            break;
        case NET_ERROR_PROTOCOL:
            net_error_stats.protocol_errors++;
            break;
        case NET_ERROR_SECURITY:
            net_error_stats.security_errors++;
            break;
        default:
            break;
    }
    
    pthread_mutex_unlock(&net_error_stats.lock);
    
    /* Log error details */
    printf("[NET ERROR] Type: %d, Message: %s\n", ctx->type, ctx->message);
    if (ctx->interface) {
        printf("[NET ERROR] Interface: %s\n", ctx->interface->name);
    }
    if (ctx->src_ip || ctx->dst_ip) {
        printf("[NET ERROR] %u.%u.%u.%u:%u -> %u.%u.%u.%u:%u\n",
               (ctx->src_ip >> 24) & 0xFF, (ctx->src_ip >> 16) & 0xFF,
               (ctx->src_ip >> 8) & 0xFF, ctx->src_ip & 0xFF, ctx->src_port,
               (ctx->dst_ip >> 24) & 0xFF, (ctx->dst_ip >> 16) & 0xFF,
               (ctx->dst_ip >> 8) & 0xFF, ctx->dst_ip & 0xFF, ctx->dst_port);
    }
    printf("[NET ERROR] Location: %s:%d in %s()\n",
           ctx->file ? ctx->file : "unknown", ctx->line,
           ctx->function ? ctx->function : "unknown");
}

/* Handle network error with recovery */
static int handle_network_error(net_error_ctx_t *ctx)
{
    if (!check_rate_limit(&global_rate_limiter)) {
        /* Rate limited - drop silently */
        pthread_mutex_lock(&net_error_stats.lock);
        net_error_stats.packets_dropped++;
        pthread_mutex_unlock(&net_error_stats.lock);
        return -1;
    }
    
    log_network_error(ctx);
    
    pthread_mutex_lock(&net_error_stats.lock);
    net_error_stats.recoveries_attempted++;
    pthread_mutex_unlock(&net_error_stats.lock);
    
    switch (ctx->recovery) {
        case NET_RECOVERY_DROP:
            pthread_mutex_lock(&net_error_stats.lock);
            net_error_stats.packets_dropped++;
            pthread_mutex_unlock(&net_error_stats.lock);
            return -1;
            
        case NET_RECOVERY_RETRY:
            if (ctx->retry_count < 3) {
                ctx->retry_count++;
                usleep(1000 * ctx->retry_count); /* Exponential backoff */
                pthread_mutex_lock(&net_error_stats.lock);
                net_error_stats.recoveries_successful++;
                pthread_mutex_unlock(&net_error_stats.lock);
                return 0; /* Retry */
            }
            return -1; /* Give up */
            
        case NET_RECOVERY_FALLBACK:
            /* Try alternative method */
            return net_try_fallback_method(ctx);
            
        case NET_RECOVERY_THROTTLE:
            /* Apply rate limiting */
            global_rate_limiter.max_errors_per_second /= 2;
            if (global_rate_limiter.max_errors_per_second < 10) {
                global_rate_limiter.max_errors_per_second = 10;
            }
            return 0;
            
        case NET_RECOVERY_RESET:
            /* Reset connection or interface */
            if (ctx->interface) {
                return net_reset_interface(ctx->interface);
            }
            return net_reset_connection(ctx->src_ip, ctx->dst_ip, 
                                      ctx->src_port, ctx->dst_port);
            
        case NET_RECOVERY_ISOLATE:
            /* Isolate problematic component */
            return net_isolate_component(ctx);
            
        default:
            return -1;
    }
}

/* Comprehensive packet validation */
int net_validate_packet(kos_packet_t *pkt, kos_netif_t *netif, const char *context)
{
    if (!pkt) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_INVALID_PACKET,
            .message = "NULL packet",
            .packet = pkt,
            .interface = netif,
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return 0;
    }
    
    if (pkt->size == 0 || pkt->size > 65535) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_INVALID_PACKET,
            .message = "Invalid packet size",
            .packet = pkt,
            .packet_size = pkt->size,
            .interface = netif,
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return 0;
    }
    
    if (!pkt->data) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_INVALID_PACKET,
            .message = "NULL packet data",
            .packet = pkt,
            .packet_size = pkt->size,
            .interface = netif,
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return 0;
    }
    
    /* Validate based on protocol layer */
    if (pkt->l2_header) {
        if (!validate_ethernet_packet(pkt)) {
            net_error_ctx_t ctx = {
                .type = NET_ERROR_INVALID_PACKET,
                .message = "Invalid Ethernet packet",
                .packet = pkt,
                .packet_size = pkt->size,
                .interface = netif,
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .timestamp = time(NULL),
                .recovery = NET_RECOVERY_DROP
            };
            handle_network_error(&ctx);
            return 0;
        }
    }
    
    if (pkt->l3_header) {
        kos_ip_header_t *iph = (kos_ip_header_t *)pkt->l3_header;
        if (!validate_ip_packet(pkt)) {
            net_error_ctx_t ctx = {
                .type = NET_ERROR_CHECKSUM,
                .message = "Invalid IP packet",
                .packet = pkt,
                .packet_size = pkt->size,
                .interface = netif,
                .src_ip = ntohl(iph->src_addr),
                .dst_ip = ntohl(iph->dst_addr),
                .protocol = iph->protocol,
                .file = __FILE__,
                .line = __LINE__,
                .function = context,
                .timestamp = time(NULL),
                .recovery = NET_RECOVERY_DROP
            };
            handle_network_error(&ctx);
            return 0;
        }
        
        /* Validate L4 protocols */
        if (pkt->l4_header && iph->protocol == IPPROTO_TCP) {
            if (!validate_tcp_packet(pkt, iph)) {
                kos_tcp_header_t *tcph = (kos_tcp_header_t *)pkt->l4_header;
                net_error_ctx_t ctx = {
                    .type = NET_ERROR_CHECKSUM,
                    .message = "Invalid TCP packet",
                    .packet = pkt,
                    .packet_size = pkt->size,
                    .interface = netif,
                    .src_ip = ntohl(iph->src_addr),
                    .dst_ip = ntohl(iph->dst_addr),
                    .src_port = ntohs(tcph->src_port),
                    .dst_port = ntohs(tcph->dst_port),
                    .protocol = iph->protocol,
                    .file = __FILE__,
                    .line = __LINE__,
                    .function = context,
                    .timestamp = time(NULL),
                    .recovery = NET_RECOVERY_DROP
                };
                handle_network_error(&ctx);
                return 0;
            }
        }
    }
    
    return 1;
}

/* Buffer overflow protection */
int net_safe_buffer_write(void *dst, size_t dst_size, const void *src, size_t src_size, const char *context)
{
    if (!dst || !src) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_BUFFER_OVERFLOW,
            .message = "NULL buffer in write operation",
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return -1;
    }
    
    if (src_size > dst_size) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_BUFFER_OVERFLOW,
            .message = "Buffer overflow attempt",
            .packet_size = src_size,
            .file = __FILE__,
            .line = __LINE__,
            .function = context,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return -1;
    }
    
    memcpy(dst, src, src_size);
    return 0;
}

/* Connection monitoring and recovery */
int net_monitor_connection(uint32_t src_ip, uint32_t dst_ip, uint16_t src_port, uint16_t dst_port)
{
    /* Check for connection health */
    kos_socket_t *sock = find_socket(src_ip, dst_ip, src_port, dst_port);
    if (!sock) {
        return -1;
    }
    
    /* Check for timeout */
    struct timeval now;
    gettimeofday(&now, NULL);
    uint64_t now_ms = now.tv_sec * 1000ULL + now.tv_usec / 1000;
    
    if (sock->last_activity_time && 
        now_ms - sock->last_activity_time > 300000) { /* 5 minutes */
        
        net_error_ctx_t ctx = {
            .type = NET_ERROR_TIMEOUT,
            .message = "Connection timeout",
            .src_ip = src_ip,
            .dst_ip = dst_ip,
            .src_port = src_port,
            .dst_port = dst_port,
            .protocol = IPPROTO_TCP,
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_RESET
        };
        return handle_network_error(&ctx);
    }
    
    return 0;
}

/* Security validation */
int net_validate_security(kos_packet_t *pkt, kos_netif_t *netif)
{
    if (!pkt || !pkt->l3_header) {
        return 1; /* Pass through non-IP packets */
    }
    
    kos_ip_header_t *iph = (kos_ip_header_t *)pkt->l3_header;
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    
    /* Check for spoofed addresses */
    if (is_private_ip(src_ip) && netif && !is_local_interface(netif, src_ip)) {
        net_error_ctx_t ctx = {
            .type = NET_ERROR_SECURITY,
            .message = "Spoofed private IP address",
            .packet = pkt,
            .interface = netif,
            .src_ip = src_ip,
            .dst_ip = dst_ip,
            .protocol = iph->protocol,
            .file = __FILE__,
            .line = __LINE__,
            .function = __func__,
            .timestamp = time(NULL),
            .recovery = NET_RECOVERY_DROP
        };
        handle_network_error(&ctx);
        return 0;
    }
    
    /* Check for broadcast/multicast abuse */
    if (is_broadcast_ip(dst_ip) || is_multicast_ip(dst_ip)) {
        if (pkt->size > 1024) { /* Large broadcast/multicast packet */
            net_error_ctx_t ctx = {
                .type = NET_ERROR_SECURITY,
                .message = "Large broadcast/multicast packet",
                .packet = pkt,
                .packet_size = pkt->size,
                .interface = netif,
                .src_ip = src_ip,
                .dst_ip = dst_ip,
                .protocol = iph->protocol,
                .file = __FILE__,
                .line = __LINE__,
                .function = __func__,
                .timestamp = time(NULL),
                .recovery = NET_RECOVERY_THROTTLE
            };
            return handle_network_error(&ctx) == 0;
        }
    }
    
    return 1;
}

/* Get network error statistics */
void net_get_error_stats(void)
{
    pthread_mutex_lock(&net_error_stats.lock);
    
    printf("\nNetwork Error Statistics:\n");
    printf("=========================\n");
    printf("Total errors:          %lu\n", net_error_stats.total_errors);
    printf("Packet errors:         %lu\n", net_error_stats.packet_errors);
    printf("Checksum errors:       %lu\n", net_error_stats.checksum_errors);
    printf("Buffer overflows:      %lu\n", net_error_stats.buffer_overflows);
    printf("Queue full errors:     %lu\n", net_error_stats.queue_full_errors);
    printf("Interface errors:      %lu\n", net_error_stats.interface_errors);
    printf("Routing errors:        %lu\n", net_error_stats.routing_errors);
    printf("Congestion errors:     %lu\n", net_error_stats.congestion_errors);
    printf("Timeout errors:        %lu\n", net_error_stats.timeout_errors);
    printf("Protocol errors:       %lu\n", net_error_stats.protocol_errors);
    printf("Security errors:       %lu\n", net_error_stats.security_errors);
    printf("Recovery attempts:     %lu\n", net_error_stats.recoveries_attempted);
    printf("Recovery successes:    %lu\n", net_error_stats.recoveries_successful);
    printf("Packets dropped:       %lu\n", net_error_stats.packets_dropped);
    printf("Connections reset:     %lu\n", net_error_stats.connections_reset);
    
    if (net_error_stats.recoveries_attempted > 0) {
        double success_rate = (double)net_error_stats.recoveries_successful / 
                             net_error_stats.recoveries_attempted * 100.0;
        printf("Recovery success rate: %.1f%%\n", success_rate);
    }
    
    pthread_mutex_unlock(&net_error_stats.lock);
}

/* Initialize network error handling */
void net_error_init(void)
{
    printf("Network error handling initialized\n");
}