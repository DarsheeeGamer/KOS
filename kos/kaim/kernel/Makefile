# Makefile for KAIM kernel module and libraries

# Kernel module settings
KERNEL_VERSION := $(shell uname -r)
KERNEL_DIR := /lib/modules/$(KERNEL_VERSION)/build
PWD := $(shell pwd)

# Module name
MODULE_NAME := kaim
obj-m := $(MODULE_NAME).o
$(MODULE_NAME)-objs := kaim_module.o

# C++ library settings
CXX := g++
CC := gcc
CXXFLAGS := -std=c++17 -fPIC -Wall -Wextra -O2 -g
CFLAGS := -fPIC -Wall -Wextra -O2 -g
LDFLAGS := -shared -pthread

# Library names
LIB_NAME := libkaim.so
LIB_STATIC := libkaim.a

# Source files
CPP_SOURCES := kaim_lib.cpp
CPP_OBJECTS := $(CPP_SOURCES:.cpp=.o)

# Installation directories
INSTALL_DIR := /usr/local
LIB_INSTALL_DIR := $(INSTALL_DIR)/lib
INCLUDE_INSTALL_DIR := $(INSTALL_DIR)/include

# Python module compilation
PYTHON := python3
PYTHON_CONFIG := python3-config
PYTHON_CFLAGS := $(shell $(PYTHON_CONFIG) --cflags)
PYTHON_LDFLAGS := $(shell $(PYTHON_CONFIG) --ldflags)

# Targets
.PHONY: all clean install uninstall module library python test

all: module library

# Kernel module
module:
	@echo "Building kernel module..."
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD) modules

module_clean:
	$(MAKE) -C $(KERNEL_DIR) M=$(PWD) clean

# C++ library
library: $(LIB_NAME) $(LIB_STATIC)

$(LIB_NAME): $(CPP_OBJECTS)
	@echo "Building shared library..."
	$(CXX) $(LDFLAGS) -o $@ $^

$(LIB_STATIC): $(CPP_OBJECTS)
	@echo "Building static library..."
	ar rcs $@ $^

%.o: %.cpp kaim_lib.h
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Python extension module (optional)
python: _kaim.so

_kaim.so: kaim_python_wrapper.cpp $(LIB_STATIC)
	@echo "Building Python extension..."
	$(CXX) $(CXXFLAGS) $(PYTHON_CFLAGS) -c kaim_python_wrapper.cpp -o kaim_python_wrapper.o
	$(CXX) -shared kaim_python_wrapper.o $(LIB_STATIC) $(PYTHON_LDFLAGS) -o $@

# Installation
install: install_module install_library install_headers install_udev

install_module: module
	@echo "Installing kernel module..."
	sudo cp $(MODULE_NAME).ko /lib/modules/$(KERNEL_VERSION)/kernel/drivers/misc/
	sudo depmod -a
	sudo modprobe $(MODULE_NAME)

install_library: library
	@echo "Installing libraries..."
	sudo mkdir -p $(LIB_INSTALL_DIR)
	sudo cp $(LIB_NAME) $(LIB_INSTALL_DIR)/
	sudo cp $(LIB_STATIC) $(LIB_INSTALL_DIR)/
	sudo ldconfig

install_headers:
	@echo "Installing headers..."
	sudo mkdir -p $(INCLUDE_INSTALL_DIR)
	sudo cp kaim_lib.h $(INCLUDE_INSTALL_DIR)/

install_udev:
	@echo "Installing udev rules..."
	echo 'KERNEL=="kaim", MODE="0660", GROUP="kaim"' | sudo tee /etc/udev/rules.d/99-kaim.rules
	sudo udevadm control --reload-rules
	sudo udevadm trigger

# Create kaim group and user
install_user:
	@echo "Creating kaim user and group..."
	sudo groupadd -f kaim
	sudo useradd -r -g kaim -d /var/lib/kaim -s /bin/false _kaim || true
	sudo mkdir -p /var/lib/kaim
	sudo chown _kaim:kaim /var/lib/kaim
	sudo chmod 750 /var/lib/kaim

# Uninstallation
uninstall: uninstall_module uninstall_library uninstall_headers

uninstall_module:
	@echo "Uninstalling kernel module..."
	sudo modprobe -r $(MODULE_NAME) || true
	sudo rm -f /lib/modules/$(KERNEL_VERSION)/kernel/drivers/misc/$(MODULE_NAME).ko
	sudo depmod -a

uninstall_library:
	@echo "Uninstalling libraries..."
	sudo rm -f $(LIB_INSTALL_DIR)/$(LIB_NAME)
	sudo rm -f $(LIB_INSTALL_DIR)/$(LIB_STATIC)
	sudo ldconfig

uninstall_headers:
	@echo "Uninstalling headers..."
	sudo rm -f $(INCLUDE_INSTALL_DIR)/kaim_lib.h

# Testing
test: test_cpp test_python

test_cpp: test_kaim
	@echo "Running C++ tests..."
	./test_kaim

test_kaim: test_kaim.cpp library
	$(CXX) $(CXXFLAGS) test_kaim.cpp -L. -lkaim -o $@

test_python: library
	@echo "Running Python tests..."
	LD_LIBRARY_PATH=. $(PYTHON) test_kaim.py

# Development helpers
check_module:
	@echo "Checking module status..."
	lsmod | grep $(MODULE_NAME) || echo "Module not loaded"
	@echo "Checking device..."
	ls -la /dev/$(MODULE_NAME) || echo "Device not found"
	@echo "Checking proc entries..."
	ls -la /proc/$(MODULE_NAME)/ || echo "Proc entries not found"

logs:
	@echo "Recent kernel logs for KAIM:"
	sudo dmesg | grep -i kaim | tail -20

# Clean everything
clean: module_clean
	rm -f *.o *.so *.a test_kaim
	rm -f Module.symvers modules.order

# Debug build
debug: CXXFLAGS += -DDEBUG -g3 -O0
debug: CFLAGS += -DDEBUG -g3 -O0
debug: all

# Documentation
docs:
	doxygen Doxyfile

.PHONY: check_module logs debug docs