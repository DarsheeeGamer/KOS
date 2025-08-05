/*
 * KOS Kernel Debugger Interface
 * Interactive debugging and inspection capabilities
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <signal.h>
#include <setjmp.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/mman.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <errno.h>

#include "logger.h"
#include "../mm/mm.h"
#include "../sched/sched.h"

/* Debugger commands */
typedef enum {
    DBG_CMD_HELP = 0,
    DBG_CMD_CONTINUE,
    DBG_CMD_STEP,
    DBG_CMD_NEXT,
    DBG_CMD_BREAK,
    DBG_CMD_DELETE,
    DBG_CMD_LIST,
    DBG_CMD_PRINT,
    DBG_CMD_EXAMINE,
    DBG_CMD_BACKTRACE,
    DBG_CMD_REGISTERS,
    DBG_CMD_MEMORY,
    DBG_CMD_THREADS,
    DBG_CMD_PROCESSES,
    DBG_CMD_SYMBOLS,
    DBG_CMD_MODULES,
    DBG_CMD_LOG,
    DBG_CMD_TRACE,
    DBG_CMD_WATCH,
    DBG_CMD_QUIT,
    DBG_CMD_MAX
} dbg_command_t;

/* Breakpoint types */
typedef enum {
    BP_TYPE_SOFTWARE = 0,     /* Software breakpoint (INT3) */
    BP_TYPE_HARDWARE,         /* Hardware breakpoint */
    BP_TYPE_WATCHPOINT,       /* Memory watchpoint */
    BP_TYPE_CONDITIONAL       /* Conditional breakpoint */
} bp_type_t;

/* Breakpoint structure */
typedef struct breakpoint {
    uint32_t id;              /* Breakpoint ID */
    bp_type_t type;           /* Breakpoint type */
    void *address;            /* Breakpoint address */
    uint8_t original_byte;    /* Original instruction byte */
    bool enabled;             /* Breakpoint enabled */
    uint32_t hit_count;       /* Hit count */
    char condition[256];      /* Conditional expression */
    struct breakpoint *next;  /* Next breakpoint */
} breakpoint_t;

/* Watchpoint structure */
typedef struct watchpoint {
    uint32_t id;              /* Watchpoint ID */
    void *address;            /* Watch address */
    size_t size;              /* Watch size */
    uint32_t access_type;     /* Read/Write/Execute */
    uint32_t hit_count;       /* Hit count */
    struct watchpoint *next;  /* Next watchpoint */
} watchpoint_t;

/* Debugger state */
static struct {
    bool active;                      /* Debugger active */
    bool single_step;                 /* Single stepping */
    pid_t target_pid;                 /* Target process */
    pthread_t target_tid;             /* Target thread */
    breakpoint_t *breakpoints;        /* Breakpoint list */
    watchpoint_t *watchpoints;        /* Watchpoint list */
    uint32_t next_bp_id;              /* Next breakpoint ID */
    uint32_t next_wp_id;              /* Next watchpoint ID */
    jmp_buf jmp_env;                  /* Jump buffer for signal handling */
    struct termios saved_termios;     /* Saved terminal settings */
    bool terminal_saved;              /* Terminal settings saved */
    FILE *output;                     /* Output stream */
    FILE *input;                      /* Input stream */
    char last_command[256];           /* Last command for repeat */
    pthread_mutex_t lock;             /* Debugger lock */
} debugger_state = {
    .active = false,
    .single_step = false,
    .target_pid = -1,
    .next_bp_id = 1,
    .next_wp_id = 1,
    .output = NULL,
    .input = NULL,
    .lock = PTHREAD_MUTEX_INITIALIZER
};

/* Command handlers */
typedef int (*dbg_cmd_handler_t)(char *args);

/* Command structure */
typedef struct {
    const char *name;
    const char *shortcut;
    const char *description;
    dbg_cmd_handler_t handler;
} dbg_command_info_t;

/* Forward declarations */
static int dbg_cmd_help(char *args);
static int dbg_cmd_continue(char *args);
static int dbg_cmd_step(char *args);
static int dbg_cmd_next(char *args);
static int dbg_cmd_break(char *args);
static int dbg_cmd_delete(char *args);
static int dbg_cmd_list(char *args);
static int dbg_cmd_print(char *args);
static int dbg_cmd_examine(char *args);
static int dbg_cmd_backtrace(char *args);
static int dbg_cmd_registers(char *args);
static int dbg_cmd_memory(char *args);
static int dbg_cmd_threads(char *args);
static int dbg_cmd_processes(char *args);
static int dbg_cmd_symbols(char *args);
static int dbg_cmd_modules(char *args);
static int dbg_cmd_log(char *args);
static int dbg_cmd_trace(char *args);
static int dbg_cmd_watch(char *args);
static int dbg_cmd_quit(char *args);

/* Command table */
static dbg_command_info_t dbg_commands[] = {
    {"help",      "h",  "Show help information",           dbg_cmd_help},
    {"continue",  "c",  "Continue execution",              dbg_cmd_continue},
    {"step",      "s",  "Single step instruction",         dbg_cmd_step},
    {"next",      "n",  "Step over function calls",        dbg_cmd_next},
    {"break",     "b",  "Set breakpoint",                  dbg_cmd_break},
    {"delete",    "d",  "Delete breakpoint",               dbg_cmd_delete},
    {"list",      "l",  "List source code",                dbg_cmd_list},
    {"print",     "p",  "Print expression",                dbg_cmd_print},
    {"examine",   "x",  "Examine memory",                  dbg_cmd_examine},
    {"backtrace", "bt", "Show stack backtrace",            dbg_cmd_backtrace},
    {"registers", "r",  "Show registers",                  dbg_cmd_registers},
    {"memory",    "m",  "Show memory map",                 dbg_cmd_memory},
    {"threads",   "t",  "List threads",                    dbg_cmd_threads},
    {"processes", "ps", "List processes",                  dbg_cmd_processes},
    {"symbols",   "sym","Show symbol table",               dbg_cmd_symbols},
    {"modules",   "mod","List loaded modules",             dbg_cmd_modules},
    {"log",       "lg", "Show kernel log",                 dbg_cmd_log},
    {"trace",     "tr", "Control tracing",                 dbg_cmd_trace},
    {"watch",     "w",  "Set watchpoint",                  dbg_cmd_watch},
    {"quit",      "q",  "Quit debugger",                   dbg_cmd_quit}
};

/* ANSI color codes */
#define COLOR_RESET   "\033[0m"
#define COLOR_RED     "\033[31m"
#define COLOR_GREEN   "\033[32m"
#define COLOR_YELLOW  "\033[33m"
#define COLOR_BLUE    "\033[34m"
#define COLOR_MAGENTA "\033[35m"
#define COLOR_CYAN    "\033[36m"
#define COLOR_WHITE   "\033[37m"
#define COLOR_BOLD    "\033[1m"

/* Print formatted output */
static void dbg_printf(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    vfprintf(debugger_state.output, format, args);
    va_end(args);
    fflush(debugger_state.output);
}

/* Print error message */
static void dbg_error(const char *format, ...)
{
    va_list args;
    fprintf(debugger_state.output, COLOR_RED "Error: " COLOR_RESET);
    va_start(args, format);
    vfprintf(debugger_state.output, format, args);
    va_end(args);
    fprintf(debugger_state.output, "\n");
    fflush(debugger_state.output);
}

/* Print success message */
static void dbg_success(const char *format, ...)
{
    va_list args;
    fprintf(debugger_state.output, COLOR_GREEN);
    va_start(args, format);
    vfprintf(debugger_state.output, format, args);
    va_end(args);
    fprintf(debugger_state.output, COLOR_RESET "\n");
    fflush(debugger_state.output);
}

/* Setup terminal for raw input */
static void setup_terminal(void)
{
    if (!debugger_state.terminal_saved) {
        tcgetattr(STDIN_FILENO, &debugger_state.saved_termios);
        debugger_state.terminal_saved = true;
    }
    
    struct termios raw = debugger_state.saved_termios;
    raw.c_lflag &= ~(ECHO | ICANON);
    raw.c_cc[VMIN] = 1;
    raw.c_cc[VTIME] = 0;
    
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
}

/* Restore terminal settings */
static void restore_terminal(void)
{
    if (debugger_state.terminal_saved) {
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &debugger_state.saved_termios);
    }
}

/* Signal handler for debugger */
static void dbg_signal_handler(int sig)
{
    switch (sig) {
        case SIGINT:
            dbg_printf("\n" COLOR_YELLOW "Interrupted" COLOR_RESET "\n");
            siglongjmp(debugger_state.jmp_env, 1);
            break;
            
        case SIGTRAP:
            /* Breakpoint hit */
            dbg_printf(COLOR_YELLOW "Breakpoint hit" COLOR_RESET "\n");
            break;
            
        case SIGSEGV:
            dbg_error("Segmentation fault in target");
            break;
            
        default:
            dbg_printf("Signal %d received\n", sig);
            break;
    }
}

/* Install signal handlers */
static void install_signal_handlers(void)
{
    struct sigaction sa;
    sa.sa_handler = dbg_signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTRAP, &sa, NULL);
    sigaction(SIGSEGV, &sa, NULL);
}

/* Command: help */
static int dbg_cmd_help(char *args)
{
    (void)args;
    
    dbg_printf(COLOR_BOLD "KOS Kernel Debugger Commands:\n" COLOR_RESET);
    dbg_printf("==============================\n");
    
    for (int i = 0; i < DBG_CMD_MAX; i++) {
        dbg_printf(COLOR_CYAN "%-10s" COLOR_RESET " %-4s - %s\n",
                   dbg_commands[i].name,
                   dbg_commands[i].shortcut,
                   dbg_commands[i].description);
    }
    
    dbg_printf("\nExamples:\n");
    dbg_printf("  break main              - Set breakpoint at main\n");
    dbg_printf("  break *0x401234         - Set breakpoint at address\n");
    dbg_printf("  print $rax              - Print register value\n");
    dbg_printf("  x/10x $rsp              - Examine 10 hex words at stack pointer\n");
    dbg_printf("  watch *0x601000 4 rw    - Watch 4 bytes at address for read/write\n");
    
    return 0;
}

/* Command: continue */
static int dbg_cmd_continue(char *args)
{
    (void)args;
    
    debugger_state.single_step = false;
    
    if (debugger_state.target_pid > 0) {
        if (ptrace(PTRACE_CONT, debugger_state.target_pid, NULL, NULL) == -1) {
            dbg_error("Failed to continue process: %s", strerror(errno));
            return -1;
        }
        dbg_success("Continuing execution...");
    } else {
        dbg_error("No target process");
        return -1;
    }
    
    return 0;
}

/* Command: step */
static int dbg_cmd_step(char *args)
{
    (void)args;
    
    debugger_state.single_step = true;
    
    if (debugger_state.target_pid > 0) {
        if (ptrace(PTRACE_SINGLESTEP, debugger_state.target_pid, NULL, NULL) == -1) {
            dbg_error("Failed to single step: %s", strerror(errno));
            return -1;
        }
        dbg_success("Single stepping...");
    } else {
        dbg_error("No target process");
        return -1;
    }
    
    return 0;
}

/* Command: next */
static int dbg_cmd_next(char *args)
{
    (void)args;
    
    /* Similar to step but steps over function calls */
    /* This would require disassembly to detect calls */
    dbg_printf("Step over not yet implemented\n");
    return 0;
}

/* Set software breakpoint */
static int set_software_breakpoint(void *address)
{
    breakpoint_t *bp = malloc(sizeof(breakpoint_t));
    if (!bp) {
        return -1;
    }
    
    bp->id = debugger_state.next_bp_id++;
    bp->type = BP_TYPE_SOFTWARE;
    bp->address = address;
    bp->enabled = true;
    bp->hit_count = 0;
    bp->condition[0] = '\0';
    
    /* Read original byte */
    errno = 0;
    long data = ptrace(PTRACE_PEEKTEXT, debugger_state.target_pid, address, NULL);
    if (errno != 0) {
        free(bp);
        return -1;
    }
    
    bp->original_byte = data & 0xFF;
    
    /* Write INT3 instruction */
    data = (data & ~0xFF) | 0xCC;
    if (ptrace(PTRACE_POKETEXT, debugger_state.target_pid, address, data) == -1) {
        free(bp);
        return -1;
    }
    
    /* Add to list */
    bp->next = debugger_state.breakpoints;
    debugger_state.breakpoints = bp;
    
    return bp->id;
}

/* Command: break */
static int dbg_cmd_break(char *args)
{
    if (!args || !*args) {
        dbg_error("Usage: break <address|symbol>");
        return -1;
    }
    
    void *address = NULL;
    
    /* Parse address */
    if (args[0] == '*') {
        /* Direct address */
        address = (void *)strtoul(args + 1, NULL, 0);
    } else {
        /* Symbol name - would need symbol table lookup */
        dbg_error("Symbol lookup not yet implemented");
        return -1;
    }
    
    int bp_id = set_software_breakpoint(address);
    if (bp_id > 0) {
        dbg_success("Breakpoint %d set at %p", bp_id, address);
    } else {
        dbg_error("Failed to set breakpoint");
    }
    
    return 0;
}

/* Command: delete */
static int dbg_cmd_delete(char *args)
{
    if (!args || !*args) {
        /* Delete all breakpoints */
        breakpoint_t *bp = debugger_state.breakpoints;
        while (bp) {
            breakpoint_t *next = bp->next;
            
            /* Restore original byte */
            if (bp->type == BP_TYPE_SOFTWARE && bp->enabled) {
                long data = ptrace(PTRACE_PEEKTEXT, debugger_state.target_pid, 
                                 bp->address, NULL);
                data = (data & ~0xFF) | bp->original_byte;
                ptrace(PTRACE_POKETEXT, debugger_state.target_pid, 
                       bp->address, data);
            }
            
            free(bp);
            bp = next;
        }
        debugger_state.breakpoints = NULL;
        dbg_success("All breakpoints deleted");
    } else {
        /* Delete specific breakpoint */
        uint32_t id = strtoul(args, NULL, 0);
        breakpoint_t **bp_ptr = &debugger_state.breakpoints;
        
        while (*bp_ptr) {
            if ((*bp_ptr)->id == id) {
                breakpoint_t *bp = *bp_ptr;
                *bp_ptr = bp->next;
                
                /* Restore original byte */
                if (bp->type == BP_TYPE_SOFTWARE && bp->enabled) {
                    long data = ptrace(PTRACE_PEEKTEXT, debugger_state.target_pid,
                                     bp->address, NULL);
                    data = (data & ~0xFF) | bp->original_byte;
                    ptrace(PTRACE_POKETEXT, debugger_state.target_pid,
                           bp->address, data);
                }
                
                free(bp);
                dbg_success("Breakpoint %u deleted", id);
                return 0;
            }
            bp_ptr = &(*bp_ptr)->next;
        }
        
        dbg_error("Breakpoint %u not found", id);
    }
    
    return 0;
}

/* Command: list */
static int dbg_cmd_list(char *args)
{
    (void)args;
    
    dbg_printf(COLOR_BOLD "Breakpoints:\n" COLOR_RESET);
    dbg_printf("ID  Type      Address      Enabled  Hits  Condition\n");
    dbg_printf("--  --------  -----------  -------  ----  ---------\n");
    
    breakpoint_t *bp = debugger_state.breakpoints;
    while (bp) {
        const char *type_str = "Unknown";
        switch (bp->type) {
            case BP_TYPE_SOFTWARE:    type_str = "Software"; break;
            case BP_TYPE_HARDWARE:    type_str = "Hardware"; break;
            case BP_TYPE_WATCHPOINT:  type_str = "Watch"; break;
            case BP_TYPE_CONDITIONAL: type_str = "Conditional"; break;
        }
        
        dbg_printf("%-3u %-8s  %p  %-7s  %-4u  %s\n",
                   bp->id, type_str, bp->address,
                   bp->enabled ? "Yes" : "No",
                   bp->hit_count,
                   bp->condition[0] ? bp->condition : "-");
        
        bp = bp->next;
    }
    
    return 0;
}

/* Command: print */
static int dbg_cmd_print(char *args)
{
    if (!args || !*args) {
        dbg_error("Usage: print <expression>");
        return -1;
    }
    
    /* Simple register printing for now */
    if (args[0] == '$') {
        /* Register name */
        struct user_regs_struct regs;
        if (ptrace(PTRACE_GETREGS, debugger_state.target_pid, NULL, &regs) == -1) {
            dbg_error("Failed to get registers: %s", strerror(errno));
            return -1;
        }
        
        /* Parse register name */
        if (strcmp(args, "$rax") == 0) {
            dbg_printf("$rax = 0x%llx\n", regs.rax);
        } else if (strcmp(args, "$rbx") == 0) {
            dbg_printf("$rbx = 0x%llx\n", regs.rbx);
        } else if (strcmp(args, "$rcx") == 0) {
            dbg_printf("$rcx = 0x%llx\n", regs.rcx);
        } else if (strcmp(args, "$rdx") == 0) {
            dbg_printf("$rdx = 0x%llx\n", regs.rdx);
        } else if (strcmp(args, "$rsi") == 0) {
            dbg_printf("$rsi = 0x%llx\n", regs.rsi);
        } else if (strcmp(args, "$rdi") == 0) {
            dbg_printf("$rdi = 0x%llx\n", regs.rdi);
        } else if (strcmp(args, "$rsp") == 0) {
            dbg_printf("$rsp = 0x%llx\n", regs.rsp);
        } else if (strcmp(args, "$rbp") == 0) {
            dbg_printf("$rbp = 0x%llx\n", regs.rbp);
        } else if (strcmp(args, "$rip") == 0) {
            dbg_printf("$rip = 0x%llx\n", regs.rip);
        } else {
            dbg_error("Unknown register: %s", args);
        }
    } else {
        dbg_error("Expression evaluation not yet implemented");
    }
    
    return 0;
}

/* Command: examine */
static int dbg_cmd_examine(char *args)
{
    if (!args || !*args) {
        dbg_error("Usage: x/[count][format] <address>");
        return -1;
    }
    
    /* Parse format: x/10x $rsp */
    int count = 1;
    char format = 'x';
    char *addr_str = args;
    
    if (args[0] == '/') {
        args++;
        count = strtol(args, &addr_str, 10);
        if (count == 0) count = 1;
        
        if (*addr_str && *addr_str != ' ') {
            format = *addr_str++;
        }
        
        while (*addr_str == ' ') addr_str++;
    }
    
    /* Parse address */
    void *address = NULL;
    if (addr_str[0] == '$') {
        /* Register */
        struct user_regs_struct regs;
        if (ptrace(PTRACE_GETREGS, debugger_state.target_pid, NULL, &regs) == -1) {
            dbg_error("Failed to get registers");
            return -1;
        }
        
        if (strcmp(addr_str, "$rsp") == 0) {
            address = (void *)regs.rsp;
        } else if (strcmp(addr_str, "$rbp") == 0) {
            address = (void *)regs.rbp;
        } else {
            dbg_error("Unknown register: %s", addr_str);
            return -1;
        }
    } else {
        address = (void *)strtoul(addr_str, NULL, 0);
    }
    
    /* Read and display memory */
    for (int i = 0; i < count; i++) {
        errno = 0;
        long data = ptrace(PTRACE_PEEKDATA, debugger_state.target_pid, 
                          address + i * sizeof(long), NULL);
        if (errno != 0) {
            dbg_error("Cannot access memory at %p", address + i * sizeof(long));
            break;
        }
        
        if (i % 4 == 0) {
            dbg_printf("%p: ", address + i * sizeof(long));
        }
        
        switch (format) {
            case 'x':
                dbg_printf("0x%016lx ", data);
                break;
            case 'd':
                dbg_printf("%20ld ", data);
                break;
            case 'c':
                for (int j = 0; j < 8; j++) {
                    char c = (data >> (j * 8)) & 0xFF;
                    dbg_printf("%c", (c >= 32 && c < 127) ? c : '.');
                }
                dbg_printf(" ");
                break;
        }
        
        if ((i + 1) % 4 == 0 || i == count - 1) {
            dbg_printf("\n");
        }
    }
    
    return 0;
}

/* Command: backtrace */
static int dbg_cmd_backtrace(char *args)
{
    (void)args;
    
    struct user_regs_struct regs;
    if (ptrace(PTRACE_GETREGS, debugger_state.target_pid, NULL, &regs) == -1) {
        dbg_error("Failed to get registers");
        return -1;
    }
    
    dbg_printf(COLOR_BOLD "Stack backtrace:\n" COLOR_RESET);
    
    void *rbp = (void *)regs.rbp;
    void *rip = (void *)regs.rip;
    int frame = 0;
    
    dbg_printf("#%-2d %p in <unknown>\n", frame++, rip);
    
    /* Walk stack frames */
    while (rbp && frame < 20) {
        errno = 0;
        long next_rbp = ptrace(PTRACE_PEEKDATA, debugger_state.target_pid, rbp, NULL);
        long ret_addr = ptrace(PTRACE_PEEKDATA, debugger_state.target_pid, 
                              rbp + sizeof(void*), NULL);
        
        if (errno != 0) {
            break;
        }
        
        dbg_printf("#%-2d %p in <unknown>\n", frame++, (void *)ret_addr);
        
        if (next_rbp <= (long)rbp) {
            break; /* Prevent infinite loop */
        }
        
        rbp = (void *)next_rbp;
    }
    
    return 0;
}

/* Command: registers */
static int dbg_cmd_registers(char *args)
{
    (void)args;
    
    struct user_regs_struct regs;
    if (ptrace(PTRACE_GETREGS, debugger_state.target_pid, NULL, &regs) == -1) {
        dbg_error("Failed to get registers");
        return -1;
    }
    
    dbg_printf(COLOR_BOLD "Registers:\n" COLOR_RESET);
    dbg_printf("rax: 0x%016llx  rbx: 0x%016llx\n", regs.rax, regs.rbx);
    dbg_printf("rcx: 0x%016llx  rdx: 0x%016llx\n", regs.rcx, regs.rdx);
    dbg_printf("rsi: 0x%016llx  rdi: 0x%016llx\n", regs.rsi, regs.rdi);
    dbg_printf("rbp: 0x%016llx  rsp: 0x%016llx\n", regs.rbp, regs.rsp);
    dbg_printf("r8:  0x%016llx  r9:  0x%016llx\n", regs.r8, regs.r9);
    dbg_printf("r10: 0x%016llx  r11: 0x%016llx\n", regs.r10, regs.r11);
    dbg_printf("r12: 0x%016llx  r13: 0x%016llx\n", regs.r12, regs.r13);
    dbg_printf("r14: 0x%016llx  r15: 0x%016llx\n", regs.r14, regs.r15);
    dbg_printf("rip: 0x%016llx  eflags: 0x%08llx\n", regs.rip, regs.eflags);
    dbg_printf("cs:  0x%04llx  ss: 0x%04llx  ds: 0x%04llx  es: 0x%04llx\n",
               regs.cs, regs.ss, regs.ds, regs.es);
    dbg_printf("fs:  0x%04llx  gs: 0x%04llx\n", regs.fs, regs.gs);
    
    return 0;
}

/* Command: memory */
static int dbg_cmd_memory(char *args)
{
    (void)args;
    
    char maps_path[256];
    snprintf(maps_path, sizeof(maps_path), "/proc/%d/maps", debugger_state.target_pid);
    
    FILE *maps = fopen(maps_path, "r");
    if (!maps) {
        dbg_error("Failed to open memory maps");
        return -1;
    }
    
    dbg_printf(COLOR_BOLD "Memory mappings:\n" COLOR_RESET);
    dbg_printf("Start              End                Perm  Offset    Device   Inode  Path\n");
    
    char line[512];
    while (fgets(line, sizeof(line), maps)) {
        dbg_printf("%s", line);
    }
    
    fclose(maps);
    return 0;
}

/* Command: threads */
static int dbg_cmd_threads(char *args)
{
    (void)args;
    
    dbg_printf(COLOR_BOLD "Threads:\n" COLOR_RESET);
    
    /* List threads from /proc/[pid]/task/ */
    char task_dir[256];
    snprintf(task_dir, sizeof(task_dir), "/proc/%d/task", debugger_state.target_pid);
    
    /* Would need to iterate through task directory */
    dbg_printf("Thread listing not yet implemented\n");
    
    return 0;
}

/* Command: processes */
static int dbg_cmd_processes(char *args)
{
    (void)args;
    
    dbg_printf(COLOR_BOLD "Processes:\n" COLOR_RESET);
    dbg_printf("PID   PPID  State  Name\n");
    dbg_printf("----  ----  -----  ----\n");
    
    /* Would iterate through /proc to list processes */
    /* For now, just show current target */
    if (debugger_state.target_pid > 0) {
        dbg_printf("%-5d -     R      <target>\n", debugger_state.target_pid);
    }
    
    return 0;
}

/* Command: symbols */
static int dbg_cmd_symbols(char *args)
{
    (void)args;
    
    dbg_printf("Symbol table not yet implemented\n");
    return 0;
}

/* Command: modules */
static int dbg_cmd_modules(char *args)
{
    (void)args;
    
    dbg_printf("Module listing not yet implemented\n");
    return 0;
}

/* Command: log */
static int dbg_cmd_log(char *args)
{
    int count = 20;
    
    if (args && *args) {
        count = atoi(args);
    }
    
    dbg_printf(COLOR_BOLD "Recent kernel log entries:\n" COLOR_RESET);
    kos_log_dump_recent(count);
    
    return 0;
}

/* Command: trace */
static int dbg_cmd_trace(char *args)
{
    if (!args || !*args) {
        dbg_error("Usage: trace <on|off|stats>");
        return -1;
    }
    
    if (strcmp(args, "on") == 0) {
        dbg_printf("Enabling kernel tracing...\n");
        /* Would enable tracing */
    } else if (strcmp(args, "off") == 0) {
        dbg_printf("Disabling kernel tracing...\n");
        /* Would disable tracing */
    } else if (strcmp(args, "stats") == 0) {
        dbg_printf("Trace statistics:\n");
        /* Would show trace stats */
    } else {
        dbg_error("Unknown trace command: %s", args);
    }
    
    return 0;
}

/* Command: watch */
static int dbg_cmd_watch(char *args)
{
    if (!args || !*args) {
        dbg_error("Usage: watch <address> <size> <rw>");
        return -1;
    }
    
    dbg_printf("Watchpoints not yet implemented\n");
    return 0;
}

/* Command: quit */
static int dbg_cmd_quit(char *args)
{
    (void)args;
    
    dbg_printf("Quitting debugger...\n");
    debugger_state.active = false;
    
    return 0;
}

/* Parse and execute command */
static int execute_command(char *cmdline)
{
    if (!cmdline || !*cmdline) {
        /* Repeat last command */
        if (debugger_state.last_command[0]) {
            cmdline = debugger_state.last_command;
        } else {
            return 0;
        }
    } else {
        /* Save command for repeat */
        strncpy(debugger_state.last_command, cmdline, sizeof(debugger_state.last_command) - 1);
    }
    
    /* Parse command and arguments */
    char *cmd = strtok(cmdline, " \t\n");
    char *args = strtok(NULL, "\n");
    
    if (!cmd) {
        return 0;
    }
    
    /* Find and execute command */
    for (int i = 0; i < DBG_CMD_MAX; i++) {
        if (strcmp(cmd, dbg_commands[i].name) == 0 ||
            strcmp(cmd, dbg_commands[i].shortcut) == 0) {
            return dbg_commands[i].handler(args);
        }
    }
    
    dbg_error("Unknown command: %s", cmd);
    return -1;
}

/* Main debugger loop */
static void debugger_loop(void)
{
    char cmdline[256];
    
    dbg_printf(COLOR_BOLD COLOR_GREEN "KOS Kernel Debugger\n" COLOR_RESET);
    dbg_printf("Type 'help' for available commands\n\n");
    
    while (debugger_state.active) {
        /* Set jump point for signal handling */
        if (sigsetjmp(debugger_state.jmp_env, 1) != 0) {
            /* Returned from signal handler */
            dbg_printf("\n");
        }
        
        /* Show prompt */
        dbg_printf(COLOR_CYAN "(kdb) " COLOR_RESET);
        fflush(debugger_state.output);
        
        /* Read command */
        if (!fgets(cmdline, sizeof(cmdline), debugger_state.input)) {
            break;
        }
        
        /* Remove newline */
        size_t len = strlen(cmdline);
        if (len > 0 && cmdline[len-1] == '\n') {
            cmdline[len-1] = '\0';
        }
        
        /* Execute command */
        execute_command(cmdline);
    }
}

/* Attach to process */
int kos_debugger_attach(pid_t pid)
{
    pthread_mutex_lock(&debugger_state.lock);
    
    if (debugger_state.active) {
        pthread_mutex_unlock(&debugger_state.lock);
        return -1;
    }
    
    /* Attach to process */
    if (ptrace(PTRACE_ATTACH, pid, NULL, NULL) == -1) {
        pthread_mutex_unlock(&debugger_state.lock);
        return -1;
    }
    
    /* Wait for process to stop */
    int status;
    waitpid(pid, &status, 0);
    
    debugger_state.target_pid = pid;
    debugger_state.active = true;
    
    pthread_mutex_unlock(&debugger_state.lock);
    
    return 0;
}

/* Detach from process */
void kos_debugger_detach(void)
{
    pthread_mutex_lock(&debugger_state.lock);
    
    if (debugger_state.target_pid > 0) {
        /* Remove all breakpoints */
        breakpoint_t *bp = debugger_state.breakpoints;
        while (bp) {
            breakpoint_t *next = bp->next;
            
            /* Restore original byte */
            if (bp->type == BP_TYPE_SOFTWARE && bp->enabled) {
                long data = ptrace(PTRACE_PEEKTEXT, debugger_state.target_pid,
                                 bp->address, NULL);
                data = (data & ~0xFF) | bp->original_byte;
                ptrace(PTRACE_POKETEXT, debugger_state.target_pid,
                       bp->address, data);
            }
            
            free(bp);
            bp = next;
        }
        debugger_state.breakpoints = NULL;
        
        /* Detach from process */
        ptrace(PTRACE_DETACH, debugger_state.target_pid, NULL, NULL);
        debugger_state.target_pid = -1;
    }
    
    debugger_state.active = false;
    
    pthread_mutex_unlock(&debugger_state.lock);
}

/* Initialize debugger */
int kos_debugger_init(void)
{
    debugger_state.output = stdout;
    debugger_state.input = stdin;
    
    /* Install signal handlers */
    install_signal_handlers();
    
    return 0;
}

/* Start interactive debugger */
void kos_debugger_start(void)
{
    pthread_mutex_lock(&debugger_state.lock);
    
    if (debugger_state.active) {
        pthread_mutex_unlock(&debugger_state.lock);
        return;
    }
    
    debugger_state.active = true;
    pthread_mutex_unlock(&debugger_state.lock);
    
    /* Setup terminal */
    setup_terminal();
    
    /* Run debugger loop */
    debugger_loop();
    
    /* Restore terminal */
    restore_terminal();
    
    /* Cleanup */
    kos_debugger_detach();
}

/* Kernel panic handler with debugger */
void kos_panic_debugger(const char *format, ...)
{
    va_list args;
    
    /* Print panic message */
    fprintf(stderr, COLOR_RED COLOR_BOLD "\nKERNEL PANIC: " COLOR_RESET);
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fprintf(stderr, "\n");
    
    /* Dump registers and stack */
    dbg_printf("\nEntering debugger due to panic...\n");
    
    /* Start debugger */
    kos_debugger_start();
    
    /* If debugger exits, abort */
    abort();
}