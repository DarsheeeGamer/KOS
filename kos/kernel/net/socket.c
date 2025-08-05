/*
 * KOS Socket Layer Implementation
 * Socket system calls and socket management
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

/* External functions from netstack.c */
extern kos_socket_t* _kos_socket_find(int fd);
extern int _kos_socket_add(kos_socket_t* sock);
extern int _kos_socket_remove(kos_socket_t* sock);
extern int _kos_get_next_socket_fd(void);
extern pthread_mutex_t* _kos_get_netstack_lock(void);

/* Forward declarations */
static int socket_init_buffers(kos_socket_t* sock);
static void socket_cleanup_buffers(kos_socket_t* sock);
static int socket_can_send(kos_socket_t* sock);
static int socket_can_recv(kos_socket_t* sock);

/*
 * Create a socket
 */
int kos_socket(int domain, int type, int protocol) {
    /* Validate parameters */
    if (domain != KOS_AF_INET && domain != KOS_AF_INET6) {
        return -EAFNOSUPPORT;
    }
    
    if (type != KOS_SOCK_STREAM && type != KOS_SOCK_DGRAM && type != KOS_SOCK_RAW) {
        return -EPROTONOSUPPORT;
    }
    
    /* Allocate socket structure */
    kos_socket_t* sock = calloc(1, sizeof(kos_socket_t));
    if (!sock) {
        return -ENOMEM;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    /* Initialize socket */
    sock->fd = _kos_get_next_socket_fd();
    sock->domain = domain;
    sock->type = type;
    sock->protocol = protocol;
    sock->state = KOS_SS_UNCONNECTED;
    sock->tcp_state = KOS_TCP_CLOSED;
    
    /* Initialize addresses */
    memset(&sock->local_addr, 0, sizeof(sock->local_addr));
    memset(&sock->remote_addr, 0, sizeof(sock->remote_addr));
    sock->addr_len = 0;
    
    /* Initialize buffers */
    if (socket_init_buffers(sock) != 0) {
        free(sock);
        pthread_mutex_unlock(netstack_lock);
        return -ENOMEM;
    }
    
    /* Set default options */
    sock->backlog = 128;
    sock->reuse_addr = false;
    sock->keep_alive = false;
    sock->no_delay = false;
    sock->recv_timeout.tv_sec = 0;
    sock->recv_timeout.tv_usec = 0;
    sock->send_timeout.tv_sec = 0;
    sock->send_timeout.tv_usec = 0;
    
    /* Initialize TCP specific fields */
    if (type == KOS_SOCK_STREAM) {
        sock->send_seq = rand();
        sock->recv_seq = 0;
        sock->send_ack = 0;
        sock->recv_ack = 0;
        sock->send_window = 65535;
        sock->recv_window = 65535;
        sock->mss = 1460; /* Standard MSS for Ethernet */
    }
    
    /* Initialize statistics */
    sock->bytes_sent = 0;
    sock->bytes_recv = 0;
    sock->packets_sent = 0;
    sock->packets_recv = 0;
    
    /* Add to socket list */
    _kos_socket_add(sock);
    
    int fd = sock->fd;
    pthread_mutex_unlock(netstack_lock);
    
    return fd;
}

/*
 * Bind socket to address
 */
int kos_bind(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    if (!addr) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->state != KOS_SS_UNCONNECTED) {
        pthread_mutex_unlock(netstack_lock);
        return -EINVAL;
    }
    
    /* Check if address is already in use */
    if (!sock->reuse_addr) {
        kos_socket_t* other = _kos_socket_find(1000); /* Start from first socket */
        while (other) {
            if (other != sock && other->state != KOS_SS_CLOSED) {
                if (addr->sa_family == AF_INET) {
                    struct sockaddr_in* sin1 = (struct sockaddr_in*)addr;
                    struct sockaddr_in* sin2 = (struct sockaddr_in*)&other->local_addr;
                    if (sin1->sin_port == sin2->sin_port &&
                        (sin1->sin_addr.s_addr == INADDR_ANY ||
                         sin2->sin_addr.s_addr == INADDR_ANY ||
                         sin1->sin_addr.s_addr == sin2->sin_addr.s_addr)) {
                        pthread_mutex_unlock(netstack_lock);
                        return -EADDRINUSE;
                    }
                }
            }
            other = other->next;
        }
    }
    
    /* Copy address */
    memcpy(&sock->local_addr, addr, addrlen);
    sock->addr_len = addrlen;
    
    pthread_mutex_unlock(netstack_lock);
    return 0;
}

/*
 * Listen for connections
 */
int kos_listen(int sockfd, int backlog) {
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->type != KOS_SOCK_STREAM) {
        pthread_mutex_unlock(netstack_lock);
        return -EOPNOTSUPP;
    }
    
    if (sock->state != KOS_SS_UNCONNECTED) {
        pthread_mutex_unlock(netstack_lock);
        return -EINVAL;
    }
    
    /* Set listening state */
    sock->state = KOS_SS_LISTENING;
    sock->tcp_state = KOS_TCP_LISTEN;
    sock->backlog = backlog > 0 ? backlog : 128;
    
    pthread_mutex_unlock(netstack_lock);
    return 0;
}

/*
 * Accept a connection
 */
int kos_accept(int sockfd, struct sockaddr* addr, socklen_t* addrlen) {
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* listen_sock = _kos_socket_find(sockfd);
    if (!listen_sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (listen_sock->state != KOS_SS_LISTENING) {
        pthread_mutex_unlock(netstack_lock);
        return -EINVAL;
    }
    
    /* For now, simulate accepting a connection */
    /* In a real implementation, this would wait for incoming connections */
    
    /* Create new socket for accepted connection */
    kos_socket_t* new_sock = calloc(1, sizeof(kos_socket_t));
    if (!new_sock) {
        pthread_mutex_unlock(netstack_lock);
        return -ENOMEM;
    }
    
    /* Copy properties from listening socket */
    new_sock->fd = _kos_get_next_socket_fd();
    new_sock->domain = listen_sock->domain;
    new_sock->type = listen_sock->type;
    new_sock->protocol = listen_sock->protocol;
    new_sock->state = KOS_SS_CONNECTED;
    new_sock->tcp_state = KOS_TCP_ESTABLISHED;
    
    /* Initialize buffers */
    if (socket_init_buffers(new_sock) != 0) {
        free(new_sock);
        pthread_mutex_unlock(netstack_lock);
        return -ENOMEM;
    }
    
    /* Copy local address */
    memcpy(&new_sock->local_addr, &listen_sock->local_addr, listen_sock->addr_len);
    new_sock->addr_len = listen_sock->addr_len;
    
    /* Set remote address (simulated) */
    if (addr && addrlen) {
        memcpy(&new_sock->remote_addr, addr, *addrlen);
        memcpy(addr, &new_sock->remote_addr, *addrlen);
    }
    
    /* Initialize TCP sequence numbers */
    new_sock->send_seq = rand();
    new_sock->recv_seq = rand();
    new_sock->send_ack = new_sock->recv_seq + 1;
    new_sock->recv_ack = new_sock->send_seq + 1;
    new_sock->send_window = 65535;
    new_sock->recv_window = 65535;
    new_sock->mss = 1460;
    
    /* Add to socket list */
    _kos_socket_add(new_sock);
    
    int new_fd = new_sock->fd;
    pthread_mutex_unlock(netstack_lock);
    
    return new_fd;
}

/*
 * Connect to remote address
 */
int kos_connect(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    if (!addr) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->state != KOS_SS_UNCONNECTED) {
        pthread_mutex_unlock(netstack_lock);
        return -EISCONN;
    }
    
    /* Copy remote address */
    memcpy(&sock->remote_addr, addr, addrlen);
    
    if (sock->type == KOS_SOCK_STREAM) {
        /* TCP connection */
        sock->state = KOS_SS_CONNECTING;
        sock->tcp_state = KOS_TCP_SYN_SENT;
        
        /* Send SYN packet */
        /* In a real implementation, this would send a TCP SYN */
        
        /* For simulation, immediately establish connection */
        sock->state = KOS_SS_CONNECTED;
        sock->tcp_state = KOS_TCP_ESTABLISHED;
        
        /* Initialize TCP sequence numbers */
        sock->recv_seq = rand();
        sock->send_ack = sock->recv_seq + 1;
        sock->recv_ack = sock->send_seq + 1;
        
    } else if (sock->type == KOS_SOCK_DGRAM) {
        /* UDP "connection" - just store remote address */
        sock->state = KOS_SS_CONNECTED;
    }
    
    pthread_mutex_unlock(netstack_lock);
    return 0;
}

/*
 * Send data
 */
ssize_t kos_send(int sockfd, const void* buf, size_t len, int flags __attribute__((unused))) {
    if (!buf || len == 0) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->state != KOS_SS_CONNECTED) {
        pthread_mutex_unlock(netstack_lock);
        return -ENOTCONN;
    }
    
    /* Check if socket can send */
    if (!socket_can_send(sock)) {
        pthread_mutex_unlock(netstack_lock);
        return -EAGAIN;
    }
    
    ssize_t sent = 0;
    
    if (sock->type == KOS_SOCK_STREAM) {
        /* TCP send */
        sent = kos_tcp_output(sock, buf, len, 0);
    } else if (sock->type == KOS_SOCK_DGRAM) {
        /* UDP send */
        sent = kos_udp_output(sock, buf, len);
    }
    
    if (sent > 0) {
        sock->bytes_sent += sent;
        sock->packets_sent++;
    }
    
    pthread_mutex_unlock(netstack_lock);
    return sent;
}

/*
 * Receive data
 */
ssize_t kos_recv(int sockfd, void* buf, size_t len, int flags __attribute__((unused))) {
    if (!buf || len == 0) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->state != KOS_SS_CONNECTED && sock->state != KOS_SS_LISTENING) {
        pthread_mutex_unlock(netstack_lock);
        return -ENOTCONN;
    }
    
    /* Check if socket has data */
    if (!socket_can_recv(sock)) {
        pthread_mutex_unlock(netstack_lock);
        return -EAGAIN;
    }
    
    ssize_t received = 0;
    
    /* Get data from receive buffer */
    pthread_mutex_lock(&sock->recv_buffer.lock);
    
    kos_packet_t* pkt = sock->recv_buffer.head;
    if (pkt && pkt->l7_data) {
        size_t available = pkt->size - ((uint8_t*)pkt->l7_data - pkt->data);
        size_t to_copy = len < available ? len : available;
        
        memcpy(buf, pkt->l7_data, to_copy);
        received = to_copy;
        
        /* Update packet */
        if (to_copy == available) {
            /* Remove packet from buffer */
            sock->recv_buffer.head = pkt->next;
            if (!sock->recv_buffer.head) {
                sock->recv_buffer.tail = NULL;
            }
            sock->recv_buffer.count--;
            sock->recv_buffer.total_size -= pkt->size;
            kos_packet_free(pkt);
        } else {
            /* Partial read - advance data pointer */
            pkt->l7_data = (uint8_t*)pkt->l7_data + to_copy;
        }
        
        sock->bytes_recv += received;
        sock->packets_recv++;
    }
    
    pthread_mutex_unlock(&sock->recv_buffer.lock);
    pthread_mutex_unlock(netstack_lock);
    
    return received;
}

/*
 * Send to specific address
 */
ssize_t kos_sendto(int sockfd, const void* buf, size_t len, int flags,
                   const struct sockaddr* dest_addr, socklen_t addrlen) {
    if (!buf || len == 0) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    /* For UDP, temporarily set destination */
    struct sockaddr_storage old_remote;
    bool restore_remote = false;
    
    if (dest_addr && sock->type == KOS_SOCK_DGRAM) {
        memcpy(&old_remote, &sock->remote_addr, sizeof(old_remote));
        memcpy(&sock->remote_addr, dest_addr, addrlen);
        restore_remote = true;
    }
    
    ssize_t sent = kos_send(sockfd, buf, len, flags);
    
    /* Restore original remote address */
    if (restore_remote) {
        memcpy(&sock->remote_addr, &old_remote, sizeof(old_remote));
    }
    
    pthread_mutex_unlock(netstack_lock);
    return sent;
}

/*
 * Receive from specific address
 */
ssize_t kos_recvfrom(int sockfd, void* buf, size_t len, int flags,
                     struct sockaddr* src_addr, socklen_t* addrlen) {
    ssize_t received = kos_recv(sockfd, buf, len, flags);
    
    if (received > 0 && src_addr && addrlen) {
        pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
        pthread_mutex_lock(netstack_lock);
        
        kos_socket_t* sock = _kos_socket_find(sockfd);
        if (sock) {
            socklen_t copy_len = *addrlen < sizeof(sock->remote_addr) ? 
                                *addrlen : sizeof(sock->remote_addr);
            memcpy(src_addr, &sock->remote_addr, copy_len);
            *addrlen = copy_len;
        }
        
        pthread_mutex_unlock(netstack_lock);
    }
    
    return received;
}

/*
 * Set socket option
 */
int kos_setsockopt(int sockfd, int level, int optname, const void* optval, socklen_t optlen) {
    if (!optval) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    int ret = 0;
    
    if (level == KOS_SOL_SOCKET) {
        switch (optname) {
            case KOS_SO_REUSEADDR:
                if (optlen >= sizeof(int)) {
                    sock->reuse_addr = *(int*)optval != 0;
                } else {
                    ret = -EINVAL;
                }
                break;
                
            case KOS_SO_KEEPALIVE:
                if (optlen >= sizeof(int)) {
                    sock->keep_alive = *(int*)optval != 0;
                } else {
                    ret = -EINVAL;
                }
                break;
                
            case KOS_SO_RCVTIMEO:
                if (optlen >= sizeof(struct timeval)) {
                    sock->recv_timeout = *(struct timeval*)optval;
                } else {
                    ret = -EINVAL;
                }
                break;
                
            case KOS_SO_SNDTIMEO:
                if (optlen >= sizeof(struct timeval)) {
                    sock->send_timeout = *(struct timeval*)optval;
                } else {
                    ret = -EINVAL;
                }
                break;
                
            default:
                ret = -ENOPROTOOPT;
                break;
        }
    } else if (level == KOS_IPPROTO_TCP) {
        switch (optname) {
            case KOS_TCP_NODELAY:
                if (optlen >= sizeof(int)) {
                    sock->no_delay = *(int*)optval != 0;
                } else {
                    ret = -EINVAL;
                }
                break;
                
            default:
                ret = -ENOPROTOOPT;
                break;
        }
    } else {
        ret = -ENOPROTOOPT;
    }
    
    pthread_mutex_unlock(netstack_lock);
    return ret;
}

/*
 * Get socket option
 */
int kos_getsockopt(int sockfd, int level, int optname, void* optval, socklen_t* optlen) {
    if (!optval || !optlen) {
        return -EINVAL;
    }
    
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    int ret = 0;
    
    if (level == KOS_SOL_SOCKET) {
        switch (optname) {
            case KOS_SO_REUSEADDR:
                if (*optlen >= sizeof(int)) {
                    *(int*)optval = sock->reuse_addr ? 1 : 0;
                    *optlen = sizeof(int);
                } else {
                    ret = -EINVAL;
                }
                break;
                
            case KOS_SO_KEEPALIVE:
                if (*optlen >= sizeof(int)) {
                    *(int*)optval = sock->keep_alive ? 1 : 0;
                    *optlen = sizeof(int);
                } else {
                    ret = -EINVAL;
                }
                break;
                
            default:
                ret = -ENOPROTOOPT;
                break;
        }
    } else {
        ret = -ENOPROTOOPT;
    }
    
    pthread_mutex_unlock(netstack_lock);
    return ret;
}

/*
 * Shutdown socket
 */
int kos_shutdown(int sockfd, int how __attribute__((unused))) {
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    if (sock->type == KOS_SOCK_STREAM && sock->tcp_state == KOS_TCP_ESTABLISHED) {
        /* Initiate TCP close */
        sock->tcp_state = KOS_TCP_FIN_WAIT1;
        sock->state = KOS_SS_DISCONNECTING;
        
        /* Send FIN packet */
        kos_tcp_output(sock, NULL, 0, 0x01); /* FIN flag */
    }
    
    pthread_mutex_unlock(netstack_lock);
    return 0;
}

/*
 * Close socket
 */
int kos_close_socket(int sockfd) {
    pthread_mutex_t* netstack_lock = _kos_get_netstack_lock();
    pthread_mutex_lock(netstack_lock);
    
    kos_socket_t* sock = _kos_socket_find(sockfd);
    if (!sock) {
        pthread_mutex_unlock(netstack_lock);
        return -EBADF;
    }
    
    /* Remove from socket list */
    _kos_socket_remove(sock);
    
    /* Cleanup buffers */
    socket_cleanup_buffers(sock);
    
    /* Free socket */
    free(sock);
    
    pthread_mutex_unlock(netstack_lock);
    return 0;
}

/*
 * Initialize socket buffers
 */
static int socket_init_buffers(kos_socket_t* sock) {
    /* Initialize receive buffer */
    sock->recv_buffer.head = NULL;
    sock->recv_buffer.tail = NULL;
    sock->recv_buffer.count = 0;
    sock->recv_buffer.total_size = 0;
    if (pthread_mutex_init(&sock->recv_buffer.lock, NULL) != 0) {
        return -ENOMEM;
    }
    
    /* Initialize send buffer */
    sock->send_buffer.head = NULL;
    sock->send_buffer.tail = NULL;
    sock->send_buffer.count = 0;
    sock->send_buffer.total_size = 0;
    if (pthread_mutex_init(&sock->send_buffer.lock, NULL) != 0) {
        pthread_mutex_destroy(&sock->recv_buffer.lock);
        return -ENOMEM;
    }
    
    return 0;
}

/*
 * Cleanup socket buffers
 */
static void socket_cleanup_buffers(kos_socket_t* sock) {
    /* Cleanup receive buffer */
    kos_packet_t* pkt = sock->recv_buffer.head;
    while (pkt) {
        kos_packet_t* next = pkt->next;
        kos_packet_free(pkt);
        pkt = next;
    }
    pthread_mutex_destroy(&sock->recv_buffer.lock);
    
    /* Cleanup send buffer */
    pkt = sock->send_buffer.head;
    while (pkt) {
        kos_packet_t* next = pkt->next;
        kos_packet_free(pkt);
        pkt = next;
    }
    pthread_mutex_destroy(&sock->send_buffer.lock);
}

/*
 * Check if socket can send
 */
static int socket_can_send(kos_socket_t* sock) {
    if (sock->type == KOS_SOCK_STREAM) {
        return sock->tcp_state == KOS_TCP_ESTABLISHED;
    } else if (sock->type == KOS_SOCK_DGRAM) {
        return sock->state == KOS_SS_CONNECTED || sock->state == KOS_SS_UNCONNECTED;
    }
    return 0;
}

/*
 * Check if socket can receive
 */
static int socket_can_recv(kos_socket_t* sock) {
    pthread_mutex_lock(&sock->recv_buffer.lock);
    int has_data = sock->recv_buffer.count > 0;
    pthread_mutex_unlock(&sock->recv_buffer.lock);
    return has_data;
}