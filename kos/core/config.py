"""
System configuration management for KOS
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class ConfigFile:
    """Configuration file representation"""
    path: str
    format: str  # 'ini', 'json', 'yaml', 'conf', 'properties'
    content: Dict[str, Any] = field(default_factory=dict)
    raw_content: str = ""
    readonly: bool = False

class ConfigManager:
    """System configuration manager"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.configs: Dict[str, ConfigFile] = {}
        self.etc_dir = "/etc"
        
        self._init_system_configs()
    
    def _init_system_configs(self):
        """Initialize system configuration files"""
        if not self.vfs:
            return
        
        # Create /etc directory structure
        dirs = [
            "/etc",
            "/etc/init.d",
            "/etc/systemd",
            "/etc/systemd/system",
            "/etc/network",
            "/etc/ssh",
            "/etc/ssl",
            "/etc/apt",
            "/etc/profile.d"
        ]
        
        for dir_path in dirs:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path)
                except:
                    pass
        
        # Create default configuration files
        self._create_default_configs()
    
    def _create_default_configs(self):
        """Create default system configuration files"""
        # /etc/hostname
        self.write_config("/etc/hostname", {"hostname": "kos"}, format="text")
        
        # /etc/hosts
        hosts_content = """127.0.0.1       localhost
127.0.1.1       kos
::1             localhost ip6-localhost ip6-loopback
ff02::1         ip6-allnodes
ff02::2         ip6-allrouters"""
        self.write_raw("/etc/hosts", hosts_content)
        
        # /etc/passwd
        passwd_content = """root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
admin:x:1000:1000:Admin User:/home/admin:/bin/bash"""
        self.write_raw("/etc/passwd", passwd_content)
        
        # /etc/group
        group_content = """root:x:0:
daemon:x:1:
bin:x:2:
sys:x:3:
adm:x:4:
tty:x:5:
disk:x:6:
sudo:x:27:admin
admin:x:1000:"""
        self.write_raw("/etc/group", group_content)
        
        # /etc/fstab
        fstab_content = """# /etc/fstab: static file system information
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
/dev/sda1       /               ext4    defaults        0       1
proc            /proc           proc    defaults        0       0
sysfs           /sys            sysfs   defaults        0       0
devtmpfs        /dev            devtmpfs defaults       0       0"""
        self.write_raw("/etc/fstab", fstab_content)
        
        # /etc/resolv.conf
        resolv_content = """# DNS Configuration
nameserver 8.8.8.8
nameserver 8.8.4.4
search kos.local"""
        self.write_raw("/etc/resolv.conf", resolv_content)
        
        # /etc/network/interfaces
        network_content = """# Network interfaces configuration
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp"""
        self.write_raw("/etc/network/interfaces", network_content)
        
        # /etc/ssh/sshd_config
        sshd_config = {
            "Port": 22,
            "PermitRootLogin": "no",
            "PasswordAuthentication": "yes",
            "PubkeyAuthentication": "yes",
            "X11Forwarding": "no",
            "PrintMotd": "yes",
            "TCPKeepAlive": "yes",
            "ClientAliveInterval": 120,
            "ClientAliveCountMax": 3
        }
        self.write_config("/etc/ssh/sshd_config", sshd_config, format="conf")
        
        # /etc/profile
        profile_content = """# System-wide profile
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="/home/$USER"
export TERM="xterm-256color"
export LANG="en_US.UTF-8"

# Source profile.d scripts
for script in /etc/profile.d/*.sh; do
    [ -r "$script" ] && . "$script"
done

# Set prompt
export PS1='\\u@\\h:\\w\\$ '"""
        self.write_raw("/etc/profile", profile_content)
        
        # /etc/bashrc
        bashrc_content = """# System-wide bashrc
alias ls='ls --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias grep='grep --color=auto'
alias df='df -h'
alias free='free -h'

# Safety aliases
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Enable bash completion
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
fi"""
        self.write_raw("/etc/bashrc", bashrc_content)
        
        # /etc/os-release
        os_release = {
            "NAME": "KOS",
            "VERSION": "1.0",
            "ID": "kos",
            "ID_LIKE": "debian",
            "PRETTY_NAME": "KOS 1.0",
            "VERSION_ID": "1.0",
            "HOME_URL": "https://github.com/kaededev/kos",
            "SUPPORT_URL": "https://github.com/kaededev/kos/issues"
        }
        self.write_config("/etc/os-release", os_release, format="properties")
    
    def read_config(self, path: str, format: str = "auto") -> Optional[ConfigFile]:
        """Read configuration file"""
        if not self.vfs or not self.vfs.exists(path):
            return None
        
        try:
            with self.vfs.open(path, 'r') as f:
                raw_content = f.read().decode()
            
            # Auto-detect format
            if format == "auto":
                format = self._detect_format(path, raw_content)
            
            # Parse content
            content = self._parse_config(raw_content, format)
            
            config = ConfigFile(
                path=path,
                format=format,
                content=content,
                raw_content=raw_content
            )
            
            self.configs[path] = config
            return config
        except:
            return None
    
    def write_config(self, path: str, content: Dict[str, Any], 
                    format: str = "auto") -> bool:
        """Write configuration file"""
        if not self.vfs:
            return False
        
        # Auto-detect format
        if format == "auto":
            format = self._detect_format(path, "")
        
        # Serialize content
        raw_content = self._serialize_config(content, format)
        
        try:
            with self.vfs.open(path, 'w') as f:
                f.write(raw_content.encode())
            
            # Cache config
            self.configs[path] = ConfigFile(
                path=path,
                format=format,
                content=content,
                raw_content=raw_content
            )
            
            return True
        except:
            return False
    
    def write_raw(self, path: str, content: str) -> bool:
        """Write raw configuration content"""
        if not self.vfs:
            return False
        
        try:
            with self.vfs.open(path, 'w') as f:
                f.write(content.encode())
            return True
        except:
            return False
    
    def _detect_format(self, path: str, content: str) -> str:
        """Detect configuration file format"""
        # Check by extension
        if path.endswith('.json'):
            return 'json'
        elif path.endswith('.ini'):
            return 'ini'
        elif path.endswith('.yaml') or path.endswith('.yml'):
            return 'yaml'
        elif path.endswith('.properties'):
            return 'properties'
        elif path.endswith('.conf'):
            return 'conf'
        
        # Check by content
        if content.strip().startswith('{') or content.strip().startswith('['):
            return 'json'
        elif '[' in content and ']' in content:
            return 'ini'
        elif '=' in content or ':' in content:
            return 'properties'
        
        return 'text'
    
    def _parse_config(self, content: str, format: str) -> Dict[str, Any]:
        """Parse configuration content"""
        if format == 'json':
            try:
                return json.loads(content)
            except:
                return {}
        
        elif format == 'ini':
            return self._parse_ini(content)
        
        elif format == 'properties' or format == 'conf':
            return self._parse_properties(content)
        
        elif format == 'yaml':
            return self._parse_yaml(content)
        
        else:
            return {'content': content}
    
    def _serialize_config(self, content: Dict[str, Any], format: str) -> str:
        """Serialize configuration content"""
        if format == 'json':
            return json.dumps(content, indent=2)
        
        elif format == 'ini':
            return self._serialize_ini(content)
        
        elif format == 'properties' or format == 'conf':
            return self._serialize_properties(content)
        
        elif format == 'yaml':
            return self._serialize_yaml(content)
        
        elif format == 'text':
            return content.get('content', '') if isinstance(content, dict) else str(content)
        
        else:
            return str(content)
    
    def _parse_ini(self, content: str) -> Dict[str, Any]:
        """Parse INI format"""
        result = {}
        current_section = 'DEFAULT'
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            
            # Section header
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                if current_section not in result:
                    result[current_section] = {}
            
            # Key-value pair
            elif '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if current_section not in result:
                    result[current_section] = {}
                
                result[current_section][key] = value
        
        return result
    
    def _serialize_ini(self, content: Dict[str, Any]) -> str:
        """Serialize to INI format"""
        lines = []
        
        for section, values in content.items():
            if section != 'DEFAULT':
                lines.append(f"[{section}]")
            
            if isinstance(values, dict):
                for key, value in values.items():
                    lines.append(f"{key} = {value}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _parse_properties(self, content: str) -> Dict[str, str]:
        """Parse properties format"""
        result = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Key-value pair
            if '=' in line:
                key, value = line.split('=', 1)
                result[key.strip()] = value.strip().strip('"')
            elif ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        
        return result
    
    def _serialize_properties(self, content: Dict[str, Any]) -> str:
        """Serialize to properties format"""
        lines = []
        
        for key, value in content.items():
            if isinstance(value, str) and ' ' in value:
                lines.append(f'{key}="{value}"')
            else:
                lines.append(f'{key}={value}')
        
        return '\n'.join(lines)
    
    def _parse_yaml(self, content: str) -> Dict[str, Any]:
        """Parse YAML format (simplified)"""
        result = {}
        current_indent = 0
        stack = [result]
        
        for line in content.split('\n'):
            if not line.strip() or line.strip().startswith('#'):
                continue
            
            indent = len(line) - len(line.lstrip())
            line = line.strip()
            
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if value:
                    stack[-1][key] = value
                else:
                    stack[-1][key] = {}
                    stack.append(stack[-1][key])
        
        return result
    
    def _serialize_yaml(self, content: Dict[str, Any], indent: int = 0) -> str:
        """Serialize to YAML format"""
        lines = []
        
        for key, value in content.items():
            if isinstance(value, dict):
                lines.append(' ' * indent + f'{key}:')
                lines.append(self._serialize_yaml(value, indent + 2))
            else:
                lines.append(' ' * indent + f'{key}: {value}')
        
        return '\n'.join(lines)
    
    def get(self, path: str, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        config = self.configs.get(path)
        if not config:
            config = self.read_config(path)
        
        if not config:
            return default
        
        # Navigate nested keys
        keys = key.split('.')
        value = config.content
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, path: str, key: str, value: Any) -> bool:
        """Set configuration value"""
        config = self.configs.get(path)
        if not config:
            config = self.read_config(path)
        
        if not config:
            config = ConfigFile(path=path, format='properties')
        
        # Navigate nested keys
        keys = key.split('.')
        target = config.content
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
        
        # Save configuration
        return self.write_config(path, config.content, config.format)
    
    def reload(self, path: str) -> bool:
        """Reload configuration from disk"""
        if path in self.configs:
            del self.configs[path]
        
        config = self.read_config(path)
        return config is not None

class EnvironmentManager:
    """System environment variable manager"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.env_file = "/etc/environment"
        self.env_vars: Dict[str, str] = {}
        
        self._load_environment()
    
    def _load_environment(self):
        """Load environment variables"""
        config = self.config_manager.read_config(self.env_file, format='properties')
        if config:
            self.env_vars = config.content.copy()
        else:
            # Default environment
            self.env_vars = {
                'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                'LANG': 'en_US.UTF-8',
                'HOME': '/root',
                'SHELL': '/bin/bash',
                'TERM': 'xterm-256color'
            }
    
    def get(self, name: str, default: str = None) -> Optional[str]:
        """Get environment variable"""
        return self.env_vars.get(name, default)
    
    def set(self, name: str, value: str) -> bool:
        """Set environment variable"""
        self.env_vars[name] = value
        return self._save_environment()
    
    def unset(self, name: str) -> bool:
        """Unset environment variable"""
        if name in self.env_vars:
            del self.env_vars[name]
            return self._save_environment()
        return False
    
    def _save_environment(self) -> bool:
        """Save environment variables"""
        return self.config_manager.write_config(
            self.env_file, self.env_vars, format='properties'
        )
    
    def export_all(self) -> Dict[str, str]:
        """Export all environment variables"""
        return self.env_vars.copy()