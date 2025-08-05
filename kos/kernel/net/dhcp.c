/*
 * KOS DHCP Client Implementation
 * Handles DHCP discovery, IP address negotiation, and lease renewal
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>

/* DHCP constants */
#define DHCP_SERVER_PORT    67
#define DHCP_CLIENT_PORT    68
#define DHCP_MAGIC_COOKIE   0x63825363

/* DHCP message types */
#define DHCP_DISCOVER       1
#define DHCP_OFFER          2
#define DHCP_REQUEST        3
#define DHCP_DECLINE        4
#define DHCP_ACK            5
#define DHCP_NAK            6
#define DHCP_RELEASE        7
#define DHCP_INFORM         8

/* DHCP options */
#define DHCP_OPT_PAD            0
#define DHCP_OPT_SUBNET_MASK    1
#define DHCP_OPT_ROUTER         3
#define DHCP_OPT_DNS_SERVER     6
#define DHCP_OPT_HOSTNAME       12
#define DHCP_OPT_DOMAIN_NAME    15
#define DHCP_OPT_BROADCAST      28
#define DHCP_OPT_REQUESTED_IP   50
#define DHCP_OPT_LEASE_TIME     51
#define DHCP_OPT_MESSAGE_TYPE   53
#define DHCP_OPT_SERVER_ID      54
#define DHCP_OPT_PARAM_LIST     55
#define DHCP_OPT_RENEWAL_TIME   58
#define DHCP_OPT_REBIND_TIME    59
#define DHCP_OPT_CLIENT_ID      61
#define DHCP_OPT_END            255

/* DHCP states */
typedef enum {
    DHCP_STATE_INIT,
    DHCP_STATE_SELECTING,
    DHCP_STATE_REQUESTING,
    DHCP_STATE_BOUND,
    DHCP_STATE_RENEWING,
    DHCP_STATE_REBINDING,
    DHCP_STATE_INIT_REBOOT
} dhcp_state_t;

/* DHCP message structure */
typedef struct dhcp_message {
    uint8_t op;          /* Message op code / message type */
    uint8_t htype;       /* Hardware address type */
    uint8_t hlen;        /* Hardware address length */
    uint8_t hops;        /* Client sets to zero */
    uint32_t xid;        /* Transaction ID */
    uint16_t secs;       /* Seconds elapsed */
    uint16_t flags;      /* Flags */
    uint32_t ciaddr;     /* Client IP address */
    uint32_t yiaddr;     /* Your IP address */
    uint32_t siaddr;     /* Server IP address */
    uint32_t giaddr;     /* Gateway IP address */
    uint8_t chaddr[16];  /* Client hardware address */
    uint8_t sname[64];   /* Server host name */
    uint8_t file[128];   /* Boot file name */
    uint32_t magic;      /* Magic cookie */
    uint8_t options[308]; /* Options */
} __attribute__((packed)) dhcp_message_t;

/* DHCP lease information */
typedef struct dhcp_lease {
    uint32_t ip_addr;
    uint32_t subnet_mask;
    uint32_t router;
    uint32_t dns_server[4];
    uint32_t server_id;
    uint32_t lease_time;
    uint32_t renewal_time;
    uint32_t rebind_time;
    uint64_t lease_start;
    char hostname[64];
    char domain_name[64];
} dhcp_lease_t;

/* DHCP client context */
typedef struct dhcp_client {
    kos_netif_t* netif;
    dhcp_state_t state;
    uint32_t xid;
    uint32_t requested_ip;
    dhcp_lease_t lease;
    pthread_t thread;
    bool running;
    pthread_mutex_t lock;
} dhcp_client_t;

static dhcp_client_t* dhcp_clients[16] = {NULL}; /* Support up to 16 interfaces */
static pthread_mutex_t dhcp_clients_lock = PTHREAD_MUTEX_INITIALIZER;

/* DHCP statistics */
static struct {
    uint64_t discovers_sent;
    uint64_t offers_recv;
    uint64_t requests_sent;
    uint64_t acks_recv;
    uint64_t naks_recv;
    uint64_t releases_sent;
    uint64_t renewals_sent;
    uint64_t timeouts;
    uint64_t errors;
    pthread_mutex_t lock;
} dhcp_stats = {0};

/* Utility functions */
static uint64_t get_current_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec;
}

static uint32_t generate_xid(void) {
    return rand() ^ (get_current_time() & 0xFFFFFFFF);
}

static void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

/* DHCP option parsing */
static uint8_t* dhcp_add_option(uint8_t* options, uint8_t type, uint8_t len, const void* data) {
    *options++ = type;
    *options++ = len;
    if (len > 0 && data) {
        memcpy(options, data, len);
        options += len;
    }
    return options;
}

static uint8_t* dhcp_find_option(uint8_t* options, size_t len, uint8_t type) {
    uint8_t* end = options + len;
    
    while (options < end) {
        if (*options == DHCP_OPT_END) {
            break;
        }
        if (*options == DHCP_OPT_PAD) {
            options++;
            continue;
        }
        if (*options == type) {
            return options;
        }
        options += 2 + options[1];
    }
    
    return NULL;
}

static uint32_t dhcp_get_option_uint32(uint8_t* options, size_t len, uint8_t type) {
    uint8_t* opt = dhcp_find_option(options, len, type);
    if (opt && opt[1] == 4) {
        return ntohl(*(uint32_t*)(opt + 2));
    }
    return 0;
}

static void dhcp_get_option_string(uint8_t* options, size_t len, uint8_t type, 
                                   char* buf, size_t buf_size) {
    uint8_t* opt = dhcp_find_option(options, len, type);
    if (opt && opt[1] > 0 && opt[1] < buf_size) {
        memcpy(buf, opt + 2, opt[1]);
        buf[opt[1]] = '\0';
    } else {
        buf[0] = '\0';
    }
}

/* DHCP message creation */
static kos_packet_t* dhcp_create_message(dhcp_client_t* client, uint8_t msg_type) {
    kos_packet_t* pkt = kos_packet_alloc(sizeof(dhcp_message_t));
    if (!pkt) {
        return NULL;
    }
    
    dhcp_message_t* msg = (dhcp_message_t*)pkt->data;
    memset(msg, 0, sizeof(dhcp_message_t));
    
    /* Fill basic fields */
    msg->op = 1; /* BOOTREQUEST */
    msg->htype = 1; /* Ethernet */
    msg->hlen = 6; /* MAC address length */
    msg->hops = 0;
    msg->xid = htonl(client->xid);
    msg->secs = 0;
    msg->flags = htons(0x8000); /* Broadcast flag */
    msg->ciaddr = 0;
    msg->yiaddr = 0;
    msg->siaddr = 0;
    msg->giaddr = 0;
    memcpy(msg->chaddr, client->netif->hw_addr, 6);
    msg->magic = htonl(DHCP_MAGIC_COOKIE);
    
    /* Add options */
    uint8_t* opt = msg->options;
    
    /* Message type */
    opt = dhcp_add_option(opt, DHCP_OPT_MESSAGE_TYPE, 1, &msg_type);
    
    /* Client identifier */
    uint8_t client_id[7];
    client_id[0] = 1; /* Ethernet */
    memcpy(client_id + 1, client->netif->hw_addr, 6);
    opt = dhcp_add_option(opt, DHCP_OPT_CLIENT_ID, 7, client_id);
    
    /* Hostname */
    if (strlen(client->lease.hostname) > 0) {
        opt = dhcp_add_option(opt, DHCP_OPT_HOSTNAME, 
                              strlen(client->lease.hostname), client->lease.hostname);
    }
    
    /* Message-specific options */
    switch (msg_type) {
        case DHCP_DISCOVER:
            /* Parameter request list */
            {
                uint8_t param_list[] = {
                    DHCP_OPT_SUBNET_MASK,
                    DHCP_OPT_ROUTER,
                    DHCP_OPT_DNS_SERVER,
                    DHCP_OPT_DOMAIN_NAME,
                    DHCP_OPT_BROADCAST,
                    DHCP_OPT_LEASE_TIME,
                    DHCP_OPT_RENEWAL_TIME,
                    DHCP_OPT_REBIND_TIME
                };
                opt = dhcp_add_option(opt, DHCP_OPT_PARAM_LIST, 
                                      sizeof(param_list), param_list);
            }
            break;
            
        case DHCP_REQUEST:
            if (client->state == DHCP_STATE_REQUESTING) {
                /* Requested IP address */
                uint32_t requested_ip = htonl(client->requested_ip);
                opt = dhcp_add_option(opt, DHCP_OPT_REQUESTED_IP, 4, &requested_ip);
                
                /* Server identifier */
                uint32_t server_id = htonl(client->lease.server_id);
                opt = dhcp_add_option(opt, DHCP_OPT_SERVER_ID, 4, &server_id);
            } else {
                /* Renewing - use ciaddr */
                msg->ciaddr = htonl(client->lease.ip_addr);
            }
            break;
            
        case DHCP_RELEASE:
            msg->ciaddr = htonl(client->lease.ip_addr);
            {
                uint32_t server_id = htonl(client->lease.server_id);
                opt = dhcp_add_option(opt, DHCP_OPT_SERVER_ID, 4, &server_id);
            }
            break;
    }
    
    /* End option */
    *opt++ = DHCP_OPT_END;
    
    pkt->size = sizeof(dhcp_message_t);
    return pkt;
}

/* DHCP message processing */
static void dhcp_process_offer(dhcp_client_t* client, dhcp_message_t* msg) {
    if (client->state != DHCP_STATE_SELECTING) {
        return;
    }
    
    printf("DHCP: Received OFFER for ");
    print_ip(ntohl(msg->yiaddr));
    printf(" from ");
    print_ip(ntohl(msg->siaddr));
    printf("\n");
    
    /* Parse lease information */
    client->requested_ip = ntohl(msg->yiaddr);
    client->lease.ip_addr = ntohl(msg->yiaddr);
    client->lease.server_id = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_SERVER_ID);
    client->lease.subnet_mask = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_SUBNET_MASK);
    client->lease.router = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_ROUTER);
    client->lease.dns_server[0] = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_DNS_SERVER);
    client->lease.lease_time = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_LEASE_TIME);
    client->lease.renewal_time = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_RENEWAL_TIME);
    client->lease.rebind_time = dhcp_get_option_uint32(msg->options, 308, DHCP_OPT_REBIND_TIME);
    
    dhcp_get_option_string(msg->options, 308, DHCP_OPT_DOMAIN_NAME, 
                          client->lease.domain_name, sizeof(client->lease.domain_name));
    
    /* Default renewal and rebind times if not provided */
    if (client->lease.renewal_time == 0) {
        client->lease.renewal_time = client->lease.lease_time / 2;
    }
    if (client->lease.rebind_time == 0) {
        client->lease.rebind_time = client->lease.lease_time * 7 / 8;
    }
    
    /* Move to requesting state */
    client->state = DHCP_STATE_REQUESTING;
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.offers_recv++;
    pthread_mutex_unlock(&dhcp_stats.lock);
}

static void dhcp_process_ack(dhcp_client_t* client, dhcp_message_t* msg) {
    if (client->state != DHCP_STATE_REQUESTING && 
        client->state != DHCP_STATE_RENEWING &&
        client->state != DHCP_STATE_REBINDING) {
        return;
    }
    
    printf("DHCP: Received ACK for ");
    print_ip(ntohl(msg->yiaddr));
    printf("\n");
    
    /* Update lease information */
    client->lease.ip_addr = ntohl(msg->yiaddr);
    client->lease.lease_start = get_current_time();
    
    /* Configure network interface */
    kos_netif_set_addr(client->netif, client->lease.ip_addr, client->lease.subnet_mask);
    
    /* Add default route if router provided */
    if (client->lease.router != 0) {
        kos_route_set_default_gw(client->lease.router, client->netif);
    }
    
    /* Move to bound state */
    client->state = DHCP_STATE_BOUND;
    
    printf("DHCP: Interface %s configured with IP ", client->netif->name);
    print_ip(client->lease.ip_addr);
    printf(", lease time %u seconds\n", client->lease.lease_time);
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.acks_recv++;
    pthread_mutex_unlock(&dhcp_stats.lock);
}

static void dhcp_process_nak(dhcp_client_t* client, dhcp_message_t* msg) {
    printf("DHCP: Received NAK, restarting discovery\n");
    
    /* Reset to initial state */
    client->state = DHCP_STATE_INIT;
    client->requested_ip = 0;
    memset(&client->lease, 0, sizeof(client->lease));
    
    /* Clear interface configuration */
    kos_netif_set_addr(client->netif, 0, 0);
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.naks_recv++;
    pthread_mutex_unlock(&dhcp_stats.lock);
}

/* DHCP client state machine */
static void dhcp_send_discover(dhcp_client_t* client) {
    printf("DHCP: Sending DISCOVER on %s\n", client->netif->name);
    
    kos_packet_t* pkt = dhcp_create_message(client, DHCP_DISCOVER);
    if (!pkt) {
        return;
    }
    
    /* Send as UDP packet */
    struct sockaddr_in dest;
    dest.sin_family = AF_INET;
    dest.sin_addr.s_addr = INADDR_BROADCAST;
    dest.sin_port = htons(DHCP_SERVER_PORT);
    
    /* Create UDP packet and send */
    kos_udp_header_t udp_hdr;
    udp_hdr.src_port = htons(DHCP_CLIENT_PORT);
    udp_hdr.dst_port = htons(DHCP_SERVER_PORT);
    udp_hdr.length = htons(sizeof(kos_udp_header_t) + pkt->size);
    udp_hdr.checksum = 0;
    
    /* Add UDP header */
    if (kos_packet_push(pkt, sizeof(kos_udp_header_t)) == 0) {
        memcpy(pkt->data, &udp_hdr, sizeof(kos_udp_header_t));
        pkt->l4_header = pkt->data;
        
        /* Send IP packet */
        kos_ip_output(pkt, INADDR_BROADCAST, 17); /* UDP */
    }
    
    client->state = DHCP_STATE_SELECTING;
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.discovers_sent++;
    pthread_mutex_unlock(&dhcp_stats.lock);
    
    kos_packet_free(pkt);
}

static void dhcp_send_request(dhcp_client_t* client) {
    printf("DHCP: Sending REQUEST for ");
    print_ip(client->requested_ip);
    printf("\n");
    
    kos_packet_t* pkt = dhcp_create_message(client, DHCP_REQUEST);
    if (!pkt) {
        return;
    }
    
    /* Send as UDP packet */
    uint32_t dest_ip = INADDR_BROADCAST;
    if (client->state == DHCP_STATE_RENEWING) {
        dest_ip = client->lease.server_id;
    }
    
    kos_udp_header_t udp_hdr;
    udp_hdr.src_port = htons(DHCP_CLIENT_PORT);
    udp_hdr.dst_port = htons(DHCP_SERVER_PORT);
    udp_hdr.length = htons(sizeof(kos_udp_header_t) + pkt->size);
    udp_hdr.checksum = 0;
    
    /* Add UDP header */
    if (kos_packet_push(pkt, sizeof(kos_udp_header_t)) == 0) {
        memcpy(pkt->data, &udp_hdr, sizeof(kos_udp_header_t));
        pkt->l4_header = pkt->data;
        
        /* Send IP packet */
        kos_ip_output(pkt, dest_ip, 17); /* UDP */
    }
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.requests_sent++;
    pthread_mutex_unlock(&dhcp_stats.lock);
    
    kos_packet_free(pkt);
}

static void dhcp_send_release(dhcp_client_t* client) {
    if (client->lease.ip_addr == 0 || client->lease.server_id == 0) {
        return;
    }
    
    printf("DHCP: Sending RELEASE for ");
    print_ip(client->lease.ip_addr);
    printf("\n");
    
    kos_packet_t* pkt = dhcp_create_message(client, DHCP_RELEASE);
    if (!pkt) {
        return;
    }
    
    kos_udp_header_t udp_hdr;
    udp_hdr.src_port = htons(DHCP_CLIENT_PORT);
    udp_hdr.dst_port = htons(DHCP_SERVER_PORT);
    udp_hdr.length = htons(sizeof(kos_udp_header_t) + pkt->size);
    udp_hdr.checksum = 0;
    
    /* Add UDP header */
    if (kos_packet_push(pkt, sizeof(kos_udp_header_t)) == 0) {
        memcpy(pkt->data, &udp_hdr, sizeof(kos_udp_header_t));
        pkt->l4_header = pkt->data;
        
        /* Send to server directly */
        kos_ip_output(pkt, client->lease.server_id, 17); /* UDP */
    }
    
    pthread_mutex_lock(&dhcp_stats.lock);
    dhcp_stats.releases_sent++;
    pthread_mutex_unlock(&dhcp_stats.lock);
    
    kos_packet_free(pkt);
}

/* DHCP client thread */
static void* dhcp_client_thread(void* arg) {
    dhcp_client_t* client = (dhcp_client_t*)arg;
    uint64_t last_action = 0;
    uint64_t timeout = 4; /* Initial timeout */
    
    printf("DHCP: Starting client for interface %s\n", client->netif->name);
    
    while (client->running) {
        uint64_t current_time = get_current_time();
        
        pthread_mutex_lock(&client->lock);
        
        switch (client->state) {
            case DHCP_STATE_INIT:
                client->xid = generate_xid();
                dhcp_send_discover(client);
                last_action = current_time;
                timeout = 4;
                break;
                
            case DHCP_STATE_SELECTING:
                if (current_time - last_action > timeout) {
                    /* Timeout, retry discover */
                    printf("DHCP: DISCOVER timeout, retrying\n");
                    client->state = DHCP_STATE_INIT;
                    timeout = (timeout < 64) ? timeout * 2 : 64;
                    
                    pthread_mutex_lock(&dhcp_stats.lock);
                    dhcp_stats.timeouts++;
                    pthread_mutex_unlock(&dhcp_stats.lock);
                }
                break;
                
            case DHCP_STATE_REQUESTING:
                dhcp_send_request(client);
                last_action = current_time;
                timeout = 4;
                client->state = DHCP_STATE_REQUESTING; /* Wait for ACK */
                break;
                
            case DHCP_STATE_BOUND:
                /* Check for renewal time */
                if (current_time - client->lease.lease_start >= client->lease.renewal_time) {
                    printf("DHCP: Lease renewal time reached\n");
                    client->state = DHCP_STATE_RENEWING;
                }
                break;
                
            case DHCP_STATE_RENEWING:
                dhcp_send_request(client);
                last_action = current_time;
                timeout = client->lease.rebind_time / 2;
                
                pthread_mutex_lock(&dhcp_stats.lock);
                dhcp_stats.renewals_sent++;
                pthread_mutex_unlock(&dhcp_stats.lock);
                
                /* Check for rebind time */
                if (current_time - client->lease.lease_start >= client->lease.rebind_time) {
                    client->state = DHCP_STATE_REBINDING;
                }
                break;
                
            case DHCP_STATE_REBINDING:
                dhcp_send_request(client);
                last_action = current_time;
                
                /* Check for lease expiration */
                if (current_time - client->lease.lease_start >= client->lease.lease_time) {
                    printf("DHCP: Lease expired, restarting\n");
                    client->state = DHCP_STATE_INIT;
                    kos_netif_set_addr(client->netif, 0, 0);
                    memset(&client->lease, 0, sizeof(client->lease));
                }
                break;
        }
        
        pthread_mutex_unlock(&client->lock);
        
        /* Sleep for 1 second */
        sleep(1);
    }
    
    printf("DHCP: Client thread for %s stopped\n", client->netif->name);
    return NULL;
}

/* DHCP client interface */
int kos_dhcp_start_client(kos_netif_t* netif, const char* hostname) {
    if (!netif) {
        return -1;
    }
    
    pthread_mutex_lock(&dhcp_clients_lock);
    
    /* Find free slot */
    int slot = -1;
    for (int i = 0; i < 16; i++) {
        if (dhcp_clients[i] == NULL) {
            slot = i;
            break;
        }
    }
    
    if (slot == -1) {
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1; /* No free slots */
    }
    
    /* Create client context */
    dhcp_client_t* client = malloc(sizeof(dhcp_client_t));
    if (!client) {
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1;
    }
    
    memset(client, 0, sizeof(dhcp_client_t));
    client->netif = netif;
    client->state = DHCP_STATE_INIT;
    client->running = true;
    
    if (hostname && strlen(hostname) > 0) {
        strncpy(client->lease.hostname, hostname, sizeof(client->lease.hostname) - 1);
    } else {
        snprintf(client->lease.hostname, sizeof(client->lease.hostname), 
                "kos-%s", netif->name);
    }
    
    if (pthread_mutex_init(&client->lock, NULL) != 0) {
        free(client);
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1;
    }
    
    /* Start client thread */
    if (pthread_create(&client->thread, NULL, dhcp_client_thread, client) != 0) {
        pthread_mutex_destroy(&client->lock);
        free(client);
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1;
    }
    
    dhcp_clients[slot] = client;
    pthread_mutex_unlock(&dhcp_clients_lock);
    
    printf("DHCP: Started client for interface %s\n", netif->name);
    return 0;
}

int kos_dhcp_stop_client(kos_netif_t* netif) {
    if (!netif) {
        return -1;
    }
    
    pthread_mutex_lock(&dhcp_clients_lock);
    
    /* Find client */
    dhcp_client_t* client = NULL;
    int slot = -1;
    for (int i = 0; i < 16; i++) {
        if (dhcp_clients[i] && dhcp_clients[i]->netif == netif) {
            client = dhcp_clients[i];
            slot = i;
            break;
        }
    }
    
    if (!client) {
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1; /* Client not found */
    }
    
    /* Send release if we have a lease */
    pthread_mutex_lock(&client->lock);
    if (client->state == DHCP_STATE_BOUND || 
        client->state == DHCP_STATE_RENEWING ||
        client->state == DHCP_STATE_REBINDING) {
        dhcp_send_release(client);
    }
    pthread_mutex_unlock(&client->lock);
    
    /* Stop client thread */
    client->running = false;
    pthread_join(client->thread, NULL);
    
    /* Clean up */
    pthread_mutex_destroy(&client->lock);
    free(client);
    dhcp_clients[slot] = NULL;
    
    pthread_mutex_unlock(&dhcp_clients_lock);
    
    printf("DHCP: Stopped client for interface %s\n", netif->name);
    return 0;
}

/* DHCP packet input processing */
int kos_dhcp_input(kos_packet_t* pkt) {
    if (!pkt || pkt->size < sizeof(dhcp_message_t)) {
        return -1;
    }
    
    dhcp_message_t* msg = (dhcp_message_t*)pkt->data;
    
    /* Validate DHCP message */
    if (msg->op != 2 || /* BOOTREPLY */
        msg->htype != 1 || /* Ethernet */
        msg->hlen != 6 ||
        ntohl(msg->magic) != DHCP_MAGIC_COOKIE) {
        return -1;
    }
    
    /* Find message type */
    uint8_t* msg_type_opt = dhcp_find_option(msg->options, 308, DHCP_OPT_MESSAGE_TYPE);
    if (!msg_type_opt || msg_type_opt[1] != 1) {
        return -1;
    }
    
    uint8_t msg_type = msg_type_opt[2];
    uint32_t xid = ntohl(msg->xid);
    
    pthread_mutex_lock(&dhcp_clients_lock);
    
    /* Find matching client */
    dhcp_client_t* client = NULL;
    for (int i = 0; i < 16; i++) {
        if (dhcp_clients[i] && dhcp_clients[i]->xid == xid) {
            /* Verify MAC address match */
            if (memcmp(dhcp_clients[i]->netif->hw_addr, msg->chaddr, 6) == 0) {
                client = dhcp_clients[i];
                break;
            }
        }
    }
    
    if (!client) {
        pthread_mutex_unlock(&dhcp_clients_lock);
        return -1; /* No matching client */
    }
    
    pthread_mutex_lock(&client->lock);
    
    /* Process message */
    switch (msg_type) {
        case DHCP_OFFER:
            dhcp_process_offer(client, msg);
            break;
        case DHCP_ACK:
            dhcp_process_ack(client, msg);
            break;
        case DHCP_NAK:
            dhcp_process_nak(client, msg);
            break;
        default:
            printf("DHCP: Received unknown message type %d\n", msg_type);
            break;
    }
    
    pthread_mutex_unlock(&client->lock);
    pthread_mutex_unlock(&dhcp_clients_lock);
    
    return 0;
}

/* DHCP statistics */
void kos_dhcp_dump_stats(void) {
    pthread_mutex_lock(&dhcp_stats.lock);
    
    printf("DHCP Statistics:\n");
    printf("  Discovers sent: %lu\n", dhcp_stats.discovers_sent);
    printf("  Offers received: %lu\n", dhcp_stats.offers_recv);
    printf("  Requests sent: %lu\n", dhcp_stats.requests_sent);
    printf("  ACKs received: %lu\n", dhcp_stats.acks_recv);
    printf("  NAKs received: %lu\n", dhcp_stats.naks_recv);
    printf("  Releases sent: %lu\n", dhcp_stats.releases_sent);
    printf("  Renewals sent: %lu\n", dhcp_stats.renewals_sent);
    printf("  Timeouts: %lu\n", dhcp_stats.timeouts);
    printf("  Errors: %lu\n", dhcp_stats.errors);
    
    pthread_mutex_unlock(&dhcp_stats.lock);
}

/* Initialize DHCP subsystem */
int kos_dhcp_init(void) {
    memset(dhcp_clients, 0, sizeof(dhcp_clients));
    
    memset(&dhcp_stats, 0, sizeof(dhcp_stats));
    if (pthread_mutex_init(&dhcp_stats.lock, NULL) != 0) {
        return -1;
    }
    
    printf("DHCP subsystem initialized\n");
    return 0;
}

/* Cleanup DHCP subsystem */
void kos_dhcp_cleanup(void) {
    pthread_mutex_lock(&dhcp_clients_lock);
    
    /* Stop all clients */
    for (int i = 0; i < 16; i++) {
        if (dhcp_clients[i]) {
            kos_dhcp_stop_client(dhcp_clients[i]->netif);
        }
    }
    
    pthread_mutex_unlock(&dhcp_clients_lock);
    pthread_mutex_destroy(&dhcp_stats.lock);
    
    printf("DHCP subsystem cleaned up\n");
}