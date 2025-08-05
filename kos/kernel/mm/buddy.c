#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* Global memory zones */
static struct zone zones[MAX_ZONES];
static struct page *mem_map = NULL;
static unsigned long max_pfn = 0;
static unsigned long min_pfn = 0;
static bool buddy_initialized = false;

/* Zone names */
static const char *zone_names[] = {
    "DMA",
    "Normal", 
    "HighMem"
};

/* Convert between pages and physical frame numbers */
static inline unsigned long page_to_pfn(struct page *page)
{
    return page - mem_map + min_pfn;
}

static inline struct page *pfn_to_page(unsigned long pfn)
{
    if (pfn < min_pfn || pfn >= max_pfn)
        return NULL;
    return &mem_map[pfn - min_pfn];
}

static inline void *page_address(struct page *page)
{
    return (void *)(page_to_pfn(page) << PAGE_SHIFT);
}

static inline struct page *virt_to_page(void *addr)
{
    unsigned long pfn = (unsigned long)addr >> PAGE_SHIFT;
    return pfn_to_page(pfn);
}

/* Get buddy page for a given page at order */
static inline struct page *get_buddy_page(struct page *page, unsigned int order)
{
    unsigned long pfn = page_to_pfn(page);
    unsigned long buddy_pfn = pfn ^ (1UL << order);
    return pfn_to_page(buddy_pfn);
}

/* Check if two pages are buddies */
static inline bool page_is_buddy(struct page *page, struct page *buddy, unsigned int order)
{
    if (!buddy || buddy->order != order)
        return false;
    
    unsigned long pfn = page_to_pfn(page);
    unsigned long buddy_pfn = page_to_pfn(buddy);
    
    /* Both pages must be free and aligned properly */
    if (!(page->flags & (1UL << PG_RESERVED)) || 
        !(buddy->flags & (1UL << PG_RESERVED)))
        return false;
    
    return (pfn ^ buddy_pfn) == (1UL << order);
}

/* Remove page from free list */
static void rmv_page_order(struct page *page)
{
    list_del(&page->lru);
    page->zone->free_area[page->order].nr_free--;
    page->order = -1;
}

/* Add page to free list at given order */
static void add_page_order(struct page *page, struct zone *zone, unsigned int order)
{
    page->order = order;
    list_add(&page->lru, &zone->free_area[order].free_list);
    zone->free_area[order].nr_free++;
}

/* Initialize a memory zone */
static void zone_init(struct zone *zone, const char *name, 
                     unsigned long start_pfn, unsigned long size)
{
    int i;
    
    strncpy(zone->name, name, sizeof(zone->name) - 1);
    zone->name[sizeof(zone->name) - 1] = '\0';
    
    zone->zone_start_pfn = start_pfn;
    zone->zone_size = size;
    zone->free_pages = 0;
    zone->pages_min = size / 64;
    zone->pages_low = size / 32;
    zone->pages_high = size / 16;
    zone->nr_active = 0;
    zone->nr_inactive = 0;
    
    INIT_LIST_HEAD(&zone->active_list);
    INIT_LIST_HEAD(&zone->inactive_list);
    
    /* Initialize free areas */
    for (i = 0; i <= BUDDY_MAX_ORDER; i++) {
        INIT_LIST_HEAD(&zone->free_area[i].free_list);
        zone->free_area[i].nr_free = 0;
    }
}

/* Initialize the buddy allocator */
void buddy_init(void)
{
    if (buddy_initialized)
        return;
    
    /* Initialize zones with default values */
    zone_init(&zones[ZONE_DMA], zone_names[ZONE_DMA], 0, 0);
    zone_init(&zones[ZONE_NORMAL], zone_names[ZONE_NORMAL], 0, 0);
    zone_init(&zones[ZONE_HIGHMEM], zone_names[ZONE_HIGHMEM], 0, 0);
    
    buddy_initialized = true;
    printf("Buddy allocator initialized\n");
}

/* Add memory range to buddy allocator */
void buddy_add_memory(unsigned long start_pfn, unsigned long end_pfn)
{
    unsigned long pfn, nr_pages;
    struct page *page;
    struct zone *zone;
    int i;
    
    if (!buddy_initialized) {
        buddy_init();
    }
    
    nr_pages = end_pfn - start_pfn;
    
    /* Allocate memory map if not already done */
    if (!mem_map) {
        min_pfn = start_pfn;
        max_pfn = end_pfn;
        mem_map = calloc(nr_pages, sizeof(struct page));
        if (!mem_map) {
            printf("Failed to allocate memory map\n");
            return;
        }
    } else {
        /* Extend existing memory map */
        if (start_pfn < min_pfn) {
            unsigned long new_pages = min_pfn - start_pfn;
            struct page *new_map = calloc(nr_pages + max_pfn - min_pfn, sizeof(struct page));
            if (!new_map) {
                printf("Failed to extend memory map\n");
                return;
            }
            memcpy(new_map + new_pages, mem_map, (max_pfn - min_pfn) * sizeof(struct page));
            free(mem_map);
            mem_map = new_map;
            min_pfn = start_pfn;
        }
        if (end_pfn > max_pfn) {
            max_pfn = end_pfn;
        }
    }
    
    /* Determine zone - for simplicity, put everything in ZONE_NORMAL */
    zone = &zones[ZONE_NORMAL];
    if (zone->zone_size == 0) {
        zone_init(zone, zone_names[ZONE_NORMAL], start_pfn, nr_pages);
    } else {
        zone->zone_size += nr_pages;
    }
    
    /* Initialize pages and add to free lists */
    for (pfn = start_pfn; pfn < end_pfn; pfn++) {
        page = pfn_to_page(pfn);
        page->flags = 1UL << PG_RESERVED; /* Mark as free */
        page->count = 0;
        page->zone = zone;
        page->order = -1;
        INIT_LIST_HEAD(&page->lru);
        
        /* Add single pages to order 0 initially */
        if (pfn < end_pfn) {
            add_page_order(page, zone, 0);
            zone->free_pages++;
        }
    }
    
    /* Coalesce pages into higher orders */
    for (i = 0; i < BUDDY_MAX_ORDER; i++) {
        struct list_head *pos, *tmp;
        list_for_each_safe(pos, tmp, &zone->free_area[i].free_list) {
            page = list_entry(pos, struct page, lru);
            struct page *buddy = get_buddy_page(page, i);
            
            if (buddy && page_is_buddy(page, buddy, i)) {
                /* Remove both pages from current order */
                rmv_page_order(page);
                rmv_page_order(buddy);
                
                /* Add the lower-addressed page to next order */
                struct page *combined = (page < buddy) ? page : buddy;
                add_page_order(combined, zone, i + 1);
            }
        }
    }
    
    printf("Added memory range: 0x%lx - 0x%lx (%lu pages) to zone %s\n",
           start_pfn, end_pfn, nr_pages, zone->name);
}

/* Internal allocation function */
struct page *__alloc_pages(unsigned int gfp_mask, unsigned int order, struct zone *zone)
{
    struct page *page = NULL;
    struct free_area *area;
    unsigned int current_order;
    
    if (order > BUDDY_MAX_ORDER) {
        return NULL;
    }
    
    if (!zone) {
        /* Default to normal zone */
        zone = &zones[ZONE_NORMAL];
    }
    
    /* Try to find a free block of the requested order or higher */
    for (current_order = order; current_order <= BUDDY_MAX_ORDER; current_order++) {
        area = &zone->free_area[current_order];
        
        if (list_empty(&area->free_list))
            continue;
        
        /* Found a free block */
        page = list_entry(area->free_list.next, struct page, lru);
        rmv_page_order(page);
        zone->free_pages -= (1UL << current_order);
        
        /* Split the block if it's larger than needed */
        while (current_order > order) {
            current_order--;
            struct page *buddy = page + (1UL << current_order);
            add_page_order(buddy, zone, current_order);
            zone->free_pages += (1UL << current_order);
        }
        
        /* Mark page as allocated */
        page->flags &= ~(1UL << PG_RESERVED);
        page->count = 1;
        page->order = order;
        
        break;
    }
    
    return page;
}

/* Allocate pages */
struct page *alloc_pages(unsigned int gfp_mask, unsigned int order)
{
    struct zone *zone = NULL;
    
    /* Select zone based on GFP flags */
    if (gfp_mask & GFP_DMA) {
        zone = &zones[ZONE_DMA];
    } else if (gfp_mask & GFP_HIGHMEM) {
        zone = &zones[ZONE_HIGHMEM];
    } else {
        zone = &zones[ZONE_NORMAL];
    }
    
    return __alloc_pages(gfp_mask, order, zone);
}

/* Internal free function */
void __free_pages(struct page *page, unsigned int order)
{
    struct zone *zone;
    struct page *buddy;
    unsigned int combined_order = order;
    
    if (!page || page->count <= 0) {
        return;
    }
    
    page->count--;
    if (page->count > 0) {
        return; /* Still referenced */
    }
    
    zone = page->zone;
    page->flags |= (1UL << PG_RESERVED); /* Mark as free */
    
    /* Coalesce with buddies */
    while (combined_order < BUDDY_MAX_ORDER) {
        buddy = get_buddy_page(page, combined_order);
        
        if (!buddy || !page_is_buddy(page, buddy, combined_order)) {
            break;
        }
        
        /* Remove buddy from free list */
        rmv_page_order(buddy);
        zone->free_pages -= (1UL << combined_order);
        
        /* Combine with buddy */
        if (page > buddy) {
            page = buddy;
        }
        combined_order++;
    }
    
    /* Add combined block to free list */
    add_page_order(page, zone, combined_order);
    zone->free_pages += (1UL << combined_order);
}

/* Free pages */
void free_pages(struct page *page, unsigned int order)
{
    __free_pages(page, order);
}

/* Get memory statistics */
void get_buddy_stats(void)
{
    int i, j;
    struct zone *zone;
    
    printf("\nBuddy Allocator Statistics:\n");
    printf("==========================\n");
    
    for (i = 0; i < MAX_ZONES; i++) {
        zone = &zones[i];
        
        if (zone->zone_size == 0)
            continue;
        
        printf("Zone %s:\n", zone->name);
        printf("  Start PFN: %lu\n", zone->zone_start_pfn);
        printf("  Size: %lu pages (%lu KB)\n", zone->zone_size, 
               zone->zone_size * PAGE_SIZE / 1024);
        printf("  Free pages: %lu (%lu KB)\n", zone->free_pages,
               zone->free_pages * PAGE_SIZE / 1024);
        printf("  Free areas:\n");
        
        for (j = 0; j <= BUDDY_MAX_ORDER; j++) {
            if (zone->free_area[j].nr_free > 0) {
                printf("    Order %d: %lu blocks (%lu pages)\n",
                       j, zone->free_area[j].nr_free,
                       zone->free_area[j].nr_free << j);
            }
        }
        printf("\n");
    }
}

/* Check buddy allocator consistency */
bool check_buddy_consistency(void)
{
    int i, j;
    struct zone *zone;
    struct list_head *pos;
    struct page *page;
    bool consistent = true;
    
    for (i = 0; i < MAX_ZONES; i++) {
        zone = &zones[i];
        
        if (zone->zone_size == 0)
            continue;
        
        for (j = 0; j <= BUDDY_MAX_ORDER; j++) {
            unsigned long count = 0;
            
            list_for_each(pos, &zone->free_area[j].free_list) {
                page = list_entry(pos, struct page, lru);
                
                if (page->order != j) {
                    printf("ERROR: Page order mismatch in zone %s order %d\n",
                           zone->name, j);
                    consistent = false;
                }
                
                if (!(page->flags & (1UL << PG_RESERVED))) {
                    printf("ERROR: Non-free page in free list zone %s order %d\n",
                           zone->name, j);
                    consistent = false;
                }
                
                count++;
            }
            
            if (count != zone->free_area[j].nr_free) {
                printf("ERROR: Free count mismatch in zone %s order %d: "
                       "counted %lu, recorded %lu\n",
                       zone->name, j, count, zone->free_area[j].nr_free);
                consistent = false;
            }
        }
    }
    
    return consistent;
}