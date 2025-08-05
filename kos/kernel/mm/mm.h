#ifndef MM_H
#define MM_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* Memory management constants */
#define PAGE_SIZE 4096
#define PAGE_SHIFT 12
#define PAGE_MASK (~(PAGE_SIZE - 1))
#define BUDDY_MAX_ORDER 11
#define SLAB_MAX_SIZE 8192
#define KMALLOC_MAX_SIZE (32 * 1024)

/* Memory zones */
#define ZONE_DMA 0
#define ZONE_NORMAL 1
#define ZONE_HIGHMEM 2
#define MAX_ZONES 3

/* Page flags */
#define PG_LOCKED 0
#define PG_ERROR 1
#define PG_REFERENCED 2
#define PG_UPTODATE 3
#define PG_DIRTY 4
#define PG_LRU 5
#define PG_ACTIVE 6
#define PG_SLAB 7
#define PG_RESERVED 8

/* Page table flags */
#define PTE_PRESENT 0x001
#define PTE_WRITE 0x002
#define PTE_USER 0x004
#define PTE_PWT 0x008
#define PTE_PCD 0x010
#define PTE_ACCESSED 0x020
#define PTE_DIRTY 0x040
#define PTE_PSE 0x080
#define PTE_GLOBAL 0x100

/* Memory mapping flags */
#define PROT_READ 0x1
#define PROT_WRITE 0x2
#define PROT_EXEC 0x4
#define MAP_SHARED 0x01
#define MAP_PRIVATE 0x02
#define MAP_FIXED 0x10
#define MAP_ANONYMOUS 0x20

/* Forward declarations */
struct page;
struct zone;
struct kmem_cache;
struct vm_area_struct;

/* Page descriptor */
struct page {
    unsigned long flags;
    int count;
    struct list_head lru;
    struct page *next_free;
    void *private;
    unsigned int order;
    struct zone *zone;
};

/* Memory zone descriptor */
struct zone {
    unsigned long free_pages;
    unsigned long pages_min, pages_low, pages_high;
    struct free_area free_area[BUDDY_MAX_ORDER + 1];
    struct list_head active_list;
    struct list_head inactive_list;
    unsigned long nr_active;
    unsigned long nr_inactive;
    struct page *mem_map;
    unsigned long zone_start_pfn;
    unsigned long zone_size;
    char name[16];
};

/* Free area for buddy allocator */
struct free_area {
    struct list_head free_list;
    unsigned long nr_free;
};

/* List head structure */
struct list_head {
    struct list_head *next, *prev;
};

/* Slab cache descriptor */
struct kmem_cache {
    struct list_head list;
    char name[32];
    size_t size;
    size_t align;
    unsigned long flags;
    struct list_head slabs_full;
    struct list_head slabs_partial;
    struct list_head slabs_free;
    unsigned int objsize;
    unsigned int num;
    unsigned int gfporder;
    void (*ctor)(void *);
    void (*dtor)(void *);
};

/* Slab descriptor */
struct slab {
    struct list_head list;
    unsigned long colouroff;
    void *s_mem;
    unsigned int inuse;
    unsigned int free;
    struct kmem_cache *cache;
};

/* Virtual memory area */
struct vm_area_struct {
    unsigned long vm_start;
    unsigned long vm_end;
    unsigned long vm_flags;
    struct vm_area_struct *vm_next;
    struct file *vm_file;
    unsigned long vm_pgoff;
};

/* Memory mapping descriptor */
struct mm_struct {
    struct vm_area_struct *mmap;
    unsigned long total_vm;
    unsigned long locked_vm;
    unsigned long start_code, end_code;
    unsigned long start_data, end_data;
    unsigned long start_brk, brk;
    unsigned long start_stack;
    unsigned long arg_start, arg_end;
    unsigned long env_start, env_end;
};

/* Page table entries */
typedef uint64_t pte_t;
typedef uint64_t pmd_t;
typedef uint64_t pud_t;
typedef uint64_t pgd_t;

/* Page table walking */
struct page_walk_ops {
    int (*pte_entry)(pte_t *pte, unsigned long addr, void *private);
    int (*pmd_entry)(pmd_t *pmd, unsigned long addr, void *private);
    int (*pud_entry)(pud_t *pud, unsigned long addr, void *private);
    int (*pgd_entry)(pgd_t *pgd, unsigned long addr, void *private);
};

/* Memory statistics */
struct meminfo {
    unsigned long totalram;
    unsigned long freeram;
    unsigned long sharedram;
    unsigned long bufferram;
    unsigned long totalswap;
    unsigned long freeswap;
    unsigned long totalhigh;
    unsigned long freehigh;
    unsigned long mem_unit;
};

/* Function prototypes */

/* Buddy allocator */
struct page *alloc_pages(unsigned int gfp_mask, unsigned int order);
void free_pages(struct page *page, unsigned int order);
struct page *__alloc_pages(unsigned int gfp_mask, unsigned int order, struct zone *zone);
void __free_pages(struct page *page, unsigned int order);
void buddy_init(void);
void buddy_add_memory(unsigned long start_pfn, unsigned long end_pfn);

/* Slab allocator */
struct kmem_cache *kmem_cache_create(const char *name, size_t size, size_t align,
                                   unsigned long flags, void (*ctor)(void *));
void kmem_cache_destroy(struct kmem_cache *cache);
void *kmem_cache_alloc(struct kmem_cache *cache, unsigned int flags);
void kmem_cache_free(struct kmem_cache *cache, void *obj);
void slab_init(void);

/* Kernel memory allocation */
void *kmalloc(size_t size, unsigned int flags);
void kfree(const void *ptr);
void *kzalloc(size_t size, unsigned int flags);
void *krealloc(const void *ptr, size_t new_size, unsigned int flags);
void kmalloc_init(void);

/* Page table management */
pgd_t *pgd_alloc(void);
void pgd_free(pgd_t *pgd);
pud_t *pud_alloc(pgd_t *pgd, unsigned long addr);
pmd_t *pmd_alloc(pud_t *pud, unsigned long addr);
pte_t *pte_alloc(pmd_t *pmd, unsigned long addr);
void pte_free(pte_t *pte);
int copy_page_tables(pgd_t *dst, pgd_t *src, unsigned long start, unsigned long end);
void free_page_tables(pgd_t *pgd, unsigned long start, unsigned long end);

/* Memory mapping */
unsigned long do_mmap(unsigned long addr, unsigned long len, unsigned long prot,
                     unsigned long flags, unsigned long fd, unsigned long off);
int do_munmap(unsigned long addr, size_t len);
struct vm_area_struct *find_vma(struct mm_struct *mm, unsigned long addr);
int handle_mm_fault(struct vm_area_struct *vma, unsigned long addr, unsigned int flags);

/* Page fault handling */
int do_page_fault(unsigned long addr, unsigned long error_code);
int handle_pte_fault(pte_t *pte, unsigned long addr, unsigned int flags);

/* Memory statistics and debugging */
void get_meminfo(struct meminfo *info);
void show_mem(void);
void dump_page(struct page *page);
void check_memory_leak(void);

/* Utility functions */
static inline unsigned long page_to_pfn(struct page *page);
static inline struct page *pfn_to_page(unsigned long pfn);
static inline void *page_address(struct page *page);
static inline struct page *virt_to_page(void *addr);
static inline void *pfn_to_virt(unsigned long pfn);
static inline unsigned long virt_to_pfn(void *addr);

/* List manipulation macros */
#define LIST_HEAD_INIT(name) { &(name), &(name) }
#define LIST_HEAD(name) struct list_head name = LIST_HEAD_INIT(name)

static inline void INIT_LIST_HEAD(struct list_head *list)
{
    list->next = list;
    list->prev = list;
}

static inline void list_add(struct list_head *new, struct list_head *head)
{
    new->next = head->next;
    new->prev = head;
    head->next->prev = new;
    head->next = new;
}

static inline void list_del(struct list_head *entry)
{
    entry->next->prev = entry->prev;
    entry->prev->next = entry->next;
    entry->next = NULL;
    entry->prev = NULL;
}

static inline int list_empty(const struct list_head *head)
{
    return head->next == head;
}

#define list_entry(ptr, type, member) \
    ((type *)((char *)(ptr) - (unsigned long)(&((type *)0)->member)))

#define list_for_each(pos, head) \
    for (pos = (head)->next; pos != (head); pos = pos->next)

#define list_for_each_entry(pos, head, member) \
    for (pos = list_entry((head)->next, typeof(*pos), member); \
         &pos->member != (head); \
         pos = list_entry(pos->member.next, typeof(*pos), member))

/* Memory barriers and atomic operations */
#define mb() __asm__ __volatile__("mfence":::"memory")
#define rmb() __asm__ __volatile__("lfence":::"memory")
#define wmb() __asm__ __volatile__("sfence":::"memory")

/* GFP flags */
#define GFP_KERNEL 0x01
#define GFP_ATOMIC 0x02
#define GFP_USER 0x04
#define GFP_HIGHMEM 0x08
#define GFP_DMA 0x10

/* Error codes */
#define ENOMEM 12
#define EINVAL 22
#define EFAULT 14

#endif /* MM_H */