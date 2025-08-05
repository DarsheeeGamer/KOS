"""
KOS ksudo Implementation - Kernel-level sudo with direct syscall integration
"""

import os
import pwd
import time
import hashlib
import logging
import ctypes
import threading
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import struct

logger = logging.getLogger('kos.core.ksudo')


@dataclass
class KsudoRequest:
    """Ksudo elevation request"""
    uid: int
    target_uid: int
    command: str
    args: List[str]
    env: Dict[str, str]
    timestamp: float
    auth_token: bytes


class KsudoKernel:
    """
    Kernel-level sudo implementation
    Uses direct syscalls for privilege elevation
    """
    
    # Custom syscall numbers (would be assigned by kernel)
    SYS_KSUDO_AUTH = 0x1337
    SYS_KSUDO_EXEC = 0x1338
    SYS_KSUDO_CHECK = 0x1339
    
    # Capability flags
    CAP_KSUDO = (1 << 63)  # Custom capability for ksudo
    
    def __init__(self):
        self.libc = ctypes.CDLL("libc.so.6", use_errno=True)
        self._setup_syscalls()
        self._auth_cache = {}
        self._cache_lock = threading.RLock()
        
    def _setup_syscalls(self):
        """Setup syscall wrappers"""
        # Standard syscalls
        self.libc.syscall.argtypes = [ctypes.c_long]
        self.libc.syscall.restype = ctypes.c_long
        
        # Capability syscalls
        self.libc.capget.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.libc.capget.restype = ctypes.c_int
        
        self.libc.capset.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.libc.capset.restype = ctypes.c_int
        
    def _syscall(self, number: int, *args) -> int:
        """Make direct syscall"""
        # Convert args to ctypes
        c_args = []
        for arg in args:
            if isinstance(arg, str):
                c_args.append(ctypes.c_char_p(arg.encode()))
            elif isinstance(arg, int):
                c_args.append(ctypes.c_long(arg))
            elif isinstance(arg, bytes):
                c_args.append(ctypes.c_char_p(arg))
            else:
                c_args.append(arg)
                
        return self.libc.syscall(ctypes.c_long(number), *c_args)
        
    def authenticate(self, password: str) -> Optional[bytes]:
        """
        Authenticate for ksudo access
        Returns auth token on success
        """
        # Get current user
        uid = os.getuid()
        
        # Check if already cached
        with self._cache_lock:
            if uid in self._auth_cache:
                cached = self._auth_cache[uid]
                if time.time() - cached['timestamp'] < 300:  # 5 min cache
                    return cached['token']
                    
        # Verify password using shadow manager
        from ..security.shadow_manager import get_shadow_manager
        shadow_mgr = get_shadow_manager()
        
        try:
            user = pwd.getpwuid(uid)
            if not shadow_mgr.verify_password(user.pw_name, password):
                return None
                
            # Generate auth token
            token_data = f"{uid}:{time.time()}:{os.urandom(16).hex()}"
            token = hashlib.sha256(token_data.encode()).digest()
            
            # Make kernel syscall to register token
            ret = self._syscall(self.SYS_KSUDO_AUTH, uid, token, len(token))
            if ret < 0:
                # Fallback: Store in userspace
                pass
                
            # Cache token
            with self._cache_lock:
                self._auth_cache[uid] = {
                    'token': token,
                    'timestamp': time.time()
                }
                
            return token
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None
            
    def check_permission(self, target_uid: int = 0) -> bool:
        """Check if current user has ksudo permission"""
        uid = os.getuid()
        
        # Root always has permission
        if uid == 0:
            return True
            
        # Check user groups
        try:
            user = pwd.getpwuid(uid)
            groups = os.getgrouplist(user.pw_name, user.pw_gid)
            
            # Check for sudo/wheel group
            for group_name in ['sudo', 'wheel', 'ksudo']:
                try:
                    import grp
                    group_info = grp.getgrnam(group_name)
                    if group_info.gr_gid in groups:
                        return True
                except KeyError:
                    pass
                    
        except Exception:
            pass
            
        # Check kernel capability
        ret = self._syscall(self.SYS_KSUDO_CHECK, uid, target_uid)
        return ret == 0
        
    def execute_privileged(self, command: str, args: List[str] = None,
                          target_uid: int = 0, auth_token: bytes = None) -> int:
        """
        Execute command with elevated privileges
        Returns exit code
        """
        if auth_token is None:
            logger.error("No auth token provided")
            return -1
            
        # Create request
        request = KsudoRequest(
            uid=os.getuid(),
            target_uid=target_uid,
            command=command,
            args=args or [],
            env=dict(os.environ),
            timestamp=time.time(),
            auth_token=auth_token
        )
        
        # Serialize request
        request_data = self._serialize_request(request)
        
        # Make kernel syscall
        ret = self._syscall(
            self.SYS_KSUDO_EXEC,
            request_data,
            len(request_data)
        )
        
        if ret < 0:
            # Fallback: Use standard privilege elevation
            return self._fallback_execute(request)
            
        return ret
        
    def _serialize_request(self, request: KsudoRequest) -> bytes:
        """Serialize ksudo request for kernel"""
        # Pack fixed fields
        header = struct.pack(
            '>IIIdI',
            request.uid,
            request.target_uid,
            len(request.command),
            request.timestamp,
            len(request.auth_token)
        )
        
        # Pack variable fields
        data = header
        data += request.command.encode()
        data += request.auth_token
        
        # Pack args
        data += struct.pack('>I', len(request.args))
        for arg in request.args:
            arg_bytes = arg.encode()
            data += struct.pack('>I', len(arg_bytes))
            data += arg_bytes
            
        # Pack env
        data += struct.pack('>I', len(request.env))
        for key, value in request.env.items():
            kv = f"{key}={value}".encode()
            data += struct.pack('>I', len(kv))
            data += kv
            
        return data
        
    def _fallback_execute(self, request: KsudoRequest) -> int:
        """Fallback execution using setuid"""
        import subprocess
        
        # Build command
        cmd = [request.command] + request.args
        
        # Create subprocess with elevated privileges
        if os.getuid() == 0:
            # Already root, just setuid
            def preexec():
                os.setuid(request.target_uid)
                
            proc = subprocess.Popen(
                cmd,
                env=request.env,
                preexec_fn=preexec
            )
        else:
            # Use sudo as fallback
            sudo_cmd = ['sudo', '-u', f'#{request.target_uid}'] + cmd
            proc = subprocess.Popen(sudo_cmd, env=request.env)
            
        return proc.wait()


class KsudoShell:
    """Shell integration for ksudo"""
    
    def __init__(self):
        self.kernel = KsudoKernel()
        self._last_auth = None
        self._auth_time = 0
        
    def ksudo(self, command: str, args: List[str] = None) -> int:
        """
        Execute command with ksudo
        Prompts for password if needed
        """
        # Check if we need authentication
        if not self._is_authenticated():
            password = self._prompt_password()
            if not password:
                print("ksudo: authentication cancelled")
                return 1
                
            token = self.kernel.authenticate(password)
            if not token:
                print("ksudo: authentication failure")
                return 1
                
            self._last_auth = token
            self._auth_time = time.time()
            
        # Execute with privileges
        return self.kernel.execute_privileged(
            command,
            args,
            target_uid=0,
            auth_token=self._last_auth
        )
        
    def _is_authenticated(self) -> bool:
        """Check if we have valid authentication"""
        if not self._last_auth:
            return False
            
        # Check timeout (5 minutes)
        if time.time() - self._auth_time > 300:
            self._last_auth = None
            return False
            
        return True
        
    def _prompt_password(self) -> Optional[str]:
        """Prompt for password"""
        import getpass
        try:
            return getpass.getpass("ksudo: ")
        except KeyboardInterrupt:
            print()
            return None


# Singleton instance
_ksudo_shell = None

def get_ksudo_shell() -> KsudoShell:
    """Get global ksudo shell instance"""
    global _ksudo_shell
    if _ksudo_shell is None:
        _ksudo_shell = KsudoShell()
    return _ksudo_shell


def ksudo_exec(command: str, *args) -> int:
    """
    Convenience function for ksudo execution
    """
    shell = get_ksudo_shell()
    return shell.ksudo(command, list(args))