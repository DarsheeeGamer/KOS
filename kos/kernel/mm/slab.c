#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* Global slab cache list */
static LIST_HEAD(cache_chain);
static bool slab_initialized = false;

/* Slab coloring */
#define SLAB_COLOUR_MAX 16
static int slab_colour = 0;

/* Object alignment */
#define BYTES_PER_WORD sizeof(void *)
#define SLAB_OBJ_MIN_SIZE BYTES_PER_WORD
#define SLAB_ALIGN_MASK (BYTES_PER_WORD - 1)

/* Slab management structure */
struct slab_mgmt {
    struct list_head list;
    unsigned int colouroff;
    void *s_mem;
    unsigned int inuse;
    unsigned int free;
    unsigned short freelist[0];
};

/* Free object tracking */
struct slab_free_obj {
    struct slab_free_obj *next;
};

/* Calculate slab size and number of objects */
static void calculate_slab_order(struct kmem_cache *cache)
{
    unsigned int objsize = cache->size;
    unsigned int align = cache->align;
    unsigned int left_over, slab_size;
    unsigned int order;
    
    /* Ensure minimum alignment */
    if (align < SLAB_OBJ_MIN_SIZE)
        align = SLAB_OBJ_MIN_SIZE;
    
    /* Round object size up to alignment */
    objsize = (objsize + align - 1) & ~(align - 1);
    cache->objsize = objsize;
    
    /* Try different orders to find optimal slab size */
    for (order = 0; order <= BUDDY_MAX_ORDER; order++) {
        slab_size = PAGE_SIZE << order;
        
        /* Reserve space for slab management structure */
        left_over = slab_size - sizeof(struct slab_mgmt);
        
        /* Calculate number of objects that fit */
        cache->num = left_over / (objsize + sizeof(unsigned short));
        
        if (cache->num > 0) {
            cache->gfporder = order;
            break;
        }
    }
    
    if (cache->num == 0) {
        printf("Failed to calculate slab parameters for cache %s\n", cache->name);
        cache->gfporder = 1;
        cache->num = 1;
    }
}

/* Allocate a new slab */
static struct slab_mgmt *slab_alloc(struct kmem_cache *cache)
{
    struct page *page;
    struct slab_mgmt *slab;
    unsigned int i;
    void *objp;
    
    /* Allocate pages for the slab */
    page = alloc_pages(GFP_KERNEL, cache->gfporder);
    if (!page) {
        return NULL;
    }
    
    /* Set up slab management structure at the end of the slab */
    slab = (struct slab_mgmt *)((char *)page_address(page) + 
                                (PAGE_SIZE << cache->gfporder) - 
                                sizeof(struct slab_mgmt) - 
                                cache->num * sizeof(unsigned short));
    
    slab->colouroff = slab_colour * cache->align;
    slab_colour = (slab_colour + 1) % SLAB_COLOUR_MAX;
    
    slab->s_mem = (char *)page_address(page) + slab->colouroff;
    slab->inuse = 0;
    slab->free = cache->num;
    
    INIT_LIST_HEAD(&slab->list);
    
    /* Initialize free list */
    for (i = 0; i < cache->num; i++) {
        slab->freelist[i] = i;
    }
    
    /* Mark page as slab */
    page->flags |= (1UL << PG_SLAB);
    page->private = cache;
    
    /* Call constructor on all objects */
    if (cache->ctor) {
        for (i = 0; i < cache->num; i++) {
            objp = (char *)slab->s_mem + i * cache->objsize;
            cache->ctor(objp);
        }
    }
    
    return slab;
}

/* Free a slab */
static void slab_free(struct kmem_cache *cache, struct slab_mgmt *slab)
{
    struct page *page;
    void *objp;
    unsigned int i;
    
    /* Call destructor on all objects */
    if (cache->dtor) {
        for (i = 0; i < cache->num; i++) {
            objp = (char *)slab->s_mem + i * cache->objsize;
            cache->dtor(objp);
        }
    }
    
    /* Find the page(s) for this slab */
    page = virt_to_page(slab->s_mem);
    if (page) {
        page->flags &= ~(1UL << PG_SLAB);
        page->private = NULL;
        free_pages(page, cache->gfporder);
    }
}

/* Initialize slab allocator */
void slab_init(void)
{
    if (slab_initialized)
        return;
    
    slab_initialized = true;
    printf("Slab allocator initialized\n");
}

/* Create a new slab cache */
struct kmem_cache *kmem_cache_create(const char *name, size_t size, size_t align,
                                   unsigned long flags, void (*ctor)(void *))
{
    struct kmem_cache *cache;
    
    if (!slab_initialized) {
        slab_init();
    }
    
    if (!name || size == 0 || size > SLAB_MAX_SIZE) {
        return NULL;
    }
    
    cache = malloc(sizeof(struct kmem_cache));
    if (!cache) {
        return NULL;
    }
    
    /* Initialize cache structure */
    strncpy(cache->name, name, sizeof(cache->name) - 1);
    cache->name[sizeof(cache->name) - 1] = '\0';
    
    cache->size = size;
    cache->align = align ? align : SLAB_OBJ_MIN_SIZE;
    cache->flags = flags;
    cache->ctor = ctor;
    cache->dtor = NULL;
    
    INIT_LIST_HEAD(&cache->list);
    INIT_LIST_HEAD(&cache->slabs_full);
    INIT_LIST_HEAD(&cache->slabs_partial);
    INIT_LIST_HEAD(&cache->slabs_free);
    
    /* Calculate slab parameters */
    calculate_slab_order(cache);
    
    /* Add to global cache list */
    list_add(&cache->list, &cache_chain);
    
    printf("Created slab cache '%s': obj_size=%u, align=%zu, objs_per_slab=%u\n",
           name, cache->objsize, cache->align, cache->num);
    
    return cache;
}

/* Destroy a slab cache */
void kmem_cache_destroy(struct kmem_cache *cache)
{
    struct list_head *pos, *tmp;
    struct slab_mgmt *slab;
    
    if (!cache)
        return;
    
    /* Free all slabs */
    list_for_each_safe(pos, tmp, &cache->slabs_full) {
        slab = list_entry(pos, struct slab_mgmt, list);
        list_del(&slab->list);
        slab_free(cache, slab);
    }
    
    list_for_each_safe(pos, tmp, &cache->slabs_partial) {
        slab = list_entry(pos, struct slab_mgmt, list);
        list_del(&slab->list);
        slab_free(cache, slab);
    }
    
    list_for_each_safe(pos, tmp, &cache->slabs_free) {
        slab = list_entry(pos, struct slab_mgmt, list);
        list_del(&slab->list);
        slab_free(cache, slab);
    }
    
    /* Remove from global cache list */
    list_del(&cache->list);
    
    printf("Destroyed slab cache '%s'\n", cache->name);
    free(cache);
}

/* Allocate an object from cache */
void *kmem_cache_alloc(struct kmem_cache *cache, unsigned int flags)
{
    struct slab_mgmt *slab = NULL;
    struct list_head *pos;
    void *objp = NULL;
    unsigned int objindex;
    
    if (!cache)
        return NULL;
    
    /* Try to find a partial slab first */
    if (!list_empty(&cache->slabs_partial)) {
        slab = list_entry(cache->slabs_partial.next, struct slab_mgmt, list);
    }
    /* If no partial slabs, try free slabs */
    else if (!list_empty(&cache->slabs_free)) {
        slab = list_entry(cache->slabs_free.next, struct slab_mgmt, list);
        list_del(&slab->list);
        list_add(&slab->list, &cache->slabs_partial);
    }
    /* Allocate a new slab */
    else {
        slab = slab_alloc(cache);
        if (!slab)
            return NULL;
        list_add(&slab->list, &cache->slabs_partial);
    }
    
    /* Get object from slab */
    if (slab->free > 0) {
        objindex = slab->freelist[slab->free - 1];
        objp = (char *)slab->s_mem + objindex * cache->objsize;
        
        slab->inuse++;
        slab->free--;
        
        /* Move slab to appropriate list */
        if (slab->free == 0) {
            list_del(&slab->list);
            list_add(&slab->list, &cache->slabs_full);
        }
        
        /* Clear object if requested */
        if (flags & GFP_KERNEL) {
            memset(objp, 0, cache->objsize);
        }
    }
    
    return objp;
}

/* Free an object back to cache */
void kmem_cache_free(struct kmem_cache *cache, void *obj)
{
    struct slab_mgmt *slab;
    struct page *page;
    unsigned int objindex;
    char *objp = (char *)obj;
    
    if (!cache || !obj)
        return;
    
    /* Find which slab this object belongs to */
    page = virt_to_page(obj);
    if (!page || !(page->flags & (1UL << PG_SLAB)) || page->private != cache) {
        printf("Invalid object passed to kmem_cache_free\n");
        return;
    }
    
    /* Calculate slab management structure location */
    slab = (struct slab_mgmt *)((char *)page_address(page) + 
                                (PAGE_SIZE << cache->gfporder) - 
                                sizeof(struct slab_mgmt) - 
                                cache->num * sizeof(unsigned short));
    
    /* Calculate object index */
    objindex = (objp - (char *)slab->s_mem) / cache->objsize;
    
    if (objindex >= cache->num) {
        printf("Invalid object index in kmem_cache_free\n");
        return;
    }
    
    /* Add object back to free list */
    slab->freelist[slab->free] = objindex;
    slab->free++;
    slab->inuse--;
    
    /* Move slab to appropriate list */
    if (slab->inuse == 0) {
        /* Slab is now empty */
        list_del(&slab->list);
        if (list_empty(&cache->slabs_free) && list_empty(&cache->slabs_partial)) {
            /* Keep at least one free slab */
            list_add(&slab->list, &cache->slabs_free);
        } else {
            /* Free the slab */
            slab_free(cache, slab);
        }
    } else if (slab->free == 1) {
        /* Slab was full, now partial */
        list_del(&slab->list);
        list_add(&slab->list, &cache->slabs_partial);
    }
}

/* Get slab cache statistics */
void kmem_cache_info(void)
{
    struct kmem_cache *cache;
    struct list_head *pos;
    unsigned int full_slabs, partial_slabs, free_slabs;
    unsigned int total_objs, used_objs;
    
    printf("\nSlab Cache Information:\n");
    printf("======================\n");
    
    list_for_each_entry(cache, &cache_chain, list) {
        full_slabs = 0;
        partial_slabs = 0;
        free_slabs = 0;
        total_objs = 0;
        used_objs = 0;
        
        /* Count slabs and objects */
        list_for_each(pos, &cache->slabs_full) {
            full_slabs++;
            total_objs += cache->num;
            used_objs += cache->num;
        }
        
        list_for_each(pos, &cache->slabs_partial) {
            struct slab_mgmt *slab = list_entry(pos, struct slab_mgmt, list);
            partial_slabs++;
            total_objs += cache->num;
            used_objs += slab->inuse;
        }
        
        list_for_each(pos, &cache->slabs_free) {
            free_slabs++;
            total_objs += cache->num;
        }
        
        printf("Cache: %-20s obj_size: %4u  align: %4zu  objs_per_slab: %3u\n",
               cache->name, cache->objsize, cache->align, cache->num);
        printf("  Slabs: %3u full, %3u partial, %3u free\n",
               full_slabs, partial_slabs, free_slabs);
        printf("  Objects: %5u total, %5u used, %5u free\n",
               total_objs, used_objs, total_objs - used_objs);
        printf("  Memory: %lu KB total\n",
               (full_slabs + partial_slabs + free_slabs) * 
               (PAGE_SIZE << cache->gfporder) / 1024);
        printf("\n");
    }
}

/* Find cache by name */
struct kmem_cache *kmem_cache_find(const char *name)
{
    struct kmem_cache *cache;
    
    list_for_each_entry(cache, &cache_chain, list) {
        if (strcmp(cache->name, name) == 0) {
            return cache;
        }
    }
    
    return NULL;
}

/* Shrink cache by freeing empty slabs */
int kmem_cache_shrink(struct kmem_cache *cache)
{
    struct list_head *pos, *tmp;
    struct slab_mgmt *slab;
    int freed = 0;
    
    if (!cache)
        return 0;
    
    /* Free empty slabs except keep one */
    list_for_each_safe(pos, tmp, &cache->slabs_free) {
        if (list_empty(&cache->slabs_free))
            break;
        
        slab = list_entry(pos, struct slab_mgmt, list);
        list_del(&slab->list);
        slab_free(cache, slab);
        freed++;
    }
    
    return freed;
}