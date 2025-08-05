#!/usr/bin/env python3
"""
Test Enhanced Shell Commands for KOS
"""

def test_enhanced_shell_commands():
    """Test the new enhanced shell commands"""
    try:
        from kos.shell.shell import KaedeShell
        from kos.filesystem.base import FileSystem
        from kos.user_system import UserSystem
        from kos.process.manager import ProcessManager
        
        # Create shell instance
        fs = FileSystem()
        pm = None
        process_mgr = ProcessManager() if ProcessManager else None
        us = UserSystem(fs)
        
        shell = KaedeShell(fs, pm, process_mgr, us)
        
        # Load all the new command modules
        from kos.shell.commands.system_compatibility import register_commands as register_compatibility
        from kos.shell.commands.common_aliases import register_commands as register_aliases
        from kos.shell.commands.shell_emulation import register_commands as register_shells
        from kos.shell.commands.dynamic_loader import register_commands as register_loader
        
        register_compatibility(shell)
        register_aliases(shell)
        register_shells(shell)
        register_loader(shell)
        
        # Test commands
        enhanced_commands = [
            'bash', 'zsh', 'sh', 'source', '.', 'env',  # Shell commands
            'python', 'python3', 'which', 'whoami', 'id', 'hostname',  # System commands
            'll', 'la', 'l', '..', '...', '~', 'cls', 'dir',  # Aliases
            'reload', 'loadcmd', 'listcmds'  # Dynamic loader
        ]
        
        print("🚀 Testing Enhanced KOS Shell Commands")
        print("=" * 60)
        
        available_count = 0
        for cmd in enhanced_commands:
            if hasattr(shell, f'do_{cmd}'):
                print(f"✅ {cmd:<12} - Available")
                available_count += 1
            else:
                print(f"❌ {cmd:<12} - NOT Available")
        
        print(f"\n📊 Summary: {available_count}/{len(enhanced_commands)} commands available")
        
        if available_count == len(enhanced_commands):
            print("\n🎉 All enhanced shell commands loaded successfully!")
            print("\nYou can now use in KOS:")
            print("  bash           - Full BASH shell emulator")
            print("  zsh            - ZSH shell emulator") 
            print("  source file    - Source shell scripts")
            print("  python/python3 - Python interpreter")
            print("  ll, la, ..     - Common Unix aliases")
            print("  reload         - Reload commands dynamically")
            return True
        else:
            print(f"\n⚠️  Some commands are missing. Try running 'reload' in KOS.")
            return False
            
    except Exception as e:
        print(f"❌ Error testing commands: {e}")
        return False

if __name__ == "__main__":
    test_enhanced_shell_commands()