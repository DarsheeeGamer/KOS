# KOS Kernel Makefile
# Build system for all kernel components

CC = gcc
CFLAGS = -Wall -Wextra -O2 -g -fPIC -std=c11
INCLUDES = -I. -I.. -I../..
LDFLAGS = -shared -lpthread -lrt
AR = ar
ARFLAGS = rcs

# Core source files
CORE_SRCS = kcore.c syscall.c init.c panic.c time.c irq.c resource_monitor.c sysctl.c
CORE_OBJS = $(CORE_SRCS:.c=.o)

# Debug source files
DEBUG_SRCS = debug/logger.c debug/tracer.c debug/debugger.c
DEBUG_OBJS = $(DEBUG_SRCS:.c=.o)

# Target libraries
LIBKOS_KERNEL = libkos_kernel.so
LIBKOS_KERNEL_A = libkos_kernel.a
LIBKOS_SYSCTL = libkos_sysctl.so

# Default target
all: $(LIBKOS_KERNEL) $(LIBKOS_KERNEL_A) $(LIBKOS_SYSCTL)

# Build shared library
$(LIBKOS_KERNEL): $(CORE_OBJS) $(DEBUG_OBJS)
	@echo "Building kernel shared library..."
	$(CC) $(LDFLAGS) -o $@ $^

# Build static library
$(LIBKOS_KERNEL_A): $(CORE_OBJS) $(DEBUG_OBJS)
	@echo "Building kernel static library..."
	$(AR) $(ARFLAGS) $@ $^

# Build sysctl library separately for Python wrapper
$(LIBKOS_SYSCTL): sysctl.o
	@echo "Building sysctl shared library..."
	$(CC) $(LDFLAGS) -o $@ $^

# Core kernel objects
%.o: %.c
	@echo "Compiling $<..."
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# Test program
test: test_kernel.c $(LIBKOS_KERNEL)
	@echo "Building kernel test program..."
	$(CC) $(CFLAGS) $(INCLUDES) -o test_kernel $< -L. -lkos_kernel -lpthread -lrt
	@echo "Running kernel test..."
	LD_LIBRARY_PATH=. ./test_kernel

# Create test program
test_kernel.c:
	@echo "Creating test program..."
	@echo '#include "kernel.h"' > test_kernel.c
	@echo '#include <stdio.h>' >> test_kernel.c
	@echo '#include <stdlib.h>' >> test_kernel.c
	@echo '#include <unistd.h>' >> test_kernel.c
	@echo 'int main() {' >> test_kernel.c
	@echo '    printf("KOS Kernel Integration Test\\n");' >> test_kernel.c
	@echo '    printf("Initializing kernel...\\n");' >> test_kernel.c
	@echo '    if (kos_kernel_init_full(NULL) != 0) {' >> test_kernel.c
	@echo '        printf("Failed to initialize kernel\\n");' >> test_kernel.c
	@echo '        return 1;' >> test_kernel.c
	@echo '    }' >> test_kernel.c
	@echo '    printf("Kernel initialized successfully!\\n");' >> test_kernel.c
	@echo '    return 0;' >> test_kernel.c
	@echo '}' >> test_kernel.c

# Clean targets
clean:
	@echo "Cleaning kernel build files..."
	rm -f $(CORE_OBJS)
	rm -f $(LIBKOS_KERNEL) $(LIBKOS_KERNEL_A)
	rm -f test_kernel test_kernel.c
	rm -f *.log

# Help target
help:
	@echo "KOS Kernel Build System"
	@echo "======================="
	@echo ""
	@echo "Targets:"
	@echo "  all          - Build kernel libraries"
	@echo "  test         - Build and run test program"
	@echo "  clean        - Clean build files"
	@echo "  help         - Show this help message"

.PHONY: all test clean help