# KOS Filesystem Makefile
# Compiles the C/C++ filesystem components and creates shared library

CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -fPIC -O2 -g
LDFLAGS = -shared -lpthread
TARGET = libkos_fs.so

# Source files
SOURCES = vfs.c inode.c dcache.c file.c namei.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = fs.h

# Default target
all: $(TARGET)

# Build shared library
$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

# Compile source files
%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

# Install library
install: $(TARGET)
	cp $(TARGET) /usr/local/lib/
	cp $(HEADERS) /usr/local/include/
	ldconfig

# Clean build files
clean:
	rm -f $(OBJECTS) $(TARGET)

# Debug build
debug: CFLAGS += -DDEBUG -O0
debug: $(TARGET)

# Test build (includes test main)
test: CFLAGS += -DTEST_BUILD
test: test_fs

test_fs: $(OBJECTS) test_main.o
	$(CC) -lpthread -o $@ $^

test_main.o: test_main.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

# Create test main if it doesn't exist
test_main.c:
	@echo "Creating test main..."
	@cat > test_main.c << 'EOF'
#include "fs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

int main() {
    printf("KOS Filesystem Test\n");
    
    // Initialize VFS
    kos_vfs_init();
    
    // Test basic operations
    printf("Testing basic filesystem operations...\n");
    
    // Test file creation
    int fd = kos_sys_open("/tmp/test.txt", KOS_O_CREAT | KOS_O_WRONLY, 0644);
    if (fd >= 0) {
        printf("✓ File creation successful (fd=%d)\n", fd);
        
        // Test write
        const char *data = "Hello, KOS Filesystem!";
        ssize_t written = kos_sys_write(fd, data, strlen(data));
        printf("✓ Wrote %zd bytes\n", written);
        
        // Close file
        kos_sys_close(fd);
        printf("✓ File closed\n");
    } else {
        printf("✗ File creation failed\n");
    }
    
    // Test file reading
    fd = kos_sys_open("/tmp/test.txt", KOS_O_RDONLY, 0);
    if (fd >= 0) {
        printf("✓ File opened for reading\n");
        
        char buffer[256];
        ssize_t read_bytes = kos_sys_read(fd, buffer, sizeof(buffer) - 1);
        if (read_bytes > 0) {
            buffer[read_bytes] = '\0';
            printf("✓ Read %zd bytes: '%s'\n", read_bytes, buffer);
        }
        
        kos_sys_close(fd);
    }
    
    // Test directory operations
    if (kos_sys_mkdir("/tmp/testdir", 0755) == 0) {
        printf("✓ Directory creation successful\n");
    }
    
    // Cleanup VFS
    kos_vfs_cleanup();
    
    printf("All tests completed!\n");
    return 0;
}
EOF

# Documentation
doc:
	@echo "KOS Filesystem Documentation"
	@echo "============================"
	@echo ""
	@echo "Build targets:"
	@echo "  all     - Build shared library (default)"
	@echo "  debug   - Build with debug symbols"
	@echo "  test    - Build test executable"
	@echo "  install - Install library and headers"
	@echo "  clean   - Remove build files"
	@echo "  doc     - Show this documentation"
	@echo ""
	@echo "Library: $(TARGET)"
	@echo "Headers: $(HEADERS)"

.PHONY: all clean install debug test doc

# Include dependency tracking
-include $(OBJECTS:.o=.d)

# Generate dependency files
%.d: %.c
	@$(CC) $(CFLAGS) -MM $< > $@