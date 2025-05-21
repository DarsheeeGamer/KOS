"""
Kaede Operating System (KOS) - A Python-based Linux-like OS simulation
Advanced version with consolidated functionality
"""
import os
import sys
import cmd
import shlex
import hashlib
import getpass
import json
import signal
import platform
import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import re
import subprocess
import gzip
import tarfile
import zipfile
import fnmatch

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('KOS')

# Constants
VERSION = "1.0.0"
BLOCK_SIZE = 512  # bytes
INODE_SIZE = 316  # bytes
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max file size
USER_DATA_FILE = "users.json"

# Exception Classes
class KOSError(Exception):
    """Base exception for KOS"""
    pass

class FileSystemError(KOSError):
    """File system related errors"""
    pass

class AuthenticationError(KOSError):
    """Authentication related errors"""
    pass

class PackageError(KOSError):
    """Package management related errors"""
    pass

# Authentication Manager
class AuthenticationManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout = 3600  # 1 hour
        self.active_users: Dict[str, str] = {}  # username -> status mapping

    def create_session(self, username: str) -> str:
        """Create a new session"""
        import secrets
        session_id = secrets.token_hex(32)
        self.sessions[session_id] = {
            'username': username,
            'created_at': datetime.now(),
            'last_accessed': datetime.now()
        }
        self.active_users[username] = "active"
        return session_id

    def end_session(self, username: str):
        """End a user session"""
        # Remove from active sessions
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if session['username'] == username:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.sessions[session_id]

        # Update user status
        if username in self.active_users:
            self.active_users[username] = "offline"

    def validate_session(self, session_id: str) -> Optional[str]:
        """Validate session and return username if valid"""
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        if (datetime.now() - session['last_accessed']).total_seconds() > self.session_timeout:
            self.end_session(session['username'])
            return None
        session['last_accessed'] = datetime.now()
        return session['username']

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify password against stored hash"""
        return stored_hash == self.hash_password(password)


    def do_grep(self, arg):
        """Search for patterns in files"""
        try:
            args = shlex.split(arg)
            if not args:
                print("grep: missing pattern")
                return

            ignore_case = '-i' in args
            show_numbers = '-n' in args
            recursive = '-r' in args

            # Remove options from args
            pattern = next((a for a in args if not a.startswith('-')), None)
            if pattern is None:
                print("grep: missing pattern")
                return

            files = [a for a in args if not a.startswith('-') and a != pattern]
            if not files:
                files = ['.']

            def search_file(filepath, pattern):
                try:
                    content = self.fs.cat(filepath)
                    lines = content.splitlines()
                    for i, line in enumerate(lines, 1):
                        if (ignore_case and re.search(pattern, line, re.IGNORECASE)) or \
                           (not ignore_case and re.search(pattern, line)):
                            if show_numbers:
                                print(f"{filepath}:{i}:{line}")
                            else:
                                print(f"{filepath}:{line}")
                except Exception as e:
                    logger.error(f"Error searching file {filepath}: {e}")

            for filepath in files:
                if recursive and self.fs.is_dir(filepath):
                    for root, _, fnames in self.fs.walk(filepath):
                        for fname in fnames:
                            search_file(os.path.join(root, fname), pattern)
                else:
                    search_file(filepath, pattern)

        except Exception as e:
            print(f"grep: {str(e)}")
            logger.error(f"Grep error: {str(e)}")

    def do_gzip(self, arg):
        """Compress or decompress files using gzip compression"""
        try:
            args = shlex.split(arg)
            if not args:
                print("gzip: missing file operand")
                return

            file_path = args[0]
            if file_path.endswith('.gz'):
                with gzip.open(file_path, 'rb') as f_in:
                    with open(file_path[:-3], 'wb') as f_out:
                        f_out.write(f_in.read())
                print(f"Decompressed '{file_path}'")
            else:
                with open(file_path, 'rb') as f_in:
                    with gzip.open(file_path + ".gz", 'wb') as f_out:
                        f_out.write(f_in.read())
                print(f"Compressed '{file_path}'")
        except Exception as e:
            print(f"gzip: {str(e)}")
            logger.error(f"Gzip error: {str(e)}")



def main():
    """Initialize and start KOS"""
    try:
        logger.info("Initializing KOS components...")
        filesystem = FileSystem(disk_size_mb=100)
        logger.info("FileSystem initialized")

        package_manager = PackageManager()
        logger.info("Package Manager initialized")

        user_system = UserSystem()
        logger.info(f"User System initialized with current user: {user_system.current_user}")

        # Set filesystem's user system reference
        filesystem.user_system = user_system
        logger.info("Filesystem user system reference set")

        shell = KaedeShell(filesystem, package_manager, user_system)
        logger.info("Shell initialized, starting command loop...")
        shell.cmdloop()
    except Exception as e:
        logger.error(f"Failed to start KOS: {str(e)}")
        raise

if __name__ == "__main__":
    main()