# KOS Device Driver Framework Makefile

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -fPIC -O2 -g -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L
LDFLAGS = -shared -lpthread -lrt

# Directories
SRCDIR = .
OBJDIR = obj
LIBDIR = .

# Source files
SOURCES = base.c char.c block.c net.c tty.c
OBJECTS = $(SOURCES:%.c=$(OBJDIR)/%.o)

# Target library
TARGET = $(LIBDIR)/libkos_drivers.so

# Header files
HEADERS = drivers.h

.PHONY: all clean install test

all: $(TARGET)

$(TARGET): $(OBJECTS) | $(LIBDIR)
	$(CC) $(LDFLAGS) -o $@ $^
	@echo "Built KOS driver library: $@"

$(OBJDIR)/%.o: $(SRCDIR)/%.c $(HEADERS) | $(OBJDIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(LIBDIR):
	mkdir -p $(LIBDIR)

clean:
	rm -rf $(OBJDIR) $(TARGET)
	@echo "Cleaned build files"

install: $(TARGET)
	@echo "Installing KOS driver library..."
	sudo cp $(TARGET) /usr/local/lib/
	sudo cp $(HEADERS) /usr/local/include/
	sudo ldconfig
	@echo "Installation complete"

test: $(TARGET)
	@echo "Running Python binding tests..."
	python3 drivers_wrapper.py
	@echo "Tests complete"

# Development targets
debug: CFLAGS += -DDEBUG -O0
debug: $(TARGET)

profile: CFLAGS += -pg
profile: LDFLAGS += -pg
profile: $(TARGET)

# Static analysis
analyze:
	@echo "Running static analysis..."
	cppcheck --enable=all --std=c99 $(SOURCES) $(HEADERS)

# Format code
format:
	@echo "Formatting code..."
	clang-format -i $(SOURCES) $(HEADERS)

# Documentation
docs:
	@echo "Generating documentation..."
	doxygen Doxyfile 2>/dev/null || echo "Doxygen not available"

# Help
help:
	@echo "KOS Device Driver Framework Build System"
	@echo "========================================"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build the driver library (default)"
	@echo "  clean    - Remove build files"
	@echo "  install  - Install library and headers system-wide"
	@echo "  test     - Run Python binding tests"
	@echo "  debug    - Build with debug symbols and no optimization"
	@echo "  profile  - Build with profiling support"
	@echo "  analyze  - Run static code analysis"
	@echo "  format   - Format source code"
	@echo "  docs     - Generate documentation"
	@echo "  help     - Show this help"
	@echo ""
	@echo "Usage: make [target]"