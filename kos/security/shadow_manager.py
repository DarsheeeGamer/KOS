"""
KOS Shadow File System Implementation
Implements /etc/kos/shadow with one-way encryption
"""

import os
import time
import hashlib
import secrets
import struct
import fcntl
import logging
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import threading

logger = logging.getLogger('kos.security.shadow')


@dataclass
class ShadowEntry:
    """Shadow file entry"""
    username: str
    password_hash: str  # $6$salt$hash format
    last_change: int    # Days since epoch
    min_days: int       # Minimum days between changes
    max_days: int       # Maximum days before expiry
    warn_days: int      # Warning days before expiry
    inactive_days: int  # Days after expiry before account lock
    expire_date: int    # Account expiration date (days since epoch)
    reserved: str       # Reserved field


class ShadowManager:
    """
    Manages /etc/kos/shadow file with proper security
    """
    
    SHADOW_PATH = "/etc/kos/shadow"
    SHADOW_BACKUP = "/etc/kos/shadow-"
    SHADOW_LOCK = "/etc/kos/.shadow.lock"
    
    # SHA512 with 200k iterations as specified
    HASH_ITERATIONS = 200000
    
    def __init__(self):
        self._ensure_directories()
        self._lock = threading.RLock()
        self._file_lock_fd = None
        
    def _ensure_directories(self):
        """Ensure shadow directory exists with proper permissions"""
        shadow_dir = Path(self.SHADOW_PATH).parent
        shadow_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Create shadow file if it doesn't exist
        if not Path(self.SHADOW_PATH).exists():
            Path(self.SHADOW_PATH).touch(mode=0o000)
            
    def _acquire_file_lock(self):
        """Acquire exclusive lock on shadow file"""
        self._file_lock_fd = os.open(self.SHADOW_LOCK, os.O_CREAT | os.O_WRONLY, 0o600)
        fcntl.flock(self._file_lock_fd, fcntl.LOCK_EX)
        
    def _release_file_lock(self):
        """Release shadow file lock"""
        if self._file_lock_fd:
            fcntl.flock(self._file_lock_fd, fcntl.LOCK_UN)
            os.close(self._file_lock_fd)
            self._file_lock_fd = None
            
    def _apply_formula_encoding(self, password: str, salt: bytes) -> str:
        """
        Apply the formula encoding before hashing
        This implements the custom encoding mentioned in the blueprint
        """
        # Base components
        a = base64.b64encode(f"Encryptionkey_{salt.hex()}".encode()).decode()
        b = base64.b64encode(f"{password}_{salt.hex()}".encode()).decode()
        
        # Metadata components
        M = base64.b85encode(f"Meta_{time.time()}".encode()).decode()
        C = base64.b85encode(f"Control_{os.getpid()}".encode()).decode()
        E = base64.b85encode(f"Env_{os.environ.get('USER', 'kos')}".encode()).decode()
        
        # Apply formula similar to fingerprint
        encoded = base64.b64encode(
            f"{a}{b}{M}{C}{E}".encode()
        ).decode()
        
        return encoded
        
    def _hash_password(self, password: str, salt: Optional[bytes] = None) -> str:
        """
        Hash password using SHA512 with 200k iterations
        Returns in format: $6$salt$hash
        """
        import base64
        
        if salt is None:
            salt = secrets.token_bytes(16)
            
        # Apply formula encoding
        encoded_password = self._apply_formula_encoding(password, salt)
        
        # SHA512 with iterations
        hash_result = hashlib.pbkdf2_hmac(
            'sha512',
            encoded_password.encode(),
            salt,
            self.HASH_ITERATIONS
        )
        
        # Format: $6$salt$hash
        salt_b64 = base64.b64encode(salt).decode().rstrip('=')
        hash_b64 = base64.b64encode(hash_result).decode().rstrip('=')
        
        return f"$6${salt_b64}${hash_b64}"
        
    def _parse_shadow_line(self, line: str) -> Optional[ShadowEntry]:
        """Parse a shadow file line"""
        parts = line.strip().split(':')
        if len(parts) < 9:
            return None
            
        try:
            return ShadowEntry(
                username=parts[0],
                password_hash=parts[1],
                last_change=int(parts[2]) if parts[2] else 0,
                min_days=int(parts[3]) if parts[3] else 0,
                max_days=int(parts[4]) if parts[4] else 99999,
                warn_days=int(parts[5]) if parts[5] else 7,
                inactive_days=int(parts[6]) if parts[6] else -1,
                expire_date=int(parts[7]) if parts[7] else -1,
                reserved=parts[8] if len(parts) > 8 else ""
            )
        except ValueError:
            return None
            
    def _format_shadow_line(self, entry: ShadowEntry) -> str:
        """Format shadow entry as line"""
        return f"{entry.username}:{entry.password_hash}:{entry.last_change}:" \
               f"{entry.min_days}:{entry.max_days}:{entry.warn_days}:" \
               f"{entry.inactive_days}:{entry.expire_date}:{entry.reserved}"
               
    def _read_shadow_file(self) -> Dict[str, ShadowEntry]:
        """Read and parse shadow file"""
        entries = {}
        
        try:
            # Temporarily change permissions to read
            os.chmod(self.SHADOW_PATH, 0o600)
            
            with open(self.SHADOW_PATH, 'r') as f:
                for line in f:
                    entry = self._parse_shadow_line(line)
                    if entry:
                        entries[entry.username] = entry
                        
        except FileNotFoundError:
            pass
        finally:
            # Restore permissions
            os.chmod(self.SHADOW_PATH, 0o000)
            
        return entries
        
    def _write_shadow_file(self, entries: Dict[str, ShadowEntry]):
        """Write shadow file with proper permissions"""
        # Create backup
        if Path(self.SHADOW_PATH).exists():
            import shutil
            shutil.copy2(self.SHADOW_PATH, self.SHADOW_BACKUP)
            
        # Write new file
        temp_path = f"{self.SHADOW_PATH}.tmp"
        
        try:
            with open(temp_path, 'w', opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
                for username in sorted(entries.keys()):
                    f.write(self._format_shadow_line(entries[username]) + '\n')
                    
            # Atomic replace
            os.rename(temp_path, self.SHADOW_PATH)
            
            # Set final permissions
            os.chmod(self.SHADOW_PATH, 0o000)
            
        except Exception as e:
            # Restore from backup
            if Path(self.SHADOW_BACKUP).exists():
                import shutil
                shutil.copy2(self.SHADOW_BACKUP, self.SHADOW_PATH)
            raise
            
    def set_password(self, username: str, password: str) -> bool:
        """Set user password"""
        with self._lock:
            self._acquire_file_lock()
            try:
                # Read current entries
                entries = self._read_shadow_file()
                
                # Hash password
                password_hash = self._hash_password(password)
                
                # Calculate days since epoch
                days_since_epoch = int(time.time() / 86400)
                
                # Create or update entry
                if username in entries:
                    entry = entries[username]
                    entry.password_hash = password_hash
                    entry.last_change = days_since_epoch
                else:
                    entry = ShadowEntry(
                        username=username,
                        password_hash=password_hash,
                        last_change=days_since_epoch,
                        min_days=0,
                        max_days=99999,
                        warn_days=7,
                        inactive_days=-1,
                        expire_date=-1,
                        reserved=""
                    )
                    entries[username] = entry
                    
                # Write back
                self._write_shadow_file(entries)
                
                logger.info(f"Password updated for user {username}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to set password: {e}")
                return False
            finally:
                self._release_file_lock()
                
    def verify_password(self, username: str, password: str) -> bool:
        """Verify user password"""
        with self._lock:
            self._acquire_file_lock()
            try:
                entries = self._read_shadow_file()
                
                if username not in entries:
                    return False
                    
                entry = entries[username]
                
                # Parse existing hash
                if not entry.password_hash.startswith('$6$'):
                    return False
                    
                parts = entry.password_hash.split('$')
                if len(parts) < 4:
                    return False
                    
                salt_b64 = parts[2]
                stored_hash = parts[3]
                
                # Decode salt
                import base64
                salt = base64.b64decode(salt_b64 + '==')
                
                # Hash provided password
                test_hash = self._hash_password(password, salt)
                
                # Compare
                return test_hash == entry.password_hash
                
            except Exception as e:
                logger.error(f"Failed to verify password: {e}")
                return False
            finally:
                self._release_file_lock()
                
    def lock_account(self, username: str) -> bool:
        """Lock user account by prefixing hash with !"""
        with self._lock:
            self._acquire_file_lock()
            try:
                entries = self._read_shadow_file()
                
                if username not in entries:
                    return False
                    
                entry = entries[username]
                if not entry.password_hash.startswith('!'):
                    entry.password_hash = '!' + entry.password_hash
                    
                self._write_shadow_file(entries)
                return True
                
            except Exception as e:
                logger.error(f"Failed to lock account: {e}")
                return False
            finally:
                self._release_file_lock()
                
    def unlock_account(self, username: str) -> bool:
        """Unlock user account"""
        with self._lock:
            self._acquire_file_lock()
            try:
                entries = self._read_shadow_file()
                
                if username not in entries:
                    return False
                    
                entry = entries[username]
                if entry.password_hash.startswith('!'):
                    entry.password_hash = entry.password_hash[1:]
                    
                self._write_shadow_file(entries)
                return True
                
            except Exception as e:
                logger.error(f"Failed to unlock account: {e}")
                return False
            finally:
                self._release_file_lock()
                
    def get_account_info(self, username: str) -> Optional[Dict[str, any]]:
        """Get account information"""
        with self._lock:
            self._acquire_file_lock()
            try:
                entries = self._read_shadow_file()
                
                if username not in entries:
                    return None
                    
                entry = entries[username]
                
                return {
                    'username': entry.username,
                    'locked': entry.password_hash.startswith('!'),
                    'last_change': entry.last_change,
                    'min_days': entry.min_days,
                    'max_days': entry.max_days,
                    'warn_days': entry.warn_days,
                    'inactive_days': entry.inactive_days,
                    'expire_date': entry.expire_date
                }
                
            except Exception as e:
                logger.error(f"Failed to get account info: {e}")
                return None
            finally:
                self._release_file_lock()
                
    def remove_user(self, username: str) -> bool:
        """Remove user from shadow file"""
        with self._lock:
            self._acquire_file_lock()
            try:
                entries = self._read_shadow_file()
                
                if username in entries:
                    del entries[username]
                    self._write_shadow_file(entries)
                    return True
                    
                return False
                
            except Exception as e:
                logger.error(f"Failed to remove user: {e}")
                return False
            finally:
                self._release_file_lock()


# Global instance
_shadow_manager = None

def get_shadow_manager() -> ShadowManager:
    """Get global shadow manager instance"""
    global _shadow_manager
    if _shadow_manager is None:
        _shadow_manager = ShadowManager()
    return _shadow_manager