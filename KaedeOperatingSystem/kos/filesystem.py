import pickle
import time
import struct
import threading
import os
from datetime import datetime
from .utils import (
    BLOCK_SIZE, INODE_SIZE, SUPERBLOCK_SIZE, SUPERBLOCK_MAGIC,
    BITMAP_BLOCKS_INODE, BITMAP_BLOCKS_DATA, INODE_TABLE_START_BLOCK,
    DATA_BLOCKS_START_BLOCK, BLOCKS_PER_INODE_TABLE, INODES_PER_BLOCK,
    find_first_clear_bit, set_bit, clear_bit, parse_permissions, get_bit,
    SUPERBLOCK_FORMAT, SUPERBLOCK_STRUCT_SIZE
)
from .exceptions import (
    InvalidDiskFormat, DiskFullError, FileNotFound, InodeLimitReached,
    IOError, DiskRepairFailed, PermissionDenied, NotADirectory, IsADirectory
)

class Inode:
    def __init__(self, inode_number, file_type, permissions, uid, gid, size=0, data_blocks=None, parent_inode=None, children_inodes=None):
        self.inode_number = inode_number
        self.file_type = file_type
        self.permissions = permissions
        self.uid = uid
        self.gid = gid
        self.size = size
        self.data_blocks = data_blocks if data_blocks else []
        self.parent_inode = parent_inode
        self.children_inodes = children_inodes if children_inodes else []
        self.created_at = time.time()
        self.modified_at = time.time()
        self.accessed_at = time.time()
        self.links = 1

    def to_bytes(self):
        data_blocks_str = ','.join(map(str, self.data_blocks))
        children_inodes_str = ','.join(map(str, self.children_inodes))
        inode_struct = struct.Struct("<IHHIIQQ128s128sQQQI")
        packed_inode = inode_struct.pack(
            self.inode_number,
            0 if self.file_type == 'file' else 1,
            self.permissions,
            self.uid,
            self.gid,
            self.size,
            self.parent_inode or 0,
            data_blocks_str.encode('utf-8')[:128],
            children_inodes_str.encode('utf-8')[:128],
            int(self.created_at),
            int(self.modified_at),
            int(self.accessed_at),
            self.links
        )
        return packed_inode

    @staticmethod
    def from_bytes(data):
        if len(data) < 316:
            return None
        try:
            inode_struct = struct.Struct("<IHHIIQQ128s128sQQQI")
            unpacked = inode_struct.unpack(data[:inode_struct.size])
            inode_number, file_type_int, permissions, uid, gid, size, parent_inode, \
            data_blocks_bytes, children_inodes_bytes, created_at, modified_at, \
            accessed_at, links = unpacked
            data_blocks_str = data_blocks_bytes.split(b'\0')[0].decode('utf-8')
            children_inodes_str = children_inodes_bytes.split(b'\0')[0].decode('utf-8')
            inode = Inode(
                inode_number=inode_number,
                file_type='file' if file_type_int == 0 else 'dir',
                permissions=permissions,
                uid=uid,
                gid=gid,
                size=size,
                parent_inode=parent_inode if parent_inode != 0 else None,
                data_blocks=[int(x) for x in data_blocks_str.split(',') if x],
                children_inodes=[int(x) for x in children_inodes_str.split(',') if x]
            )
            inode.created_at = created_at
            inode.modified_at = modified_at
            inode.accessed_at = accessed_at
            inode.links = links
            return inode
        except (struct.error, ValueError) as e:
            raise InvalidDiskFormat(f"Invalid inode format: {e}")

class FileSystem:
    def __init__(self, disk_size_mb=100):
        print(f"Initializing filesystem with size {disk_size_mb}MB")
        self.disk_file = 'kaede.kdsk'
        self.disk_size = disk_size_mb * 1024 * 1024
        self.num_blocks = self.disk_size // BLOCK_SIZE
        self.current_path = "/"
        self.current_inode = 1
        self.data_block_bitmap_lock = threading.Lock()
        self.inode_bitmap_lock = threading.Lock()
        self.inodes = {}
        self.superblock = None

        if not os.path.exists(self.disk_file):
            print("No existing disk file found. Creating new filesystem.")
            self.initialize_disk(disk_size_mb)
        else:
            try:
                print("Found existing disk file. Attempting to load...")
                self.load_superblock()
                self.load_inodes()
            except Exception as e:
                print(f"Error loading disk: {e}")
                print("Reinitializing disk...")
                self.initialize_disk(disk_size_mb)

    def initialize_disk(self, disk_size_mb):
        print("Initializing new disk...")
        if os.path.exists(self.disk_file):
            os.remove(self.disk_file)

        with open(self.disk_file, 'wb') as f:
            f.truncate(self.disk_size)

        self.superblock = {
            "magic": SUPERBLOCK_MAGIC,
            "disk_size_blocks": self.num_blocks,
            "block_size": BLOCK_SIZE,
            "inode_bitmap_start": 1,
            "inode_bitmap_blocks": BITMAP_BLOCKS_INODE,
            "data_block_bitmap_start": 1 + BITMAP_BLOCKS_INODE,
            "data_block_bitmap_blocks": BITMAP_BLOCKS_DATA,
            "inode_table_start": INODE_TABLE_START_BLOCK,
            "data_blocks_start": DATA_BLOCKS_START_BLOCK,
            "blocks_per_inode_table": BLOCKS_PER_INODE_TABLE,
            "root_inode": 1
        }

        try:
            print("Writing superblock...")
            self.write_superblock()
            print("Initializing bitmaps...")
            self._init_bitmaps()
            print("Creating root directory...")
            self._init_root_directory()
            print("Disk initialization complete.")
        except Exception as e:
            print(f"Error during disk initialization: {e}")
            if os.path.exists(self.disk_file):
                os.remove(self.disk_file)
            raise

    def write_superblock(self):
        print("Writing superblock...")
        print(f"Superblock to write: {self.superblock}")
        data = struct.pack(SUPERBLOCK_FORMAT,
            self.superblock["magic"],
            self.superblock["disk_size_blocks"],
            self.superblock["block_size"],
            self.superblock["inode_bitmap_start"],
            self.superblock["inode_bitmap_blocks"],
            self.superblock["data_block_bitmap_start"],
            self.superblock["data_block_bitmap_blocks"],
            self.superblock["inode_table_start"],
            self.superblock["data_blocks_start"],
            self.superblock["blocks_per_inode_table"],
            self.superblock["root_inode"]
        )
        print(f"Superblock data size: {len(data)}, expected: {SUPERBLOCK_STRUCT_SIZE}")
        self.write_block(0, data.ljust(BLOCK_SIZE, b'\0'))

    def load_superblock(self):
        print("Loading superblock...")
        data = self.read_block(0)
        if not data:
            raise InvalidDiskFormat("Could not read superblock")

        try:
            unpacked = struct.unpack(SUPERBLOCK_FORMAT, data[:SUPERBLOCK_STRUCT_SIZE])
            self.superblock = {
                "magic": unpacked[0],
                "disk_size_blocks": unpacked[1],
                "block_size": unpacked[2],
                "inode_bitmap_start": unpacked[3],
                "inode_bitmap_blocks": unpacked[4],
                "data_block_bitmap_start": unpacked[5],
                "data_block_bitmap_blocks": unpacked[6],
                "inode_table_start": unpacked[7],
                "data_blocks_start": unpacked[8],
                "blocks_per_inode_table": unpacked[9],
                "root_inode": unpacked[10]
            }

            if self.superblock["magic"] != SUPERBLOCK_MAGIC:
                raise InvalidDiskFormat(f"Invalid magic number in superblock: got {hex(self.superblock['magic'])}, expected {hex(SUPERBLOCK_MAGIC)}")
            print(f"Superblock loaded successfully: {self.superblock}")

        except struct.error as e:
            raise InvalidDiskFormat(f"Invalid superblock format: {e}")

    def read_block(self, block_num):
        if not os.path.exists(self.disk_file):
            raise IOError("Disk file does not exist")

        offset = block_num * BLOCK_SIZE
        if offset >= self.disk_size:
            raise IOError(f"Block number {block_num} out of range")

        with open(self.disk_file, 'rb') as f:
            f.seek(offset)
            return f.read(BLOCK_SIZE)

    def write_block(self, block_num, data):
        if len(data) > BLOCK_SIZE:
            raise ValueError(f"Data size {len(data)} exceeds block size {BLOCK_SIZE}")

        offset = block_num * BLOCK_SIZE
        if offset >= self.disk_size:
            raise IOError(f"Block number {block_num} out of range")

        with open(self.disk_file, 'r+b') as f:
            f.seek(offset)
            f.write(data.ljust(BLOCK_SIZE, b'\0'))

    def _init_bitmaps(self):
        print("Initializing bitmaps...")
        inode_bitmap = b'\0' * (BITMAP_BLOCKS_INODE * BLOCK_SIZE)
        self.write_inode_bitmap(inode_bitmap)
        data_bitmap = b'\0' * (BITMAP_BLOCKS_DATA * BLOCK_SIZE)
        self.write_data_block_bitmap(data_bitmap)
        print("Bitmaps initialized.")

    def _init_root_directory(self):
        print("Creating root directory...")
        root_inode = Inode(
            inode_number=1,
            file_type='dir',
            permissions=parse_permissions("rwxr-xr-x"),
            uid=0,
            gid=0
        )
        self.write_inode(root_inode)
        self.mark_inode_allocated(1)
        self.inodes[1] = root_inode
        print("Root directory created.")

    def read_inode(self, inum):
        block_num = self.superblock['inode_table_start'] + ((inum - 1) // INODES_PER_BLOCK)
        offset = ((inum - 1) % INODES_PER_BLOCK) * INODE_SIZE

        block = self.read_block(block_num)
        inode_data = block[offset:offset + INODE_SIZE]

        return Inode.from_bytes(inode_data)

    def write_inode(self, inode):
        block_num = self.superblock['inode_table_start'] + ((inode.inode_number - 1) // INODES_PER_BLOCK)
        offset = ((inode.inode_number - 1) % INODES_PER_BLOCK) * INODE_SIZE

        block = self.read_block(block_num)
        inode_data = inode.to_bytes()

        new_block = block[:offset] + inode_data + block[offset + len(inode_data):]
        self.write_block(block_num, new_block)
        self.inodes[inode.inode_number] = inode

    def allocate_inode(self):
        with self.inode_bitmap_lock:
            inode_number = find_first_clear_bit(self.read_inode_bitmap())
            if inode_number is None:
                raise InodeLimitReached("No more inodes available")
            self.mark_inode_allocated(inode_number)
            return inode_number

    def deallocate_inode(self, inode_number):
        with self.inode_bitmap_lock:
            self.mark_inode_deallocated(inode_number)

    def read_inode_bitmap(self):
        bitmap = b''
        start_block = self.superblock["inode_bitmap_start"]
        for i in range(self.superblock["inode_bitmap_blocks"]):
            bitmap += self.read_block(start_block + i)
        return bitmap

    def write_inode_bitmap(self, bitmap):
        start_block = self.superblock["inode_bitmap_start"]
        for i in range(self.superblock["inode_bitmap_blocks"]):
            self.write_block(start_block + i, bitmap[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE])

    def mark_inode_allocated(self, inode_number):
        bitmap = self.read_inode_bitmap()
        bitmap = set_bit(bitmap, inode_number - 1)
        self.write_inode_bitmap(bitmap)

    def mark_inode_deallocated(self, inode_number):
        bitmap = self.read_inode_bitmap()
        bitmap = clear_bit(bitmap, inode_number - 1)
        self.write_inode_bitmap(bitmap)

    def load_inodes(self):
        for i in range(1, self.superblock["disk_size_blocks"]):
            if self.is_inode_allocated(i):
                inode = self.read_inode(i)
                if inode:
                    self.inodes[i] = inode

    def is_inode_allocated(self, inode_number):
        bitmap = self.read_inode_bitmap()
        return get_bit(bitmap, inode_number - 1)


    def read_data_block_bitmap(self):
        bitmap = b''
        start_block = self.superblock["data_block_bitmap_start"]
        for i in range(self.superblock["data_block_bitmap_blocks"]):
            bitmap += self.read_block(start_block + i)
        return bitmap

    def write_data_block_bitmap(self, bitmap):
        start_block = self.superblock["data_block_bitmap_start"]
        for i in range(self.superblock["data_block_bitmap_blocks"]):
            self.write_block(start_block + i, bitmap[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE])
    
    def get_inode_by_path(self, path):
        if path == '/':
            return self.superblock["root_inode"]

        parts = path.strip('/').split('/')
        current_inode = self.superblock["root_inode"]

        for part in parts:
            if not part:
                continue
            found = False
            current = self.read_inode(current_inode)
            if not current or current.file_type != 'dir':
                raise NotADirectory(f"Path component {part} is not a directory")

            for child_inode in current.children_inodes:
                child = self.read_inode(child_inode)
                if child and child.file_type == 'dir' and part == str(child_inode):
                    current_inode = child_inode
                    found = True
                    break

            if not found:
                raise FileNotFound(f"Path component {part} not found")

        return current_inode

    def mkdir(self, path, create_parents=False):
        """Create a new directory
        Args:
            path: Path to create
            create_parents: Create parent directories if they don't exist
        """
        try:
            if not path.startswith('/'):
                path = os.path.join(self.current_path, path)
            path = os.path.normpath(path)

            # Check if directory already exists
            try:
                inode_num = self.get_inode_by_path(path)
                raise IOError(f"Cannot create directory '{path}': File exists")
            except FileNotFound:
                pass

            # Get parent directory
            parent_path = os.path.dirname(path)
            try:
                parent_inode = self.get_inode_by_path(parent_path)
            except FileNotFound:
                if not create_parents:
                    raise IOError(f"Parent directory '{parent_path}' does not exist")
                # Create parent directories recursively
                self.mkdir(parent_path, create_parents=True)
                parent_inode = self.get_inode_by_path(parent_path)

            # Create new directory inode
            new_inode_num = self.allocate_inode()
            new_inode = Inode(
                inode_number=new_inode_num,
                file_type='dir',
                permissions=parse_permissions("rwxr-xr-x"),
                uid=0,
                gid=0,
                parent_inode=parent_inode
            )

            # Add to parent's children
            parent = self.read_inode(parent_inode)
            parent.children_inodes.append(new_inode_num)

            # Write both inodes
            self.write_inode(new_inode)
            self.write_inode(parent)

        except Exception as e:
            raise IOError(f"Failed to create directory {path}: {str(e)}")

    def ls(self, path=None):
        try:
            target_path = path if path else self.current_path
            if not target_path.startswith('/'):
                target_path = os.path.join(self.current_path, target_path)
            target_path = os.path.normpath(target_path)

            inode_num = self.get_inode_by_path(target_path)
            inode = self.read_inode(inode_num)

            if not inode:
                raise FileNotFound(f"Path not found: {target_path}")
            if inode.file_type != 'dir':
                raise NotADirectory(f"Path is not a directory: {target_path}")

            entries = []
            for child_inode in inode.children_inodes:
                child = self.read_inode(child_inode)
                if child:
                    type_char = 'd' if child.file_type == 'dir' else '-'
                    entries.append(f"{type_char} {str(child_inode)}")

            return sorted(entries)

        except Exception as e:
            raise IOError(f"Failed to list directory {path}: {str(e)}")

    def cd(self, path):
        try:
            if not path.startswith('/'):
                new_path = os.path.join(self.current_path, path)
            else:
                new_path = path
            new_path = os.path.normpath(new_path)

            inode_num = self.get_inode_by_path(new_path)
            inode = self.read_inode(inode_num)

            if not inode:
                raise FileNotFound(f"Path not found: {new_path}")
            if inode.file_type != 'dir':
                raise NotADirectory(f"Path is not a directory: {new_path}")

            self.current_path = new_path
            self.current_inode = inode_num

        except Exception as e:
            raise IOError(f"Failed to change directory to {path}: {str(e)}")

    def touch(self, path):
        if not path.startswith('/'):
            path = os.path.join(self.current_path, path)
        path = os.path.normpath(path)

        parent_path = os.path.dirname(path)
        file_name = os.path.basename(path)

        if not file_name:
            raise ValueError("Invalid file name")

        try:
            parent_inode = self.get_inode_by_path(parent_path)
            parent = self.read_inode(parent_inode)

            new_inode_num = self.allocate_inode()
            new_inode = Inode(
                inode_number=new_inode_num,
                file_type='file',
                permissions=parse_permissions("rw-r--r--"),
                uid=0,
                gid=0,
                parent_inode=parent_inode
            )

            parent.children_inodes.append(new_inode_num)

            self.write_inode(new_inode)
            self.write_inode(parent)

        except Exception as e:
            raise IOError(f"Failed to create file {path}: {str(e)}")

    def get_path_by_inode(self, inode_number):
        pass

    def write_file(self, path, content):
        try:
            with open(path, 'wb') as f:
                f.write(content)
        except Exception as e:
            raise IOError(f"Failed to write file: {e}")

    def read_file(self, path):
        try:
            with open(path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFound(f"File not found: {path}")
        except Exception as e:
            raise IOError(f"Failed to read file: {e}")


    def rm(self, path, recursive=False):
        pass

    def save_disk(self):
        pass

    @staticmethod
    def load_disk():
        pass

    def get_absolute_path(self, path):
        pass

    def get_directory_at_path(self, path):
        pass

    def get_superblock(self):
        print("Reading superblock...")
        data = self.read_block(0)
        if not data:
            raise InvalidDiskFormat("Could not read superblock")
        try:
            SUPERBLOCK_FORMAT = "<IQQQQQQQQQI"
            SUPERBLOCK_STRUCT_SIZE = struct.calcsize(SUPERBLOCK_FORMAT)
            unpacked = struct.unpack(SUPERBLOCK_FORMAT, data[:SUPERBLOCK_STRUCT_SIZE])
            superblock = {
                "magic": unpacked[0],
                "disk_size_blocks": unpacked[1],
                "block_size": unpacked[2],
                "inode_bitmap_start": unpacked[3],
                "inode_bitmap_blocks": unpacked[4],
                "data_block_bitmap_start": unpacked[5],
                "data_block_bitmap_blocks": unpacked[6],
                "inode_table_start": unpacked[7],
                "data_blocks_start": unpacked[8],
                "blocks_per_inode_table": unpacked[9],
                "root_inode": unpacked[10]
            }
            print(f"Successfully read superblock: {superblock}")
            return superblock
        except struct.error as e:
            raise InvalidDiskFormat(f"Invalid superblock format: {e}")

    def chmod(self, path, mode):
        try:
            inode_num = self.get_inode_by_path(path)
            inode = self.read_inode(inode_num)

            if isinstance(mode, str):
                current = inode.permissions
                who = mode[0]
                op = mode[1]
                what = mode[2:]

                if who == 'u':
                    mask = 0o700
                elif who == 'g':
                    mask = 0o070
                elif who == 'o':
                    mask = 0o007
                else:
                    mask = 0o777

                perm = parse_permissions(what)

                if op == '+':
                    inode.permissions |= (perm & mask)
                elif op == '-':
                    inode.permissions &= ~(perm & mask)
                else:
                    inode.permissions = (perm & mask) | (current & ~mask)
            else:
                inode.permissions = int(str(mode), 8)

            self.write_inode(inode)

        except Exception as e:
            raise IOError(f"Failed to change permissions: {str(e)}")

    def chown(self, path, uid, gid=None):
        try:
            inode_num = self.get_inode_by_path(path)
            inode = self.read_inode(inode_num)

            if uid is not None:
                inode.uid = int(uid)
            if gid is not None:
                inode.gid = int(gid)

            self.write_inode(inode)

        except Exception as e:
            raise IOError(f"Failed to change owner: {str(e)}")

    def get_stats(self):
        try:
            total_blocks = self.superblock["disk_size_blocks"]
            used_blocks = sum(1 for i in range(total_blocks) if self.is_block_allocated(i))

            return {
                "total_size": total_blocks * BLOCK_SIZE,
                "used_size": used_blocks * BLOCK_SIZE,
                "free_size": (total_blocks - used_blocks) * BLOCK_SIZE,
                "total_inodes": total_blocks * INODES_PER_BLOCK,
                "used_inodes": len(self.inodes),
                "free_inodes": (total_blocks * INODES_PER_BLOCK) - len(self.inodes)
            }

        except Exception as e:
            raise IOError(f"Failed to get filesystem stats: {str(e)}")

    def find(self, start_path, criteria_func):
        results = []
        try:
            def recursive_find(path):
                inode_num = self.get_inode_by_path(path)
                inode = self.read_inode(inode_num)

                info = {
                    'name': os.path.basename(path) or '/',
                    'type': inode.file_type,
                    'size': inode.size,
                    'permissions': inode.permissions,
                    'uid': inode.uid,
                    'gid': inode.gid
                }

                if criteria_func(info):
                    results.append(path)

                if inode.file_type == 'dir':
                    for child in inode.children_inodes:
                        child_inode = self.read_inode(child)
                        child_path = os.path.join(path, str(child))
                        recursive_find(child_path)

            recursive_find(start_path)
            return results

        except Exception as e:
            raise IOError(f"Failed to find files: {str(e)}")

    def is_block_allocated(self, block_num):
        try:
            bitmap = self.read_data_block_bitmap()
            return get_bit(bitmap, block_num)
        except Exception as e:
            raise IOError(f"Failed to check block allocation: {str(e)}")

    def create_tar(self, archive_name, files):
        try:
            archive_data = {}
            for file in files:
                content = self.read_file(file)
                archive_data[file] = content

            archive_content = repr(archive_data).encode('utf-8')
            self.write_file(archive_name, archive_content)

        except Exception as e:
            raise IOError(f"Failed to create archive: {str(e)}")

    def extract_tar(self, archive_name):
        try:
            archive_content = self.read_file(archive_name)
            archive_data = eval(archive_content)

            for file, content in archive_data.items():
                self.write_file(file, content)

        except Exception as e:
            raise IOError(f"Failed to extract archive: {str(e)}")

    def gzip_file(self, input_file, output_file):
        try:
            import gzip
            content = self.read_file(input_file)
            compressed = gzip.compress(content.encode('utf-8'))
            self.write_file(output_file, compressed)

        except Exception as e:
            raise IOError(f"Failed to compress file: {str(e)}")

    def gunzip_file(self, input_file, output_file):
        try:
            import gzip
            content = self.read_file(input_file)
            decompressed = gzip.decompress(content).decode('utf-8')
            self.write_file(output_file, decompressed)

        except Exception as e:
            raise IOError(f"Failed to decompress file: {str(e)}")