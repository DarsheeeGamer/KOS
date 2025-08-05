/*
 * KOS Network Stack Header
 * Complete TCP/IP implementation
 */

#ifndef KOS_NETSTACK_H
#define KOS_NETSTACK_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <sys/types.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <time.h>

/* Socket types */
#define KOS_SOCK_STREAM     1   /* TCP */
#define KOS_SOCK_DGRAM      2   /* UDP */
#define KOS_SOCK_RAW        3   /* Raw packets */
#define KOS_SOCK_SEQPACKET  4   /* Sequenced packets */

/* Socket domains */
#define KOS_AF_UNSPEC       0
#define KOS_AF_INET         2   /* IPv4 */
#define KOS_AF_INET6        10  /* IPv6 */
#define KOS_AF_PACKET       17  /* Packet socket */
#define KOS_AF_NETLINK      16  /* Netlink */

/* Socket options */
#define KOS_SOL_SOCKET      1
#define KOS_SO_REUSEADDR    2
#define KOS_SO_KEEPALIVE    9
#define KOS_SO_LINGER       13
#define KOS_SO_RCVBUF       8
#define KOS_SO_SNDBUF       7
#define KOS_SO_RCVTIMEO     20
#define KOS_SO_SNDTIMEO     21

/* TCP options */
#define KOS_IPPROTO_TCP     6
#define KOS_TCP_NODELAY     1
#define KOS_TCP_MAXSEG      2
#define KOS_TCP_KEEPIDLE    4
#define KOS_TCP_KEEPINTVL   5
#define KOS_TCP_KEEPCNT     6

/* Socket states */
typedef enum {
    KOS_SS_UNCONNECTED = 0,
    KOS_SS_CONNECTING,
    KOS_SS_CONNECTED,
    KOS_SS_DISCONNECTING,
    KOS_SS_LISTENING,
    KOS_SS_CLOSED
} kos_socket_state_t;

/* TCP states */
typedef enum {
    KOS_TCP_CLOSED = 0,
    KOS_TCP_LISTEN,
    KOS_TCP_SYN_SENT,
    KOS_TCP_SYN_RCVD,
    KOS_TCP_ESTABLISHED,
    KOS_TCP_FIN_WAIT1,
    KOS_TCP_FIN_WAIT2,
    KOS_TCP_CLOSE_WAIT,
    KOS_TCP_CLOSING,
    KOS_TCP_LAST_ACK,
    KOS_TCP_TIME_WAIT
} kos_tcp_state_t;

/* Packet buffer */
typedef struct kos_packet {
    uint8_t* data;
    size_t size;
    size_t capacity;
    struct kos_packet* next;
    
    /* Metadata */
    uint32_t flags;
    uint64_t timestamp;
    int interface_idx;
    
    /* Protocol headers */
    void* l2_header;  /* Ethernet */
    void* l3_header;  /* IP */
    void* l4_header;  /* TCP/UDP */
    void* l7_data;    /* Application data */
} kos_packet_t;

/* Socket buffer */
typedef struct kos_skbuff {
    kos_packet_t* head;
    kos_packet_t* tail;
    size_t count;
    size_t total_size;
    pthread_mutex_t lock;
} kos_skbuff_t;

/* Socket structure */
typedef struct kos_socket {
    int fd;
    int domain;
    int type;
    int protocol;
    kos_socket_state_t state;
    
    /* Addresses */
    struct sockaddr_storage local_addr;
    struct sockaddr_storage remote_addr;
    socklen_t addr_len;
    
    /* Buffers */
    kos_skbuff_t recv_buffer;
    kos_skbuff_t send_buffer;
    
    /* Options */
    int backlog;
    bool reuse_addr;
    bool keep_alive;
    bool no_delay;
    struct timeval recv_timeout;
    struct timeval send_timeout;
    
    /* TCP specific */
    kos_tcp_state_t tcp_state;
    uint32_t send_seq;
    uint32_t recv_seq;
    uint32_t send_ack;
    uint32_t recv_ack;
    uint16_t send_window;
    uint16_t recv_window;
    uint32_t mss;
    
    /* Statistics */
    uint64_t bytes_sent;
    uint64_t bytes_recv;
    uint64_t packets_sent;
    uint64_t packets_recv;
    
    struct kos_socket* next;
} kos_socket_t;

/* Network interface */
typedef struct kos_netif {
    char name[16];
    int index;
    uint32_t flags;
    uint8_t hw_addr[6];
    uint32_t ip_addr;
    uint32_t netmask;
    uint32_t broadcast;
    uint16_t mtu;
    
    /* Statistics */
    uint64_t rx_packets;
    uint64_t tx_packets;
    uint64_t rx_bytes;
    uint64_t tx_bytes;
    uint64_t rx_errors;
    uint64_t tx_errors;
    uint64_t rx_dropped;
    uint64_t tx_dropped;
    
    /* Device operations */
    int (*send)(struct kos_netif* netif, kos_packet_t* pkt);
    int (*recv)(struct kos_netif* netif, kos_packet_t* pkt);
    int (*ioctl)(struct kos_netif* netif, int cmd, void* arg);
    
    struct kos_netif* next;
} kos_netif_t;

/* Routing table entry */
typedef struct kos_route {
    uint32_t dest;
    uint32_t gateway;
    uint32_t genmask;
    uint32_t flags;
    int metric;
    int ref;
    int use;
    kos_netif_t* interface;
    struct kos_route* next;
} kos_route_t;

/* ARP cache entry */
typedef struct kos_arp_entry {
    uint32_t ip_addr;
    uint8_t hw_addr[6];
    uint64_t timestamp;
    uint16_t flags;
    struct kos_arp_entry* next;
} kos_arp_entry_t;

/* Connection tracking */
typedef struct kos_conntrack {
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t src_port;
    uint16_t dst_port;
    uint8_t protocol;
    uint8_t state;
    uint64_t timestamp;
    uint64_t packets;
    uint64_t bytes;
    struct kos_conntrack* next;
} kos_conntrack_t;

/* Ethernet header */
typedef struct kos_eth_header {
    uint8_t dest[6];
    uint8_t src[6];
    uint16_t type;
} __attribute__((packed)) kos_eth_header_t;

/* IP header */
typedef struct kos_ip_header {
    uint8_t version_ihl;
    uint8_t tos;
    uint16_t total_length;
    uint16_t id;
    uint16_t flags_frag_offset;
    uint8_t ttl;
    uint8_t protocol;
    uint16_t checksum;
    uint32_t src_addr;
    uint32_t dst_addr;
} __attribute__((packed)) kos_ip_header_t;

/* TCP header */
typedef struct kos_tcp_header {
    uint16_t src_port;
    uint16_t dst_port;
    uint32_t seq_num;
    uint32_t ack_num;
    uint8_t data_offset;
    uint8_t flags;
    uint16_t window;
    uint16_t checksum;
    uint16_t urgent_ptr;
} __attribute__((packed)) kos_tcp_header_t;

/* UDP header */
typedef struct kos_udp_header {
    uint16_t src_port;
    uint16_t dst_port;
    uint16_t length;
    uint16_t checksum;
} __attribute__((packed)) kos_udp_header_t;

/* Netfilter hooks */
typedef enum {
    KOS_NF_PRE_ROUTING = 0,
    KOS_NF_LOCAL_IN,
    KOS_NF_FORWARD,
    KOS_NF_LOCAL_OUT,
    KOS_NF_POST_ROUTING,
    KOS_NF_MAX_HOOKS
} kos_nf_hook_t;

/* Netfilter verdict */
typedef enum {
    KOS_NF_DROP = 0,
    KOS_NF_ACCEPT,
    KOS_NF_STOLEN,
    KOS_NF_QUEUE,
    KOS_NF_REPEAT
} kos_nf_verdict_t;

/* Netfilter hook function */
typedef kos_nf_verdict_t (*kos_nf_hook_fn)(kos_packet_t* pkt, kos_netif_t* in,
                                           kos_netif_t* out, void* priv);

/* Netfilter hook entry */
typedef struct kos_nf_hook_entry {
    kos_nf_hook_fn hook;
    void* priv;
    int priority;
    struct kos_nf_hook_entry* next;
} kos_nf_hook_entry_t;

/* Network stack initialization */
int kos_netstack_init(void);
void kos_netstack_shutdown(void);

/* Socket operations */
int kos_socket(int domain, int type, int protocol);
int kos_bind(int sockfd, const struct sockaddr* addr, socklen_t addrlen);
int kos_listen(int sockfd, int backlog);
int kos_accept(int sockfd, struct sockaddr* addr, socklen_t* addrlen);
int kos_connect(int sockfd, const struct sockaddr* addr, socklen_t addrlen);
ssize_t kos_send(int sockfd, const void* buf, size_t len, int flags);
ssize_t kos_recv(int sockfd, void* buf, size_t len, int flags);
ssize_t kos_sendto(int sockfd, const void* buf, size_t len, int flags,
                   const struct sockaddr* dest_addr, socklen_t addrlen);
ssize_t kos_recvfrom(int sockfd, void* buf, size_t len, int flags,
                     struct sockaddr* src_addr, socklen_t* addrlen);
int kos_setsockopt(int sockfd, int level, int optname, const void* optval, socklen_t optlen);
int kos_getsockopt(int sockfd, int level, int optname, void* optval, socklen_t* optlen);
int kos_shutdown(int sockfd, int how);
int kos_close_socket(int sockfd);

/* Network interface operations */
kos_netif_t* kos_netif_create(const char* name);
int kos_netif_destroy(kos_netif_t* netif);
kos_netif_t* kos_netif_find(const char* name);
kos_netif_t* kos_netif_find_by_index(int index);
int kos_netif_up(kos_netif_t* netif);
int kos_netif_down(kos_netif_t* netif);
int kos_netif_set_addr(kos_netif_t* netif, uint32_t addr, uint32_t netmask);
int kos_netif_set_hw_addr(kos_netif_t* netif, const uint8_t* hw_addr);

/* Packet operations */
kos_packet_t* kos_packet_alloc(size_t size);
void kos_packet_free(kos_packet_t* pkt);
int kos_packet_put(kos_packet_t* pkt, const void* data, size_t len);
int kos_packet_push(kos_packet_t* pkt, size_t len);
int kos_packet_pull(kos_packet_t* pkt, size_t len);

/* Protocol handlers */
int kos_eth_input(kos_netif_t* netif, kos_packet_t* pkt);
int kos_eth_output(kos_netif_t* netif, kos_packet_t* pkt, const uint8_t* dest);
int kos_ip_input(kos_netif_t* netif, kos_packet_t* pkt);
int kos_ip_output(kos_packet_t* pkt, uint32_t dest, uint8_t protocol);
int kos_tcp_input(kos_packet_t* pkt);
int kos_tcp_output(kos_socket_t* sock, const void* data, size_t len, uint8_t flags);
int kos_udp_input(kos_packet_t* pkt);
int kos_udp_output(kos_socket_t* sock, const void* data, size_t len);

/* Routing */
int kos_route_add(uint32_t dest, uint32_t gateway, uint32_t genmask, kos_netif_t* netif);
int kos_route_del(uint32_t dest, uint32_t genmask);
kos_route_t* kos_route_lookup(uint32_t dest);
void kos_route_dump(void);

/* ARP */
int kos_arp_request(kos_netif_t* netif, uint32_t ip_addr);
int kos_arp_reply(kos_netif_t* netif, kos_packet_t* pkt);
int kos_arp_input(kos_netif_t* netif, kos_packet_t* pkt);
kos_arp_entry_t* kos_arp_lookup(uint32_t ip_addr);
int kos_arp_add(uint32_t ip_addr, const uint8_t* hw_addr);

/* Connection tracking */
kos_conntrack_t* kos_conntrack_find(uint32_t src_ip, uint32_t dst_ip,
                                    uint16_t src_port, uint16_t dst_port,
                                    uint8_t protocol);
int kos_conntrack_add(kos_packet_t* pkt);
int kos_conntrack_update(kos_packet_t* pkt);
void kos_conntrack_cleanup(void);

/* Netfilter */
int kos_nf_register_hook(kos_nf_hook_t hook, kos_nf_hook_fn fn, void* priv, int priority);
int kos_nf_unregister_hook(kos_nf_hook_t hook, kos_nf_hook_fn fn);
kos_nf_verdict_t kos_nf_hook_slow(kos_nf_hook_t hook, kos_packet_t* pkt,
                                  kos_netif_t* in, kos_netif_t* out);

/* Utilities */
uint16_t kos_ip_checksum(const void* data, size_t len);
uint16_t kos_tcp_checksum(kos_ip_header_t* iph, kos_tcp_header_t* tcph, const void* data, size_t len);
uint16_t kos_udp_checksum(kos_ip_header_t* iph, kos_udp_header_t* udph, const void* data, size_t len);
void kos_net_hton(void* data, size_t len);
void kos_net_ntoh(void* data, size_t len);

/* Statistics */
void kos_netstat_dump(void);
void kos_socket_dump(void);
void kos_netif_dump(void);
void kos_ip_stats(void);
void kos_udp_stats(void);

/* Additional protocol-specific functions */
int kos_udp_bind(kos_socket_t* sock, const struct sockaddr* addr, socklen_t addrlen);
int kos_udp_close(kos_socket_t* sock);

/* Missing standard network interface flags */
#ifndef IFF_UP
#define IFF_UP          0x1
#define IFF_BROADCAST   0x2
#define IFF_LOOPBACK    0x8
#define IFF_RUNNING     0x40
#endif

#ifdef __cplusplus
}
#endif

#endif /* KOS_NETSTACK_H */