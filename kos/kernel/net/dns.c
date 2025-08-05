/*
 * KOS DNS Resolver Implementation
 * Handles DNS query building, response parsing, and caching
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>
#include <ctype.h>

/* DNS constants */
#define DNS_PORT            53
#define DNS_MAX_NAME_LEN    255
#define DNS_MAX_LABEL_LEN   63
#define DNS_HEADER_SIZE     12
#define DNS_MAX_PACKET_SIZE 512

/* DNS record types */
#define DNS_TYPE_A          1   /* IPv4 address */
#define DNS_TYPE_NS         2   /* Name server */
#define DNS_TYPE_CNAME      5   /* Canonical name */
#define DNS_TYPE_SOA        6   /* Start of authority */
#define DNS_TYPE_PTR        12  /* Pointer */
#define DNS_TYPE_MX         15  /* Mail exchange */
#define DNS_TYPE_TXT        16  /* Text */
#define DNS_TYPE_AAAA       28  /* IPv6 address */

/* DNS classes */
#define DNS_CLASS_IN        1   /* Internet */

/* DNS header flags */
#define DNS_FLAG_QR         0x8000  /* Query/Response */
#define DNS_FLAG_OPCODE     0x7800  /* Opcode */
#define DNS_FLAG_AA         0x0400  /* Authoritative Answer */
#define DNS_FLAG_TC         0x0200  /* Truncated */
#define DNS_FLAG_RD         0x0100  /* Recursion Desired */
#define DNS_FLAG_RA         0x0080  /* Recursion Available */
#define DNS_FLAG_RCODE      0x000F  /* Response Code */

/* DNS response codes */
#define DNS_RCODE_NOERROR   0   /* No error */
#define DNS_RCODE_FORMERR   1   /* Format error */
#define DNS_RCODE_SERVFAIL  2   /* Server failure */
#define DNS_RCODE_NXDOMAIN  3   /* Non-existent domain */
#define DNS_RCODE_NOTIMP    4   /* Not implemented */
#define DNS_RCODE_REFUSED   5   /* Query refused */

/* DNS cache constants */
#define DNS_CACHE_SIZE      256
#define DNS_CACHE_TTL_MIN   60      /* Minimum TTL: 1 minute */
#define DNS_CACHE_TTL_MAX   86400   /* Maximum TTL: 24 hours */
#define DNS_CACHE_TTL_DEFAULT 300   /* Default TTL: 5 minutes */

/* DNS header structure */
typedef struct dns_header {
    uint16_t id;        /* Identification */
    uint16_t flags;     /* Flags */
    uint16_t qdcount;   /* Question count */
    uint16_t ancount;   /* Answer count */
    uint16_t nscount;   /* Authority count */
    uint16_t arcount;   /* Additional count */
} __attribute__((packed)) dns_header_t;

/* DNS question structure */
typedef struct dns_question {
    /* Name follows as variable length */
    uint16_t qtype;     /* Question type */
    uint16_t qclass;    /* Question class */
} __attribute__((packed)) dns_question_t;

/* DNS resource record structure */
typedef struct dns_rr {
    /* Name follows as variable length */
    uint16_t type;      /* Record type */
    uint16_t class;     /* Record class */
    uint32_t ttl;       /* Time to live */
    uint16_t rdlength;  /* Resource data length */
    /* Resource data follows */
} __attribute__((packed)) dns_rr_t;

/* DNS cache entry */
typedef struct dns_cache_entry {
    char name[DNS_MAX_NAME_LEN];
    uint16_t type;
    uint32_t ip_addr;
    uint64_t expiry;
    struct dns_cache_entry* next;
} dns_cache_entry_t;

/* DNS resolver context */
typedef struct dns_resolver {
    uint32_t servers[4];    /* DNS servers */
    int server_count;
    uint16_t next_id;
    pthread_mutex_t lock;
} dns_resolver_t;

/* Global DNS resolver */
static dns_resolver_t dns_resolver = {0};

/* DNS cache */
static dns_cache_entry_t* dns_cache[DNS_CACHE_SIZE] = {NULL};
static pthread_mutex_t dns_cache_lock = PTHREAD_MUTEX_INITIALIZER;

/* DNS statistics */
static struct {
    uint64_t queries_sent;
    uint64_t responses_recv;
    uint64_t cache_hits;
    uint64_t cache_misses;
    uint64_t timeouts;
    uint64_t errors;
    uint64_t nx_domain;
    uint64_t server_fail;
    pthread_mutex_t lock;
} dns_stats = {0};

/* Utility functions */
static uint64_t get_current_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec;
}

static uint32_t dns_hash(const char* name) {
    uint32_t hash = 5381;
    while (*name) {
        hash = ((hash << 5) + hash) + tolower(*name++);
    }
    return hash % DNS_CACHE_SIZE;
}

static void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

static bool is_valid_hostname(const char* name) {
    if (!name || strlen(name) == 0 || strlen(name) > DNS_MAX_NAME_LEN) {
        return false;
    }
    
    size_t len = strlen(name);
    if (name[len - 1] == '.') {
        len--; /* Ignore trailing dot */
    }
    
    size_t label_len = 0;
    for (size_t i = 0; i < len; i++) {
        char c = name[i];
        if (c == '.') {
            if (label_len == 0 || label_len > DNS_MAX_LABEL_LEN) {
                return false;
            }
            label_len = 0;
        } else if (isalnum(c) || c == '-') {
            label_len++;
        } else {
            return false;
        }
    }
    
    return (label_len > 0 && label_len <= DNS_MAX_LABEL_LEN);
}

/* DNS name encoding/decoding */
static size_t dns_encode_name(const char* name, uint8_t* buf, size_t buf_size) {
    if (!name || !buf || buf_size < 2) {
        return 0;
    }
    
    size_t pos = 0;
    size_t name_len = strlen(name);
    const char* start = name;
    const char* end;
    
    /* Handle trailing dot */
    if (name_len > 0 && name[name_len - 1] == '.') {
        name_len--;
    }
    
    while (start < name + name_len) {
        /* Find next dot or end */
        end = strchr(start, '.');
        if (!end) {
            end = name + name_len;
        }
        
        size_t label_len = end - start;
        if (label_len == 0 || label_len > DNS_MAX_LABEL_LEN) {
            return 0; /* Invalid label */
        }
        
        if (pos + 1 + label_len >= buf_size) {
            return 0; /* Buffer too small */
        }
        
        /* Write label length */
        buf[pos++] = (uint8_t)label_len;
        
        /* Write label */
        memcpy(buf + pos, start, label_len);
        pos += label_len;
        
        /* Move to next label */
        start = end + 1;
    }
    
    /* Write terminating zero */
    if (pos >= buf_size) {
        return 0;
    }
    buf[pos++] = 0;
    
    return pos;
}

static size_t dns_decode_name(const uint8_t* packet, size_t packet_size, 
                              size_t offset, char* name, size_t name_size) {
    if (!packet || !name || name_size < 2) {
        return 0;
    }
    
    size_t pos = 0;
    size_t jumps = 0;
    size_t original_offset = offset;
    bool jumped = false;
    
    while (offset < packet_size) {
        uint8_t len = packet[offset];
        
        /* Check for compression */
        if ((len & 0xC0) == 0xC0) {
            if (offset + 1 >= packet_size) {
                return 0; /* Invalid compression pointer */
            }
            
            /* Follow compression pointer */
            if (!jumped) {
                original_offset = offset + 2;
                jumped = true;
            }
            
            offset = ((len & 0x3F) << 8) | packet[offset + 1];
            jumps++;
            
            if (jumps > 16) {
                return 0; /* Too many jumps, probably a loop */
            }
            continue;
        }
        
        /* End of name */
        if (len == 0) {
            if (pos > 0 && pos < name_size) {
                name[pos - 1] = '\0'; /* Replace last dot with null */
            } else if (pos == 0) {
                name[0] = '\0';
            }
            return jumped ? original_offset : offset + 1;
        }
        
        /* Regular label */
        offset++;
        if (offset + len > packet_size || pos + len + 1 >= name_size) {
            return 0; /* Invalid label or buffer too small */
        }
        
        /* Add dot if not first label */
        if (pos > 0) {
            name[pos++] = '.';
        }
        
        /* Copy label */
        memcpy(name + pos, packet + offset, len);
        pos += len;
        offset += len;
    }
    
    return 0; /* Unexpected end of packet */
}

/* DNS cache management */
static dns_cache_entry_t* dns_cache_find(const char* name, uint16_t type) {
    uint32_t hash = dns_hash(name);
    dns_cache_entry_t* entry = dns_cache[hash];
    
    while (entry) {
        if (entry->type == type && strcasecmp(entry->name, name) == 0) {
            return entry;
        }
        entry = entry->next;
    }
    
    return NULL;
}

static void dns_cache_add(const char* name, uint16_t type, uint32_t ip_addr, uint32_t ttl) {
    if (!name || ttl == 0) {
        return;
    }
    
    /* Clamp TTL */
    if (ttl < DNS_CACHE_TTL_MIN) ttl = DNS_CACHE_TTL_MIN;
    if (ttl > DNS_CACHE_TTL_MAX) ttl = DNS_CACHE_TTL_MAX;
    
    uint32_t hash = dns_hash(name);
    uint64_t expiry = get_current_time() + ttl;
    
    /* Check if entry already exists */
    dns_cache_entry_t* entry = dns_cache_find(name, type);
    if (entry) {
        /* Update existing entry */
        entry->ip_addr = ip_addr;
        entry->expiry = expiry;
        return;
    }
    
    /* Create new entry */
    entry = malloc(sizeof(dns_cache_entry_t));
    if (!entry) {
        return;
    }
    
    strncpy(entry->name, name, sizeof(entry->name) - 1);
    entry->name[sizeof(entry->name) - 1] = '\0';
    entry->type = type;
    entry->ip_addr = ip_addr;
    entry->expiry = expiry;
    entry->next = dns_cache[hash];
    dns_cache[hash] = entry;
    
    printf("DNS: Cached %s -> ", name);
    print_ip(ip_addr);
    printf(" (TTL: %u)\n", ttl);
}

static void dns_cache_cleanup(void) {
    uint64_t current_time = get_current_time();
    
    for (int i = 0; i < DNS_CACHE_SIZE; i++) {
        dns_cache_entry_t* entry = dns_cache[i];
        dns_cache_entry_t* prev = NULL;
        
        while (entry) {
            dns_cache_entry_t* next = entry->next;
            
            if (entry->expiry <= current_time) {
                /* Remove expired entry */
                if (prev) {
                    prev->next = next;
                } else {
                    dns_cache[i] = next;
                }
                free(entry);
            } else {
                prev = entry;
            }
            
            entry = next;
        }
    }
}

/* DNS packet creation */
static kos_packet_t* dns_create_query(const char* name, uint16_t type) {
    if (!name || !is_valid_hostname(name)) {
        return NULL;
    }
    
    kos_packet_t* pkt = kos_packet_alloc(DNS_MAX_PACKET_SIZE);
    if (!pkt) {
        return NULL;
    }
    
    dns_header_t* hdr = (dns_header_t*)pkt->data;
    
    /* Fill DNS header */
    pthread_mutex_lock(&dns_resolver.lock);
    hdr->id = htons(dns_resolver.next_id++);
    pthread_mutex_unlock(&dns_resolver.lock);
    
    hdr->flags = htons(DNS_FLAG_RD); /* Recursion desired */
    hdr->qdcount = htons(1);
    hdr->ancount = 0;
    hdr->nscount = 0;
    hdr->arcount = 0;
    
    size_t pos = DNS_HEADER_SIZE;
    
    /* Encode question name */
    size_t name_len = dns_encode_name(name, pkt->data + pos, DNS_MAX_PACKET_SIZE - pos);
    if (name_len == 0) {
        kos_packet_free(pkt);
        return NULL;
    }
    pos += name_len;
    
    /* Add question type and class */
    if (pos + sizeof(dns_question_t) > DNS_MAX_PACKET_SIZE) {
        kos_packet_free(pkt);
        return NULL;
    }
    
    dns_question_t* question = (dns_question_t*)(pkt->data + pos);
    question->qtype = htons(type);
    question->qclass = htons(DNS_CLASS_IN);
    pos += sizeof(dns_question_t);
    
    pkt->size = pos;
    return pkt;
}

/* DNS response parsing */
static int dns_parse_response(kos_packet_t* pkt, const char* query_name, 
                              uint32_t* result_ip) {
    if (!pkt || pkt->size < DNS_HEADER_SIZE || !query_name || !result_ip) {
        return -1;
    }
    
    dns_header_t* hdr = (dns_header_t*)pkt->data;
    
    /* Check if it's a response */
    uint16_t flags = ntohs(hdr->flags);
    if (!(flags & DNS_FLAG_QR)) {
        return -1; /* Not a response */
    }
    
    /* Check response code */
    uint16_t rcode = flags & DNS_FLAG_RCODE;
    if (rcode != DNS_RCODE_NOERROR) {
        printf("DNS: Query failed with rcode %u\n", rcode);
        
        pthread_mutex_lock(&dns_stats.lock);
        if (rcode == DNS_RCODE_NXDOMAIN) {
            dns_stats.nx_domain++;
        } else if (rcode == DNS_RCODE_SERVFAIL) {
            dns_stats.server_fail++;
        } else {
            dns_stats.errors++;
        }
        pthread_mutex_unlock(&dns_stats.lock);
        
        return -1;
    }
    
    uint16_t qdcount = ntohs(hdr->qdcount);
    uint16_t ancount = ntohs(hdr->ancount);
    
    if (qdcount == 0 || ancount == 0) {
        return -1; /* No questions or answers */
    }
    
    size_t pos = DNS_HEADER_SIZE;
    
    /* Skip questions */
    for (int i = 0; i < qdcount; i++) {
        char name[DNS_MAX_NAME_LEN];
        size_t name_end = dns_decode_name(pkt->data, pkt->size, pos, name, sizeof(name));
        if (name_end == 0) {
            return -1;
        }
        pos = name_end + sizeof(dns_question_t);
        if (pos > pkt->size) {
            return -1;
        }
    }
    
    /* Parse answers */
    for (int i = 0; i < ancount; i++) {
        char name[DNS_MAX_NAME_LEN];
        size_t name_end = dns_decode_name(pkt->data, pkt->size, pos, name, sizeof(name));
        if (name_end == 0 || name_end + sizeof(dns_rr_t) > pkt->size) {
            return -1;
        }
        
        dns_rr_t* rr = (dns_rr_t*)(pkt->data + name_end);
        uint16_t type = ntohs(rr->type);
        uint16_t class = ntohs(rr->class);
        uint32_t ttl = ntohl(rr->ttl);
        uint16_t rdlength = ntohs(rr->rdlength);
        
        pos = name_end + sizeof(dns_rr_t);
        
        if (pos + rdlength > pkt->size) {
            return -1;
        }
        
        /* Check if this is an A record for our query */
        if (type == DNS_TYPE_A && class == DNS_CLASS_IN && rdlength == 4 &&
            strcasecmp(name, query_name) == 0) {
            
            uint32_t ip_addr = ntohl(*(uint32_t*)(pkt->data + pos));
            *result_ip = ip_addr;
            
            /* Add to cache */
            pthread_mutex_lock(&dns_cache_lock);
            dns_cache_add(query_name, DNS_TYPE_A, ip_addr, ttl);
            pthread_mutex_unlock(&dns_cache_lock);
            
            printf("DNS: Resolved %s -> ", query_name);
            print_ip(ip_addr);
            printf("\n");
            
            return 0;
        }
        
        pos += rdlength;
    }
    
    return -1; /* No matching A record found */
}

/* DNS resolver interface */
int kos_dns_resolve(const char* hostname, uint32_t* ip_addr) {
    if (!hostname || !ip_addr || !is_valid_hostname(hostname)) {
        return -1;
    }
    
    /* Check cache first */
    pthread_mutex_lock(&dns_cache_lock);
    dns_cache_cleanup();
    
    dns_cache_entry_t* entry = dns_cache_find(hostname, DNS_TYPE_A);
    if (entry && entry->expiry > get_current_time()) {
        *ip_addr = entry->ip_addr;
        pthread_mutex_unlock(&dns_cache_lock);
        
        pthread_mutex_lock(&dns_stats.lock);
        dns_stats.cache_hits++;
        pthread_mutex_unlock(&dns_stats.lock);
        
        printf("DNS: Cache hit for %s -> ", hostname);
        print_ip(*ip_addr);
        printf("\n");
        return 0;
    }
    pthread_mutex_unlock(&dns_cache_lock);
    
    pthread_mutex_lock(&dns_stats.lock);
    dns_stats.cache_misses++;
    pthread_mutex_unlock(&dns_stats.lock);
    
    /* No DNS servers configured */
    pthread_mutex_lock(&dns_resolver.lock);
    if (dns_resolver.server_count == 0) {
        pthread_mutex_unlock(&dns_resolver.lock);
        return -1;
    }
    pthread_mutex_unlock(&dns_resolver.lock);
    
    /* Create DNS query */
    kos_packet_t* query = dns_create_query(hostname, DNS_TYPE_A);
    if (!query) {
        return -1;
    }
    
    printf("DNS: Resolving %s...\n", hostname);
    
    /* Try each DNS server */
    pthread_mutex_lock(&dns_resolver.lock);
    for (int server = 0; server < dns_resolver.server_count; server++) {
        uint32_t dns_server = dns_resolver.servers[server];
        
        printf("DNS: Querying server ");
        print_ip(dns_server);
        printf("\n");
        
        /* Create UDP header */
        kos_udp_header_t udp_hdr;
        udp_hdr.src_port = htons(32768 + (rand() % 32768)); /* Random source port */
        udp_hdr.dst_port = htons(DNS_PORT);
        udp_hdr.length = htons(sizeof(kos_udp_header_t) + query->size);
        udp_hdr.checksum = 0;
        
        /* Add UDP header to packet */
        if (kos_packet_push(query, sizeof(kos_udp_header_t)) == 0) {
            memcpy(query->data, &udp_hdr, sizeof(kos_udp_header_t));
            query->l4_header = query->data;
            
            /* Send query */
            int result = kos_ip_output(query, dns_server, 17); /* UDP */
            
            pthread_mutex_lock(&dns_stats.lock);
            dns_stats.queries_sent++;
            pthread_mutex_unlock(&dns_stats.lock);
            
            if (result == 0) {
                /* For this implementation, we'll simulate waiting for response
                 * In a real implementation, this would be asynchronous */
                printf("DNS: Query sent successfully\n");
                break;
            }
        }
    }
    pthread_mutex_unlock(&dns_resolver.lock);
    
    kos_packet_free(query);
    return -1; /* Query sent but response handling would be asynchronous */
}

/* DNS server management */
int kos_dns_add_server(uint32_t server_ip) {
    if (server_ip == 0) {
        return -1;
    }
    
    pthread_mutex_lock(&dns_resolver.lock);
    
    if (dns_resolver.server_count >= 4) {
        pthread_mutex_unlock(&dns_resolver.lock);
        return -1; /* Too many servers */
    }
    
    /* Check for duplicates */
    for (int i = 0; i < dns_resolver.server_count; i++) {
        if (dns_resolver.servers[i] == server_ip) {
            pthread_mutex_unlock(&dns_resolver.lock);
            return 0; /* Already exists */
        }
    }
    
    dns_resolver.servers[dns_resolver.server_count++] = server_ip;
    
    printf("DNS: Added server ");
    print_ip(server_ip);
    printf("\n");
    
    pthread_mutex_unlock(&dns_resolver.lock);
    return 0;
}

int kos_dns_remove_server(uint32_t server_ip) {
    pthread_mutex_lock(&dns_resolver.lock);
    
    for (int i = 0; i < dns_resolver.server_count; i++) {
        if (dns_resolver.servers[i] == server_ip) {
            /* Shift remaining servers */
            for (int j = i; j < dns_resolver.server_count - 1; j++) {
                dns_resolver.servers[j] = dns_resolver.servers[j + 1];
            }
            dns_resolver.server_count--;
            
            printf("DNS: Removed server ");
            print_ip(server_ip);
            printf("\n");
            
            pthread_mutex_unlock(&dns_resolver.lock);
            return 0;
        }
    }
    
    pthread_mutex_unlock(&dns_resolver.lock);
    return -1; /* Server not found */
}

void kos_dns_clear_servers(void) {
    pthread_mutex_lock(&dns_resolver.lock);
    dns_resolver.server_count = 0;
    printf("DNS: Cleared all servers\n");
    pthread_mutex_unlock(&dns_resolver.lock);
}

/* DNS response input processing */
int kos_dns_input(kos_packet_t* pkt) {
    if (!pkt || pkt->size < DNS_HEADER_SIZE) {
        return -1;
    }
    
    pthread_mutex_lock(&dns_stats.lock);
    dns_stats.responses_recv++;
    pthread_mutex_unlock(&dns_stats.lock);
    
    /* In a complete implementation, this would match responses to pending queries
     * and resolve the corresponding promises/callbacks */
    printf("DNS: Received response packet\n");
    
    return 0;
}

/* DNS cache and statistics */
void kos_dns_dump_cache(void) {
    pthread_mutex_lock(&dns_cache_lock);
    
    printf("DNS Cache:\n");
    printf("%-30s %-15s %-8s %-10s\n", "Name", "IP Address", "Type", "TTL");
    printf("--------------------------------------------------------------------\n");
    
    uint64_t current_time = get_current_time();
    int count = 0;
    
    for (int i = 0; i < DNS_CACHE_SIZE; i++) {
        dns_cache_entry_t* entry = dns_cache[i];
        while (entry) {
            if (entry->expiry > current_time) {
                printf("%-30s ", entry->name);
                print_ip(entry->ip_addr);
                printf("     %-8s %-10lu\n", 
                       (entry->type == DNS_TYPE_A) ? "A" : "?",
                       entry->expiry - current_time);
                count++;
            }
            entry = entry->next;
        }
    }
    
    printf("\nTotal entries: %d\n", count);
    pthread_mutex_unlock(&dns_cache_lock);
}

void kos_dns_dump_stats(void) {
    pthread_mutex_lock(&dns_stats.lock);
    
    printf("DNS Statistics:\n");
    printf("  Queries sent: %lu\n", dns_stats.queries_sent);
    printf("  Responses received: %lu\n", dns_stats.responses_recv);
    printf("  Cache hits: %lu, misses: %lu\n", 
           dns_stats.cache_hits, dns_stats.cache_misses);
    printf("  Timeouts: %lu\n", dns_stats.timeouts);
    printf("  Errors: %lu, NXDOMAIN: %lu, SERVFAIL: %lu\n",
           dns_stats.errors, dns_stats.nx_domain, dns_stats.server_fail);
    
    pthread_mutex_unlock(&dns_stats.lock);
}

void kos_dns_flush_cache(void) {
    pthread_mutex_lock(&dns_cache_lock);
    
    for (int i = 0; i < DNS_CACHE_SIZE; i++) {
        while (dns_cache[i]) {
            dns_cache_entry_t* entry = dns_cache[i];
            dns_cache[i] = entry->next;
            free(entry);
        }
    }
    
    printf("DNS: Cache flushed\n");
    pthread_mutex_unlock(&dns_cache_lock);
}

/* Initialize DNS subsystem */
int kos_dns_init(void) {
    memset(&dns_resolver, 0, sizeof(dns_resolver));
    dns_resolver.next_id = 1;
    
    if (pthread_mutex_init(&dns_resolver.lock, NULL) != 0) {
        return -1;
    }
    
    /* Initialize cache */
    for (int i = 0; i < DNS_CACHE_SIZE; i++) {
        dns_cache[i] = NULL;
    }
    
    /* Initialize statistics */
    memset(&dns_stats, 0, sizeof(dns_stats));
    if (pthread_mutex_init(&dns_stats.lock, NULL) != 0) {
        pthread_mutex_destroy(&dns_resolver.lock);
        return -1;
    }
    
    /* Add default DNS servers (Google DNS) */
    kos_dns_add_server(0x08080808); /* 8.8.8.8 */
    kos_dns_add_server(0x08080404); /* 8.8.4.4 */
    
    printf("DNS subsystem initialized\n");
    return 0;
}

/* Cleanup DNS subsystem */
void kos_dns_cleanup(void) {
    kos_dns_flush_cache();
    pthread_mutex_destroy(&dns_resolver.lock);
    pthread_mutex_destroy(&dns_stats.lock);
    printf("DNS subsystem cleaned up\n");
}