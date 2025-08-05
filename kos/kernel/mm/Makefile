# Makefile for KOS Kernel Memory Management
CC = gcc
CFLAGS = -Wall -Wextra -O2 -fPIC -std=c99 -D_GNU_SOURCE
LDFLAGS = -shared
TARGET = libkos_mm.so
SOURCES = buddy.c slab.c kmalloc.c pgtable.c mmap.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = mm.h

# Additional flags for debugging
DEBUG_FLAGS = -g -DDEBUG -fsanitize=address
RELEASE_FLAGS = -O3 -DNDEBUG

.PHONY: all clean debug release test install

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

debug: CFLAGS += $(DEBUG_FLAGS)
debug: LDFLAGS += $(DEBUG_FLAGS)
debug: clean $(TARGET)

release: CFLAGS += $(RELEASE_FLAGS)
release: clean $(TARGET)

# Build test programs
test_buddy: buddy.c mm.h
	$(CC) $(CFLAGS) -DTEST_BUDDY -o $@ $< -lm

test_slab: slab.c buddy.c mm.h
	$(CC) $(CFLAGS) -DTEST_SLAB -o $@ slab.c buddy.c -lm

test_kmalloc: kmalloc.c slab.c buddy.c mm.h
	$(CC) $(CFLAGS) -DTEST_KMALLOC -o $@ kmalloc.c slab.c buddy.c -lm

test_pgtable: pgtable.c mm.h
	$(CC) $(CFLAGS) -DTEST_PGTABLE -o $@ $< -lm

test_mmap: mmap.c pgtable.c kmalloc.c slab.c buddy.c mm.h
	$(CC) $(CFLAGS) -DTEST_MMAP -o $@ mmap.c pgtable.c kmalloc.c slab.c buddy.c -lm

test: test_buddy test_slab test_kmalloc test_pgtable test_mmap
	@echo "Running buddy allocator tests..."
	./test_buddy
	@echo "Running slab allocator tests..."
	./test_slab
	@echo "Running kmalloc tests..."
	./test_kmalloc
	@echo "Running page table tests..."
	./test_pgtable
	@echo "Running mmap tests..."
	./test_mmap

# Python wrapper test
test_python: $(TARGET)
	python3 mm_wrapper.py

install: $(TARGET)
	cp $(TARGET) /usr/local/lib/
	cp $(HEADERS) /usr/local/include/
	ldconfig

clean:
	rm -f $(OBJECTS) $(TARGET) test_buddy test_slab test_kmalloc test_pgtable test_mmap

# Documentation
docs:
	doxygen Doxyfile

# Memory leak checking
valgrind: test_buddy test_slab test_kmalloc
	valgrind --leak-check=full --show-leak-kinds=all ./test_buddy
	valgrind --leak-check=full --show-leak-kinds=all ./test_slab
	valgrind --leak-check=full --show-leak-kinds=all ./test_kmalloc

# Static analysis
analyze:
	cppcheck --enable=all --std=c99 $(SOURCES)
	clang-static-analyzer $(CFLAGS) $(SOURCES)

# Performance profiling
profile: CFLAGS += -pg
profile: $(TARGET)

# Coverage analysis
coverage: CFLAGS += --coverage
coverage: LDFLAGS += --coverage
coverage: $(TARGET)
	gcov $(SOURCES)

help:
	@echo "Available targets:"
	@echo "  all      - Build the shared library (default)"
	@echo "  debug    - Build with debug flags"
	@echo "  release  - Build optimized release version"
	@echo "  test     - Build and run C tests"
	@echo "  test_python - Test Python wrapper"
	@echo "  clean    - Remove build artifacts"
	@echo "  install  - Install library and headers"
	@echo "  docs     - Generate documentation"
	@echo "  valgrind - Run memory leak checks"
	@echo "  analyze  - Run static analysis"
	@echo "  profile  - Build with profiling support"
	@echo "  coverage - Build with coverage analysis"