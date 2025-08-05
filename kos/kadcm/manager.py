"""
KADCM Manager - Core manager for host-KOS communication
"""

import os
import sys
import json
import yaml
import time
import threading
import logging
import struct
import hashlib
import secrets
from typing import Dict, Optional, Callable, Any, Tuple
from pathlib import Path

from .tunnel import TLSTunnel
from .protocol import KADCMProtocol
from .messages import MessageType, MessageFlags, Message
from .session import SessionManager
from ..security.fingerprint import FingerprintManager
from ..core.permissions import PermissionChecker

logger = logging.getLogger('kadcm')


class KADCMManager:
    """Main KADCM manager handling all host-KOS communications"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.tunnel: Optional[TLSTunnel] = None
        self.protocol = KADCMProtocol()
        self.session_manager = SessionManager()
        self.fingerprint_manager = FingerprintManager()
        self.permission_checker = PermissionChecker(kernel)
        
        # Configuration
        self.config = self._load_config()
        self.pipe_path = self._get_pipe_path()
        
        # State
        self.running = False
        self.handlers: Dict[MessageType, Callable] = {}
        self._setup_handlers()
        
        # Threading
        self.receive_thread = None
        self.heartbeat_thread = None
        
    def _load_config(self) -> dict:
        """Load KADCM configuration"""
        config_path = Path("/etc/kos/kadcm.conf")
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        
        # Default configuration
        return {
            "heartbeat_interval": 30,
            "session_timeout": 300,
            "max_message_size": 10 * 1024 * 1024,  # 10MB
            "tls_cert_path": "/etc/kos/certs/kadcm.crt",
            "tls_key_path": "/etc/kos/certs/kadcm.key",
            "ca_cert_path": "/etc/kos/certs/ca.crt",
            "allowed_hosts": []
        }
    
    def _get_pipe_path(self) -> str:
        """Get platform-specific pipe path"""
        if sys.platform == "win32":
            return r"\\.\pipe\kos\runtime\kadcm\kadcm"
        else:
            return "/var/run/kos/runtime/kadcm/kadcm.pipe"
    
    def _setup_handlers(self):
        """Setup message handlers"""
        self.handlers[MessageType.AUTH] = self._handle_auth
        self.handlers[MessageType.COMMAND] = self._handle_command
        self.handlers[MessageType.DATA] = self._handle_data
        self.handlers[MessageType.CONTROL] = self._handle_control
        self.handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        
    def start(self):
        """Start KADCM manager"""
        logger.info("Starting KADCM manager")
        
        # Create pipe directory if needed
        pipe_dir = os.path.dirname(self.pipe_path)
        os.makedirs(pipe_dir, mode=0o700, exist_ok=True)
        
        # Initialize TLS tunnel
        self.tunnel = TLSTunnel(
            self.pipe_path,
            self.config["tls_cert_path"],
            self.config["tls_key_path"],
            self.config["ca_cert_path"]
        )
        
        # Start tunnel
        self.tunnel.start()
        
        # Start threads
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        logger.info(f"KADCM listening on {self.pipe_path}")
        
    def stop(self):
        """Stop KADCM manager"""
        logger.info("Stopping KADCM manager")
        self.running = False
        
        if self.tunnel:
            self.tunnel.stop()
            
        if self.receive_thread:
            self.receive_thread.join(timeout=5)
            
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
    
    def _receive_loop(self):
        """Main receive loop for incoming messages"""
        while self.running:
            try:
                # Wait for connection
                connection = self.tunnel.accept_connection()
                if not connection:
                    continue
                    
                # Handle connection in separate thread
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(connection,),
                    daemon=True
                )
                thread.start()
                
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                time.sleep(1)
    
    def _handle_connection(self, connection):
        """Handle individual connection"""
        session_id = None
        try:
            # Send challenge for authentication
            challenge = self._send_challenge(connection)
            
            # Wait for AUTH response
            auth_msg = self._receive_message(connection)
            if not auth_msg or auth_msg.type != MessageType.AUTH:
                logger.warning("Invalid auth response")
                return
            
            # Verify authentication
            session_id = self._verify_auth(auth_msg, challenge)
            if not session_id:
                self._send_error(connection, "Authentication failed")
                return
            
            # Connection authenticated - handle messages
            while self.running and connection.is_active():
                msg = self._receive_message(connection)
                if not msg:
                    break
                    
                # Update session activity
                self.session_manager.update_activity(session_id)
                
                # Handle message
                self._handle_message(connection, msg, session_id)
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            
        finally:
            if session_id:
                self.session_manager.end_session(session_id)
            connection.close()
    
    def _send_challenge(self, connection) -> bytes:
        """Send authentication challenge"""
        challenge = secrets.token_bytes(32)
        
        msg = Message(
            type=MessageType.CONTROL,
            id=self._generate_msg_id(),
            priority=0,
            flags=0,
            header={"type": "challenge"},
            body=challenge.hex()
        )
        
        self._send_message(connection, msg)
        return challenge
    
    def _verify_auth(self, auth_msg: Message, challenge: bytes) -> Optional[str]:
        """Verify authentication message"""
        try:
            auth_data = yaml.safe_load(auth_msg.body)
            fingerprint = auth_data.get("fingerprint")
            signature = auth_data.get("signature")
            entity_type = auth_data.get("entity_type", "host")
            
            if not fingerprint or not signature:
                return None
            
            # Verify fingerprint
            if not self.fingerprint_manager.verify(fingerprint, entity_type):
                logger.warning(f"Invalid fingerprint for {entity_type}")
                return None
            
            # Verify challenge signature
            expected_sig = hashlib.sha256(challenge + fingerprint.encode()).hexdigest()
            if signature != expected_sig:
                logger.warning("Invalid challenge signature")
                return None
            
            # Check if host is allowed
            entity_id = auth_data.get("entity_id")
            if entity_id not in self.config.get("allowed_hosts", []) and \
               "*" not in self.config.get("allowed_hosts", []):
                logger.warning(f"Host {entity_id} not in allowed list")
                return None
            
            # Create session
            session_id = self.session_manager.create_session(
                entity_id=entity_id,
                entity_type=entity_type,
                fingerprint=fingerprint,
                permissions=self._get_entity_permissions(entity_id, entity_type)
            )
            
            logger.info(f"Authenticated {entity_type} {entity_id} with session {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Auth verification error: {e}")
            return None
    
    def _get_entity_permissions(self, entity_id: str, entity_type: str) -> dict:
        """Get permissions for authenticated entity"""
        # Load from RBAC/permission system
        try:
            from ..core.orchestration import rbac
            from ..security.permissions import PermissionManager
            
            perm_mgr = PermissionManager()
            
            # Check if entity has a role binding
            role_bindings = rbac.list_role_bindings()
            entity_roles = []
            
            for binding in role_bindings:
                for subject in binding.subjects:
                    if subject.get('name') == entity_id and subject.get('kind').lower() == entity_type:
                        entity_roles.append(binding.role_ref['name'])
            
            # Aggregate permissions from all roles
            permissions = {
                "execute_commands": False,
                "read_files": False,
                "write_files": False,
                "manage_processes": False,
                "admin_level": False
            }
            
            # Check each role's permissions
            for role_name in entity_roles:
                role = rbac.get_role(role_name)
                if role:
                    for rule in role.rules:
                        # Map RBAC rules to KADCM permissions
                        if 'kadcm:execute' in rule.get('resources', []):
                            permissions["execute_commands"] = True
                        if 'kadcm:read' in rule.get('resources', []):
                            permissions["read_files"] = True
                        if 'kadcm:write' in rule.get('resources', []):
                            permissions["write_files"] = True
                        if 'kadcm:manage' in rule.get('resources', []):
                            permissions["manage_processes"] = True
                        if '*' in rule.get('resources', []) or 'kadcm:admin' in rule.get('resources', []):
                            permissions["admin_level"] = True
                            # Admin gets all permissions
                            permissions.update({
                                "execute_commands": True,
                                "read_files": True,
                                "write_files": True,
                                "manage_processes": True
                            })
            
            # Default permissions based on entity type if no roles found
            if not entity_roles:
                if entity_type == "host":
                    return {
                        "execute_commands": True,
                        "read_files": True,
                        "write_files": True,
                        "manage_processes": True,
                        "admin_level": False
                    }
                elif entity_type == "user":
                    # Check user's system permissions
                    user_perms = perm_mgr.get_user_permissions(entity_id)
                    return {
                        "execute_commands": 'execute' in user_perms,
                        "read_files": 'read' in user_perms,
                        "write_files": 'write' in user_perms,
                        "manage_processes": 'process' in user_perms,
                        "admin_level": 'admin' in user_perms
                    }
            
            return permissions
            
        except Exception as e:
            logger.warning(f"Failed to load RBAC permissions: {e}")
            # Return default permissions based on entity type
            if entity_type == "host":
                return {
                    "execute_commands": True,
                    "read_files": True,
                    "write_files": True,
                    "manage_processes": True,
                    "admin_level": False
                }
            return {}
    
    def _handle_message(self, connection, msg: Message, session_id: str):
        """Handle received message"""
        handler = self.handlers.get(msg.type)
        if not handler:
            logger.warning(f"No handler for message type {msg.type}")
            self._send_error(connection, f"Unknown message type: {msg.type}")
            return
        
        try:
            handler(connection, msg, session_id)
        except Exception as e:
            logger.error(f"Handler error: {e}")
            self._send_error(connection, str(e))
    
    def _handle_auth(self, connection, msg: Message, session_id: str):
        """Handle AUTH message (re-authentication)"""
        # Session already authenticated
        response = Message(
            type=MessageType.AUTH,
            id=msg.id,
            priority=0,
            flags=0,
            header={"status": "already_authenticated"},
            body=""
        )
        self._send_message(connection, response)
    
    def _handle_command(self, connection, msg: Message, session_id: str):
        """Handle COMMAND message"""
        session = self.session_manager.get_session(session_id)
        if not session:
            self._send_error(connection, "Invalid session")
            return
        
        # Check permissions
        if not session.permissions.get("execute_commands"):
            self._send_error(connection, "Permission denied: execute_commands")
            return
        
        try:
            # Parse command
            cmd_data = yaml.safe_load(msg.body)
            command = cmd_data.get("command")
            args = cmd_data.get("args", [])
            env = cmd_data.get("env", {})
            cwd = cmd_data.get("cwd")
            
            logger.info(f"Executing command: {command} {args}")
            
            # Security check command
            if not self._is_command_allowed(command, session):
                self._send_error(connection, f"Command not allowed: {command}")
                return
            
            # Execute command
            result = self.kernel.execute_command(
                command=command,
                args=args,
                env=env,
                cwd=cwd,
                user=session.entity_id
            )
            
            # Send response
            response = Message(
                type=MessageType.COMMAND,
                id=msg.id,
                priority=msg.priority,
                flags=0,
                header={
                    "status": "success" if result.returncode == 0 else "error",
                    "returncode": result.returncode
                },
                body=yaml.dump({
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                })
            )
            self._send_message(connection, response)
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            self._send_error(connection, str(e))
    
    def _handle_data(self, connection, msg: Message, session_id: str):
        """Handle DATA message (file transfers)"""
        session = self.session_manager.get_session(session_id)
        if not session:
            self._send_error(connection, "Invalid session")
            return
        
        try:
            data_info = yaml.safe_load(msg.body)
            operation = data_info.get("operation")
            
            if operation == "read":
                self._handle_file_read(connection, msg, session, data_info)
            elif operation == "write":
                self._handle_file_write(connection, msg, session, data_info)
            else:
                self._send_error(connection, f"Unknown data operation: {operation}")
                
        except Exception as e:
            logger.error(f"Data handling error: {e}")
            self._send_error(connection, str(e))
    
    def _handle_control(self, connection, msg: Message, session_id: str):
        """Handle CONTROL message"""
        try:
            control_data = yaml.safe_load(msg.body) if msg.body else {}
            control_type = msg.header.get("type")
            
            if control_type == "session_info":
                session = self.session_manager.get_session(session_id)
                response = Message(
                    type=MessageType.CONTROL,
                    id=msg.id,
                    priority=0,
                    flags=0,
                    header={"type": "session_info"},
                    body=yaml.dump({
                        "session_id": session_id,
                        "entity_id": session.entity_id,
                        "created": session.created_at,
                        "expires": session.expires_at,
                        "permissions": session.permissions
                    })
                )
                self._send_message(connection, response)
                
            elif control_type == "close":
                logger.info(f"Session {session_id} requested close")
                connection.close()
                
            else:
                self._send_error(connection, f"Unknown control type: {control_type}")
                
        except Exception as e:
            logger.error(f"Control handling error: {e}")
            self._send_error(connection, str(e))
    
    def _handle_heartbeat(self, connection, msg: Message, session_id: str):
        """Handle HEARTBEAT message"""
        # Echo back heartbeat
        response = Message(
            type=MessageType.HEARTBEAT,
            id=msg.id,
            priority=0,
            flags=0,
            header={"timestamp": time.time()},
            body=""
        )
        self._send_message(connection, response)
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        interval = self.config["heartbeat_interval"]
        
        while self.running:
            try:
                # Send heartbeat to all active connections
                for session_id in self.session_manager.get_active_sessions():
                    # TODO: Send heartbeat through connection
                    pass
                    
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                
            time.sleep(interval)
    
    def _send_message(self, connection, msg: Message):
        """Send message through connection"""
        data = self.protocol.encode_message(msg)
        connection.send(data)
    
    def _receive_message(self, connection) -> Optional[Message]:
        """Receive message from connection"""
        try:
            # Read header first (5 bytes: 4 length + 1 flags)
            header_data = connection.receive(5)
            if not header_data or len(header_data) < 5:
                return None
            
            length, flags = struct.unpack(">IB", header_data)
            
            # Check message size
            if length > self.config["max_message_size"]:
                logger.error(f"Message too large: {length}")
                return None
            
            # Read rest of message
            msg_data = connection.receive(length)
            if not msg_data or len(msg_data) < length:
                return None
            
            # Decode message
            return self.protocol.decode_message(header_data + msg_data)
            
        except Exception as e:
            logger.error(f"Message receive error: {e}")
            return None
    
    def _send_error(self, connection, error: str):
        """Send error message"""
        msg = Message(
            type=MessageType.ERROR,
            id=self._generate_msg_id(),
            priority=0,
            flags=0,
            header={"error": True},
            body=error
        )
        self._send_message(connection, msg)
    
    def _generate_msg_id(self) -> str:
        """Generate unique message ID"""
        return f"{int(time.time() * 1000)}-{secrets.token_hex(4)}"
    
    def _is_command_allowed(self, command: str, session) -> bool:
        """Check if command is allowed for session"""
        # Security checks
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero",
            "mkfs",
            "fork bomb"
        ]
        
        for dangerous in dangerous_commands:
            if dangerous in command:
                return False
        
        # Check session permissions
        if session.permissions.get("admin_level"):
            return True
            
        # Additional checks based on command type
        if command.startswith(("/bin/", "/usr/bin/")):
            return True
            
        return False
    
    def _handle_file_read(self, connection, msg: Message, session, data_info: dict):
        """Handle file read operation"""
        if not session.permissions.get("read_files"):
            self._send_error(connection, "Permission denied: read_files")
            return
        
        file_path = data_info.get("path")
        if not file_path:
            self._send_error(connection, "No path specified")
            return
        
        # Security check path
        if not self._is_path_allowed(file_path, session, "read"):
            self._send_error(connection, f"Path not allowed: {file_path}")
            return
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            response = Message(
                type=MessageType.DATA,
                id=msg.id,
                priority=msg.priority,
                flags=MessageFlags.COMPRESSED if len(content) > 1024 else 0,
                header={
                    "operation": "read",
                    "path": file_path,
                    "size": len(content)
                },
                body=content.decode('utf-8', errors='replace')
            )
            self._send_message(connection, response)
            
        except Exception as e:
            self._send_error(connection, f"Read error: {e}")
    
    def _handle_file_write(self, connection, msg: Message, session, data_info: dict):
        """Handle file write operation"""
        if not session.permissions.get("write_files"):
            self._send_error(connection, "Permission denied: write_files")
            return
        
        file_path = data_info.get("path")
        content = data_info.get("content", "")
        
        if not file_path:
            self._send_error(connection, "No path specified")
            return
        
        # Security check path
        if not self._is_path_allowed(file_path, session, "write"):
            self._send_error(connection, f"Path not allowed: {file_path}")
            return
        
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w') as f:
                f.write(content)
                
            response = Message(
                type=MessageType.DATA,
                id=msg.id,
                priority=msg.priority,
                flags=0,
                header={
                    "operation": "write",
                    "path": file_path,
                    "status": "success"
                },
                body=""
            )
            self._send_message(connection, response)
            
        except Exception as e:
            self._send_error(connection, f"Write error: {e}")
    
    def _is_path_allowed(self, path: str, session, operation: str) -> bool:
        """Check if path access is allowed"""
        # Normalize path
        path = os.path.abspath(path)
        
        # Default allowed paths
        allowed_read = ["/home", "/tmp", "/var/log"]
        allowed_write = ["/tmp/host", "/home/" + session.entity_id]
        
        if operation == "read":
            return any(path.startswith(allowed) for allowed in allowed_read)
        elif operation == "write":
            return any(path.startswith(allowed) for allowed in allowed_write)
            
        return False