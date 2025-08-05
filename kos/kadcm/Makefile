# KADCM C/C++ Library Makefile

# Compiler settings
CXX = g++
CC = gcc
CXXFLAGS = -std=c++17 -Wall -Wextra -fPIC -O2
CFLAGS = -Wall -Wextra -fPIC -O2
LDFLAGS = -shared
LIBS = -lssl -lcrypto -lpthread

# Platform detection
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    LIBS += -ldl
    TARGET = libkadcm.so
    INSTALL_DIR = /usr/local/lib
    HEADER_DIR = /usr/local/include
endif
ifeq ($(UNAME_S),Darwin)
    TARGET = libkadcm.dylib
    INSTALL_DIR = /usr/local/lib
    HEADER_DIR = /usr/local/include
endif
ifeq ($(OS),Windows_NT)
    TARGET = kadcm.dll
    LIBS += -lws2_32
    INSTALL_DIR = C:/Windows/System32
    HEADER_DIR = C:/Program Files/KOS/include
endif

# Source files
SOURCES = kadcm_lib.cpp
OBJECTS = $(SOURCES:.cpp=.o)

# Test files
TEST_SOURCES = test_kadcm.cpp
TEST_OBJECTS = $(TEST_SOURCES:.cpp=.o)
TEST_TARGET = test_kadcm

# Build rules
all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LIBS)
	@echo "Built $(TARGET)"

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Test program
test: $(TEST_TARGET)
	./$(TEST_TARGET)

$(TEST_TARGET): $(TEST_OBJECTS) $(TARGET)
	$(CXX) -o $@ $(TEST_OBJECTS) -L. -lkadcm $(LIBS)

# Python test
test_python: $(TARGET)
	LD_LIBRARY_PATH=. python3 ctypes_wrapper.py

# Installation
install: $(TARGET)
	@echo "Installing KADCM library..."
	install -d $(INSTALL_DIR)
	install -m 755 $(TARGET) $(INSTALL_DIR)
	install -d $(HEADER_DIR)
	install -m 644 kadcm_lib.h $(HEADER_DIR)
	ldconfig 2>/dev/null || true
	@echo "Installation complete"

uninstall:
	rm -f $(INSTALL_DIR)/$(TARGET)
	rm -f $(HEADER_DIR)/kadcm_lib.h
	ldconfig 2>/dev/null || true

# Development
debug: CXXFLAGS += -g -DDEBUG
debug: clean $(TARGET)

# Static library
static: LDFLAGS = 
static: TARGET = libkadcm.a
static: $(OBJECTS)
	ar rcs $(TARGET) $^
	@echo "Built static library $(TARGET)"

# Shared object with version
version: LDFLAGS += -Wl,-soname,libkadcm.so.1
version: TARGET = libkadcm.so.1.0.0
version: $(TARGET)
	ln -sf $(TARGET) libkadcm.so.1
	ln -sf libkadcm.so.1 libkadcm.so

# Clean
clean:
	rm -f $(OBJECTS) $(TEST_OBJECTS)
	rm -f $(TARGET) $(TEST_TARGET)
	rm -f libkadcm.so* libkadcm.a
	rm -f *.pyc __pycache__/

# Documentation
docs:
	doxygen Doxyfile 2>/dev/null || echo "Doxygen not installed"

# Format code
format:
	clang-format -i *.cpp *.h 2>/dev/null || echo "clang-format not installed"

# Check dependencies
check_deps:
	@echo "Checking dependencies..."
	@command -v $(CXX) >/dev/null 2>&1 || { echo "g++ not found"; exit 1; }
	@command -v pkg-config >/dev/null 2>&1 || { echo "pkg-config not found"; exit 1; }
	@pkg-config --exists openssl || { echo "OpenSSL not found"; exit 1; }
	@echo "All dependencies satisfied"

# Help
help:
	@echo "KADCM Library Makefile"
	@echo "====================="
	@echo "Targets:"
	@echo "  all          - Build shared library (default)"
	@echo "  test         - Build and run C++ tests"
	@echo "  test_python  - Run Python ctypes tests"
	@echo "  install      - Install library and headers"
	@echo "  uninstall    - Remove installed files"
	@echo "  static       - Build static library"
	@echo "  debug        - Build with debug symbols"
	@echo "  clean        - Remove build artifacts"
	@echo "  docs         - Generate documentation"
	@echo "  format       - Format source code"
	@echo "  check_deps   - Check build dependencies"

.PHONY: all clean install uninstall test test_python debug static version docs format check_deps help