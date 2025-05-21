import os
import struct
from datetime import datetime

# Disk constants - Adjusted for reasonable size limits
BLOCK_SIZE = 512  # bytes
INODE_SIZE = 316  # bytes - matches our inode structure size
SUPERBLOCK_SIZE = 512  # Same as block size for simplicity
SUPERBLOCK_MAGIC = 0x4B414544  # 'KAED' in hex

# Bitmap and block allocation
BITMAP_BLOCKS_INODE = 1
BITMAP_BLOCKS_DATA = 8
INODE_TABLE_START_BLOCK = 10
DATA_BLOCKS_START_BLOCK = 50
BLOCKS_PER_INODE_TABLE = 32
INODES_PER_BLOCK = BLOCK_SIZE // INODE_SIZE  # Adjusted based on new INODE_SIZE
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max file size

# Superblock format
SUPERBLOCK_FORMAT = "<IQQQQQQQQQI"  # magic, disk_size_blocks, block_size, inode_bitmap_start, inode_bitmap_blocks, data_bitmap_start, data_bitmap_blocks, inode_table_start, data_blocks_start, blocks_per_inode_table, root_inode
SUPERBLOCK_STRUCT_SIZE = struct.calcsize(SUPERBLOCK_FORMAT)

def get_bit(bitmap, bit_index):
    """Get bit value at index in bitmap"""
    byte_index = bit_index // 8
    bit_offset = bit_index % 8
    return (bitmap[byte_index] >> bit_offset) & 1

def parse_permissions(perm_str):
    """Convert rwx format to numeric permissions"""
    perm_map = {'r': 4, 'w': 2, 'x': 1, '-': 0}
    result = 0
    for i, c in enumerate(perm_str):
        if c in perm_map:
            result += perm_map[c] * (100 if i < 3 else 10 if i < 6 else 1)
    return result

def format_permissions(perms):
    """Convert numeric permissions to rwx format"""
    result = ""
    values = [(4, "r"), (2, "w"), (1, "x")]

    for digit in str(perms):
        digit = int(digit)
        for val, char in values:
            result += char if digit & val else "-"

    return result

def parse_path(path, current_path):
    """Resolve relative paths to absolute paths"""
    if path.startswith('/'):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(current_path, path))

def split_path(path):
    """Split path into directory and filename"""
    path = os.path.normpath(path)
    return os.path.dirname(path), os.path.basename(path)

def find_first_clear_bit(bitmap):
    """Find first clear bit in bitmap"""
    for i, byte in enumerate(bitmap):
        for bit in range(8):
            if not (byte & (1 << bit)):
                return i * 8 + bit
    return None

def set_bit(bitmap, index):
    """Set bit at index in bitmap"""
    byte_index = index // 8
    bit_index = index % 8
    bitmap_list = bytearray(bitmap)
    bitmap_list[byte_index] |= (1 << bit_index)
    return bytes(bitmap_list)

def clear_bit(bitmap, index):
    """Clear bit at index in bitmap"""
    byte_index = index // 8
    bit_index = index % 8
    bitmap_list = bytearray(bitmap)
    bitmap_list[byte_index] &= ~(1 << bit_index)
    return bytes(bitmap_list)

def calculate_sha256_hash(data):
    """Calculate SHA256 hash of data"""
    import hashlib
    return hashlib.sha256(data).hexdigest()

# Error codes
ENOSPC = 28  # No space left on device
EIO = 5      # I/O error
ENOENT = 2   # No such file or directory
EEXIST = 17  # File exists