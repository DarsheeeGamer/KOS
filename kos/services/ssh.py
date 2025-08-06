"""
SSH server implementation for KOS
"""

import time
import secrets
import hashlib
import hmac
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

class SSHAuthMethod(Enum):
    """SSH authentication methods"""
    PASSWORD = "password"
    PUBLIC_KEY = "publickey"
    KEYBOARD_INTERACTIVE = "keyboard-interactive"

@dataclass
class SSHKey:
    """SSH key pair"""
    key_type: str  # rsa, ed25519, ecdsa
    public_key: str
    private_key: Optional[str] = None
    fingerprint: Optional[str] = None
    
    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self._calculate_fingerprint()
    
    def _calculate_fingerprint(self) -> str:
        """Calculate key fingerprint"""
        key_hash = hashlib.sha256(self.public_key.encode()).digest()
        return ':'.join(f'{b:02x}' for b in key_hash[:16])

@dataclass
class SSHSession:
    """SSH session"""
    session_id: str
    username: str
    client_addr: str
    auth_method: SSHAuthMethod
    connected_at: float
    last_activity: float
    shell_pid: Optional[int] = None
    env: Dict[str, str] = None
    
    def __post_init__(self):
        if self.env is None:
            self.env = {}

class SSHServer:
    """SSH server implementation"""
    
    def __init__(self, vfs=None, auth=None, executor=None, port: int = 22):
        self.vfs = vfs
        self.auth = auth
        self.executor = executor
        self.port = port
        self.running = False
        
        # Sessions
        self.sessions: Dict[str, SSHSession] = {}
        
        # Configuration
        self.config = {
            'host_key': None,
            'banner': "Welcome to KOS SSH Server",
            'max_sessions': 10,
            'idle_timeout': 600,  # 10 minutes
            'auth_methods': [SSHAuthMethod.PASSWORD, SSHAuthMethod.PUBLIC_KEY],
            'allow_root': False,
            'password_auth': True,
            'pubkey_auth': True
        }
        
        # Authorized keys
        self.authorized_keys: Dict[str, List[SSHKey]] = {}
        
        self._init_ssh()
    
    def _init_ssh(self):
        """Initialize SSH server"""
        # Generate host key if not exists
        if not self.config['host_key']:
            self.config['host_key'] = self._generate_host_key()
        
        # Load authorized keys
        self._load_authorized_keys()
    
    def _generate_host_key(self) -> SSHKey:
        """Generate SSH host key"""
        # Simulated key generation
        private_key = secrets.token_hex(64)
        public_key = secrets.token_hex(32)
        
        return SSHKey(
            key_type="ed25519",
            public_key=public_key,
            private_key=private_key
        )
    
    def _load_authorized_keys(self):
        """Load authorized keys from VFS"""
        if not self.vfs:
            return
        
        # Load system-wide authorized keys
        system_keys_file = "/etc/ssh/authorized_keys"
        if self.vfs.exists(system_keys_file):
            try:
                with self.vfs.open(system_keys_file, 'r') as f:
                    self._parse_authorized_keys(f.read().decode(), "root")
            except:
                pass
        
        # Load user authorized keys
        if self.vfs.exists("/home"):
            try:
                for username in self.vfs.listdir("/home"):
                    user_keys_file = f"/home/{username}/.ssh/authorized_keys"
                    if self.vfs.exists(user_keys_file):
                        with self.vfs.open(user_keys_file, 'r') as f:
                            self._parse_authorized_keys(f.read().decode(), username)
            except:
                pass
    
    def _parse_authorized_keys(self, content: str, username: str):
        """Parse authorized_keys file"""
        if username not in self.authorized_keys:
            self.authorized_keys[username] = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                key_type = parts[0]
                public_key = parts[1]
                
                key = SSHKey(
                    key_type=key_type,
                    public_key=public_key
                )
                
                self.authorized_keys[username].append(key)
    
    def authenticate(self, username: str, method: SSHAuthMethod, 
                     credentials: Dict) -> bool:
        """Authenticate SSH connection"""
        # Check if method is allowed
        if method not in self.config['auth_methods']:
            return False
        
        # Check root access
        if username == "root" and not self.config['allow_root']:
            return False
        
        if method == SSHAuthMethod.PASSWORD:
            # Password authentication
            if not self.config['password_auth']:
                return False
            
            password = credentials.get('password')
            if self.auth:
                return self.auth.authenticate(username, password)
            
            # Fallback to simple check
            return username == "admin" and password == "admin123"
        
        elif method == SSHAuthMethod.PUBLIC_KEY:
            # Public key authentication
            if not self.config['pubkey_auth']:
                return False
            
            public_key = credentials.get('public_key')
            if not public_key:
                return False
            
            # Check authorized keys
            if username in self.authorized_keys:
                for auth_key in self.authorized_keys[username]:
                    if auth_key.public_key == public_key:
                        return True
            
            return False
        
        return False
    
    def create_session(self, username: str, client_addr: str,
                      auth_method: SSHAuthMethod) -> Optional[str]:
        """Create SSH session"""
        # Check max sessions
        if len(self.sessions) >= self.config['max_sessions']:
            return None
        
        # Generate session ID
        session_id = secrets.token_hex(16)
        
        # Create session
        session = SSHSession(
            session_id=session_id,
            username=username,
            client_addr=client_addr,
            auth_method=auth_method,
            connected_at=time.time(),
            last_activity=time.time()
        )
        
        # Set environment
        session.env = {
            'USER': username,
            'HOME': f'/home/{username}' if username != 'root' else '/root',
            'SHELL': '/bin/bash',
            'TERM': 'xterm-256color',
            'SSH_CONNECTION': f'{client_addr} {self.port}',
            'SSH_TTY': f'/dev/pts/{len(self.sessions)}'
        }
        
        self.sessions[session_id] = session
        
        return session_id
    
    def execute_command(self, session_id: str, command: str) -> Tuple[int, str, str]:
        """Execute command in SSH session"""
        if session_id not in self.sessions:
            return -1, "", "Session not found"
        
        session = self.sessions[session_id]
        session.last_activity = time.time()
        
        # Execute command
        if self.executor:
            # Use executor with session environment
            result = self.executor.execute(command, env=session.env)
            return result
        
        # Simulated execution
        return 0, f"Executed: {command}", ""
    
    def start_shell(self, session_id: str) -> bool:
        """Start interactive shell for session"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        # Start shell process
        if self.executor:
            # Would start shell process
            session.shell_pid = 1234  # Simulated PID
        
        return True
    
    def close_session(self, session_id: str):
        """Close SSH session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Kill shell process if running
            if session.shell_pid and self.executor:
                # Would kill process
                pass
            
            del self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[SSHSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[SSHSession]:
        """List all active sessions"""
        return list(self.sessions.values())
    
    def cleanup_idle_sessions(self):
        """Clean up idle sessions"""
        current_time = time.time()
        idle_timeout = self.config['idle_timeout']
        
        sessions_to_close = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > idle_timeout:
                sessions_to_close.append(session_id)
        
        for session_id in sessions_to_close:
            self.close_session(session_id)
    
    def start(self):
        """Start SSH server"""
        self.running = True
        print(f"SSH server listening on port {self.port}")
        
        # Would start actual server socket
    
    def stop(self):
        """Stop SSH server"""
        self.running = False
        
        # Close all sessions
        for session_id in list(self.sessions.keys()):
            self.close_session(session_id)
        
        print("SSH server stopped")

class SFTPServer:
    """SFTP server implementation"""
    
    def __init__(self, ssh_server: SSHServer, vfs=None):
        self.ssh_server = ssh_server
        self.vfs = vfs
        self.transfers: Dict[str, 'FileTransfer'] = {}
    
    def handle_command(self, session_id: str, command: str, args: List[str]) -> str:
        """Handle SFTP command"""
        session = self.ssh_server.get_session(session_id)
        if not session:
            return "ERR: Invalid session"
        
        if command == "ls":
            return self._handle_ls(session, args)
        elif command == "get":
            return self._handle_get(session, args)
        elif command == "put":
            return self._handle_put(session, args)
        elif command == "rm":
            return self._handle_rm(session, args)
        elif command == "mkdir":
            return self._handle_mkdir(session, args)
        elif command == "cd":
            return self._handle_cd(session, args)
        elif command == "pwd":
            return self._handle_pwd(session)
        else:
            return f"ERR: Unknown command: {command}"
    
    def _handle_ls(self, session: SSHSession, args: List[str]) -> str:
        """Handle ls command"""
        if not self.vfs:
            return "ERR: VFS not available"
        
        path = args[0] if args else session.env.get('PWD', '/')
        
        try:
            items = self.vfs.listdir(path)
            return '\n'.join(items)
        except:
            return f"ERR: Cannot list {path}"
    
    def _handle_get(self, session: SSHSession, args: List[str]) -> str:
        """Handle get (download) command"""
        if not args:
            return "ERR: Missing filename"
        
        if not self.vfs:
            return "ERR: VFS not available"
        
        filename = args[0]
        
        try:
            with self.vfs.open(filename, 'rb') as f:
                data = f.read()
            
            # Create transfer
            transfer_id = secrets.token_hex(8)
            self.transfers[transfer_id] = FileTransfer(
                id=transfer_id,
                filename=filename,
                data=data,
                direction='download'
            )
            
            return f"OK: Transfer {transfer_id} ready ({len(data)} bytes)"
        except:
            return f"ERR: Cannot read {filename}"
    
    def _handle_put(self, session: SSHSession, args: List[str]) -> str:
        """Handle put (upload) command"""
        if len(args) < 2:
            return "ERR: Missing filename or data"
        
        if not self.vfs:
            return "ERR: VFS not available"
        
        filename = args[0]
        # In real implementation, would receive file data
        
        return f"OK: Ready to receive {filename}"
    
    def _handle_rm(self, session: SSHSession, args: List[str]) -> str:
        """Handle rm command"""
        if not args:
            return "ERR: Missing filename"
        
        if not self.vfs:
            return "ERR: VFS not available"
        
        filename = args[0]
        
        try:
            self.vfs.remove(filename)
            return f"OK: Removed {filename}"
        except:
            return f"ERR: Cannot remove {filename}"
    
    def _handle_mkdir(self, session: SSHSession, args: List[str]) -> str:
        """Handle mkdir command"""
        if not args:
            return "ERR: Missing directory name"
        
        if not self.vfs:
            return "ERR: VFS not available"
        
        dirname = args[0]
        
        try:
            self.vfs.mkdir(dirname)
            return f"OK: Created {dirname}"
        except:
            return f"ERR: Cannot create {dirname}"
    
    def _handle_cd(self, session: SSHSession, args: List[str]) -> str:
        """Handle cd command"""
        path = args[0] if args else session.env.get('HOME', '/')
        
        if self.vfs and self.vfs.exists(path) and self.vfs.isdir(path):
            session.env['PWD'] = path
            return f"OK: Changed to {path}"
        else:
            return f"ERR: Cannot change to {path}"
    
    def _handle_pwd(self, session: SSHSession) -> str:
        """Handle pwd command"""
        return session.env.get('PWD', '/')

@dataclass
class FileTransfer:
    """SFTP file transfer"""
    id: str
    filename: str
    data: bytes
    direction: str  # upload or download
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class SSHKeyManager:
    """SSH key management"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.keys_dir = "/etc/ssh"
    
    def generate_key_pair(self, key_type: str = "ed25519") -> SSHKey:
        """Generate SSH key pair"""
        # Simulated key generation
        private_key = secrets.token_hex(64)
        public_key = secrets.token_hex(32)
        
        return SSHKey(
            key_type=key_type,
            public_key=public_key,
            private_key=private_key
        )
    
    def save_key(self, key: SSHKey, name: str):
        """Save SSH key to VFS"""
        if not self.vfs:
            return
        
        # Ensure directory exists
        if not self.vfs.exists(self.keys_dir):
            try:
                self.vfs.mkdir(self.keys_dir)
            except:
                pass
        
        # Save private key
        if key.private_key:
            private_file = f"{self.keys_dir}/{name}"
            try:
                with self.vfs.open(private_file, 'w') as f:
                    f.write(key.private_key.encode())
            except:
                pass
        
        # Save public key
        public_file = f"{self.keys_dir}/{name}.pub"
        try:
            with self.vfs.open(public_file, 'w') as f:
                f.write(f"{key.key_type} {key.public_key}".encode())
        except:
            pass
    
    def load_key(self, name: str) -> Optional[SSHKey]:
        """Load SSH key from VFS"""
        if not self.vfs:
            return None
        
        public_file = f"{self.keys_dir}/{name}.pub"
        private_file = f"{self.keys_dir}/{name}"
        
        if not self.vfs.exists(public_file):
            return None
        
        try:
            # Load public key
            with self.vfs.open(public_file, 'r') as f:
                public_content = f.read().decode()
            
            parts = public_content.split()
            if len(parts) >= 2:
                key_type = parts[0]
                public_key = parts[1]
                
                # Load private key if exists
                private_key = None
                if self.vfs.exists(private_file):
                    with self.vfs.open(private_file, 'r') as f:
                        private_key = f.read().decode()
                
                return SSHKey(
                    key_type=key_type,
                    public_key=public_key,
                    private_key=private_key
                )
        except:
            pass
        
        return None