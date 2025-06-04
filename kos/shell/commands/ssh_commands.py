"""
SSH and SCP Commands for KOS
============================

Comprehensive SSH (Secure Shell) and SCP (Secure Copy Protocol) implementation
Features:
- SSH client with key authentication
- SCP file transfer capabilities
- SSH key generation and management
- SSH configuration management
- Connection multiplexing and reuse
- Advanced security features
"""

import os
import sys
import json
import time
import socket
import threading
import subprocess
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import tempfile
import stat

logger = logging.getLogger('KOS.ssh_commands')

@dataclass
class SSHConnection:
    """SSH connection information"""
    host: str
    port: int = 22
    user: str = ""
    key_file: str = ""
    password: str = ""
    config_name: str = ""
    last_used: datetime = None
    connection_count: int = 0
    is_active: bool = False

@dataclass
class SSHKey:
    """SSH key information"""
    name: str
    key_type: str  # rsa, ed25519, ecdsa
    public_key_path: str
    private_key_path: str
    fingerprint: str
    comment: str
    created_at: datetime
    last_used: Optional[datetime] = None

class SSHKeyManager:
    """Manages SSH keys"""
    
    def __init__(self, ssh_dir: str = None):
        self.ssh_dir = ssh_dir or os.path.expanduser("~/.kos/ssh")
        os.makedirs(self.ssh_dir, exist_ok=True)
        
        self.keys_file = os.path.join(self.ssh_dir, "keys.json")
        self.keys: Dict[str, SSHKey] = {}
        self._load_keys()
    
    def generate_key(self, name: str, key_type: str = "ed25519", comment: str = "", bits: int = None) -> bool:
        """Generate a new SSH key pair"""
        try:
            # Set default bits for RSA
            if key_type == "rsa" and bits is None:
                bits = 4096
            
            private_key_path = os.path.join(self.ssh_dir, f"{name}")
            public_key_path = f"{private_key_path}.pub"
            
            # Generate key using ssh-keygen
            cmd = ["ssh-keygen", "-t", key_type, "-f", private_key_path, "-N", ""]
            
            if bits and key_type == "rsa":
                cmd.extend(["-b", str(bits)])
            
            if comment:
                cmd.extend(["-C", comment])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to generate SSH key: {result.stderr}")
                return False
            
            # Get fingerprint
            fingerprint = self._get_key_fingerprint(public_key_path)
            
            # Create key object
            key = SSHKey(
                name=name,
                key_type=key_type,
                public_key_path=public_key_path,
                private_key_path=private_key_path,
                fingerprint=fingerprint,
                comment=comment or f"{name}@kos",
                created_at=datetime.now()
            )
            
            # Set proper permissions
            os.chmod(private_key_path, 0o600)
            os.chmod(public_key_path, 0o644)
            
            # Add to keys
            self.keys[name] = key
            self._save_keys()
            
            logger.info(f"Generated SSH key: {name} ({key_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error generating SSH key: {e}")
            return False
    
    def list_keys(self) -> List[SSHKey]:
        """List all SSH keys"""
        return list(self.keys.values())
    
    def get_key(self, name: str) -> Optional[SSHKey]:
        """Get SSH key by name"""
        return self.keys.get(name)
    
    def delete_key(self, name: str) -> bool:
        """Delete SSH key"""
        try:
            if name not in self.keys:
                return False
            
            key = self.keys[name]
            
            # Remove key files
            if os.path.exists(key.private_key_path):
                os.remove(key.private_key_path)
            if os.path.exists(key.public_key_path):
                os.remove(key.public_key_path)
            
            # Remove from keys
            del self.keys[name]
            self._save_keys()
            
            logger.info(f"Deleted SSH key: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting SSH key: {e}")
            return False
    
    def import_key(self, name: str, private_key_path: str, public_key_path: str = None) -> bool:
        """Import existing SSH key"""
        try:
            if not os.path.exists(private_key_path):
                logger.error(f"Private key file not found: {private_key_path}")
                return False
            
            # Determine public key path
            if public_key_path is None:
                public_key_path = f"{private_key_path}.pub"
            
            if not os.path.exists(public_key_path):
                logger.error(f"Public key file not found: {public_key_path}")
                return False
            
            # Copy keys to SSH directory
            import shutil
            dest_private = os.path.join(self.ssh_dir, name)
            dest_public = f"{dest_private}.pub"
            
            shutil.copy2(private_key_path, dest_private)
            shutil.copy2(public_key_path, dest_public)
            
            # Set proper permissions
            os.chmod(dest_private, 0o600)
            os.chmod(dest_public, 0o644)
            
            # Determine key type and get fingerprint
            key_type = self._determine_key_type(dest_private)
            fingerprint = self._get_key_fingerprint(dest_public)
            
            # Create key object
            key = SSHKey(
                name=name,
                key_type=key_type,
                public_key_path=dest_public,
                private_key_path=dest_private,
                fingerprint=fingerprint,
                comment=f"imported_{name}@kos",
                created_at=datetime.now()
            )
            
            # Add to keys
            self.keys[name] = key
            self._save_keys()
            
            logger.info(f"Imported SSH key: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing SSH key: {e}")
            return False
    
    def _get_key_fingerprint(self, public_key_path: str) -> str:
        """Get SSH key fingerprint"""
        try:
            result = subprocess.run(
                ["ssh-keygen", "-lf", public_key_path],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                # Extract fingerprint from output
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]  # SHA256 fingerprint
            return "unknown"
        except:
            return "unknown"
    
    def _determine_key_type(self, private_key_path: str) -> str:
        """Determine SSH key type from private key file"""
        try:
            with open(private_key_path, 'r') as f:
                first_line = f.readline().strip()
                if "RSA" in first_line:
                    return "rsa"
                elif "ED25519" in first_line:
                    return "ed25519"
                elif "ECDSA" in first_line:
                    return "ecdsa"
                elif "DSA" in first_line:
                    return "dsa"
            return "unknown"
        except:
            return "unknown"
    
    def _load_keys(self):
        """Load SSH keys from file"""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, 'r') as f:
                    data = json.load(f)
                
                for key_data in data:
                    key = SSHKey(
                        name=key_data['name'],
                        key_type=key_data['key_type'],
                        public_key_path=key_data['public_key_path'],
                        private_key_path=key_data['private_key_path'],
                        fingerprint=key_data['fingerprint'],
                        comment=key_data['comment'],
                        created_at=datetime.fromisoformat(key_data['created_at']),
                        last_used=datetime.fromisoformat(key_data['last_used']) if key_data.get('last_used') else None
                    )
                    self.keys[key.name] = key
                    
            except Exception as e:
                logger.error(f"Error loading SSH keys: {e}")
    
    def _save_keys(self):
        """Save SSH keys to file"""
        try:
            data = []
            for key in self.keys.values():
                data.append({
                    'name': key.name,
                    'key_type': key.key_type,
                    'public_key_path': key.public_key_path,
                    'private_key_path': key.private_key_path,
                    'fingerprint': key.fingerprint,
                    'comment': key.comment,
                    'created_at': key.created_at.isoformat(),
                    'last_used': key.last_used.isoformat() if key.last_used else None
                })
            
            with open(self.keys_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving SSH keys: {e}")

class SSHConfigManager:
    """Manages SSH configurations"""
    
    def __init__(self, ssh_dir: str = None):
        self.ssh_dir = ssh_dir or os.path.expanduser("~/.kos/ssh")
        self.config_file = os.path.join(self.ssh_dir, "config")
        self.hosts: Dict[str, Dict[str, str]] = {}
        self._load_config()
    
    def add_host(self, name: str, hostname: str, port: int = 22, user: str = None, 
                 identity_file: str = None, **kwargs) -> bool:
        """Add SSH host configuration"""
        try:
            config = {
                'HostName': hostname,
                'Port': str(port)
            }
            
            if user:
                config['User'] = user
            if identity_file:
                config['IdentityFile'] = identity_file
            
            # Add additional options
            for key, value in kwargs.items():
                config[key] = str(value)
            
            self.hosts[name] = config
            self._save_config()
            
            logger.info(f"Added SSH host configuration: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding SSH host: {e}")
            return False
    
    def get_host(self, name: str) -> Optional[Dict[str, str]]:
        """Get SSH host configuration"""
        return self.hosts.get(name)
    
    def list_hosts(self) -> List[str]:
        """List all configured SSH hosts"""
        return list(self.hosts.keys())
    
    def remove_host(self, name: str) -> bool:
        """Remove SSH host configuration"""
        if name in self.hosts:
            del self.hosts[name]
            self._save_config()
            logger.info(f"Removed SSH host configuration: {name}")
            return True
        return False
    
    def _load_config(self):
        """Load SSH configuration from file"""
        if os.path.exists(self.config_file):
            try:
                current_host = None
                
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.startswith('Host '):
                            current_host = line[5:].strip()
                            if current_host not in self.hosts:
                                self.hosts[current_host] = {}
                        elif current_host and ' ' in line:
                            key, value = line.split(' ', 1)
                            self.hosts[current_host][key] = value.strip()
                            
            except Exception as e:
                logger.error(f"Error loading SSH config: {e}")
    
    def _save_config(self):
        """Save SSH configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                f.write("# KOS SSH Configuration\n")
                f.write("# Generated automatically - edit with caution\n\n")
                
                for host_name, config in self.hosts.items():
                    f.write(f"Host {host_name}\n")
                    for key, value in config.items():
                        f.write(f"    {key} {value}\n")
                    f.write("\n")
                    
        except Exception as e:
            logger.error(f"Error saving SSH config: {e}")

class SSHClient:
    """SSH client implementation"""
    
    def __init__(self, key_manager: SSHKeyManager, config_manager: SSHConfigManager):
        self.key_manager = key_manager
        self.config_manager = config_manager
        self.active_connections: Dict[str, SSHConnection] = {}
    
    def connect(self, target: str, port: int = 22, user: str = None, 
                key_name: str = None, password: str = None, **options) -> bool:
        """Connect to SSH host"""
        try:
            # Parse target (user@host or just host)
            if '@' in target:
                user_part, host = target.split('@', 1)
                if user is None:
                    user = user_part
            else:
                host = target
            
            # Check if host is in configuration
            host_config = self.config_manager.get_host(host)
            if host_config:
                hostname = host_config.get('HostName', host)
                port = int(host_config.get('Port', port))
                user = user or host_config.get('User')
                key_file = host_config.get('IdentityFile')
                
                # Use specified key if available
                if key_name:
                    key = self.key_manager.get_key(key_name)
                    if key:
                        key_file = key.private_key_path
            else:
                hostname = host
                key_file = None
                
                # Use specified key
                if key_name:
                    key = self.key_manager.get_key(key_name)
                    if key:
                        key_file = key.private_key_path
            
            # Build SSH command
            ssh_cmd = ["ssh"]
            
            if port != 22:
                ssh_cmd.extend(["-p", str(port)])
            
            if key_file and os.path.exists(key_file):
                ssh_cmd.extend(["-i", key_file])
            
            # Add additional options
            for option, value in options.items():
                if value is True:
                    ssh_cmd.extend(["-o", f"{option}=yes"])
                elif value is False:
                    ssh_cmd.extend(["-o", f"{option}=no"])
                else:
                    ssh_cmd.extend(["-o", f"{option}={value}"])
            
            # Add target
            if user:
                ssh_cmd.append(f"{user}@{hostname}")
            else:
                ssh_cmd.append(hostname)
            
            logger.info(f"Connecting to SSH: {' '.join(ssh_cmd)}")
            
            # Execute SSH command
            result = subprocess.run(ssh_cmd)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error connecting to SSH: {e}")
            return False
    
    def execute_command(self, target: str, command: str, port: int = 22, 
                       user: str = None, key_name: str = None) -> Tuple[bool, str, str]:
        """Execute command on remote host"""
        try:
            # Parse target
            if '@' in target:
                user_part, host = target.split('@', 1)
                if user is None:
                    user = user_part
            else:
                host = target
            
            # Get SSH parameters
            host_config = self.config_manager.get_host(host)
            if host_config:
                hostname = host_config.get('HostName', host)
                port = int(host_config.get('Port', port))
                user = user or host_config.get('User')
                key_file = host_config.get('IdentityFile')
            else:
                hostname = host
                key_file = None
            
            # Use specified key
            if key_name:
                key = self.key_manager.get_key(key_name)
                if key:
                    key_file = key.private_key_path
            
            # Build SSH command
            ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no"]
            
            if port != 22:
                ssh_cmd.extend(["-p", str(port)])
            
            if key_file and os.path.exists(key_file):
                ssh_cmd.extend(["-i", key_file])
            
            # Add target and command
            if user:
                ssh_cmd.append(f"{user}@{hostname}")
            else:
                ssh_cmd.append(hostname)
            
            ssh_cmd.append(command)
            
            # Execute command
            result = subprocess.run(ssh_cmd, capture_output=True, text=True)
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            logger.error(f"Error executing SSH command: {e}")
            return False, "", str(e)

class SCPClient:
    """SCP (Secure Copy Protocol) client implementation"""
    
    def __init__(self, key_manager: SSHKeyManager, config_manager: SSHConfigManager):
        self.key_manager = key_manager
        self.config_manager = config_manager
    
    def copy_to_remote(self, local_path: str, remote_target: str, port: int = 22,
                       user: str = None, key_name: str = None, recursive: bool = False,
                       preserve: bool = False) -> bool:
        """Copy file/directory to remote host"""
        try:
            # Parse remote target (user@host:path)
            if ':' not in remote_target:
                logger.error("Remote target must be in format user@host:path")
                return False
            
            host_part, remote_path = remote_target.split(':', 1)
            
            if '@' in host_part:
                user_part, host = host_part.split('@', 1)
                if user is None:
                    user = user_part
            else:
                host = host_part
            
            return self._scp_transfer(local_path, remote_target, port, user, key_name, 
                                    recursive, preserve, to_remote=True)
            
        except Exception as e:
            logger.error(f"Error copying to remote: {e}")
            return False
    
    def copy_from_remote(self, remote_source: str, local_path: str, port: int = 22,
                        user: str = None, key_name: str = None, recursive: bool = False,
                        preserve: bool = False) -> bool:
        """Copy file/directory from remote host"""
        try:
            # Parse remote source (user@host:path)
            if ':' not in remote_source:
                logger.error("Remote source must be in format user@host:path")
                return False
            
            host_part, remote_path = remote_source.split(':', 1)
            
            if '@' in host_part:
                user_part, host = host_part.split('@', 1)
                if user is None:
                    user = user_part
            else:
                host = host_part
            
            return self._scp_transfer(remote_source, local_path, port, user, key_name,
                                    recursive, preserve, to_remote=False)
            
        except Exception as e:
            logger.error(f"Error copying from remote: {e}")
            return False
    
    def _scp_transfer(self, source: str, destination: str, port: int, user: str,
                     key_name: str, recursive: bool, preserve: bool, to_remote: bool) -> bool:
        """Internal SCP transfer implementation"""
        try:
            # Parse host from source or destination
            if to_remote:
                host_part = destination.split(':', 1)[0]
            else:
                host_part = source.split(':', 1)[0]
            
            if '@' in host_part:
                _, host = host_part.split('@', 1)
            else:
                host = host_part
            
            # Get SSH parameters
            host_config = self.config_manager.get_host(host)
            if host_config:
                hostname = host_config.get('HostName', host)
                port = int(host_config.get('Port', port))
                if user is None:
                    user = host_config.get('User')
                key_file = host_config.get('IdentityFile')
            else:
                hostname = host
                key_file = None
            
            # Use specified key
            if key_name:
                key = self.key_manager.get_key(key_name)
                if key:
                    key_file = key.private_key_path
            
            # Build SCP command
            scp_cmd = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no"]
            
            if port != 22:
                scp_cmd.extend(["-P", str(port)])
            
            if key_file and os.path.exists(key_file):
                scp_cmd.extend(["-i", key_file])
            
            if recursive:
                scp_cmd.append("-r")
            
            if preserve:
                scp_cmd.append("-p")
            
            # Add source and destination
            # Update target with corrected hostname and user
            if to_remote:
                final_destination = destination
                if '@' in destination:
                    user_part, path_part = destination.split(':', 1)
                    if user and user not in user_part:
                        final_destination = f"{user}@{hostname}:{path_part}"
                    else:
                        final_destination = f"{user_part.split('@')[0]}@{hostname}:{path_part}"
                else:
                    if user:
                        final_destination = f"{user}@{hostname}:{destination.split(':', 1)[1]}"
                
                scp_cmd.extend([source, final_destination])
            else:
                final_source = source
                if '@' in source:
                    user_part, path_part = source.split(':', 1)
                    if user and user not in user_part:
                        final_source = f"{user}@{hostname}:{path_part}"
                    else:
                        final_source = f"{user_part.split('@')[0]}@{hostname}:{path_part}"
                else:
                    if user:
                        final_source = f"{user}@{hostname}:{source.split(':', 1)[1]}"
                
                scp_cmd.extend([final_source, destination])
            
            logger.info(f"Executing SCP: {' '.join(scp_cmd)}")
            
            # Execute SCP command
            result = subprocess.run(scp_cmd)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error in SCP transfer: {e}")
            return False

class SSHCommand:
    """SSH command handler for KOS shell"""
    
    def __init__(self, shell):
        self.shell = shell
        self.key_manager = SSHKeyManager()
        self.config_manager = SSHConfigManager()
        self.ssh_client = SSHClient(self.key_manager, self.config_manager)
        self.scp_client = SCPClient(self.key_manager, self.config_manager)
    
    def execute(self, args: List[str]) -> bool:
        """Execute SSH command"""
        if not args:
            self._show_help()
            return True
        
        subcommand = args[0]
        
        if subcommand == "connect" or subcommand == "login":
            return self._ssh_connect(args[1:])
        elif subcommand == "exec":
            return self._ssh_exec(args[1:])
        elif subcommand == "keygen":
            return self._ssh_keygen(args[1:])
        elif subcommand == "keys":
            return self._ssh_keys(args[1:])
        elif subcommand == "config":
            return self._ssh_config(args[1:])
        elif subcommand == "hosts":
            return self._ssh_hosts(args[1:])
        else:
            # Direct connection
            return self._ssh_connect(args)
    
    def _ssh_connect(self, args: List[str]) -> bool:
        """SSH connect/login command"""
        if not args:
            print("Usage: ssh connect <target> [options]")
            return False
        
        target = args[0]
        options = {}
        port = 22
        user = None
        key_name = None
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i] == "-p" and i + 1 < len(args):
                port = int(args[i + 1])
                i += 2
            elif args[i] == "-l" and i + 1 < len(args):
                user = args[i + 1]
                i += 2
            elif args[i] == "-i" and i + 1 < len(args):
                key_name = args[i + 1]
                i += 2
            elif args[i] == "-o" and i + 1 < len(args):
                option_pair = args[i + 1]
                if '=' in option_pair:
                    key, value = option_pair.split('=', 1)
                    options[key] = value
                i += 2
            else:
                i += 1
        
        return self.ssh_client.connect(target, port, user, key_name, **options)
    
    def _ssh_exec(self, args: List[str]) -> bool:
        """SSH execute command"""
        if len(args) < 2:
            print("Usage: ssh exec <target> <command>")
            return False
        
        target = args[0]
        command = ' '.join(args[1:])
        
        success, stdout, stderr = self.ssh_client.execute_command(target, command)
        
        if stdout:
            print(stdout.rstrip())
        if stderr:
            print(stderr.rstrip(), file=sys.stderr)
        
        return success
    
    def _ssh_keygen(self, args: List[str]) -> bool:
        """SSH key generation command"""
        if not args:
            print("Usage: ssh keygen <name> [options]")
            return False
        
        name = args[0]
        key_type = "ed25519"
        comment = ""
        bits = None
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i] == "-t" and i + 1 < len(args):
                key_type = args[i + 1]
                i += 2
            elif args[i] == "-C" and i + 1 < len(args):
                comment = args[i + 1]
                i += 2
            elif args[i] == "-b" and i + 1 < len(args):
                bits = int(args[i + 1])
                i += 2
            else:
                i += 1
        
        success = self.key_manager.generate_key(name, key_type, comment, bits)
        
        if success:
            key = self.key_manager.get_key(name)
            print(f"Generated SSH key: {name}")
            print(f"Type: {key.key_type}")
            print(f"Fingerprint: {key.fingerprint}")
            print(f"Public key: {key.public_key_path}")
            print(f"Private key: {key.private_key_path}")
        else:
            print(f"Failed to generate SSH key: {name}")
        
        return success
    
    def _ssh_keys(self, args: List[str]) -> bool:
        """SSH keys management command"""
        if not args or args[0] == "list":
            # List keys
            keys = self.key_manager.list_keys()
            if not keys:
                print("No SSH keys found")
                return True
            
            print("SSH Keys:")
            print("-" * 80)
            for key in keys:
                status = f"Created: {key.created_at.strftime('%Y-%m-%d %H:%M')}"
                if key.last_used:
                    status += f", Last used: {key.last_used.strftime('%Y-%m-%d %H:%M')}"
                
                print(f"{key.name:<20} {key.key_type:<10} {key.fingerprint}")
                print(f"{'':20} {status}")
                print(f"{'':20} Public: {key.public_key_path}")
                print()
            
            return True
        
        elif args[0] == "delete" and len(args) > 1:
            name = args[1]
            success = self.key_manager.delete_key(name)
            if success:
                print(f"Deleted SSH key: {name}")
            else:
                print(f"Failed to delete SSH key: {name}")
            return success
        
        elif args[0] == "import" and len(args) > 2:
            name = args[1]
            private_key_path = args[2]
            public_key_path = args[3] if len(args) > 3 else None
            
            success = self.key_manager.import_key(name, private_key_path, public_key_path)
            if success:
                print(f"Imported SSH key: {name}")
            else:
                print(f"Failed to import SSH key: {name}")
            return success
        
        else:
            print("Usage: ssh keys [list|delete <name>|import <name> <private_key> [public_key]]")
            return False
    
    def _ssh_config(self, args: List[str]) -> bool:
        """SSH configuration command"""
        if not args or args[0] == "list":
            # List host configurations
            hosts = self.config_manager.list_hosts()
            if not hosts:
                print("No SSH host configurations found")
                return True
            
            print("SSH Host Configurations:")
            print("-" * 60)
            for host in hosts:
                config = self.config_manager.get_host(host)
                print(f"Host {host}")
                for key, value in config.items():
                    print(f"    {key} {value}")
                print()
            
            return True
        
        elif args[0] == "add" and len(args) >= 3:
            name = args[1]
            hostname = args[2]
            
            # Parse additional options
            port = 22
            user = None
            identity_file = None
            options = {}
            
            i = 3
            while i < len(args):
                if args[i] == "-p" and i + 1 < len(args):
                    port = int(args[i + 1])
                    i += 2
                elif args[i] == "-l" and i + 1 < len(args):
                    user = args[i + 1]
                    i += 2
                elif args[i] == "-i" and i + 1 < len(args):
                    identity_file = args[i + 1]
                    i += 2
                else:
                    i += 1
            
            success = self.config_manager.add_host(name, hostname, port, user, identity_file, **options)
            if success:
                print(f"Added SSH host configuration: {name}")
            else:
                print(f"Failed to add SSH host configuration: {name}")
            return success
        
        elif args[0] == "remove" and len(args) > 1:
            name = args[1]
            success = self.config_manager.remove_host(name)
            if success:
                print(f"Removed SSH host configuration: {name}")
            else:
                print(f"Failed to remove SSH host configuration: {name}")
            return success
        
        else:
            print("Usage: ssh config [list|add <name> <hostname> [options]|remove <name>]")
            return False
    
    def _ssh_hosts(self, args: List[str]) -> bool:
        """SSH hosts command"""
        hosts = self.config_manager.list_hosts()
        if not hosts:
            print("No SSH hosts configured")
            return True
        
        print("Configured SSH Hosts:")
        for host in hosts:
            config = self.config_manager.get_host(host)
            hostname = config.get('HostName', host)
            port = config.get('Port', '22')
            user = config.get('User', '')
            
            host_info = f"{host} -> {hostname}:{port}"
            if user:
                host_info += f" (user: {user})"
            
            print(f"  {host_info}")
        
        return True
    
    def _show_help(self):
        """Show SSH command help"""
        print("""SSH Command Usage:
  ssh <target>                    - Connect to SSH host
  ssh connect <target> [options]  - Connect to SSH host with options
  ssh exec <target> <command>     - Execute command on remote host
  ssh keygen <name> [options]     - Generate SSH key pair
  ssh keys [list|delete|import]   - Manage SSH keys
  ssh config [list|add|remove]    - Manage SSH host configurations
  ssh hosts                       - List configured SSH hosts

Options:
  -p <port>        - SSH port (default: 22)
  -l <user>        - SSH user
  -i <key>         - SSH key name
  -t <type>        - Key type for keygen (rsa, ed25519, ecdsa)
  -C <comment>     - Key comment for keygen
  -b <bits>        - Key size for RSA keys
  -o <option>      - SSH option (format: key=value)

Examples:
  ssh user@example.com
  ssh connect server1 -p 2222 -i mykey
  ssh exec server1 "ls -la"
  ssh keygen mykey -t ed25519
  ssh config add server1 example.com -p 2222 -l user -i mykey""")

class SCPCommand:
    """SCP command handler for KOS shell"""
    
    def __init__(self, shell):
        self.shell = shell
        self.key_manager = SSHKeyManager()
        self.config_manager = SSHConfigManager()
        self.scp_client = SCPClient(self.key_manager, self.config_manager)
    
    def execute(self, args: List[str]) -> bool:
        """Execute SCP command"""
        if len(args) < 2:
            self._show_help()
            return False
        
        # Parse options
        recursive = False
        preserve = False
        port = 22
        user = None
        key_name = None
        
        source_args = []
        i = 0
        
        while i < len(args):
            if args[i] == "-r":
                recursive = True
            elif args[i] == "-p":
                preserve = True
            elif args[i] == "-P" and i + 1 < len(args):
                port = int(args[i + 1])
                i += 1
            elif args[i] == "-l" and i + 1 < len(args):
                user = args[i + 1]
                i += 1
            elif args[i] == "-i" and i + 1 < len(args):
                key_name = args[i + 1]
                i += 1
            else:
                source_args.append(args[i])
            i += 1
        
        if len(source_args) < 2:
            print("Error: SCP requires source and destination")
            return False
        
        source = source_args[0]
        destination = source_args[1]
        
        # Determine transfer direction
        if ':' in source:
            # Copy from remote
            success = self.scp_client.copy_from_remote(
                source, destination, port, user, key_name, recursive, preserve
            )
        elif ':' in destination:
            # Copy to remote
            success = self.scp_client.copy_to_remote(
                source, destination, port, user, key_name, recursive, preserve
            )
        else:
            print("Error: Either source or destination must be remote (contain ':')")
            return False
        
        if success:
            print(f"SCP transfer completed: {source} -> {destination}")
        else:
            print(f"SCP transfer failed: {source} -> {destination}")
        
        return success
    
    def _show_help(self):
        """Show SCP command help"""
        print("""SCP Command Usage:
  scp [options] <source> <destination>

Options:
  -r           - Recursively copy directories
  -p           - Preserve file attributes
  -P <port>    - SSH port (default: 22)
  -l <user>    - SSH user
  -i <key>     - SSH key name

Remote format: [user@]host:path

Examples:
  scp file.txt user@server:/tmp/
  scp -r /local/dir user@server:/remote/dir
  scp user@server:/remote/file.txt /local/
  scp -P 2222 -i mykey file.txt server:/tmp/""")

# Export command classes
__all__ = ['SSHCommand', 'SCPCommand', 'SSHKeyManager', 'SSHConfigManager'] 