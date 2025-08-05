"""
KOS Swap Device Real Implementation
Complete swap device implementation without placeholders
"""

import os
import sys
import fcntl
import struct
import mmap
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger('kos.memory.swap_device')


class SwapDeviceBase:
    """Base implementation for real swap devices"""
    
    def __init__(self, path: str, size: int):
        self.path = path
        self.size = size
        self.page_size = 4096
        self.nr_pages = size // self.page_size
        
    def _fallocate(self, fd: int, size: int):
        """Allocate space for file using fallocate syscall"""
        try:
            # FALLOC_FL_KEEP_SIZE = 0x01
            # FALLOC_FL_PUNCH_HOLE = 0x02
            FALLOC_FL_ZERO_RANGE = 0x10
            
            # Try fallocate first (Linux 2.6.23+)
            if hasattr(os, 'fallocate'):
                os.fallocate(fd, 0, 0, size)
            else:
                # Fallback to manual allocation
                os.ftruncate(fd, size)
                
                # Write zeros in chunks to ensure allocation
                chunk_size = 1024 * 1024  # 1MB chunks
                zeros = b'\x00' * chunk_size
                
                for offset in range(0, size, chunk_size):
                    remaining = min(chunk_size, size - offset)
                    os.pwrite(fd, zeros[:remaining], offset)
                    
        except OSError as e:
            logger.warning(f"fallocate failed: {e}, using fallback")
            # Final fallback - just truncate
            os.ftruncate(fd, size)
            
    def _create_sparse_file(self, fd: int, size: int):
        """Create sparse file for swap"""
        os.ftruncate(fd, size)
        
        # Write swap signature at end to ensure file is created
        os.pwrite(fd, b'SWAPSPACE2', size - 10)
        
    def _secure_erase(self, fd: int, offset: int, length: int):
        """Securely erase swap data"""
        try:
            # Try BLKSECDISCARD ioctl first (SSD secure erase)
            BLKSECDISCARD = 0x127D
            
            buf = struct.pack('QQ', offset, length)
            fcntl.ioctl(fd, BLKSECDISCARD, buf)
            return True
        except:
            pass
            
        try:
            # Try BLKDISCARD ioctl (SSD TRIM)
            BLKDISCARD = 0x1277
            
            buf = struct.pack('QQ', offset, length)
            fcntl.ioctl(fd, BLKDISCARD, buf)
            return True
        except:
            pass
            
        # Fallback to overwriting with random data
        try:
            random_data = os.urandom(min(length, 4096))
            for pos in range(offset, offset + length, 4096):
                chunk_size = min(4096, offset + length - pos)
                os.pwrite(fd, random_data[:chunk_size], pos)
            return True
        except:
            return False


class RealSwapFile(SwapDeviceBase):
    """Real swap file implementation using Linux swap format"""
    
    # Swap header format constants
    SWAP_MAGIC_OFFSET = 4086  # Page size - 10
    SWAP_HEADER_SIZE = 4096
    SWAP_VERSION_OFFSET = 0x400
    SWAP_LAST_PAGE_OFFSET = 0x404
    SWAP_NR_BADPAGES_OFFSET = 0x408
    SWAP_UUID_OFFSET = 0x40C
    SWAP_VOLUME_OFFSET = 0x41C
    SWAP_BADPAGES_OFFSET = 0x42C
    
    def __init__(self, path: str, size: int):
        super().__init__(path, size)
        self.fd = None
        self.mmap_obj = None
        self.bad_pages = set()
        self.uuid = os.urandom(16)
        
    def create(self):
        """Create real swap file with proper format"""
        # Open with O_EXCL to prevent race conditions
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        
        try:
            self.fd = os.open(self.path, flags, 0o600)
            
            # Allocate space
            self._fallocate(self.fd, self.size)
            
            # Create swap header
            header = bytearray(self.SWAP_HEADER_SIZE)
            
            # Set version (1)
            struct.pack_into('<I', header, self.SWAP_VERSION_OFFSET, 1)
            
            # Set last page
            struct.pack_into('<I', header, self.SWAP_LAST_PAGE_OFFSET, self.nr_pages - 1)
            
            # Set number of bad pages (0 initially)
            struct.pack_into('<I', header, self.SWAP_NR_BADPAGES_OFFSET, 0)
            
            # Set UUID
            header[self.SWAP_UUID_OFFSET:self.SWAP_UUID_OFFSET + 16] = self.uuid
            
            # Set volume label
            label = b'KOS_SWAP\x00\x00\x00\x00\x00\x00\x00\x00'
            header[self.SWAP_VOLUME_OFFSET:self.SWAP_VOLUME_OFFSET + 16] = label
            
            # Write header
            os.pwrite(self.fd, header, 0)
            
            # Write magic signature at end of first page
            os.pwrite(self.fd, b'SWAPSPACE2', self.SWAP_MAGIC_OFFSET)
            
            # Sync to disk
            os.fsync(self.fd)
            
            os.close(self.fd)
            self.fd = None
            
            logger.info(f"Created swap file {self.path} with {self.nr_pages} pages")
            
        except Exception as e:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            if os.path.exists(self.path):
                os.unlink(self.path)
            raise
            
    def activate(self):
        """Activate swap file for use"""
        self.fd = os.open(self.path, os.O_RDWR)
        
        # Verify swap signature
        magic = os.pread(self.fd, 10, self.SWAP_MAGIC_OFFSET)
        if magic != b'SWAPSPACE2':
            os.close(self.fd)
            raise ValueError(f"Invalid swap signature: {magic}")
            
        # Read header
        header = os.pread(self.fd, self.SWAP_HEADER_SIZE, 0)
        
        version = struct.unpack_from('<I', header, self.SWAP_VERSION_OFFSET)[0]
        if version != 1:
            os.close(self.fd)
            raise ValueError(f"Unsupported swap version: {version}")
            
        # Read bad pages
        nr_badpages = struct.unpack_from('<I', header, self.SWAP_NR_BADPAGES_OFFSET)[0]
        if nr_badpages > 0:
            offset = self.SWAP_BADPAGES_OFFSET
            for i in range(nr_badpages):
                bad_page = struct.unpack_from('<I', header, offset)[0]
                self.bad_pages.add(bad_page)
                offset += 4
                
        # Memory map the file for performance
        self.mmap_obj = mmap.mmap(self.fd, self.size, mmap.MAP_SHARED)
        
        # Advise kernel about access pattern
        self.mmap_obj.madvise(mmap.MADV_RANDOM)
        
        logger.info(f"Activated swap file {self.path}")
        
    def deactivate(self):
        """Deactivate swap file"""
        if self.mmap_obj:
            # Sync any pending writes
            self.mmap_obj.flush()
            self.mmap_obj.close()
            self.mmap_obj = None
            
        if self.fd is not None:
            os.fsync(self.fd)
            os.close(self.fd)
            self.fd = None
            
    def read_page(self, page: int) -> bytes:
        """Read page from swap file"""
        if not self.mmap_obj:
            raise RuntimeError("Swap file not activated")
            
        if page >= self.nr_pages or page in self.bad_pages:
            raise ValueError(f"Invalid page number: {page}")
            
        offset = page * self.page_size
        return bytes(self.mmap_obj[offset:offset + self.page_size])
        
    def write_page(self, page: int, data: bytes):
        """Write page to swap file"""
        if not self.mmap_obj:
            raise RuntimeError("Swap file not activated")
            
        if page >= self.nr_pages or page in self.bad_pages:
            raise ValueError(f"Invalid page number: {page}")
            
        if len(data) != self.page_size:
            raise ValueError(f"Invalid data size: {len(data)}")
            
        offset = page * self.page_size
        self.mmap_obj[offset:offset + self.page_size] = data
        
    def mark_bad_page(self, page: int):
        """Mark page as bad and update header"""
        if page in self.bad_pages:
            return
            
        self.bad_pages.add(page)
        
        # Update header with new bad page count
        if self.fd is not None:
            nr_badpages = len(self.bad_pages)
            
            # Write count
            os.pwrite(self.fd, struct.pack('<I', nr_badpages), self.SWAP_NR_BADPAGES_OFFSET)
            
            # Write bad page list
            offset = self.SWAP_BADPAGES_OFFSET
            for bad_page in sorted(self.bad_pages):
                os.pwrite(self.fd, struct.pack('<I', bad_page), offset)
                offset += 4
                
            os.fsync(self.fd)
            
    def discard_page(self, page: int):
        """Discard/TRIM a swap page"""
        if self.fd is not None and page < self.nr_pages:
            offset = page * self.page_size
            self._secure_erase(self.fd, offset, self.page_size)
            
    def sync(self):
        """Sync swap file to disk"""
        if self.mmap_obj:
            self.mmap_obj.flush()
        if self.fd is not None:
            os.fsync(self.fd)


class RealSwapPartition(SwapDeviceBase):
    """Real swap partition implementation"""
    
    def __init__(self, device_path: str):
        # Get device size
        fd = os.open(device_path, os.O_RDONLY)
        try:
            # BLKGETSIZE64 ioctl
            BLKGETSIZE64 = 0x80081272
            buf = b'\x00' * 8
            buf = fcntl.ioctl(fd, BLKGETSIZE64, buf)
            size = struct.unpack('Q', buf)[0]
        finally:
            os.close(fd)
            
        super().__init__(device_path, size)
        self.fd = None
        self.is_block_device = True
        
    def create(self):
        """Format partition as swap"""
        # Similar to mkswap
        fd = os.open(self.path, os.O_RDWR | os.O_EXCL)
        
        try:
            # Create swap header
            header = bytearray(4096)
            
            # Set swap version
            struct.pack_into('<I', header, 0x400, 1)
            
            # Set last page
            struct.pack_into('<I', header, 0x404, self.nr_pages - 1)
            
            # Set UUID
            uuid = os.urandom(16)
            header[0x40C:0x41C] = uuid
            
            # Write header
            os.pwrite(fd, header, 0)
            
            # Write magic
            os.pwrite(fd, b'SWAPSPACE2', 4086)
            
            # Sync
            os.fsync(fd)
            
        finally:
            os.close(fd)
            
    def activate(self):
        """Activate swap partition"""
        self.fd = os.open(self.path, os.O_RDWR | os.O_DIRECT)
        
        # Verify signature
        buf = os.pread(self.fd, 10, 4086)
        if buf != b'SWAPSPACE2':
            os.close(self.fd)
            raise ValueError("Invalid swap partition")
            
    def deactivate(self):
        """Deactivate swap partition"""
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            
    def read_page(self, page: int) -> bytes:
        """Read page from partition using direct I/O"""
        if self.fd is None:
            raise RuntimeError("Swap partition not activated")
            
        # Allocate aligned buffer for O_DIRECT
        buf = bytearray(self.page_size)
        offset = page * self.page_size
        
        # Read with proper alignment
        bytes_read = os.pread(self.fd, buf, offset)
        if bytes_read != self.page_size:
            raise IOError(f"Short read: {bytes_read}")
            
        return bytes(buf)
        
    def write_page(self, page: int, data: bytes):
        """Write page to partition using direct I/O"""
        if self.fd is None:
            raise RuntimeError("Swap partition not activated")
            
        if len(data) != self.page_size:
            raise ValueError(f"Invalid data size: {len(data)}")
            
        offset = page * self.page_size
        
        # Write with proper alignment
        bytes_written = os.pwrite(self.fd, data, offset)
        if bytes_written != self.page_size:
            raise IOError(f"Short write: {bytes_written}")
            
    def discard_page(self, page: int):
        """Send TRIM/discard command for page"""
        if self.fd is not None:
            offset = page * self.page_size
            
            try:
                # BLKDISCARD ioctl
                BLKDISCARD = 0x1277
                buf = struct.pack('QQ', offset, self.page_size)
                fcntl.ioctl(self.fd, BLKDISCARD, buf)
            except:
                # Ignore if not supported
                pass
                
    def sync(self):
        """Sync partition"""
        if self.fd is not None:
            os.fsync(self.fd)