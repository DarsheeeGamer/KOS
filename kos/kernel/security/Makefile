# KOS Security Framework Makefile

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -fPIC -O2 -g
LDFLAGS = -shared -lpthread
PYTHON = python3

# Source files
SOURCES = security.c capabilities.c selinux.c seccomp.c audit.c crypto.c
OBJECTS = $(SOURCES:.c=.o)
LIBRARY = libkos_security.so
HEADER = security.h

# Python bindings
PYTHON_WRAPPER = security_wrapper.py
PYTHON_TEST = test_security.py

# Installation paths
PREFIX ?= /usr/local
LIBDIR = $(PREFIX)/lib
INCLUDEDIR = $(PREFIX)/include/kos
PYTHONDIR = $(shell $(PYTHON) -c "import site; print(site.getsitepackages()[0])")/kos

.PHONY: all clean install uninstall test python-test

all: $(LIBRARY)

$(LIBRARY): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c $(HEADER)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(LIBRARY) *.pyc __pycache__/* test_security

install: $(LIBRARY) $(HEADER)
	install -d $(LIBDIR)
	install -d $(INCLUDEDIR)
	install -d $(PYTHONDIR)
	install -m 644 $(LIBRARY) $(LIBDIR)/
	install -m 644 $(HEADER) $(INCLUDEDIR)/
	install -m 644 $(PYTHON_WRAPPER) $(PYTHONDIR)/
	ldconfig

uninstall:
	rm -f $(LIBDIR)/$(LIBRARY)
	rm -f $(INCLUDEDIR)/$(HEADER)
	rm -f $(PYTHONDIR)/$(PYTHON_WRAPPER)
	ldconfig

# Test programs
test: test_security
	./test_security

test_security: test_security.c $(LIBRARY)
	$(CC) $(CFLAGS) $< -L. -lkos_security -lpthread -o $@

python-test: $(LIBRARY) $(PYTHON_WRAPPER)
	$(PYTHON) $(PYTHON_WRAPPER)

# Development targets
debug: CFLAGS += -DDEBUG -O0
debug: $(LIBRARY)

profile: CFLAGS += -pg
profile: $(LIBRARY)

# Static analysis
analyze:
	cppcheck --enable=all --std=c99 $(SOURCES)

# Documentation
docs:
	doxygen Doxyfile

# Package
package: clean
	tar -czf kos-security.tar.gz *.c *.h *.py Makefile README.md

help:
	@echo "KOS Security Framework Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all          - Build the security library"
	@echo "  clean        - Remove build artifacts"
	@echo "  install      - Install library and headers"
	@echo "  uninstall    - Remove installed files"
	@echo "  test         - Build and run C tests"
	@echo "  python-test  - Run Python tests"
	@echo "  debug        - Build with debug symbols"
	@echo "  analyze      - Run static analysis"
	@echo "  docs         - Generate documentation"
	@echo "  package      - Create source package"
	@echo "  help         - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  PREFIX       - Installation prefix (default: /usr/local)"
	@echo "  CC           - C compiler (default: gcc)"
	@echo "  PYTHON       - Python interpreter (default: python3)"