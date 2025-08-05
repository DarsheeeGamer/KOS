/*
 * KOS Routing Implementation
 * Handles routing table management, route lookup algorithms, and default gateway handling
 */

#include "netstack.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>

/* Route flags */
#define RTF_UP          0x0001  /* Route is up */
#define RTF_GATEWAY     0x0002  /* Destination is a gateway */
#define RTF_HOST        0x0004  /* Host entry (net otherwise) */
#define RTF_REINSTATE   0x0008  /* Reinstate route after timeout */
#define RTF_DYNAMIC     0x0010  /* Created dynamically by redirect */
#define RTF_MODIFIED    0x0020  /* Modified dynamically by redirect */
#define RTF_MTU         0x0040  /* Specific MTU for this route */
#define RTF_MSS         0x0080  /* Specific MSS for this route */
#define RTF_WINDOW      0x0100  /* Per route window clamping */
#define RTF_IRTT        0x0200  /* Initial round trip time */
#define RTF_REJECT      0x0400  /* Reject route */
#define RTF_STATIC      0x0800  /* Manually added */
#define RTF_XRESOLVE    0x1000  /* External resolver */
#define RTF_NOFORWARD   0x2000  /* Forwarding inhibited */
#define RTF_THROW       0x4000  /* Go to next rule */
#define RTF_NOPMTUDISC  0x8000  /* Do not send packets with DF */

/* Route table constants */
#define ROUTE_TABLE_SIZE    1024    /* Maximum routing table entries */

/* Global routing table */
static kos_route_t* route_table = NULL;
static pthread_mutex_t route_table_lock = PTHREAD_MUTEX_INITIALIZER;
static uint32_t route_count = 0;

/* Routing statistics */
static struct {
    uint64_t lookups;
    uint64_t cache_hits;
    uint64_t cache_misses;
    uint64_t route_adds;
    uint64_t route_dels;
    uint64_t no_route;
    uint64_t gc_runs;
    pthread_mutex_t lock;
} route_stats = {0};

/* Default gateway */
static uint32_t default_gateway = 0;
static kos_netif_t* default_interface = NULL;
static pthread_mutex_t default_gw_lock = PTHREAD_MUTEX_INITIALIZER;

/* Utility functions */
static void print_ip(uint32_t ip) {
    printf("%d.%d.%d.%d", 
           (ip >> 24) & 0xFF, (ip >> 16) & 0xFF,
           (ip >> 8) & 0xFF, ip & 0xFF);
}

static uint32_t ip_mask_len(uint32_t mask) {
    uint32_t len = 0;
    while (mask) {
        if (mask & 0x80000000) {
            len++;
            mask <<= 1;
        } else {
            break;
        }
    }
    return len;
}

static uint32_t ip_len_mask(uint32_t len) {
    if (len == 0) return 0;
    if (len >= 32) return 0xFFFFFFFF;
    return ~((1UL << (32 - len)) - 1);
}

static bool is_subnet_match(uint32_t addr, uint32_t dest, uint32_t mask) {
    return (addr & mask) == (dest & mask);
}

/* Route table management */
static kos_route_t* route_find_exact(uint32_t dest, uint32_t genmask) {
    kos_route_t* route = route_table;
    while (route) {
        if (route->dest == dest && route->genmask == genmask) {
            return route;
        }
        route = route->next;
    }
    return NULL;
}

static kos_route_t* route_find_best_match(uint32_t dest) {
    kos_route_t* best_route = NULL;
    uint32_t best_mask = 0;
    int best_metric = INT32_MAX;
    
    kos_route_t* route = route_table;
    while (route) {
        /* Check if route is up */
        if (!(route->flags & RTF_UP)) {
            route = route->next;
            continue;
        }
        
        /* Check if destination matches */
        if (is_subnet_match(dest, route->dest, route->genmask)) {
            /* Prefer more specific routes (longer prefix) */
            if (route->genmask > best_mask ||
                (route->genmask == best_mask && route->metric < best_metric)) {
                best_route = route;
                best_mask = route->genmask;
                best_metric = route->metric;
            }
        }
        route = route->next;
    }
    
    return best_route;
}

static int route_insert(kos_route_t* new_route) {
    if (route_count >= ROUTE_TABLE_SIZE) {
        return -1; /* Route table full */
    }
    
    /* Insert at head for simplicity */
    new_route->next = route_table;
    route_table = new_route;
    route_count++;
    
    return 0;
}

static int route_remove(kos_route_t* target_route) {
    kos_route_t* route = route_table;
    kos_route_t* prev = NULL;
    
    while (route) {
        if (route == target_route) {
            if (prev) {
                prev->next = route->next;
            } else {
                route_table = route->next;
            }
            free(route);
            route_count--;
            return 0;
        }
        prev = route;
        route = route->next;
    }
    
    return -1; /* Route not found */
}

/* Add route to routing table */
int kos_route_add(uint32_t dest, uint32_t gateway, uint32_t genmask, kos_netif_t* netif) {
    if (!netif) {
        return -1;
    }
    
    pthread_mutex_lock(&route_table_lock);
    
    /* Check if route already exists */
    kos_route_t* existing = route_find_exact(dest, genmask);
    if (existing) {
        /* Update existing route */
        existing->gateway = gateway;
        existing->interface = netif;
        existing->flags |= RTF_UP;
        if (gateway != 0) {
            existing->flags |= RTF_GATEWAY;
        }
        
        printf("Updated route: ");
        print_ip(dest);
        printf("/%u via ", ip_mask_len(genmask));
        if (gateway != 0) {
            print_ip(gateway);
        } else {
            printf("direct");
        }
        printf(" dev %s\n", netif->name);
        
        pthread_mutex_unlock(&route_table_lock);
        return 0;
    }
    
    /* Create new route */
    kos_route_t* route = malloc(sizeof(kos_route_t));
    if (!route) {
        pthread_mutex_unlock(&route_table_lock);
        return -1;
    }
    
    route->dest = dest;
    route->gateway = gateway;
    route->genmask = genmask;
    route->flags = RTF_UP | RTF_STATIC;
    route->metric = 0;
    route->ref = 0;
    route->use = 0;
    route->interface = netif;
    route->next = NULL;
    
    if (gateway != 0) {
        route->flags |= RTF_GATEWAY;
    }
    
    /* Handle default route */
    if (dest == 0 && genmask == 0) {
        pthread_mutex_lock(&default_gw_lock);
        default_gateway = gateway;
        default_interface = netif;
        pthread_mutex_unlock(&default_gw_lock);
        printf("Set default gateway to ");
        print_ip(gateway);
        printf(" via %s\n", netif->name);
    }
    
    if (route_insert(route) < 0) {
        free(route);
        pthread_mutex_unlock(&route_table_lock);
        return -1;
    }
    
    pthread_mutex_lock(&route_stats.lock);
    route_stats.route_adds++;
    pthread_mutex_unlock(&route_stats.lock);
    
    printf("Added route: ");
    print_ip(dest);
    printf("/%u via ", ip_mask_len(genmask));
    if (gateway != 0) {
        print_ip(gateway);
    } else {
        printf("direct");
    }
    printf(" dev %s\n", netif->name);
    
    pthread_mutex_unlock(&route_table_lock);
    return 0;
}

/* Delete route from routing table */
int kos_route_del(uint32_t dest, uint32_t genmask) {
    pthread_mutex_lock(&route_table_lock);
    
    kos_route_t* route = route_find_exact(dest, genmask);
    if (!route) {
        pthread_mutex_unlock(&route_table_lock);
        return -1; /* Route not found */
    }
    
    /* Handle default route removal */
    if (dest == 0 && genmask == 0) {
        pthread_mutex_lock(&default_gw_lock);
        default_gateway = 0;
        default_interface = NULL;
        pthread_mutex_unlock(&default_gw_lock);
        printf("Removed default gateway\n");
    }
    
    printf("Deleted route: ");
    print_ip(dest);
    printf("/%u\n", ip_mask_len(genmask));
    
    route_remove(route);
    
    pthread_mutex_lock(&route_stats.lock);
    route_stats.route_dels++;
    pthread_mutex_unlock(&route_stats.lock);
    
    pthread_mutex_unlock(&route_table_lock);
    return 0;
}

/* Lookup route for destination */
kos_route_t* kos_route_lookup(uint32_t dest) {
    pthread_mutex_lock(&route_table_lock);
    pthread_mutex_lock(&route_stats.lock);
    route_stats.lookups++;
    pthread_mutex_unlock(&route_stats.lock);
    
    kos_route_t* route = route_find_best_match(dest);
    
    if (route) {
        route->use++;
        pthread_mutex_lock(&route_stats.lock);
        route_stats.cache_hits++;
        pthread_mutex_unlock(&route_stats.lock);
    } else {
        pthread_mutex_lock(&route_stats.lock);
        route_stats.cache_misses++;
        route_stats.no_route++;
        pthread_mutex_unlock(&route_stats.lock);
    }
    
    pthread_mutex_unlock(&route_table_lock);
    return route;
}

/* Get default gateway */
uint32_t kos_route_get_default_gw(void) {
    pthread_mutex_lock(&default_gw_lock);
    uint32_t gw = default_gateway;
    pthread_mutex_unlock(&default_gw_lock);
    return gw;
}

/* Get default interface */
kos_netif_t* kos_route_get_default_if(void) {
    pthread_mutex_lock(&default_gw_lock);
    kos_netif_t* netif = default_interface;
    pthread_mutex_unlock(&default_gw_lock);
    return netif;
}

/* Set default gateway */
int kos_route_set_default_gw(uint32_t gateway, kos_netif_t* netif) {
    if (!netif) {
        return -1;
    }
    
    /* Add/update default route */
    int result = kos_route_add(0, gateway, 0, netif);
    
    if (result == 0) {
        pthread_mutex_lock(&default_gw_lock);
        default_gateway = gateway;
        default_interface = netif;
        pthread_mutex_unlock(&default_gw_lock);
    }
    
    return result;
}

/* Add direct route for network interface */
int kos_route_add_interface_route(kos_netif_t* netif) {
    if (!netif || netif->ip_addr == 0 || netif->netmask == 0) {
        return -1;
    }
    
    uint32_t network = netif->ip_addr & netif->netmask;
    
    return kos_route_add(network, 0, netif->netmask, netif);
}

/* Remove direct route for network interface */
int kos_route_del_interface_route(kos_netif_t* netif) {
    if (!netif || netif->ip_addr == 0 || netif->netmask == 0) {
        return -1;
    }
    
    uint32_t network = netif->ip_addr & netif->netmask;
    
    return kos_route_del(network, netif->netmask);
}

/* Check if destination is reachable */
bool kos_route_is_reachable(uint32_t dest) {
    kos_route_t* route = kos_route_lookup(dest);
    return (route != NULL);
}

/* Get next hop for destination */
uint32_t kos_route_get_nexthop(uint32_t dest) {
    kos_route_t* route = kos_route_lookup(dest);
    if (!route) {
        return 0; /* No route */
    }
    
    /* If it's a direct route, next hop is the destination */
    if (route->gateway == 0) {
        return dest;
    }
    
    /* Otherwise, next hop is the gateway */
    return route->gateway;
}

/* Get output interface for destination */
kos_netif_t* kos_route_get_output_if(uint32_t dest) {
    kos_route_t* route = kos_route_lookup(dest);
    if (!route) {
        return NULL;
    }
    
    return route->interface;
}

/* Flush routing table */
void kos_route_flush(void) {
    pthread_mutex_lock(&route_table_lock);
    
    while (route_table) {
        kos_route_t* route = route_table;
        route_table = route->next;
        free(route);
    }
    
    route_count = 0;
    
    pthread_mutex_lock(&default_gw_lock);
    default_gateway = 0;
    default_interface = NULL;
    pthread_mutex_unlock(&default_gw_lock);
    
    printf("Routing table flushed\n");
    
    pthread_mutex_unlock(&route_table_lock);
}

/* Dump routing table */
void kos_route_dump(void) {
    pthread_mutex_lock(&route_table_lock);
    
    printf("Kernel IP routing table\n");
    printf("%-18s %-18s %-18s %-8s %-6s %-6s %-6s %-10s\n",
           "Destination", "Gateway", "Genmask", "Flags", "Metric", "Ref", "Use", "Iface");
    printf("--------------------------------------------------------------------------------\n");
    
    kos_route_t* route = route_table;
    while (route) {
        /* Destination */
        if (route->dest == 0 && route->genmask == 0) {
            printf("%-18s ", "default");
        } else {
            char dest_str[20];
            snprintf(dest_str, sizeof(dest_str), "%d.%d.%d.%d",
                     (route->dest >> 24) & 0xFF, (route->dest >> 16) & 0xFF,
                     (route->dest >> 8) & 0xFF, route->dest & 0xFF);
            printf("%-18s ", dest_str);
        }
        
        /* Gateway */
        if (route->gateway == 0) {
            printf("%-18s ", "*");
        } else {
            char gw_str[20];
            snprintf(gw_str, sizeof(gw_str), "%d.%d.%d.%d",
                     (route->gateway >> 24) & 0xFF, (route->gateway >> 16) & 0xFF,
                     (route->gateway >> 8) & 0xFF, route->gateway & 0xFF);
            printf("%-18s ", gw_str);
        }
        
        /* Genmask */
        char mask_str[20];
        snprintf(mask_str, sizeof(mask_str), "%d.%d.%d.%d",
                 (route->genmask >> 24) & 0xFF, (route->genmask >> 16) & 0xFF,
                 (route->genmask >> 8) & 0xFF, route->genmask & 0xFF);
        printf("%-18s ", mask_str);
        
        /* Flags */
        char flags_str[10] = {0};
        int flag_pos = 0;
        if (route->flags & RTF_UP) flags_str[flag_pos++] = 'U';
        if (route->flags & RTF_GATEWAY) flags_str[flag_pos++] = 'G';
        if (route->flags & RTF_HOST) flags_str[flag_pos++] = 'H';
        if (route->flags & RTF_DYNAMIC) flags_str[flag_pos++] = 'D';
        if (route->flags & RTF_MODIFIED) flags_str[flag_pos++] = 'M';
        printf("%-8s ", flags_str);
        
        /* Metric, Ref, Use */
        printf("%-6d %-6d %-6d ", route->metric, route->ref, route->use);
        
        /* Interface */
        printf("%-10s\n", route->interface ? route->interface->name : "none");
        
        route = route->next;
    }
    
    printf("\nTotal routes: %u\n", route_count);
    pthread_mutex_unlock(&route_table_lock);
}

/* Dump routing statistics */
void kos_route_dump_stats(void) {
    pthread_mutex_lock(&route_stats.lock);
    
    printf("Routing Statistics:\n");
    printf("  Lookups: %lu\n", route_stats.lookups);
    printf("  Cache hits: %lu, misses: %lu\n", 
           route_stats.cache_hits, route_stats.cache_misses);
    printf("  Routes added: %lu, deleted: %lu\n",
           route_stats.route_adds, route_stats.route_dels);
    printf("  No route: %lu\n", route_stats.no_route);
    printf("  GC runs: %lu\n", route_stats.gc_runs);
    
    pthread_mutex_unlock(&route_stats.lock);
}

/* Route garbage collection */
void kos_route_gc(void) {
    pthread_mutex_lock(&route_table_lock);
    pthread_mutex_lock(&route_stats.lock);
    route_stats.gc_runs++;
    pthread_mutex_unlock(&route_stats.lock);
    
    /* Remove unused dynamic routes */
    kos_route_t* route = route_table;
    kos_route_t* prev = NULL;
    
    while (route) {
        kos_route_t* next = route->next;
        
        /* Remove dynamic routes that haven't been used recently */
        if ((route->flags & RTF_DYNAMIC) && route->use == 0) {
            if (prev) {
                prev->next = next;
            } else {
                route_table = next;
            }
            free(route);
            route_count--;
        } else {
            /* Reset use counter for next GC cycle */
            route->use = 0;
            prev = route;
        }
        
        route = next;
    }
    
    pthread_mutex_unlock(&route_table_lock);
}

/* Initialize routing subsystem */
int kos_route_init(void) {
    route_table = NULL;
    route_count = 0;
    default_gateway = 0;
    default_interface = NULL;
    
    memset(&route_stats, 0, sizeof(route_stats));
    if (pthread_mutex_init(&route_stats.lock, NULL) != 0) {
        return -1;
    }
    
    printf("Routing subsystem initialized\n");
    return 0;
}

/* Cleanup routing subsystem */
void kos_route_cleanup(void) {
    kos_route_flush();
    pthread_mutex_destroy(&route_stats.lock);
    printf("Routing subsystem cleaned up\n");
}