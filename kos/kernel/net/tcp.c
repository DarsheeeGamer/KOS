/*
 * KOS TCP Protocol Implementation
 * Complete TCP state machine and protocol handling
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
#include <time.h>

/* For older systems that might not have these defined */
#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC 1
#endif

/* TCP flags */
#define TCP_FIN     0x01
#define TCP_SYN     0x02
#define TCP_RST     0x04
#define TCP_PSH     0x08
#define TCP_ACK     0x10
#define TCP_URG     0x20

/* TCP options */
#define TCP_OPT_END         0
#define TCP_OPT_NOP         1
#define TCP_OPT_MSS         2
#define TCP_OPT_WINDOW      3
#define TCP_OPT_SACK_PERM   4
#define TCP_OPT_SACK        5
#define TCP_OPT_TIMESTAMP   8

/* TCP timers (in milliseconds) */
#define TCP_RTO_MIN         200
#define TCP_RTO_MAX         120000
#define TCP_RTO_INIT        3000
#define TCP_DELACK_MAX      200
#define TCP_KEEPALIVE_TIME  7200000
#define TCP_KEEPALIVE_INTVL 75000
#define TCP_KEEPALIVE_PROBES 9

/* TCP congestion control */
#define TCP_INIT_CWND       10
#define TCP_MAX_CWND        65535

/* External functions */
extern kos_socket_t* _kos_socket_find(int fd);
extern pthread_mutex_t* _kos_get_netstack_lock(void);

/* TCP control block */
typedef struct tcp_cb {
    kos_socket_t* sock;
    
    /* Sequence numbers */
    uint32_t snd_una;     /* Send unacknowledged */
    uint32_t snd_nxt;     /* Send next */
    uint32_t snd_wnd;     /* Send window */
    uint32_t snd_up;      /* Send urgent pointer */
    uint32_t snd_wl1;     /* Segment sequence number used for last window update */
    uint32_t snd_wl2;     /* Segment acknowledgment number used for last window update */
    uint32_t iss;         /* Initial send sequence number */
    
    uint32_t rcv_nxt;     /* Receive next */
    uint32_t rcv_wnd;     /* Receive window */
    uint32_t rcv_up;      /* Receive urgent pointer */
    uint32_t irs;         /* Initial receive sequence number */
    
    /* Timers */
    uint64_t rto;         /* Retransmission timeout */
    uint64_t srtt;        /* Smoothed round trip time */
    uint64_t rttvar;      /* Round trip time variance */
    uint64_t last_ack_time;
    uint64_t keepalive_time;
    
    /* Congestion control */
    uint32_t cwnd;        /* Congestion window */
    uint32_t ssthresh;    /* Slow start threshold */
    uint32_t dupacks;     /* Duplicate ACK count */
    
    /* Retransmission */
    kos_packet_t* retrans_queue;
    int retrans_count;
    
    /* Flags */
    bool delayed_ack;
    bool nagle;
    bool fast_recovery;
    
} tcp_cb_t;

/* TCP connection hash table */
#define TCP_HASH_SIZE 256
static tcp_cb_t* tcp_hash[TCP_HASH_SIZE];
static pthread_mutex_t tcp_hash_lock = PTHREAD_MUTEX_INITIALIZER;

/* Forward declarations */
static tcp_cb_t* tcp_cb_create(kos_socket_t* sock);
static void tcp_cb_destroy(tcp_cb_t* tcb);
static tcp_cb_t* tcp_cb_find(uint32_t local_ip, uint16_t local_port, 
                             uint32_t remote_ip, uint16_t remote_port);
static uint32_t tcp_hash_function(uint32_t local_ip, uint16_t local_port,
                                  uint32_t remote_ip, uint16_t remote_port);
static int tcp_send_segment(tcp_cb_t* tcb, const void* data, size_t len, uint8_t flags);
static int tcp_process_options(tcp_cb_t* tcb, kos_tcp_header_t* tcph);
static void tcp_update_window(tcp_cb_t* tcb, kos_tcp_header_t* tcph);
static void tcp_fast_retransmit(tcp_cb_t* tcb);
static void tcp_enter_recovery(tcp_cb_t* tcb);
static void tcp_exit_recovery(tcp_cb_t* tcb);
static uint32_t tcp_get_timestamp(void);

/*
 * Process incoming TCP packet
 */
int kos_tcp_input(kos_packet_t* pkt) {
    if (!pkt || !pkt->l3_header || !pkt->l4_header) {
        return -EINVAL;
    }
    
    kos_ip_header_t* iph = (kos_ip_header_t*)pkt->l3_header;
    kos_tcp_header_t* tcph = (kos_tcp_header_t*)pkt->l4_header;
    
    /* Convert from network byte order */
    uint32_t src_ip = ntohl(iph->src_addr);
    uint32_t dst_ip = ntohl(iph->dst_addr);
    uint16_t src_port = ntohs(tcph->src_port);
    uint16_t dst_port = ntohs(tcph->dst_port);
    uint32_t seq = ntohl(tcph->seq_num);
    uint32_t ack = ntohl(tcph->ack_num);
    uint16_t window __attribute__((unused)) = ntohs(tcph->window);
    uint8_t flags = tcph->flags;
    
    /* Calculate data length */
    uint16_t ip_len = ntohs(iph->total_length);
    uint8_t ip_hlen = (iph->version_ihl & 0x0F) * 4;
    uint8_t tcp_hlen = (tcph->data_offset >> 4) * 4;
    size_t data_len = ip_len - ip_hlen - tcp_hlen;
    
    /* Set data pointer */
    if (data_len > 0) {
        pkt->l7_data = (uint8_t*)tcph + tcp_hlen;
    }
    
    pthread_mutex_lock(&tcp_hash_lock);
    
    /* Find existing connection */
    tcp_cb_t* tcb = tcp_cb_find(dst_ip, dst_port, src_ip, src_port);
    
    if (!tcb) {
        /* Check for listening socket */
        tcb = tcp_cb_find(dst_ip, dst_port, 0, 0);
        if (!tcb || tcb->sock->tcp_state != KOS_TCP_LISTEN) {
            pthread_mutex_unlock(&tcp_hash_lock);
            /* Send RST */
            return -ECONNREFUSED;
        }
        
        /* Handle SYN on listening socket */
        if (flags & TCP_SYN) {
            /* Create new connection */
            kos_socket_t* new_sock = calloc(1, sizeof(kos_socket_t));
            if (!new_sock) {
                pthread_mutex_unlock(&tcp_hash_lock);
                return -ENOMEM;
            }
            
            /* Initialize new socket */
            *new_sock = *tcb->sock; /* Copy listening socket properties */
            new_sock->fd = 0; /* Will be set by accept */
            new_sock->state = KOS_SS_CONNECTING;
            new_sock->tcp_state = KOS_TCP_SYN_RCVD;
            
            /* Set addresses */
            struct sockaddr_in* local = (struct sockaddr_in*)&new_sock->local_addr;
            struct sockaddr_in* remote = (struct sockaddr_in*)&new_sock->remote_addr;
            local->sin_addr.s_addr = htonl(dst_ip);
            local->sin_port = htons(dst_port);
            remote->sin_addr.s_addr = htonl(src_ip);
            remote->sin_port = htons(src_port);
            
            /* Create new TCB */
            tcp_cb_t* new_tcb = tcp_cb_create(new_sock);
            if (!new_tcb) {
                free(new_sock);
                pthread_mutex_unlock(&tcp_hash_lock);
                return -ENOMEM;
            }
            
            /* Initialize sequence numbers */
            new_tcb->irs = seq;
            new_tcb->rcv_nxt = seq + 1;
            new_tcb->iss = rand();
            new_tcb->snd_nxt = new_tcb->iss;
            new_tcb->snd_una = new_tcb->iss;
            
            /* Send SYN-ACK */
            tcp_send_segment(new_tcb, NULL, 0, TCP_SYN | TCP_ACK);
            new_tcb->snd_nxt++;
            
            tcb = new_tcb;
        }
    }
    
    if (!tcb) {
        pthread_mutex_unlock(&tcp_hash_lock);
        return -ENOENT;
    }
    
    /* Process packet based on TCP state */
    switch (tcb->sock->tcp_state) {
        case KOS_TCP_LISTEN:
            if (flags & TCP_SYN) {
                /* Already handled above */
            }
            break;
            
        case KOS_TCP_SYN_SENT:
            if ((flags & (TCP_SYN | TCP_ACK)) == (TCP_SYN | TCP_ACK)) {
                if (ack == tcb->snd_nxt) {
                    tcb->snd_una = ack;
                    tcb->irs = seq;
                    tcb->rcv_nxt = seq + 1;
                    tcb->sock->tcp_state = KOS_TCP_ESTABLISHED;
                    tcb->sock->state = KOS_SS_CONNECTED;
                    
                    /* Send ACK */
                    tcp_send_segment(tcb, NULL, 0, TCP_ACK);
                }
            } else if (flags & TCP_SYN) {
                /* Simultaneous open */
                tcb->irs = seq;
                tcb->rcv_nxt = seq + 1;
                tcb->sock->tcp_state = KOS_TCP_SYN_RCVD;
                
                tcp_send_segment(tcb, NULL, 0, TCP_SYN | TCP_ACK);
            }
            break;
            
        case KOS_TCP_SYN_RCVD:
            if ((flags & TCP_ACK) && ack == tcb->snd_nxt) {
                tcb->snd_una = ack;
                tcb->sock->tcp_state = KOS_TCP_ESTABLISHED;
                tcb->sock->state = KOS_SS_CONNECTED;
            }
            break;
            
        case KOS_TCP_ESTABLISHED:
            /* Handle data and ACKs */
            if (flags & TCP_ACK) {
                if (ack > tcb->snd_una && ack <= tcb->snd_nxt) {
                    tcb->snd_una = ack;
                    tcp_update_window(tcb, tcph);
                    
                    /* Reset duplicate ACK counter */
                    tcb->dupacks = 0;
                    
                    /* Update congestion window */
                    if (tcb->cwnd < tcb->ssthresh) {
                        /* Slow start */
                        tcb->cwnd += tcb->sock->mss;
                    } else {
                        /* Congestion avoidance */
                        tcb->cwnd += tcb->sock->mss * tcb->sock->mss / tcb->cwnd;
                    }
                    
                    if (tcb->cwnd > TCP_MAX_CWND) {
                        tcb->cwnd = TCP_MAX_CWND;
                    }
                } else if (ack == tcb->snd_una) {
                    /* Duplicate ACK */
                    tcb->dupacks++;
                    if (tcb->dupacks == 3) {
                        tcp_fast_retransmit(tcb);
                    }
                }
            }
            
            /* Handle incoming data */
            if (data_len > 0 && seq == tcb->rcv_nxt) {
                /* Data is in sequence */
                pthread_mutex_lock(&tcb->sock->recv_buffer.lock);
                
                if (tcb->sock->recv_buffer.total_size + data_len <= 65536) {
                    /* Add to receive buffer */
                    if (!tcb->sock->recv_buffer.tail) {
                        tcb->sock->recv_buffer.head = tcb->sock->recv_buffer.tail = pkt;
                    } else {
                        tcb->sock->recv_buffer.tail->next = pkt;
                        tcb->sock->recv_buffer.tail = pkt;
                    }
                    tcb->sock->recv_buffer.count++;
                    tcb->sock->recv_buffer.total_size += data_len;
                    
                    tcb->rcv_nxt += data_len;
                    
                    /* Send ACK */
                    if (!tcb->delayed_ack || data_len > tcb->sock->mss / 2) {
                        tcp_send_segment(tcb, NULL, 0, TCP_ACK);
                    } else {
                        tcb->delayed_ack = true;
                        tcb->last_ack_time = tcp_get_timestamp();
                    }
                }
                
                pthread_mutex_unlock(&tcb->sock->recv_buffer.lock);
            }
            
            /* Handle FIN */
            if (flags & TCP_FIN) {
                tcb->rcv_nxt++;
                tcb->sock->tcp_state = KOS_TCP_CLOSE_WAIT;
                tcp_send_segment(tcb, NULL, 0, TCP_ACK);
            }
            break;
            
        case KOS_TCP_FIN_WAIT1:
            if (flags & TCP_ACK && ack == tcb->snd_nxt) {
                tcb->snd_una = ack;
                tcb->sock->tcp_state = KOS_TCP_FIN_WAIT2;
            }
            if (flags & TCP_FIN) {
                tcb->rcv_nxt++;
                if (tcb->sock->tcp_state == KOS_TCP_FIN_WAIT2) {
                    tcb->sock->tcp_state = KOS_TCP_TIME_WAIT;
                } else {
                    tcb->sock->tcp_state = KOS_TCP_CLOSING;
                }
                tcp_send_segment(tcb, NULL, 0, TCP_ACK);
            }
            break;
            
        case KOS_TCP_FIN_WAIT2:
            if (flags & TCP_FIN) {
                tcb->rcv_nxt++;
                tcb->sock->tcp_state = KOS_TCP_TIME_WAIT;
                tcp_send_segment(tcb, NULL, 0, TCP_ACK);
            }
            break;
            
        case KOS_TCP_CLOSE_WAIT:
            /* Waiting for application to close */
            break;
            
        case KOS_TCP_CLOSING:
            if (flags & TCP_ACK && ack == tcb->snd_nxt) {
                tcb->sock->tcp_state = KOS_TCP_TIME_WAIT;
            }
            break;
            
        case KOS_TCP_LAST_ACK:
            if (flags & TCP_ACK && ack == tcb->snd_nxt) {
                tcb->sock->tcp_state = KOS_TCP_CLOSED;
                tcb->sock->state = KOS_SS_CLOSED;
            }
            break;
            
        case KOS_TCP_TIME_WAIT:
            /* Just wait for timeout */
            break;
            
        default:
            break;
    }
    
    pthread_mutex_unlock(&tcp_hash_lock);
    return 0;
}

/*
 * Send TCP data
 */
int kos_tcp_output(kos_socket_t* sock, const void* data, size_t len, uint8_t flags) {
    if (!sock) {
        return -EINVAL;
    }
    
    pthread_mutex_lock(&tcp_hash_lock);
    
    /* Find TCB */
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    struct sockaddr_in* remote = (struct sockaddr_in*)&sock->remote_addr;
    
    tcp_cb_t* tcb = tcp_cb_find(ntohl(local->sin_addr.s_addr), ntohs(local->sin_port),
                                ntohl(remote->sin_addr.s_addr), ntohs(remote->sin_port));
    
    if (!tcb) {
        /* Create new TCB for outgoing connection */
        tcb = tcp_cb_create(sock);
        if (!tcb) {
            pthread_mutex_unlock(&tcp_hash_lock);
            return -ENOMEM;
        }
        
        tcb->iss = rand();
        tcb->snd_nxt = tcb->iss;
        tcb->snd_una = tcb->iss;
    }
    
    int sent = tcp_send_segment(tcb, data, len, flags);
    
    pthread_mutex_unlock(&tcp_hash_lock);
    return sent;
}

/*
 * Create TCP control block
 */
static tcp_cb_t* tcp_cb_create(kos_socket_t* sock) {
    tcp_cb_t* tcb = calloc(1, sizeof(tcp_cb_t));
    if (!tcb) {
        return NULL;
    }
    
    tcb->sock = sock;
    tcb->rto = TCP_RTO_INIT;
    tcb->cwnd = TCP_INIT_CWND * sock->mss;
    tcb->ssthresh = 65535;
    tcb->delayed_ack = false;
    tcb->nagle = !sock->no_delay;
    
    /* Add to hash table */
    struct sockaddr_in* local = (struct sockaddr_in*)&sock->local_addr;
    struct sockaddr_in* remote = (struct sockaddr_in*)&sock->remote_addr;
    
    uint32_t hash = tcp_hash_function(ntohl(local->sin_addr.s_addr), ntohs(local->sin_port),
                                      ntohl(remote->sin_addr.s_addr), ntohs(remote->sin_port));
    
    tcb->sock = sock; /* Link back to socket */
    
    /* Insert into hash chain */
    tcp_cb_t** head = &tcp_hash[hash % TCP_HASH_SIZE];
    tcb->sock->next = (kos_socket_t*)*head; /* Reuse next pointer for chaining */
    *head = tcb;
    
    return tcb;
}

/*
 * Find TCP control block
 */
static tcp_cb_t* tcp_cb_find(uint32_t local_ip, uint16_t local_port,
                             uint32_t remote_ip, uint16_t remote_port) {
    uint32_t hash = tcp_hash_function(local_ip, local_port, remote_ip, remote_port);
    tcp_cb_t* tcb = tcp_hash[hash % TCP_HASH_SIZE];
    
    while (tcb) {
        struct sockaddr_in* local = (struct sockaddr_in*)&tcb->sock->local_addr;
        struct sockaddr_in* remote = (struct sockaddr_in*)&tcb->sock->remote_addr;
        
        if (ntohl(local->sin_addr.s_addr) == local_ip &&
            ntohs(local->sin_port) == local_port &&
            (remote_ip == 0 || ntohl(remote->sin_addr.s_addr) == remote_ip) &&
            (remote_port == 0 || ntohs(remote->sin_port) == remote_port)) {
            return tcb;
        }
        
        tcb = (tcp_cb_t*)tcb->sock->next; /* Navigate chain */
    }
    
    return NULL;
}

/*
 * Hash function for TCP connections
 */
static uint32_t tcp_hash_function(uint32_t local_ip, uint16_t local_port,
                                  uint32_t remote_ip, uint16_t remote_port) {
    return (local_ip ^ remote_ip ^ local_port ^ remote_port);
}

/*
 * Send TCP segment
 */
static int tcp_send_segment(tcp_cb_t* tcb, const void* data, size_t len, uint8_t flags) {
    /* Allocate packet */
    size_t pkt_size = sizeof(kos_eth_header_t) + sizeof(kos_ip_header_t) + 
                      sizeof(kos_tcp_header_t) + len;
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
    iph->version_ihl = 0x45; /* IPv4, 20 byte header */
    iph->tos = 0;
    iph->total_length = htons(sizeof(kos_ip_header_t) + sizeof(kos_tcp_header_t) + len);
    iph->id = htons(rand());
    iph->flags_frag_offset = htons(0x4000); /* Don't fragment */
    iph->ttl = 64;
    iph->protocol = 6; /* TCP */
    iph->checksum = 0;
    
    struct sockaddr_in* local = (struct sockaddr_in*)&tcb->sock->local_addr;
    struct sockaddr_in* remote = (struct sockaddr_in*)&tcb->sock->remote_addr;
    iph->src_addr = local->sin_addr.s_addr;
    iph->dst_addr = remote->sin_addr.s_addr;
    iph->checksum = kos_ip_checksum(iph, sizeof(kos_ip_header_t));
    pkt->l3_header = iph;
    
    /* Build TCP header */
    kos_tcp_header_t* tcph = (kos_tcp_header_t*)(iph + 1);
    tcph->src_port = local->sin_port;
    tcph->dst_port = remote->sin_port;
    tcph->seq_num = htonl(tcb->snd_nxt);
    tcph->ack_num = htonl(tcb->rcv_nxt);
    tcph->data_offset = 0x50; /* 20 byte header */
    tcph->flags = flags;
    tcph->window = htons(tcb->sock->recv_window);
    tcph->checksum = 0;
    tcph->urgent_ptr = 0;
    pkt->l4_header = tcph;
    
    /* Copy data */
    if (data && len > 0) {
        memcpy(tcph + 1, data, len);
        pkt->l7_data = tcph + 1;
    }
    
    /* Calculate TCP checksum */
    tcph->checksum = kos_tcp_checksum(iph, tcph, data, len);
    
    pkt->size = pkt_size;
    
    /* Send via IP layer */
    int ret = kos_ip_output(pkt, ntohl(remote->sin_addr.s_addr), 6);
    
    /* Update sequence number for data */
    if (len > 0 || (flags & (TCP_SYN | TCP_FIN))) {
        tcb->snd_nxt += len;
        if (flags & TCP_SYN) tcb->snd_nxt++;
        if (flags & TCP_FIN) tcb->snd_nxt++;
    }
    
    return ret < 0 ? ret : (int)len;
}

/*
 * Calculate TCP checksum
 */
uint16_t kos_tcp_checksum(kos_ip_header_t* iph, kos_tcp_header_t* tcph, 
                          const void* data, size_t len) {
    /* Create pseudo header */
    struct {
        uint32_t src_addr;
        uint32_t dst_addr;
        uint8_t zero;
        uint8_t protocol;
        uint16_t tcp_length;
    } pseudo_header;
    
    pseudo_header.src_addr = iph->src_addr;
    pseudo_header.dst_addr = iph->dst_addr;
    pseudo_header.zero = 0;
    pseudo_header.protocol = 6;
    pseudo_header.tcp_length = htons(sizeof(kos_tcp_header_t) + len);
    
    /* Calculate checksum over pseudo header, TCP header, and data */
    uint32_t sum = 0;
    uint16_t* ptr;
    
    /* Pseudo header */
    ptr = (uint16_t*)&pseudo_header;
    for (int i = 0; i < sizeof(pseudo_header) / 2; i++) {
        sum += ntohs(*ptr++);
    }
    
    /* TCP header */
    uint16_t old_checksum = tcph->checksum;
    tcph->checksum = 0;
    ptr = (uint16_t*)tcph;
    for (int i = 0; i < sizeof(kos_tcp_header_t) / 2; i++) {
        sum += ntohs(*ptr++);
    }
    tcph->checksum = old_checksum;
    
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
    
    return htons(~sum);
}

/*
 * Update TCP window
 */
static void tcp_update_window(tcp_cb_t* tcb, kos_tcp_header_t* tcph) {
    uint32_t seq = ntohl(tcph->seq_num);
    uint32_t ack = ntohl(tcph->ack_num);
    uint16_t window = ntohs(tcph->window);
    
    if (seq > tcb->snd_wl1 || (seq == tcb->snd_wl1 && ack >= tcb->snd_wl2)) {
        tcb->snd_wnd = window;
        tcb->snd_wl1 = seq;
        tcb->snd_wl2 = ack;
    }
}

/*
 * Fast retransmit on triple duplicate ACK
 */
static void tcp_fast_retransmit(tcp_cb_t* tcb) {
    /* Enter fast recovery */
    tcp_enter_recovery(tcb);
    
    /* Retransmit the lost segment */
    if (tcb->retrans_queue) {
        kos_packet_t* pkt = tcb->retrans_queue;
        kos_tcp_header_t* tcph = (kos_tcp_header_t*)pkt->l4_header;
        size_t data_len = pkt->size - sizeof(kos_eth_header_t) - 
                         sizeof(kos_ip_header_t) - sizeof(kos_tcp_header_t);
        
        tcp_send_segment(tcb, pkt->l7_data, data_len, tcph->flags);
    }
}

/*
 * Enter fast recovery mode
 */
static void tcp_enter_recovery(tcp_cb_t* tcb) {
    tcb->fast_recovery = true;
    tcb->ssthresh = tcb->cwnd / 2;
    if (tcb->ssthresh < 2 * tcb->sock->mss) {
        tcb->ssthresh = 2 * tcb->sock->mss;
    }
    tcb->cwnd = tcb->ssthresh + 3 * tcb->sock->mss;
}

/*
 * Exit fast recovery mode
 */
static void tcp_exit_recovery(tcp_cb_t* tcb) {
    tcb->fast_recovery = false;
    tcb->cwnd = tcb->ssthresh;
    tcb->dupacks = 0;
}

/*
 * Get current timestamp
 */
static uint32_t tcp_get_timestamp(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}