# KOS (Kaede Operating System) Architecture Blueprint

## Table of Contents
1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Security Architecture](#security-architecture)
4. [Authentication Systems](#authentication-systems)
5. [Communication Architecture](#communication-architecture)
6. [Permission Model](#permission-model)
7. [Shell & User Interface](#shell--user-interface)
8. [Implementation Plan](#implementation-plan)

## Overview

KOS is a modern operating system built on Python with C/C++ support, featuring advanced security, containerization, and host-OS integration capabilities.

### Key Features
- Fingerprint-based authentication with custom encryption
- Bidirectional host-OS communication via secure tunnels
- Fine-grained permission system with RBAC
- Advanced shell with command history and typo correction
- Application management through KAIM
- Host communication through KADCM

## Core Components

### 1. KADCM (Kaede Advanced Device Communication Manager)
**Purpose**: Enables secure bidirectional communication between host OS and KOS

#### Architecture
- **Transport**: Named pipes with TLS/SSL encryption
- **Protocol**: Custom binary with JSON+YAML payload
- **Authentication**: Fingerprint-based mutual authentication
- **Sessions**: 300-second validity with resume capability

#### Message Structure
```
[4 bytes: length][1 byte: flags][JSON header + YAML body]
```

#### Message Types
- COMMAND - Execute host/KOS commands
- DATA - File transfers
- AUTH - Authentication/fingerprint exchange
- CONTROL - Tunnel management
- HEARTBEAT - Keepalive (30s interval)
- ERROR - Error reporting
- NOTIFY - Asynchronous alerts

### 2. KAIM (Kaede Application Interface Manager)
**Purpose**: Provides controlled kernel access for applications

#### Architecture
- **Kernel Module**: `kaim.ko` - handles low-level operations
- **Daemon**: `_kaim` user - manages policy enforcement
- **Interface**: Unix socket at `/var/run/kaim.sock`
- **Device**: `/dev/kaim` with 0660 permissions

#### API Examples
```c
kaim_device_open("sda", "rw")
kaim_device_control("sda", "reset")
kaim_process_elevate(pid, flags)
kaim_get_status()
```

## Security Architecture

### 1. Fingerprint System
**Purpose**: Cryptographic identification for all entities

#### Encryption Formula
```
F = base64(
      base85(a+b+f) + 
      base64(base85(C)+base85(E)) + 
      base85(base64(c+e)+base85(a+b+f)+...)
    )
```

#### Variables
- a = Base64(Encryptionkey + salt)
- b = Base64(Fingerprint + salt)
- M = Base85(Base64(Metadata))
- C = Base85(Base64(Control Metadata))
- E = Base85(Base64(Environment Metadata))

#### Storage
- Database with fields: `fp_part_1` to `fp_part_16`
- 128 characters per part maximum
- CRC32 checksum per entry

### 2. Password System
**Purpose**: User authentication with one-way encryption

#### Algorithm
```
Password → Formula Encoding → SHA512 (200k iterations) → Store
```

#### Shadow File Format
```
username:$6$salt$hash:lastchange:min:max:warn:inactive:expire:
```

Location: `/etc/kos/shadow` (permissions: 0000)

## Authentication Systems

### 1. Multi-Factor Authentication
- Fingerprints (primary)
- Passwords (secondary)
- Hardware tokens (optional)

### 2. Session Management
- PAM integration
- Session-bound privileges
- Automatic expiration on logout

## Communication Architecture

### 1. TLS Tunnels
- **Cipher**: TLS 1.3 minimum
- **Certificates**: Internal CA with 1-year validity
- **Ports**: Platform-specific named pipes

### 2. Binary Protocol
```
[4 bytes: length][2 bytes: type][2 bytes: flags][payload]
```

Flags:
- 0x01 = COMPRESSED
- 0x02 = ENCRYPTED
- 0x04 = FRAGMENTED
- 0x08 = REQUIRES_ACK

## Permission Model

### 1. Permission Flags
- **KROOT** - Full unrestricted access
- **KSYSTEM** - System management (limited)
- **KUSR** - User management
- **KAM** - Access management
- **KNET** - Network configuration
- **KDEV** - Device access
- **KPROC** - Process management
- **KFILE_R/W/X** - File operations
- **KLOG** - Log access
- **KSEC** - Security management
- **Others**: KAUD, KCFG, KUPD, KSRV, KDBG

### 2. RBAC Roles
- **root** - KROOT (all permissions)
- **admin** - KSYSTEM set
- **operator** - KPROC, KSRV, KLOG
- **user** - Basic permissions
- **guest** - Minimal access

### 3. Ubuntu-like Groups
- sudo - ksudo access
- adm - Log reading
- audio - Audio device access
- network - Network configuration

## Shell & User Interface

### 1. Command History
- **Format**: Custom binary with CRC32
- **Storage**: `/var/lib/kos/history/<uid>.klog`
- **Features**: 
  - Up/down navigation
  - Ctrl+R fuzzy search
  - History expansion (!!, !$)

### 2. Typo Correction
- Levenshtein distance algorithm
- Command suggestions
- User-configurable aliases

### 3. Shell Integration
- Built-in ksudo (kernel syscall)
- Command filtering for security
- Real-time permission checking

## Implementation Plan

### Phase 1: Core Security
1. Implement fingerprint system with strong crypto
2. Create password management with shadow file
3. Build permission flag system
4. Implement RBAC with policy files

### Phase 2: Communication Layer
1. Develop KADCM with TLS tunnels
2. Create message protocol handlers
3. Implement bidirectional command execution
4. Add session management

### Phase 3: Application Interface
1. Build KAIM kernel module
2. Create userspace daemon
3. Implement client library
4. Add PAM integration

### Phase 4: User Experience
1. Enhance shell with history
2. Add typo correction
3. Implement command aliases
4. Create management tools

### Phase 5: Integration
1. Host driver development
2. Full system testing
3. Security auditing
4. Performance optimization

## Configuration Files

### System Configuration
- `/etc/kos/rbac.json` - Role definitions
- `/etc/kos/shadow` - Password storage
- `/etc/kos/fingerprints.db` - Fingerprint database
- `/etc/kos/aliases.conf` - System aliases

### User Configuration
- `~/.kos_aliases` - User aliases
- `~/.kos_history_filters` - History filters

### Runtime Data
- `/var/lib/kaim/` - KAIM session data
- `/var/run/kos/` - Runtime sockets/pipes
- `/var/log/kos/` - System logs

## Security Considerations

1. **Zero Trust Model** - Verify everything
2. **Least Privilege** - Minimal permissions by default
3. **Defense in Depth** - Multiple security layers
4. **Audit Everything** - Comprehensive logging
5. **Fail Secure** - Deny by default

## Next Steps

1. Begin implementation of core security components
2. Set up development environment
3. Create initial test framework
4. Start with fingerprint system implementation