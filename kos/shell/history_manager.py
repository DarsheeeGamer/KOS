"""
KOS Command History Manager with Custom Binary Format
Implements history storage at /var/lib/kos/history/<uid>.klog
"""

import os
import time
import struct
import zlib
import mmap
import fcntl
import logging
from typing import List, Optional, Dict, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
import threading
from collections import deque

# Try to use VFS if available, fallback to host filesystem
try:
    from ..vfs.vfs_wrapper import get_vfs, VFS_O_RDONLY, VFS_O_WRONLY, VFS_O_CREAT, VFS_O_APPEND
    USE_VFS = True
    logger = logging.getLogger('kos.shell.history')
    logger.info("Using KOS VFS for history management")
except Exception as e:
    USE_VFS = False
    logger = logging.getLogger('kos.shell.history')
    logger.warning(f"VFS not available, using host filesystem: {e}")


@dataclass
class HistoryEntry:
    """Single history entry"""
    timestamp: float
    uid: int
    pid: int
    cwd: str
    command: str
    exit_code: int
    duration: float
    crc32: int


class HistoryManager:
    """
    Command history manager with custom binary format
    
    Format:
    [4 bytes: magic] [4 bytes: version] [4 bytes: entry_count]
    For each entry:
    [4 bytes: entry_size] [4 bytes: crc32]
    [8 bytes: timestamp] [4 bytes: uid] [4 bytes: pid]
    [2 bytes: cwd_len] [cwd_data]
    [2 bytes: cmd_len] [cmd_data]
    [4 bytes: exit_code] [8 bytes: duration]
    """
    
    MAGIC = 0x4B484953  # 'KHIS'
    VERSION = 1
    HEADER_SIZE = 12
    ENTRY_HEADER_SIZE = 8
    MAX_HISTORY = 10000
    HISTORY_DIR = os.path.expanduser("~/.kos/history")
    
    def __init__(self, uid: int = None):
        self.uid = uid or os.getuid()
        
        # Use home directory for history (both VFS and regular filesystem)
        history_dir = Path(self.HISTORY_DIR)
        history_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.history_file = history_dir / f"{self.uid}.klog"
            
        self._ensure_directories()
        
        # In-memory cache
        self._cache: deque = deque(maxlen=self.MAX_HISTORY)
        self._lock = threading.RLock()
        self._file_lock_fd = None
        
        # Load existing history
        self._load_history()
        
        # Search state
        self._search_cache = {}
        
    def _ensure_directories(self):
        """Ensure history directory exists with proper permissions"""
        try:
            # Directory already created in __init__, just ensure it's accessible
            if not self.history_file.parent.exists():
                self.history_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        except Exception as e:
            logger.debug(f"Directory creation failed: {e}")
            # Continue anyway, the file operations will handle the error
            pass
        
    def _acquire_file_lock(self):
        """Acquire exclusive lock on history file"""
        lock_path = f"{self.history_file}.lock"
        self._file_lock_fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
        fcntl.flock(self._file_lock_fd, fcntl.LOCK_EX)
        
    def _release_file_lock(self):
        """Release history file lock"""
        if self._file_lock_fd:
            fcntl.flock(self._file_lock_fd, fcntl.LOCK_UN)
            os.close(self._file_lock_fd)
            self._file_lock_fd = None
            
    def _calculate_crc32(self, data: bytes) -> int:
        """Calculate CRC32 checksum"""
        return zlib.crc32(data) & 0xffffffff
        
    def _pack_entry(self, entry: HistoryEntry) -> bytes:
        """Pack history entry to binary format"""
        # Encode strings
        cwd_bytes = entry.cwd.encode('utf-8')
        cmd_bytes = entry.command.encode('utf-8')
        
        # Pack data
        data = struct.pack(
            '>dIIHH',
            entry.timestamp,
            entry.uid,
            entry.pid,
            len(cwd_bytes),
            len(cmd_bytes)
        )
        data += cwd_bytes
        data += cmd_bytes
        data += struct.pack('>id', entry.exit_code, entry.duration)
        
        # Calculate CRC32
        crc32 = self._calculate_crc32(data)
        
        # Pack with size and CRC
        return struct.pack('>II', len(data), crc32) + data
        
    def _unpack_entry(self, data: bytes) -> Optional[HistoryEntry]:
        """Unpack binary data to history entry"""
        if len(data) < 24:  # Minimum entry size
            return None
            
        try:
            # Unpack fixed fields
            offset = 0
            timestamp, uid, pid, cwd_len, cmd_len = struct.unpack_from(
                '>dIIHH', data, offset
            )
            offset += 20
            
            # Unpack strings
            cwd = data[offset:offset + cwd_len].decode('utf-8')
            offset += cwd_len
            
            command = data[offset:offset + cmd_len].decode('utf-8')
            offset += cmd_len
            
            # Unpack remaining fields
            exit_code, duration = struct.unpack_from('>id', data, offset)
            
            return HistoryEntry(
                timestamp=timestamp,
                uid=uid,
                pid=pid,
                cwd=cwd,
                command=command,
                exit_code=exit_code,
                duration=duration,
                crc32=0  # Set by caller
            )
            
        except Exception as e:
            logger.error(f"Failed to unpack history entry: {e}")
            return None
            
    def _load_history(self):
        """Load history from file into cache"""
        if not self.history_file.exists():
            return
            
        with self._lock:
            self._acquire_file_lock()
            try:
                with open(self.history_file, 'rb') as f:
                    # Read header
                    header = f.read(self.HEADER_SIZE)
                    if len(header) < self.HEADER_SIZE:
                        return
                        
                    magic, version, entry_count = struct.unpack('>III', header)
                    
                    if magic != self.MAGIC or version != self.VERSION:
                        logger.warning("Invalid history file format")
                        return
                        
                    # Read entries
                    for _ in range(entry_count):
                        # Read entry header
                        entry_header = f.read(self.ENTRY_HEADER_SIZE)
                        if len(entry_header) < self.ENTRY_HEADER_SIZE:
                            break
                            
                        entry_size, crc32 = struct.unpack('>II', entry_header)
                        
                        # Read entry data
                        entry_data = f.read(entry_size)
                        if len(entry_data) < entry_size:
                            break
                            
                        # Verify CRC32
                        if self._calculate_crc32(entry_data) != crc32:
                            logger.warning("CRC32 mismatch in history entry")
                            continue
                            
                        # Unpack entry
                        entry = self._unpack_entry(entry_data)
                        if entry:
                            entry.crc32 = crc32
                            self._cache.append(entry)
                            
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
            finally:
                self._release_file_lock()
                
    def _save_history(self):
        """Save cache to history file"""
        with self._lock:
            self._acquire_file_lock()
            try:
                # Write to temporary file
                temp_file = f"{self.history_file}.tmp"
                
                with open(temp_file, 'wb') as f:
                    # Write header
                    header = struct.pack(
                        '>III',
                        self.MAGIC,
                        self.VERSION,
                        len(self._cache)
                    )
                    f.write(header)
                    
                    # Write entries
                    for entry in self._cache:
                        entry_data = self._pack_entry(entry)
                        f.write(entry_data)
                        
                # Atomic replace
                os.rename(temp_file, self.history_file)
                os.chmod(self.history_file, 0o600)
                
            except Exception as e:
                logger.error(f"Failed to save history: {e}")
            finally:
                self._release_file_lock()
                
    def add_entry(self, command: str, exit_code: int = 0, duration: float = 0.0):
        """Add command to history"""
        if not command.strip():
            return
            
        entry = HistoryEntry(
            timestamp=time.time(),
            uid=self.uid,
            pid=os.getpid(),
            cwd=os.getcwd(),
            command=command,
            exit_code=exit_code,
            duration=duration,
            crc32=0
        )
        
        with self._lock:
            self._cache.append(entry)
            
            # Save periodically
            if len(self._cache) % 10 == 0:
                self._save_history()
                
    def get_history(self, limit: int = None) -> List[HistoryEntry]:
        """Get command history"""
        with self._lock:
            if limit:
                return list(self._cache)[-limit:]
            return list(self._cache)
            
    def search_history(self, pattern: str, fuzzy: bool = True) -> List[HistoryEntry]:
        """Search command history"""
        results = []
        pattern_lower = pattern.lower()
        
        with self._lock:
            for entry in reversed(self._cache):
                if fuzzy:
                    # Fuzzy search
                    if self._fuzzy_match(pattern_lower, entry.command.lower()):
                        results.append(entry)
                else:
                    # Exact substring match
                    if pattern_lower in entry.command.lower():
                        results.append(entry)
                        
        return results
        
    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Simple fuzzy matching"""
        p_idx = 0
        for char in text:
            if p_idx < len(pattern) and char == pattern[p_idx]:
                p_idx += 1
        return p_idx == len(pattern)
        
    def get_last_command(self) -> Optional[str]:
        """Get last executed command"""
        with self._lock:
            if self._cache:
                return self._cache[-1].command
        return None
        
    def clear_history(self):
        """Clear all history"""
        with self._lock:
            self._cache.clear()
            self._save_history()
            
    def export_history(self, format: str = 'text') -> str:
        """Export history in various formats"""
        with self._lock:
            if format == 'text':
                lines = []
                for i, entry in enumerate(self._cache):
                    lines.append(f"{i+1}  {entry.command}")
                return '\n'.join(lines)
                
            elif format == 'json':
                import json
                data = []
                for entry in self._cache:
                    data.append({
                        'timestamp': entry.timestamp,
                        'command': entry.command,
                        'cwd': entry.cwd,
                        'exit_code': entry.exit_code,
                        'duration': entry.duration
                    })
                return json.dumps(data, indent=2)
                
        return ""
        
    def handle_expansion(self, text: str) -> Optional[str]:
        """Handle history expansion (!! !$ etc)"""
        if not text:
            return None
            
        with self._lock:
            # !! - last command
            if text == '!!':
                return self.get_last_command()
                
            # !$ - last argument of last command
            elif text == '!$':
                last_cmd = self.get_last_command()
                if last_cmd:
                    parts = last_cmd.split()
                    if len(parts) > 1:
                        return parts[-1]
                        
            # !n - nth command
            elif text.startswith('!') and text[1:].isdigit():
                n = int(text[1:])
                if 0 < n <= len(self._cache):
                    return self._cache[n-1].command
                    
            # !string - last command starting with string
            elif text.startswith('!'):
                search = text[1:]
                for entry in reversed(self._cache):
                    if entry.command.startswith(search):
                        return entry.command
                        
        return None
        
    def close(self):
        """Save and close history"""
        self._save_history()


# Singleton instance per UID
_history_managers: Dict[int, HistoryManager] = {}

def get_history_manager(uid: int = None) -> HistoryManager:
    """Get history manager for user"""
    if uid is None:
        uid = os.getuid()
        
    if uid not in _history_managers:
        _history_managers[uid] = HistoryManager(uid)
        
    return _history_managers[uid]