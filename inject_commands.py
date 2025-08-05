#!/usr/bin/env python3
"""
Direct Command Injection for Current KOS Session
================================================

This script directly adds the enhanced shell commands to the running KOS session
by monkey-patching the shell instance.
"""

import sys
import os
import logging

# Add KOS to Python path
sys.path.insert(0, '/home/kaededev/KOS')

def inject_commands_to_running_shell():
    """
    Inject enhanced commands directly into the running KOS shell
    This is a workaround to add commands without restarting
    """
    try:
        print("🔧 Injecting enhanced commands into running KOS session...")
        
        # Import required modules
        from kos.shell.commands.system_compatibility import register_commands as register_compatibility
        from kos.shell.commands.common_aliases import register_commands as register_aliases  
        from kos.shell.commands.shell_emulation import register_commands as register_shells
        from kos.shell.commands.dynamic_loader import register_commands as register_loader
        
        # Find the running shell instance (this is a bit hacky but necessary)
        import gc
        from kos.shell.shell import KaedeShell
        
        # Look for KaedeShell instances in memory
        shell_instances = []
        for obj in gc.get_objects():
            if isinstance(obj, KaedeShell):
                shell_instances.append(obj)
        
        if not shell_instances:
            print("❌ No running KOS shell found")
            return False
        
        print(f"🎯 Found {len(shell_instances)} shell instance(s)")
        
        # Inject commands into all found shell instances
        for i, shell in enumerate(shell_instances):
            print(f"📦 Injecting commands into shell instance {i+1}...")
            
            try:
                register_compatibility(shell)
                print("  ✅ System compatibility commands")
            except Exception as e:
                print(f"  ❌ System compatibility: {e}")
            
            try:
                register_aliases(shell)
                print("  ✅ Common aliases")
            except Exception as e:
                print(f"  ❌ Common aliases: {e}")
            
            try:
                register_shells(shell)
                print("  ✅ Shell emulation")
            except Exception as e:
                print(f"  ❌ Shell emulation: {e}")
            
            try:
                register_loader(shell)
                print("  ✅ Dynamic loader")
            except Exception as e:
                print(f"  ❌ Dynamic loader: {e}")
        
        print("🎉 Command injection completed!")
        print("\nNow try in your KOS session:")
        print("  bash           - BASH shell emulator")
        print("  source file    - Source shell scripts") 
        print("  python3        - Python interpreter")
        print("  ll             - Long listing")
        print("  reload         - Reload commands")
        print("  ..             - Go up directory")
        
        return True
        
    except Exception as e:
        print(f"❌ Error injecting commands: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = inject_commands_to_running_shell()
    if success:
        print("\n✨ Commands successfully injected! Try 'bash' or 'source' in your KOS session.")
    else:
        print("\n💡 Alternative: Restart KOS to get the enhanced commands automatically.")