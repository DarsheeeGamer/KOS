#!/usr/bin/env python3
"""
Test script to verify the new compatibility commands work
"""

def test_reload_commands():
    """Test if we can load the new commands"""
    try:
        # Import the shell
        from kos.shell.shell import KaedeShell
        from kos.filesystem.base import FileSystem
        from kos.user_system import UserSystem
        from kos.process.manager import ProcessManager
        
        # Create basic instances
        fs = FileSystem()
        pm = None
        process_mgr = ProcessManager() if ProcessManager else None
        us = UserSystem(fs)
        
        # Create shell instance
        shell = KaedeShell(fs, pm, process_mgr, us)
        
        # Register the new commands
        from kos.shell.commands.system_compatibility import register_commands as register_compatibility_commands
        from kos.shell.commands.common_aliases import register_commands as register_alias_commands
        
        register_compatibility_commands(shell)
        register_alias_commands(shell)
        
        # Test some commands
        test_commands = ['bash', 'python', 'python3', 'll', 'la', '..', 'which', 'whoami']
        
        print("Testing new KOS compatibility commands:")
        print("=" * 50)
        
        for cmd in test_commands:
            if hasattr(shell, f'do_{cmd}'):
                print(f"✓ {cmd} command is available")
            else:
                print(f"✗ {cmd} command is NOT available")
        
        print("\nCommands loaded successfully!")
        return True
        
    except Exception as e:
        print(f"Error testing commands: {e}")
        return False

if __name__ == "__main__":
    test_reload_commands()