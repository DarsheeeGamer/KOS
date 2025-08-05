#include "mm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <errno.h>

/* External page table functions from pgtable.c */
extern pgd_t *pgd_alloc(void);
extern void pgd_free(pgd_t *pgd);
extern int map_page(pgd_t *pgd, unsigned long vaddr, unsigned long paddr, unsigned long prot);
extern void unmap_page(pgd_t *pgd, unsigned long vaddr);
extern void free_page_tables(pgd_t *pgd, unsigned long start, unsigned long end);
extern unsigned long virt_to_phys_pgtable(pgd_t *pgd, unsigned long vaddr);

/* Current process page directory - in real kernel would come from current task */
static pgd_t *current_pgd = NULL;

/* Global memory management structures */
static struct mm_struct init_mm;
static struct mm_struct *current_mm = &init_mm;
static struct kmem_cache *vma_cache = NULL;

/* VMA tree for efficient lookups */
struct vma_tree_node {
    struct vm_area_struct *vma;
    struct vma_tree_node *left, *right;
    int height;
};

static struct vma_tree_node *vma_tree_root = NULL;

/* Initialize memory mapping subsystem */
static void mmap_init(void)
{
    if (vma_cache)
        return;
    
    vma_cache = kmem_cache_create("vm_area_struct", sizeof(struct vm_area_struct),
                                 0, 0, NULL);
    if (!vma_cache) {
        printf("Failed to create VMA cache\n");
        return;
    }
    
    /* Initialize init_mm */
    memset(&init_mm, 0, sizeof(init_mm));
    init_mm.start_code = 0x400000;      /* Typical user code start */
    init_mm.end_code = 0x500000;
    init_mm.start_data = 0x500000;
    init_mm.end_data = 0x600000;
    init_mm.start_brk = 0x600000;
    init_mm.brk = 0x600000;
    init_mm.start_stack = 0x7ffe0000;   /* Typical stack start */
    init_mm.mmap = NULL;
    
    printf("Memory mapping initialized\n");
}

/* AVL tree operations for VMA management */
static int vma_tree_height(struct vma_tree_node *node)
{
    return node ? node->height : 0;
}

static int vma_tree_balance(struct vma_tree_node *node)
{
    return node ? vma_tree_height(node->left) - vma_tree_height(node->right) : 0;
}

static void vma_tree_update_height(struct vma_tree_node *node)
{
    if (node) {
        int left_height = vma_tree_height(node->left);
        int right_height = vma_tree_height(node->right);
        node->height = 1 + (left_height > right_height ? left_height : right_height);
    }
}

static struct vma_tree_node *vma_tree_rotate_right(struct vma_tree_node *y)
{
    struct vma_tree_node *x = y->left;
    struct vma_tree_node *T2 = x->right;
    
    x->right = y;
    y->left = T2;
    
    vma_tree_update_height(y);
    vma_tree_update_height(x);
    
    return x;
}

static struct vma_tree_node *vma_tree_rotate_left(struct vma_tree_node *x)
{
    struct vma_tree_node *y = x->right;
    struct vma_tree_node *T2 = y->left;
    
    y->left = x;
    x->right = T2;
    
    vma_tree_update_height(x);
    vma_tree_update_height(y);
    
    return y;
}

/* Insert VMA into tree */
static struct vma_tree_node *vma_tree_insert(struct vma_tree_node *node, 
                                            struct vm_area_struct *vma)
{
    /* Normal BST insertion */
    if (!node) {
        node = malloc(sizeof(struct vma_tree_node));
        if (!node)
            return NULL;
        node->vma = vma;
        node->left = node->right = NULL;
        node->height = 1;
        return node;
    }
    
    if (vma->vm_start < node->vma->vm_start) {
        node->left = vma_tree_insert(node->left, vma);
    } else if (vma->vm_start > node->vma->vm_start) {
        node->right = vma_tree_insert(node->right, vma);
    } else {
        return node; /* Duplicate not allowed */
    }
    
    /* Update height */
    vma_tree_update_height(node);
    
    /* Get balance factor */
    int balance = vma_tree_balance(node);
    
    /* Left-Left case */
    if (balance > 1 && vma->vm_start < node->left->vma->vm_start) {
        return vma_tree_rotate_right(node);
    }
    
    /* Right-Right case */
    if (balance < -1 && vma->vm_start > node->right->vma->vm_start) {
        return vma_tree_rotate_left(node);
    }
    
    /* Left-Right case */
    if (balance > 1 && vma->vm_start > node->left->vma->vm_start) {
        node->left = vma_tree_rotate_left(node->left);
        return vma_tree_rotate_right(node);
    }
    
    /* Right-Left case */
    if (balance < -1 && vma->vm_start < node->right->vma->vm_start) {
        node->right = vma_tree_rotate_right(node->right);
        return vma_tree_rotate_left(node);
    }
    
    return node;
}

/* Find VMA containing address */
struct vm_area_struct *find_vma(struct mm_struct *mm, unsigned long addr)
{
    struct vm_area_struct *vma;
    
    if (!mm)
        mm = current_mm;
    
    /* Linear search through VMA list */
    for (vma = mm->mmap; vma; vma = vma->vm_next) {
        if (addr >= vma->vm_start && addr < vma->vm_end) {
            return vma;
        }
    }
    
    return NULL;
}

/* Find VMA that would contain address (including next VMA) */
struct vm_area_struct *find_vma_intersection(struct mm_struct *mm,
                                           unsigned long start_addr,
                                           unsigned long end_addr)
{
    struct vm_area_struct *vma;
    
    if (!mm)
        mm = current_mm;
    
    for (vma = mm->mmap; vma; vma = vma->vm_next) {
        if (vma->vm_start < end_addr && vma->vm_end > start_addr) {
            return vma;
        }
    }
    
    return NULL;
}

/* Get unmapped address in range */
static unsigned long get_unmapped_area(unsigned long addr, unsigned long len,
                                     unsigned long flags)
{
    struct vm_area_struct *vma;
    unsigned long start;
    
    if (!current_mm) {
        mmap_init();
    }
    
    /* If specific address requested, try to honor it */
    if (addr && !(flags & MAP_FIXED)) {
        addr = (addr + PAGE_SIZE - 1) & PAGE_MASK;
        vma = find_vma_intersection(current_mm, addr, addr + len);
        if (!vma) {
            return addr;
        }
    }
    
    /* Find free area */
    start = current_mm->start_brk;
    
    for (vma = current_mm->mmap; vma; vma = vma->vm_next) {
        if (start + len <= vma->vm_start) {
            return start;
        }
        start = vma->vm_end;
    }
    
    /* Check if we have space after last VMA */
    if (start + len < current_mm->start_stack) {
        return start;
    }
    
    return 0; /* No space found */
}

/* Insert VMA into mm */
static void insert_vm_struct(struct mm_struct *mm, struct vm_area_struct *vma)
{
    struct vm_area_struct **pprev, *prev = NULL;
    
    /* Find insertion point */
    pprev = &mm->mmap;
    while (*pprev && (*pprev)->vm_start < vma->vm_start) {
        prev = *pprev;
        pprev = &(*pprev)->vm_next;
    }
    
    /* Insert VMA */
    vma->vm_next = *pprev;
    *pprev = vma;
    
    /* Update total VM */
    mm->total_vm += (vma->vm_end - vma->vm_start) >> PAGE_SHIFT;
    
    /* Insert into tree for fast lookups */
    vma_tree_root = vma_tree_insert(vma_tree_root, vma);
}

/* Helper to find minimum node in tree */
static struct vma_tree_node *vma_tree_min_node(struct vma_tree_node *node)
{
    while (node->left)
        node = node->left;
    return node;
}

/* Remove VMA from tree */
static struct vma_tree_node *vma_tree_remove(struct vma_tree_node *root,
                                            struct vm_area_struct *vma)
{
    if (!root)
        return root;
    
    /* Find node to delete */
    if (vma->vm_start < root->vma->vm_start) {
        root->left = vma_tree_remove(root->left, vma);
    } else if (vma->vm_start > root->vma->vm_start) {
        root->right = vma_tree_remove(root->right, vma);
    } else {
        /* Node with only one child or no child */
        if (!root->left) {
            struct vma_tree_node *temp = root->right;
            free(root);
            return temp;
        } else if (!root->right) {
            struct vma_tree_node *temp = root->left;
            free(root);
            return temp;
        }
        
        /* Node with two children: get inorder successor */
        struct vma_tree_node *temp = vma_tree_min_node(root->right);
        
        /* Copy the inorder successor's data to this node */
        root->vma = temp->vma;
        
        /* Delete the inorder successor */
        root->right = vma_tree_remove(root->right, temp->vma);
    }
    
    if (!root)
        return root;
    
    /* Update height */
    vma_tree_update_height(root);
    
    /* Get balance factor */
    int balance = vma_tree_balance(root);
    
    /* Left-Left case */
    if (balance > 1 && vma_tree_balance(root->left) >= 0)
        return vma_tree_rotate_right(root);
    
    /* Left-Right case */
    if (balance > 1 && vma_tree_balance(root->left) < 0) {
        root->left = vma_tree_rotate_left(root->left);
        return vma_tree_rotate_right(root);
    }
    
    /* Right-Right case */
    if (balance < -1 && vma_tree_balance(root->right) <= 0)
        return vma_tree_rotate_left(root);
    
    /* Right-Left case */
    if (balance < -1 && vma_tree_balance(root->right) > 0) {
        root->right = vma_tree_rotate_right(root->right);
        return vma_tree_rotate_left(root);
    }
    
    return root;
}

/* Remove VMA from mm */
static void remove_vm_struct(struct mm_struct *mm, struct vm_area_struct *vma)
{
    struct vm_area_struct **pprev;
    
    /* Remove from linked list */
    pprev = &mm->mmap;
    while (*pprev && *pprev != vma) {
        pprev = &(*pprev)->vm_next;
    }
    
    if (*pprev) {
        *pprev = vma->vm_next;
        mm->total_vm -= (vma->vm_end - vma->vm_start) >> PAGE_SHIFT;
    }
    
    /* Remove from tree */
    vma_tree_root = vma_tree_remove(vma_tree_root, vma);
}

/* Create new VMA */
static struct vm_area_struct *create_vma(unsigned long start, unsigned long end,
                                       unsigned long flags, unsigned long pgoff,
                                       struct file *file)
{
    struct vm_area_struct *vma;
    
    if (!vma_cache) {
        mmap_init();
    }
    
    vma = kmem_cache_alloc(vma_cache, GFP_KERNEL);
    if (!vma)
        return NULL;
    
    vma->vm_start = start;
    vma->vm_end = end;
    vma->vm_flags = flags;
    vma->vm_pgoff = pgoff;
    vma->vm_file = file;
    vma->vm_next = NULL;
    
    return vma;
}

/* Map pages into VMA */
static int map_vma_pages(struct vm_area_struct *vma)
{
    unsigned long addr, end;
    struct page *page;
    unsigned long prot = PTE_PRESENT | PTE_USER;
    
    if (vma->vm_flags & PROT_WRITE)
        prot |= PTE_WRITE;
    
    end = vma->vm_end;
    for (addr = vma->vm_start; addr < end; addr += PAGE_SIZE) {
        /* Allocate physical page */
        page = alloc_pages(GFP_USER, 0);
        if (!page) {
            /* Unmap what we've mapped so far */
            for (unsigned long unmap_addr = vma->vm_start; 
                 unmap_addr < addr; unmap_addr += PAGE_SIZE) {
                if (current_pgd) {
                    unmap_page(current_pgd, unmap_addr);
                }
                /* Free the physical page */
                struct page *old_page = pfn_to_page(virt_to_phys((void*)unmap_addr) >> PAGE_SHIFT);
                if (old_page) {
                    free_pages(old_page, 0);
                }
            }
            return -ENOMEM;
        }
        
        /* Map page using current process page tables */
        if (!current_pgd) {
            current_pgd = pgd_alloc();
            if (!current_pgd) {
                free_pages(page, 0);
                return -ENOMEM;
            }
        }
        
        if (map_page(current_pgd, addr, page_to_pfn(page) << PAGE_SHIFT, prot) < 0) {
            free_pages(page, 0);
            /* Unmap previously mapped pages */
            for (unsigned long unmap_addr = vma->vm_start;
                 unmap_addr < addr; unmap_addr += PAGE_SIZE) {
                unmap_page(current_pgd, unmap_addr);
            }
            return -ENOMEM;
        }
    }
    
    return 0;
}

/* Memory mapping implementation */
unsigned long do_mmap(unsigned long addr, unsigned long len, unsigned long prot,
                     unsigned long flags, unsigned long fd, unsigned long off)
{
    struct vm_area_struct *vma;
    unsigned long vm_flags = 0;
    
    if (!current_mm) {
        mmap_init();
    }
    
    /* Validate parameters */
    if (!len || (len & ~PAGE_MASK))
        return -EINVAL;
    
    len = (len + PAGE_SIZE - 1) & PAGE_MASK;
    
    /* Convert protection flags */
    if (prot & PROT_READ)   vm_flags |= PROT_READ;
    if (prot & PROT_WRITE)  vm_flags |= PROT_WRITE;
    if (prot & PROT_EXEC)   vm_flags |= PROT_EXEC;
    
    /* Convert mapping flags */
    if (flags & MAP_SHARED)   vm_flags |= MAP_SHARED;
    if (flags & MAP_PRIVATE)  vm_flags |= MAP_PRIVATE;
    
    /* Get unmapped area */
    if (!(flags & MAP_FIXED)) {
        addr = get_unmapped_area(addr, len, flags);
        if (!addr)
            return -ENOMEM;
    } else {
        /* Check if fixed address is available */
        if (find_vma_intersection(current_mm, addr, addr + len)) {
            return -EEXIST;
        }
    }
    
    /* Check for overlaps with existing VMAs */
    if (find_vma_intersection(current_mm, addr, addr + len)) {
        return -EEXIST;
    }
    
    /* Create VMA */
    vma = create_vma(addr, addr + len, vm_flags, off >> PAGE_SHIFT, NULL);
    if (!vma)
        return -ENOMEM;
    
    /* Insert VMA */
    insert_vm_struct(current_mm, vma);
    
    /* For anonymous mappings, we can defer page allocation */
    if (flags & MAP_ANONYMOUS) {
        /* Pages will be allocated on demand */
    } else {
        /* File-backed mapping - would need file operations */
        printf("File-backed mappings not fully implemented\n");
    }
    
    return addr;
}

/* Unmap memory */
int do_munmap(unsigned long addr, size_t len)
{
    struct vm_area_struct *vma, *next;
    unsigned long end;
    
    if (!current_mm)
        return -EINVAL;
    
    if (!len)
        return -EINVAL;
    
    len = (len + PAGE_SIZE - 1) & PAGE_MASK;
    end = addr + len;
    
    /* Find all VMAs in range */
    vma = find_vma(current_mm, addr);
    if (!vma || vma->vm_start > addr)
        return -EINVAL;
    
    while (vma && vma->vm_start < end) {
        next = vma->vm_next;
        
        if (vma->vm_start >= addr && vma->vm_end <= end) {
            /* Completely remove this VMA */
            remove_vm_struct(current_mm, vma);
            
            /* Unmap pages and free physical memory */
            if (current_pgd) {
                for (unsigned long unmap_addr = vma->vm_start;
                     unmap_addr < vma->vm_end; unmap_addr += PAGE_SIZE) {
                    /* Get physical address before unmapping */
                    unsigned long phys = virt_to_phys_pgtable(current_pgd, unmap_addr);
                    if (phys) {
                        /* Unmap from page table */
                        unmap_page(current_pgd, unmap_addr);
                        
                        /* Free physical page */
                        struct page *page = pfn_to_page(phys >> PAGE_SHIFT);
                        if (page) {
                            free_pages(page, 0);
                        }
                    }
                }
                
                /* Free page table pages if empty */
                free_page_tables(current_pgd, vma->vm_start, vma->vm_end);
            }
            
            /* Free VMA */
            kmem_cache_free(vma_cache, vma);
        } else if (vma->vm_start < addr && vma->vm_end > end) {
            /* VMA spans the entire unmap region - split it */
            struct vm_area_struct *new_vma;
            
            new_vma = create_vma(end, vma->vm_end, vma->vm_flags, 
                               vma->vm_pgoff + ((end - vma->vm_start) >> PAGE_SHIFT),
                               vma->vm_file);
            if (!new_vma)
                return -ENOMEM;
            
            /* Shrink original VMA */
            vma->vm_end = addr;
            
            /* Insert new VMA */
            insert_vm_struct(current_mm, new_vma);
            
            break;
        } else if (vma->vm_start < addr) {
            /* Partial unmap from end of VMA */
            vma->vm_end = addr;
        } else {
            /* Partial unmap from start of VMA */
            unsigned long old_start = vma->vm_start;
            vma->vm_start = end;
            vma->vm_pgoff += (end - old_start) >> PAGE_SHIFT;
        }
        
        vma = next;
    }
    
    return 0;
}

/* Handle memory fault */
int handle_mm_fault(struct vm_area_struct *vma, unsigned long addr, 
                   unsigned int flags)
{
    struct page *page;
    unsigned long prot = PTE_PRESENT | PTE_USER;
    
    if (!vma)
        return -EFAULT;
    
    /* Check permissions */
    if ((flags & FAULT_FLAG_WRITE) && !(vma->vm_flags & PROT_WRITE))
        return -EFAULT;
    
    if (!(vma->vm_flags & PROT_READ))
        return -EFAULT;
    
    /* Allocate page on demand */
    page = alloc_pages(GFP_USER, 0);
    if (!page)
        return -ENOMEM;
    
    /* Set up page table entry */
    if (vma->vm_flags & PROT_WRITE)
        prot |= PTE_WRITE;
    
    /* Map the page using actual page tables */
    if (!current_pgd) {
        current_pgd = pgd_alloc();
        if (!current_pgd) {
            free_pages(page, 0);
            return -ENOMEM;
        }
    }
    
    if (map_page(current_pgd, addr & PAGE_MASK, 
                 page_to_pfn(page) << PAGE_SHIFT, prot) < 0) {
        free_pages(page, 0);
        return -ENOMEM;
    }
    
    return 0;
}

/* Expand heap (brk system call) */
unsigned long do_brk(unsigned long addr, unsigned long len)
{
    struct vm_area_struct *vma;
    unsigned long old_brk, new_brk;
    
    if (!current_mm) {
        mmap_init();
    }
    
    old_brk = current_mm->brk;
    new_brk = addr + len;
    
    /* Round up to page boundary */
    new_brk = (new_brk + PAGE_SIZE - 1) & PAGE_MASK;
    
    if (new_brk <= old_brk) {
        /* Shrinking heap */
        if (new_brk < current_mm->start_brk)
            new_brk = current_mm->start_brk;
        
        /* Unmap pages between new_brk and old_brk */
        do_munmap(new_brk, old_brk - new_brk);
    } else {
        /* Expanding heap */
        if (do_mmap(old_brk, new_brk - old_brk, 
                   PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, 0, 0) != old_brk) {
            return old_brk;
        }
    }
    
    current_mm->brk = new_brk;
    return new_brk;
}

/* Get memory mapping information */
void show_mm_info(struct mm_struct *mm)
{
    struct vm_area_struct *vma;
    unsigned long total_vm = 0;
    int vma_count = 0;
    
    if (!mm)
        mm = current_mm;
    
    printf("\nMemory Mapping Information:\n");
    printf("==========================\n");
    printf("Code:   0x%08lx - 0x%08lx (%lu KB)\n", 
           mm->start_code, mm->end_code, 
           (mm->end_code - mm->start_code) / 1024);
    printf("Data:   0x%08lx - 0x%08lx (%lu KB)\n",
           mm->start_data, mm->end_data,
           (mm->end_data - mm->start_data) / 1024);
    printf("Heap:   0x%08lx - 0x%08lx (%lu KB)\n",
           mm->start_brk, mm->brk,
           (mm->brk - mm->start_brk) / 1024);
    printf("Stack:  0x%08lx\n", mm->start_stack);
    printf("Total VM: %lu pages (%lu KB)\n", mm->total_vm, mm->total_vm * 4);
    
    printf("\nVMA List:\n");
    printf("---------\n");
    
    for (vma = mm->mmap; vma; vma = vma->vm_next) {
        printf("0x%08lx - 0x%08lx [", vma->vm_start, vma->vm_end);
        if (vma->vm_flags & PROT_READ)  printf("r");
        else printf("-");
        if (vma->vm_flags & PROT_WRITE) printf("w");
        else printf("-");
        if (vma->vm_flags & PROT_EXEC)  printf("x");
        else printf("-");
        printf("] %lu KB\n", (vma->vm_end - vma->vm_start) / 1024);
        
        total_vm += vma->vm_end - vma->vm_start;
        vma_count++;
    }
    
    printf("\nSummary: %d VMAs, %lu KB total\n", vma_count, total_vm / 1024);
}

/* Test memory mapping functions */
void test_mmap(void)
{
    unsigned long addr1, addr2, addr3;
    
    printf("\nTesting memory mapping...\n");
    
    /* Initialize current page directory if not done */
    if (!current_pgd) {
        current_pgd = pgd_alloc();
        if (!current_pgd) {
            printf("Failed to allocate page directory\n");
            return;
        }
    }
    
    /* Test anonymous mapping */
    addr1 = do_mmap(0, 4096, PROT_READ | PROT_WRITE, 
                   MAP_PRIVATE | MAP_ANONYMOUS, 0, 0);
    printf("Anonymous mapping: 0x%lx\n", addr1);
    
    /* Test fixed mapping */
    addr2 = do_mmap(0x10000000, 8192, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 0, 0);
    printf("Fixed mapping: 0x%lx\n", addr2);
    
    /* Test another mapping */
    addr3 = do_mmap(0, 2048, PROT_READ,
                   MAP_PRIVATE | MAP_ANONYMOUS, 0, 0);
    printf("Read-only mapping: 0x%lx\n", addr3);
    
    show_mm_info(NULL);
    
    /* Test unmapping */
    printf("\nUnmapping 0x%lx...\n", addr2);
    do_munmap(addr2, 8192);
    
    show_mm_info(NULL);
}