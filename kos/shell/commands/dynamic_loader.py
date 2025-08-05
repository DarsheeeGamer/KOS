"""
Dynamic Command Loader for KOS
==============================

Provides runtime loading and reloading of shell commands
without requiring a shell restart.
"""

import logging
import importlib
import sys

logger = logging.getLogger('KOS.shell.dynamic_loader')

def register_commands(shell):
    """Register dynamic command loading functionality"""
    
    def reload_command(shell_instance, args):
        """Reload shell commands dynamically"""
        print("🔄 Reloading KOS shell commands...")
        
        try:
            # Count loaded commands
            commands_loaded = 0
            
            # Reload system compatibility commands
            try:
                if 'kos.shell.commands.system_compatibility' in sys.modules:
                    importlib.reload(sys.modules['kos.shell.commands.system_compatibility'])
                from kos.shell.commands.system_compatibility import register_commands as register_compatibility_commands
                register_compatibility_commands(shell_instance)
                commands_loaded += 14
                print("✅ System compatibility commands reloaded")
            except Exception as e:
                print(f"❌ System compatibility: {e}")
            
            # Reload common aliases
            try:
                if 'kos.shell.commands.common_aliases' in sys.modules:
                    importlib.reload(sys.modules['kos.shell.commands.common_aliases'])
                from kos.shell.commands.common_aliases import register_commands as register_alias_commands
                register_alias_commands(shell_instance)
                commands_loaded += 17
                print("✅ Common aliases reloaded")
            except Exception as e:
                print(f"❌ Common aliases: {e}")
            
            # Reload shell emulation commands
            try:
                if 'kos.shell.commands.shell_emulation' in sys.modules:
                    importlib.reload(sys.modules['kos.shell.commands.shell_emulation'])
                from kos.shell.commands.shell_emulation import register_commands as register_shell_emulation_commands
                register_shell_emulation_commands(shell_instance)
                commands_loaded += 6
                print("✅ Shell emulation commands reloaded")
            except Exception as e:
                print(f"❌ Shell emulation: {e}")
            
            # Reinitialize package CLI integration
            try:
                shell_instance._init_package_cli_integration()
                print("✅ Package CLI integration reloaded")
            except Exception as e:
                print(f"❌ Package CLI: {e}")
            
            print(f"✨ Successfully loaded {commands_loaded} commands!")
            print("\nNow available:")
            print("🐚 Shell: bash, zsh, sh, source, .")
            print("🐍 Python: python, python3")
            print("📁 Aliases: ll, la, .., ..., ~")
            print("🔧 Tools: which, env, whoami, id, hostname")
            print("🎯 Package: kpm install/list/search")
            
            return True
            
        except Exception as e:
            print(f"❌ Error reloading commands: {e}")
            logger.error(f"Command reload failed: {e}")
            return False
    
    def loadcmd_command(shell_instance, args):
        """Load specific command module"""
        if not args:
            print("Usage: loadcmd <module_name>")
            print("Available modules:")
            print("  system_compatibility - bash, python, which, etc.")
            print("  common_aliases - ll, la, .., etc.")
            print("  shell_emulation - enhanced bash, zsh, source")
            return
        
        module_name = args.strip()
        
        try:
            if module_name == "system_compatibility":
                from kos.shell.commands.system_compatibility import register_commands
                register_commands(shell_instance)
                print("✅ System compatibility commands loaded")
            elif module_name == "common_aliases":
                from kos.shell.commands.common_aliases import register_commands
                register_commands(shell_instance)
                print("✅ Common aliases loaded")
            elif module_name == "shell_emulation":
                from kos.shell.commands.shell_emulation import register_commands
                register_commands(shell_instance)
                print("✅ Shell emulation commands loaded")
            else:
                print(f"❌ Unknown module: {module_name}")
                return False
            
            print(f"📦 Module '{module_name}' loaded successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error loading module {module_name}: {e}")
            return False
    
    def listcmds_command(shell_instance, args):
        """List available commands"""
        print("📋 Available KOS Commands:")
        print("=" * 50)
        
        # Get all do_ methods
        commands = []
        for attr_name in dir(shell_instance):
            if attr_name.startswith('do_'):
                cmd_name = attr_name[3:]
                if hasattr(shell_instance, f'help_{cmd_name}'):
                    help_method = getattr(shell_instance, f'help_{cmd_name}')
                    doc = getattr(help_method, '__doc__', '') or 'No description'
                else:
                    method = getattr(shell_instance, attr_name)
                    doc = getattr(method, '__doc__', '') or 'No description'
                
                commands.append((cmd_name, doc.split('\n')[0] if doc else 'No description'))
        
        # Sort and display
        commands.sort()
        
        categories = {
            'Shell': ['bash', 'zsh', 'sh', 'source', '.'],
            'System': ['python', 'python3', 'which', 'env', 'whoami', 'id'],
            'Files': ['ls', 'cd', 'pwd', 'cat', 'cp', 'mv', 'rm', 'mkdir'],
            'Aliases': ['ll', 'la', 'l', '..', '...', '~'],
            'Package': ['kpm', 'pip', 'apt'],
            'Utilities': ['clear', 'history', 'help', 'reload', 'loadcmd']
        }
        
        # Display by category
        for category, cmd_list in categories.items():
            found_cmds = [(cmd, desc) for cmd, desc in commands if cmd in cmd_list]
            if found_cmds:
                print(f"\n{category}:")
                for cmd, desc in found_cmds:
                    print(f"  {cmd:<12} - {desc}")
        
        # Show other commands
        all_categorized = set()
        for cmd_list in categories.values():
            all_categorized.update(cmd_list)
        
        other_cmds = [(cmd, desc) for cmd, desc in commands if cmd not in all_categorized]
        if other_cmds:
            print(f"\nOther:")
            for cmd, desc in other_cmds[:10]:  # Limit to 10
                print(f"  {cmd:<12} - {desc}")
            if len(other_cmds) > 10:
                print(f"  ... and {len(other_cmds) - 10} more")
        
        print(f"\nTotal: {len(commands)} commands available")
        return True
    
    # Register dynamic loading commands
    dynamic_commands = {
        'reload': (reload_command, "Reload all shell commands dynamically"),
        'loadcmd': (loadcmd_command, "Load specific command module"),
        'listcmds': (listcmds_command, "List all available commands"),
    }
    
    for cmd_name, (cmd_func, cmd_help) in dynamic_commands.items():
        shell.register_command(cmd_name, cmd_func, cmd_help)
    
    logger.info(f"Registered {len(dynamic_commands)} dynamic loading commands")

__all__ = ['register_commands']