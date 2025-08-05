#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* Size-indexed caches for kmalloc */
static struct kmem_cache *malloc_sizes[13]; /* 32, 64, 96, 128, 192, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768 */
static const size_t cache_sizes[] = {
    32, 64, 96, 128, 192, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768
};
static const int num_cache_sizes = sizeof(cache_sizes) / sizeof(cache_sizes[0]);

/* Large allocation tracking */
struct large_alloc {
    struct list_head list;
    void *addr;
    size_t size;
    unsigned int order;
};

static LIST_HEAD(large_alloc_list);
static bool kmalloc_initialized = false;

/* Initialize kmalloc subsystem */
void kmalloc_init(void)
{
    int i;
    char cache_name[32];
    
    if (kmalloc_initialized)
        return;
    
    /* Initialize slab allocator first */
    if (!slab_initialized) {
        slab_init();
    }
    
    /* Create size-indexed caches */
    for (i = 0; i < num_cache_sizes; i++) {
        snprintf(cache_name, sizeof(cache_name), "kmalloc-%zu", cache_sizes[i]);
        malloc_sizes[i] = kmem_cache_create(cache_name, cache_sizes[i], 
                                          BYTES_PER_WORD, 0, NULL);
        if (!malloc_sizes[i]) {
            printf("Failed to create kmalloc cache for size %zu\n", cache_sizes[i]);
        }
    }
    
    kmalloc_initialized = true;
    printf("kmalloc initialized with %d size caches\n", num_cache_sizes);
}

/* Find appropriate cache for size */
static struct kmem_cache *find_cache_for_size(size_t size)
{
    int i;
    
    for (i = 0; i < num_cache_sizes; i++) {
        if (size <= cache_sizes[i]) {
            return malloc_sizes[i];
        }
    }
    
    return NULL; /* Too large for caches */
}

/* Calculate order needed for large allocation */
static unsigned int size_to_order(size_t size)
{
    unsigned int order = 0;
    size_t pages = (size + PAGE_SIZE - 1) >> PAGE_SHIFT;
    
    while ((1UL << order) < pages) {
        order++;
    }
    
    return order;
}

/* Track large allocation */
static void track_large_alloc(void *addr, size_t size, unsigned int order)
{
    struct large_alloc *alloc = malloc(sizeof(struct large_alloc));
    if (alloc) {
        alloc->addr = addr;
        alloc->size = size;
        alloc->order = order;
        INIT_LIST_HEAD(&alloc->list);
        list_add(&alloc->list, &large_alloc_list);
    }
}

/* Find and remove large allocation tracking */
static struct large_alloc *find_large_alloc(const void *addr)
{
    struct large_alloc *alloc;
    struct list_head *pos, *tmp;
    
    list_for_each_safe(pos, tmp, &large_alloc_list) {
        alloc = list_entry(pos, struct large_alloc, list);
        if (alloc->addr == addr) {
            list_del(&alloc->list);
            return alloc;
        }
    }
    
    return NULL;
}

/* Allocate kernel memory */
void *kmalloc(size_t size, unsigned int flags)
{
    struct kmem_cache *cache;
    struct page *page;
    void *ptr = NULL;
    unsigned int order;
    
    if (!kmalloc_initialized) {
        kmalloc_init();
    }
    
    if (size == 0) {
        return NULL;
    }
    
    /* Handle large allocations directly with buddy allocator */
    if (size > KMALLOC_MAX_SIZE) {
        order = size_to_order(size);
        page = alloc_pages(flags, order);
        if (page) {
            ptr = page_address(page);
            track_large_alloc(ptr, size, order);
        }
        return ptr;
    }
    
    /* Find appropriate cache */
    cache = find_cache_for_size(size);
    if (!cache) {
        /* Fallback to buddy allocator for large sizes */
        order = size_to_order(size);
        page = alloc_pages(flags, order);
        if (page) {
            ptr = page_address(page);
            track_large_alloc(ptr, size, order);
        }
        return ptr;
    }
    
    /* Allocate from slab cache */
    ptr = kmem_cache_alloc(cache, flags);
    
    return ptr;
}

/* Allocate zeroed kernel memory */
void *kzalloc(size_t size, unsigned int flags)
{
    void *ptr = kmalloc(size, flags);
    if (ptr) {
        memset(ptr, 0, size);
    }
    return ptr;
}

/* Free kernel memory */
void kfree(const void *ptr)
{
    struct page *page;
    struct kmem_cache *cache;
    struct large_alloc *alloc;
    
    if (!ptr)
        return;
    
    /* Check if it's a large allocation */
    alloc = find_large_alloc(ptr);
    if (alloc) {
        page = virt_to_page((void *)ptr);
        if (page) {
            free_pages(page, alloc->order);
        }
        free(alloc);
        return;
    }
    
    /* Get page for this address */
    page = virt_to_page((void *)ptr);
    if (!page) {
        printf("kfree: invalid pointer %p\n", ptr);
        return;
    }
    
    /* Check if it's from a slab */
    if (page->flags & (1UL << PG_SLAB)) {
        cache = (struct kmem_cache *)page->private;
        if (cache) {
            kmem_cache_free(cache, (void *)ptr);
        } else {
            printf("kfree: slab page with no cache\n");
        }
    } else {
        printf("kfree: cannot determine allocation type for %p\n", ptr);
    }
}

/* Reallocate kernel memory */
void *krealloc(const void *ptr, size_t new_size, unsigned int flags)
{
    void *new_ptr;
    size_t old_size = 0;
    struct page *page;
    struct kmem_cache *cache;
    struct large_alloc *alloc;
    int i;
    
    if (!ptr) {
        return kmalloc(new_size, flags);
    }
    
    if (new_size == 0) {
        kfree(ptr);
        return NULL;
    }
    
    /* Determine old size */
    alloc = find_large_alloc(ptr);
    if (alloc) {
        old_size = alloc->size;
        /* Re-add to list since find_large_alloc removed it */
        list_add(&alloc->list, &large_alloc_list);
    } else {
        page = virt_to_page((void *)ptr);
        if (page && (page->flags & (1UL << PG_SLAB))) {
            cache = (struct kmem_cache *)page->private;
            if (cache) {
                old_size = cache->objsize;
            }
        }
    }
    
    if (old_size == 0) {
        printf("krealloc: cannot determine old size\n");
        return NULL;
    }
    
    /* Allocate new memory */
    new_ptr = kmalloc(new_size, flags);
    if (!new_ptr) {
        return NULL;
    }
    
    /* Copy old data */
    memcpy(new_ptr, ptr, (old_size < new_size) ? old_size : new_size);
    
    /* Free old memory */
    kfree(ptr);
    
    return new_ptr;
}

/* Get allocation size */
size_t ksize(const void *ptr)
{
    struct page *page;
    struct kmem_cache *cache;
    struct large_alloc *alloc;
    
    if (!ptr)
        return 0;
    
    /* Check if it's a large allocation */
    list_for_each_entry(alloc, &large_alloc_list, list) {
        if (alloc->addr == ptr) {
            return alloc->size;
        }
    }
    
    /* Check slab allocation */
    page = virt_to_page((void *)ptr);
    if (page && (page->flags & (1UL << PG_SLAB))) {
        cache = (struct kmem_cache *)page->private;
        if (cache) {
            return cache->objsize;
        }
    }
    
    return 0;
}

/* Get kmalloc statistics */
void kmalloc_info(void)
{
    int i;
    struct large_alloc *alloc;
    unsigned int large_count = 0;
    size_t large_size = 0;
    
    printf("\nKmalloc Information:\n");
    printf("===================\n");
    
    /* Show cache-based allocations */
    printf("Size-indexed caches:\n");
    for (i = 0; i < num_cache_sizes; i++) {
        if (malloc_sizes[i]) {
            struct kmem_cache *cache = malloc_sizes[i];
            struct list_head *pos;
            unsigned int slabs = 0, used_objs = 0, total_objs = 0;
            
            /* Count slabs and objects */
            list_for_each(pos, &cache->slabs_full) {
                slabs++;
                total_objs += cache->num;
                used_objs += cache->num;
            }
            
            list_for_each(pos, &cache->slabs_partial) {
                struct slab_mgmt *slab = (struct slab_mgmt *)
                    ((char *)pos - offsetof(struct slab_mgmt, list));
                slabs++;
                total_objs += cache->num;
                used_objs += slab->inuse;
            }
            
            list_for_each(pos, &cache->slabs_free) {
                slabs++;
                total_objs += cache->num;
            }
            
            printf("  %-20s: %4zu bytes, %3u slabs, %5u/%5u objects\n",
                   cache->name, cache_sizes[i], slabs, used_objs, total_objs);
        }
    }
    
    /* Show large allocations */
    list_for_each_entry(alloc, &large_alloc_list, list) {
        large_count++;
        large_size += alloc->size;
    }
    
    printf("\nLarge allocations: %u allocations, %zu bytes total\n",
           large_count, large_size);
}

/* Check for memory leaks in kmalloc */
void kmalloc_check_leaks(void)
{
    struct large_alloc *alloc;
    unsigned int leak_count = 0;
    size_t leak_size = 0;
    
    printf("\nKmalloc Leak Check:\n");
    printf("==================\n");
    
    list_for_each_entry(alloc, &large_alloc_list, list) {
        printf("LEAK: %p size %zu order %u\n", 
               alloc->addr, alloc->size, alloc->order);
        leak_count++;
        leak_size += alloc->size;
    }
    
    if (leak_count == 0) {
        printf("No large allocation leaks detected\n");
    } else {
        printf("Found %u leaked allocations, %zu bytes total\n",
               leak_count, leak_size);
    }
}

/* Stress test kmalloc */
void kmalloc_stress_test(void)
{
    void *ptrs[1000];
    int i, j;
    size_t sizes[] = {16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192};
    int num_sizes = sizeof(sizes) / sizeof(sizes[0]);
    
    printf("\nKmalloc stress test starting...\n");
    
    /* Test various allocation sizes */
    for (j = 0; j < 10; j++) {
        for (i = 0; i < 1000; i++) {
            size_t size = sizes[i % num_sizes];
            ptrs[i] = kmalloc(size, GFP_KERNEL);
            if (ptrs[i]) {
                memset(ptrs[i], 0xAA, size);
            }
        }
        
        /* Free half randomly */
        for (i = 0; i < 500; i++) {
            int idx = rand() % 1000;
            if (ptrs[idx]) {
                kfree(ptrs[idx]);
                ptrs[idx] = NULL;
            }
        }
        
        /* Free the rest */
        for (i = 0; i < 1000; i++) {
            if (ptrs[i]) {
                kfree(ptrs[i]);
                ptrs[i] = NULL;
            }
        }
    }
    
    printf("Kmalloc stress test completed\n");
}