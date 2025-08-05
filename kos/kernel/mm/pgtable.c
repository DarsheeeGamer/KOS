#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* Page table levels */
#define PTRS_PER_PGD 512
#define PTRS_PER_PUD 512
#define PTRS_PER_PMD 512
#define PTRS_PER_PTE 512

/* Page table shifts */
#define PGD_SHIFT 39
#define PUD_SHIFT 30
#define PMD_SHIFT 21
#define PTE_SHIFT 12

/* Page table masks */
#define PGD_MASK (~((1UL << PGD_SHIFT) - 1))
#define PUD_MASK (~((1UL << PUD_SHIFT) - 1))
#define PMD_MASK (~((1UL << PMD_SHIFT) - 1))
#define PTE_MASK (~((1UL << PTE_SHIFT) - 1))

/* Page table entry extraction */
#define pgd_index(addr) (((addr) >> PGD_SHIFT) & (PTRS_PER_PGD - 1))
#define pud_index(addr) (((addr) >> PUD_SHIFT) & (PTRS_PER_PUD - 1))
#define pmd_index(addr) (((addr) >> PMD_SHIFT) & (PTRS_PER_PMD - 1))
#define pte_index(addr) (((addr) >> PTE_SHIFT) & (PTRS_PER_PTE - 1))

/* Page table entry manipulation */
#define pte_none(pte) (!(pte))
#define pte_present(pte) ((pte) & PTE_PRESENT)
#define pte_pfn(pte) (((pte) & ~0xFFF) >> PAGE_SHIFT)
#define pfn_pte(pfn, prot) (((pfn) << PAGE_SHIFT) | (prot))

/* x86-64 TLB invalidation functions */
static inline void invlpg(unsigned long addr)
{
    __asm__ __volatile__("invlpg (%0)" : : "r" (addr) : "memory");
}

static inline void flush_tlb_single(unsigned long addr)
{
    invlpg(addr);
}

static inline void flush_tlb_range(unsigned long start, unsigned long end)
{
    unsigned long addr;
    
    /* For small ranges, use single page invalidation */
    if ((end - start) <= 16 * PAGE_SIZE) {
        for (addr = start; addr < end; addr += PAGE_SIZE) {
            invlpg(addr);
        }
    } else {
        /* For large ranges, flush entire TLB */
        flush_tlb_all();
    }
}

static inline void flush_tlb_all(void)
{
    unsigned long cr3;
    
    /* Reload CR3 to flush entire TLB */
    __asm__ __volatile__(
        "mov %%cr3, %0\n\t"
        "mov %0, %%cr3"
        : "=r" (cr3)
        :
        : "memory"
    );
}

/* Get current CR3 (page directory base) */
static inline unsigned long get_cr3(void)
{
    unsigned long cr3;
    __asm__ __volatile__("mov %%cr3, %0" : "=r" (cr3));
    return cr3;
}

/* Set CR3 (page directory base) */
static inline void set_cr3(unsigned long cr3)
{
    __asm__ __volatile__("mov %0, %%cr3" : : "r" (cr3) : "memory");
}

/* Cache for page table pages */
static struct kmem_cache *pgtable_cache = NULL;

/* Statistics */
static unsigned long pgtable_pages_allocated = 0;
static unsigned long pgtable_pages_freed = 0;

/* Initialize page table management */
static void pgtable_init(void)
{
    if (pgtable_cache)
        return;
    
    pgtable_cache = kmem_cache_create("pgtable", PAGE_SIZE, PAGE_SIZE, 0, NULL);
    if (!pgtable_cache) {
        printf("Failed to create page table cache\n");
    } else {
        printf("Page table management initialized\n");
    }
}

/* Allocate a page directory */
pgd_t *pgd_alloc(void)
{
    pgd_t *pgd;
    
    if (!pgtable_cache) {
        pgtable_init();
    }
    
    pgd = (pgd_t *)kmem_cache_alloc(pgtable_cache, GFP_KERNEL);
    if (pgd) {
        memset(pgd, 0, PAGE_SIZE);
        pgtable_pages_allocated++;
    }
    
    return pgd;
}

/* Free a page directory */
void pgd_free(pgd_t *pgd)
{
    if (!pgd || !pgtable_cache)
        return;
    
    kmem_cache_free(pgtable_cache, pgd);
    pgtable_pages_freed++;
}

/* Get PUD entry from PGD */
static inline pud_t *pgd_to_pud(pgd_t *pgd, unsigned long addr)
{
    if (!pte_present(*pgd))
        return NULL;
    
    return (pud_t *)(pte_pfn(*pgd) << PAGE_SHIFT) + pud_index(addr);
}

/* Allocate PUD table */
pud_t *pud_alloc(pgd_t *pgd, unsigned long addr)
{
    pud_t *pud;
    
    if (!pgtable_cache) {
        pgtable_init();
    }
    
    pud = pgd_to_pud(pgd, addr);
    if (pud)
        return pud;
    
    /* Allocate new PUD table */
    pud = (pud_t *)kmem_cache_alloc(pgtable_cache, GFP_KERNEL);
    if (!pud)
        return NULL;
    
    memset(pud, 0, PAGE_SIZE);
    pgtable_pages_allocated++;
    
    /* Link it to PGD */
    *pgd = pfn_pte(virt_to_pfn(pud), PTE_PRESENT | PTE_WRITE | PTE_USER);
    
    return pud + pud_index(addr);
}

/* Get PMD entry from PUD */
static inline pmd_t *pud_to_pmd(pud_t *pud, unsigned long addr)
{
    if (!pte_present(*pud))
        return NULL;
    
    return (pmd_t *)(pte_pfn(*pud) << PAGE_SHIFT) + pmd_index(addr);
}

/* Allocate PMD table */
pmd_t *pmd_alloc(pud_t *pud, unsigned long addr)
{
    pmd_t *pmd;
    
    if (!pgtable_cache) {
        pgtable_init();
    }
    
    pmd = pud_to_pmd(pud, addr);
    if (pmd)
        return pmd;
    
    /* Allocate new PMD table */
    pmd = (pmd_t *)kmem_cache_alloc(pgtable_cache, GFP_KERNEL);
    if (!pmd)
        return NULL;
    
    memset(pmd, 0, PAGE_SIZE);
    pgtable_pages_allocated++;
    
    /* Link it to PUD */
    *pud = pfn_pte(virt_to_pfn(pmd), PTE_PRESENT | PTE_WRITE | PTE_USER);
    
    return pmd + pmd_index(addr);
}

/* Get PTE entry from PMD */
static inline pte_t *pmd_to_pte(pmd_t *pmd, unsigned long addr)
{
    if (!pte_present(*pmd))
        return NULL;
    
    return (pte_t *)(pte_pfn(*pmd) << PAGE_SHIFT) + pte_index(addr);
}

/* Allocate PTE table */
pte_t *pte_alloc(pmd_t *pmd, unsigned long addr)
{
    pte_t *pte;
    
    if (!pgtable_cache) {
        pgtable_init();
    }
    
    pte = pmd_to_pte(pmd, addr);
    if (pte)
        return pte;
    
    /* Allocate new PTE table */
    pte = (pte_t *)kmem_cache_alloc(pgtable_cache, GFP_KERNEL);
    if (!pte)
        return NULL;
    
    memset(pte, 0, PAGE_SIZE);
    pgtable_pages_allocated++;
    
    /* Link it to PMD */
    *pmd = pfn_pte(virt_to_pfn(pte), PTE_PRESENT | PTE_WRITE | PTE_USER);
    
    return pte + pte_index(addr);
}

/* Free PTE table */
void pte_free(pte_t *pte)
{
    if (!pte || !pgtable_cache)
        return;
    
    kmem_cache_free(pgtable_cache, pte);
    pgtable_pages_freed++;
}

/* Walk page tables and call callback */
int walk_page_range(unsigned long start, unsigned long end,
                   struct page_walk_ops *ops, void *private)
{
    unsigned long addr;
    pgd_t *pgd;
    pud_t *pud;
    pmd_t *pmd;
    pte_t *pte;
    int ret = 0;
    
    /* Get current page directory */
    pgd = pgd_alloc(); /* This should get current process pgd */
    if (!pgd)
        return -ENOMEM;
    
    for (addr = start; addr < end; addr += PAGE_SIZE) {
        unsigned long pgd_idx = pgd_index(addr);
        
        if (!pte_present(pgd[pgd_idx]))
            continue;
        
        if (ops->pgd_entry) {
            ret = ops->pgd_entry(&pgd[pgd_idx], addr, private);
            if (ret)
                break;
        }
        
        pud = pgd_to_pud(&pgd[pgd_idx], addr);
        if (!pud || !pte_present(*pud))
            continue;
        
        if (ops->pud_entry) {
            ret = ops->pud_entry(pud, addr, private);
            if (ret)
                break;
        }
        
        pmd = pud_to_pmd(pud, addr);
        if (!pmd || !pte_present(*pmd))
            continue;
        
        if (ops->pmd_entry) {
            ret = ops->pmd_entry(pmd, addr, private);
            if (ret)
                break;
        }
        
        pte = pmd_to_pte(pmd, addr);
        if (!pte || !pte_present(*pte))
            continue;
        
        if (ops->pte_entry) {
            ret = ops->pte_entry(pte, addr, private);
            if (ret)
                break;
        }
    }
    
    return ret;
}

/* Copy page tables from source to destination */
int copy_page_tables(pgd_t *dst_pgd, pgd_t *src_pgd, 
                    unsigned long start, unsigned long end)
{
    unsigned long addr;
    int ret = 0;
    
    for (addr = start; addr < end; addr += PAGE_SIZE) {
        pgd_t *src_pgd_entry = &src_pgd[pgd_index(addr)];
        pgd_t *dst_pgd_entry = &dst_pgd[pgd_index(addr)];
        pud_t *src_pud, *dst_pud;
        pmd_t *src_pmd, *dst_pmd;
        pte_t *src_pte, *dst_pte;
        
        if (!pte_present(*src_pgd_entry))
            continue;
        
        /* Allocate destination PUD if needed */
        dst_pud = pud_alloc(dst_pgd_entry, addr);
        if (!dst_pud) {
            ret = -ENOMEM;
            break;
        }
        
        src_pud = pgd_to_pud(src_pgd_entry, addr);
        if (!src_pud || !pte_present(*src_pud))
            continue;
        
        /* Allocate destination PMD if needed */
        dst_pmd = pmd_alloc(dst_pud, addr);
        if (!dst_pmd) {
            ret = -ENOMEM;
            break;
        }
        
        src_pmd = pud_to_pmd(src_pud, addr);
        if (!src_pmd || !pte_present(*src_pmd))
            continue;
        
        /* Allocate destination PTE if needed */
        dst_pte = pte_alloc(dst_pmd, addr);
        if (!dst_pte) {
            ret = -ENOMEM;
            break;
        }
        
        src_pte = pmd_to_pte(src_pmd, addr);
        if (!src_pte || !pte_present(*src_pte))
            continue;
        
        /* Copy PTE */
        *dst_pte = *src_pte;
        
        /* Handle copy-on-write */
        if (*src_pte & PTE_WRITE) {
            *src_pte &= ~PTE_WRITE;
            *dst_pte &= ~PTE_WRITE;
        }
    }
    
    return ret;
}

/* Free page tables in range */
void free_page_tables(pgd_t *pgd, unsigned long start, unsigned long end)
{
    unsigned long addr;
    
    for (addr = start; addr < end; addr += PAGE_SIZE) {
        pgd_t *pgd_entry = &pgd[pgd_index(addr)];
        pud_t *pud;
        pmd_t *pmd;
        pte_t *pte;
        
        if (!pte_present(*pgd_entry))
            continue;
        
        pud = pgd_to_pud(pgd_entry, addr);
        if (!pud || !pte_present(*pud))
            continue;
        
        pmd = pud_to_pmd(pud, addr);
        if (!pmd || !pte_present(*pmd))
            continue;
        
        pte = pmd_to_pte(pmd, addr);
        if (!pte)
            continue;
        
        /* Clear PTE */
        pte_t *pte_entry = &pte[pte_index(addr)];
        if (pte_present(*pte_entry)) {
            unsigned long pfn = pte_pfn(*pte_entry);
            struct page *page = pfn_to_page(pfn);
            if (page) {
                free_pages(page, 0);
            }
            *pte_entry = 0;
        }
    }
}

/* Map physical page to virtual address */
int map_page(pgd_t *pgd, unsigned long vaddr, unsigned long paddr, 
            unsigned long prot)
{
    pud_t *pud;
    pmd_t *pmd;
    pte_t *pte;
    
    /* Allocate page table hierarchy */
    pud = pud_alloc(&pgd[pgd_index(vaddr)], vaddr);
    if (!pud)
        return -ENOMEM;
    
    pmd = pmd_alloc(pud, vaddr);
    if (!pmd)
        return -ENOMEM;
    
    pte = pte_alloc(pmd, vaddr);
    if (!pte)
        return -ENOMEM;
    
    /* Set up PTE */
    pte_t *pte_entry = &pte[pte_index(vaddr)];
    *pte_entry = pfn_pte(paddr >> PAGE_SHIFT, prot);
    
    return 0;
}

/* Unmap virtual address */
void unmap_page(pgd_t *pgd, unsigned long vaddr)
{
    pgd_t *pgd_entry = &pgd[pgd_index(vaddr)];
    pud_t *pud;
    pmd_t *pmd;
    pte_t *pte;
    
    if (!pte_present(*pgd_entry))
        return;
    
    pud = pgd_to_pud(pgd_entry, vaddr);
    if (!pud || !pte_present(*pud))
        return;
    
    pmd = pud_to_pmd(pud, vaddr);
    if (!pmd || !pte_present(*pmd))
        return;
    
    pte = pmd_to_pte(pmd, vaddr);
    if (!pte)
        return;
    
    pte_t *pte_entry = &pte[pte_index(vaddr)];
    if (pte_present(*pte_entry)) {
        *pte_entry = 0;
        /* Invalidate TLB entry for this virtual address */
        flush_tlb_single(vaddr);
    }
}

/* Lookup physical address for virtual address */
unsigned long virt_to_phys_pgtable(pgd_t *pgd, unsigned long vaddr)
{
    pgd_t *pgd_entry = &pgd[pgd_index(vaddr)];
    pud_t *pud;
    pmd_t *pmd;
    pte_t *pte;
    pte_t pte_val;
    
    if (!pte_present(*pgd_entry))
        return 0;
    
    pud = pgd_to_pud(pgd_entry, vaddr);
    if (!pud || !pte_present(*pud))
        return 0;
    
    pmd = pud_to_pmd(pud, vaddr);
    if (!pmd || !pte_present(*pmd))
        return 0;
    
    pte = pmd_to_pte(pmd, vaddr);
    if (!pte)
        return 0;
    
    pte_val = pte[pte_index(vaddr)];
    if (!pte_present(pte_val))
        return 0;
    
    return (pte_pfn(pte_val) << PAGE_SHIFT) | (vaddr & ~PAGE_MASK);
}

/* Get page table statistics */
void pgtable_info(void)
{
    printf("\nPage Table Information:\n");
    printf("======================\n");
    printf("Page table pages allocated: %lu\n", pgtable_pages_allocated);
    printf("Page table pages freed: %lu\n", pgtable_pages_freed);
    printf("Page table pages in use: %lu\n", 
           pgtable_pages_allocated - pgtable_pages_freed);
    printf("Memory used by page tables: %lu KB\n",
           (pgtable_pages_allocated - pgtable_pages_freed) * PAGE_SIZE / 1024);
}

/* Dump page table structure */
void dump_page_tables(pgd_t *pgd, unsigned long start, unsigned long end)
{
    unsigned long addr;
    
    printf("\nPage Table Dump (0x%lx - 0x%lx):\n", start, end);
    printf("=====================================\n");
    
    for (addr = start; addr < end; addr += PAGE_SIZE) {
        pgd_t *pgd_entry = &pgd[pgd_index(addr)];
        pud_t *pud;
        pmd_t *pmd;
        pte_t *pte;
        pte_t pte_val;
        
        if (!pte_present(*pgd_entry))
            continue;
        
        pud = pgd_to_pud(pgd_entry, addr);
        if (!pud || !pte_present(*pud))
            continue;
        
        pmd = pud_to_pmd(pud, addr);
        if (!pmd || !pte_present(*pmd))
            continue;
        
        pte = pmd_to_pte(pmd, addr);
        if (!pte)
            continue;
        
        pte_val = pte[pte_index(addr)];
        if (!pte_present(pte_val))
            continue;
        
        printf("0x%016lx -> 0x%016lx [", addr, pte_pfn(pte_val) << PAGE_SHIFT);
        if (pte_val & PTE_PRESENT) printf("P");
        if (pte_val & PTE_WRITE) printf("W");
        if (pte_val & PTE_USER) printf("U");
        if (pte_val & PTE_ACCESSED) printf("A");
        if (pte_val & PTE_DIRTY) printf("D");
        printf("]\n");
    }
}