"""
KOS sysctl command - Runtime kernel parameter configuration
"""

import logging
from typing import Optional, List, Dict, Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.tree import Tree
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ...kernel.sysctl_wrapper import get_kernel_sysctl, sysctl_get, sysctl_set, sysctl_list

logger = logging.getLogger('KOS.shell.sysctl')

def register_commands(shell):
    """Register sysctl commands with the shell"""
    
    def do_sysctl(self, args):
        """Manage kernel runtime parameters
        
        Usage:
            sysctl                      # List all parameters
            sysctl <name>              # Show specific parameter
            sysctl -w <name>=<value>   # Set parameter value
            sysctl -a                  # Show all parameters
            sysctl -p [file]          # Load parameters from file
            sysctl -h                  # Show help
        
        Examples:
            sysctl vm.swappiness
            sysctl -w vm.swappiness=30
            sysctl -a | grep net
        """
        if not args:
            # Show all parameters
            return show_all_sysctls(self)
        
        parts = args.split()
        
        if parts[0] == '-h' or parts[0] == '--help':
            self.console.print(do_sysctl.__doc__)
            return
        
        if parts[0] == '-a' or parts[0] == '--all':
            # Show all parameters
            return show_all_sysctls(self)
        
        if parts[0] == '-w' or parts[0] == '--write':
            # Write mode
            if len(parts) < 2:
                self.error("Usage: sysctl -w <name>=<value>")
                return
            
            param = ' '.join(parts[1:])
            if '=' not in param:
                self.error("Invalid format. Use: sysctl -w <name>=<value>")
                return
            
            name, value = param.split('=', 1)
            return set_sysctl_value(self, name.strip(), value.strip())
        
        if parts[0] == '-p' or parts[0] == '--load':
            # Load from file
            filename = parts[1] if len(parts) > 1 else '/etc/sysctl.conf'
            return load_sysctl_file(self, filename)
        
        # Show specific parameter
        param_name = args.strip()
        return show_sysctl_value(self, param_name)
    
    def complete_sysctl(self, text, line, begidx, endidx):
        """Tab completion for sysctl"""
        if line.startswith('sysctl -w '):
            # Complete parameter names for write
            return complete_sysctl_names(text)
        elif '-' not in line:
            # Complete parameter names
            return complete_sysctl_names(text)
        else:
            # Complete options
            options = ['-a', '-w', '-p', '-h', '--all', '--write', '--load', '--help']
            return [opt for opt in options if opt.startswith(text)]
    
    # Register the command
    shell.do_sysctl = do_sysctl.__get__(shell, shell.__class__)
    shell.complete_sysctl = complete_sysctl.__get__(shell, shell.__class__)
    
    logger.info("Registered sysctl command")

def show_all_sysctls(shell) -> None:
    """Show all sysctl parameters"""
    try:
        sysctls = sysctl_list()
        
        if not sysctls:
            shell.print("No sysctl parameters available")
            return
        
        if RICH_AVAILABLE and hasattr(shell, 'console'):
            # Use rich table
            table = Table(title="Kernel Parameters (sysctl)")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="yellow")
            table.add_column("Type", style="green")
            table.add_column("Access", style="magenta")
            
            for entry in sorted(sysctls, key=lambda x: x['path']):
                access = "RO" if entry['readonly'] else "RW"
                if entry['secure']:
                    access += " [SECURE]"
                
                table.add_row(
                    entry['path'],
                    str(entry['value']),
                    entry['type'],
                    access
                )
            
            shell.console.print(table)
        else:
            # Plain output
            shell.print("Kernel Parameters:")
            shell.print("-" * 80)
            
            for entry in sorted(sysctls, key=lambda x: x['path']):
                access = "RO" if entry['readonly'] else "RW"
                if entry['secure']:
                    access += " [SECURE]"
                
                shell.print(f"{entry['path']:<40} = {str(entry['value']):<20} ({entry['type']}, {access})")
    
    except Exception as e:
        shell.error(f"Failed to list sysctls: {e}")

def show_sysctl_value(shell, name: str) -> None:
    """Show a specific sysctl value"""
    try:
        # Try to get the value
        value = sysctl_get(name)
        
        # Also get full info if available
        sysctls = sysctl_list()
        info = next((s for s in sysctls if s['path'] == name), None)
        
        if info:
            shell.print(f"{name} = {value}")
            if info['description']:
                shell.print(f"  Description: {info['description']}")
            shell.print(f"  Type: {info['type']}")
            shell.print(f"  Access: {'Read-only' if info['readonly'] else 'Read-write'}")
            if info['secure']:
                shell.print("  Security: Requires CAP_SYS_ADMIN")
        else:
            shell.print(f"{name} = {value}")
    
    except KeyError:
        shell.error(f"sysctl: cannot stat /proc/sys/{name.replace('.', '/')}: No such file or directory")
    except Exception as e:
        shell.error(f"Failed to read sysctl '{name}': {e}")

def set_sysctl_value(shell, name: str, value: str) -> None:
    """Set a sysctl value"""
    try:
        # Get current value for display
        old_value = sysctl_get(name)
        
        # Set new value
        sysctl_set(name, value)
        
        # Verify it was set
        new_value = sysctl_get(name)
        
        shell.print(f"{name} = {new_value}")
        
        if str(old_value) != str(new_value):
            shell.print(f"  (was {old_value})")
    
    except PermissionError:
        shell.error(f"sysctl: permission denied on key '{name}'")
    except KeyError:
        shell.error(f"sysctl: cannot stat /proc/sys/{name.replace('.', '/')}: No such file or directory")
    except ValueError as e:
        shell.error(f"sysctl: invalid value '{value}' for parameter '{name}'")
    except Exception as e:
        shell.error(f"Failed to set sysctl '{name}': {e}")

def load_sysctl_file(shell, filename: str) -> None:
    """Load sysctl settings from a file"""
    try:
        import os
        
        if not os.path.exists(filename):
            shell.error(f"sysctl: cannot open '{filename}': No such file or directory")
            return
        
        loaded = 0
        errors = 0
        
        with open(filename, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse key = value
                if '=' not in line:
                    shell.error(f"{filename}:{line_num}: invalid syntax")
                    errors += 1
                    continue
                
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                try:
                    sysctl_set(key, value)
                    loaded += 1
                except Exception as e:
                    shell.error(f"{filename}:{line_num}: {key} - {e}")
                    errors += 1
        
        shell.print(f"Loaded {loaded} parameters from '{filename}'")
        if errors > 0:
            shell.print(f"  ({errors} errors)")
    
    except Exception as e:
        shell.error(f"Failed to load sysctl file '{filename}': {e}")

def complete_sysctl_names(text: str) -> List[str]:
    """Complete sysctl parameter names"""
    try:
        sysctls = sysctl_list()
        names = [s['path'] for s in sysctls]
        
        if not text:
            return names
        
        # Filter matching names
        matches = [n for n in names if n.startswith(text)]
        
        # If exact match exists, show sub-parameters
        if text in names:
            prefix = text + '.'
            sub_params = [n for n in names if n.startswith(prefix)]
            if sub_params:
                return sub_params
        
        return matches
    
    except Exception:
        return []

# Create default sysctl.conf if it doesn't exist
def create_default_sysctl_conf():
    """Create default /etc/sysctl.conf file"""
    default_conf = """# KOS Kernel Runtime Configuration
# /etc/sysctl.conf
#
# This file contains kernel parameters that can be modified at runtime.
# Use 'sysctl -p' to load these settings.

# Virtual Memory Settings
vm.swappiness = 60                    # Swappiness (0-100)
vm.dirty_ratio = 20                   # Dirty page ratio
vm.dirty_background_ratio = 10        # Background dirty ratio
vm.min_free_kbytes = 65536           # Minimum free memory

# Scheduler Settings
kernel.sched_latency_ns = 6000000     # Scheduler latency (6ms)
kernel.sched_min_granularity_ns = 1500000  # Min preemption granularity

# Network Settings
net.core.rmem_default = 212992       # Default receive buffer
net.core.wmem_default = 212992       # Default send buffer
net.ipv4.ip_forward = 0              # IPv4 forwarding
net.ipv6.conf.all.forwarding = 0    # IPv6 forwarding

# Security Settings
kernel.randomize_va_space = 1        # ASLR enabled
kernel.dmesg_restrict = 0            # dmesg access
kernel.kptr_restrict = 1             # Kernel pointer hiding
"""
    
    try:
        import os
        os.makedirs('/etc', exist_ok=True)
        
        if not os.path.exists('/etc/sysctl.conf'):
            with open('/etc/sysctl.conf', 'w') as f:
                f.write(default_conf)
            logger.info("Created default /etc/sysctl.conf")
    except Exception as e:
        logger.debug(f"Could not create default sysctl.conf: {e}")