# Linux/Ubuntu System Architecture Overview

## 1. Linux Kernel Architecture

### Core Subsystems
The Linux kernel is organized into five major subsystems:

1. **Process Management**
   - Responsible for process creation, scheduling, and termination
   - Manages threads, process groups, and sessions
   - Implements scheduling algorithms (CFS - Completely Fair Scheduler)
   - Handles inter-process communication (IPC)

2. **Memory Management**
   - Virtual memory management with demand paging
   - Physical memory allocation (buddy system and slab allocator)
   - Memory mapping and protection
   - Swap management and page replacement algorithms
   - Memory zones: DMA, Normal, HighMem

3. **Virtual Filesystem (VFS)**
   - Provides abstraction layer for different filesystems
   - Key objects: superblock, inode, dentry, file
   - Supports multiple filesystem types (ext4, btrfs, xfs, etc.)
   - Implements standard POSIX file operations

4. **Networking Stack**
   - Implements full TCP/IP protocol suite
   - Socket layer provides BSD socket interface
   - Network device management and driver framework
   - Netfilter for packet filtering and NAT

5. **Device Drivers**
   - Character and block device interfaces
   - Bus drivers (PCI, USB, I2C, SPI)
   - DMA and interrupt handling
   - Power management support

### Kernel Organization
```
arch/       - Architecture-specific code
block/      - Block I/O subsystem
drivers/    - Device drivers
fs/         - Filesystem implementations
include/    - Header files
init/       - Initialization code
ipc/        - Inter-process communication
kernel/     - Core kernel code
lib/        - Library routines
mm/         - Memory management
net/        - Networking stack
security/   - Security modules
```

## 2. Boot Process

### Boot Sequence
1. **BIOS/UEFI** - Hardware initialization
2. **Bootloader** (GRUB) - Loads kernel and initramfs
3. **Kernel initialization** - Hardware detection, driver loading
4. **Init system** - Starts userspace services

### Kernel Boot Stages
1. Early boot (assembly) - Set up initial environment
2. start_kernel() - Main C entry point
3. Architecture-specific initialization
4. Memory management initialization
5. Scheduler initialization
6. Device and driver initialization
7. Mount root filesystem
8. Execute init process

## 3. Process Management

### Process Structure
- Each process has unique PID (Process ID)
- Processes organized in parent-child hierarchy
- Process states: Running, Sleeping, Stopped, Zombie
- Threads share address space within process

### Scheduling
- **CFS (Completely Fair Scheduler)** - Default scheduler
- Uses red-black tree for O(log n) operations
- Virtual runtime (vruntime) tracks CPU usage
- Multiple scheduling classes: Real-time, Normal, Idle
- CPU affinity and NUMA support

## 4. Memory Management

### Virtual Memory
- Each process has separate virtual address space
- Page tables translate virtual to physical addresses
- Demand paging - pages loaded when accessed
- Copy-on-write (COW) optimization for fork()

### Memory Allocation
- **Buddy System** - Allocates contiguous page frames
- **Slab Allocator** - Efficient allocation for kernel objects
- **vmalloc** - Allocates virtually contiguous memory
- **kmalloc** - Allocates physically contiguous memory

### Memory Zones
- **ZONE_DMA** - Memory suitable for DMA
- **ZONE_NORMAL** - Regular memory
- **ZONE_HIGHMEM** - Memory above ~896MB on 32-bit

## 5. Filesystem Architecture

### VFS Layer
Provides unified interface for different filesystems:
- Common system calls (open, read, write, close)
- Filesystem registration and mounting
- Path lookup and permission checking
- Page cache for performance

### Common Filesystems
- **ext4** - Default for many distributions
- **btrfs** - Advanced features (snapshots, compression)
- **xfs** - High-performance for large files
- **tmpfs** - RAM-based temporary storage
- **proc** - Process and kernel information
- **sysfs** - Device and driver information

## 6. Init Systems

### System V Init
- Traditional init system
- Sequential service startup
- Runlevels (0-6) define system states
- Scripts in /etc/init.d/

### Upstart
- Event-based init replacement
- Parallel service startup
- Used by older Ubuntu versions

### systemd
- Modern init system and service manager
- Dependency-based parallel startup
- Unit files describe services
- Integrated logging (journald)
- Cgroup integration for resource control

## 7. Package Management

### Debian/Ubuntu (APT/dpkg)
- **dpkg** - Low-level package manager
- **apt** - High-level with dependency resolution
- Package format: .deb files
- Repositories provide package sources

### Red Hat/Fedora (YUM/RPM)
- **rpm** - Low-level package manager
- **yum/dnf** - High-level with dependency resolution
- Package format: .rpm files

### Universal Packages
- **Snap** - Containerized applications
- **Flatpak** - Desktop application sandboxing
- **AppImage** - Portable application format

## 8. Networking

### Network Stack Layers
1. Link Layer (Ethernet, WiFi)
2. Network Layer (IP)
3. Transport Layer (TCP, UDP)
4. Application Layer

### Network Configuration
- Network interfaces managed through netlink
- IP address configuration (static/DHCP)
- Routing tables and rules
- Firewall (netfilter/iptables)

### Network Namespaces
- Isolate network resources
- Used for containers and virtualization
- Separate routing tables, interfaces, firewall rules

## 9. Security Architecture

### Access Control
- **Discretionary Access Control (DAC)** - Traditional Unix permissions
- **Mandatory Access Control (MAC)** - SELinux, AppArmor
- **Capabilities** - Fine-grained privileges

### Linux Security Modules (LSM)
- Framework for security modules
- Hooks throughout kernel for access decisions
- Modules: SELinux, AppArmor, Tomoyo, Smack

## 10. Virtualization and Containers

### Virtualization Types
- **Full Virtualization** - KVM with hardware support
- **Paravirtualization** - Xen with modified guests
- **Container Virtualization** - LXC, Docker

### Container Technologies
- **Namespaces** - Isolate system resources
- **Cgroups** - Resource limits and accounting
- **Union Filesystems** - Layered file systems

### Hypervisors
- **KVM** - Kernel-based Virtual Machine
- **QEMU** - Hardware emulation
- **Xen** - Type 1 hypervisor
- **VirtualBox** - Type 2 hypervisor