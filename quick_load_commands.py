#!/usr/bin/env python3
"""
Quick Command Loader - Add essential commands to KOS shell
"""

def create_reload_command():
    """Create a standalone reload command file"""
    reload_content = '''
def do_reload(self, arg):
    """Reload shell commands dynamically"""
    try:
        print("🔄 Reloading KOS shell commands...")
        
        # Import and register system compatibility
        try:
            import sys
            sys.path.insert(0, '/home/kaededev/KOS')
            from kos.shell.commands.system_compatibility import register_commands as register_compatibility
            register_compatibility(self)
            print("✅ System compatibility commands (bash, python, which, etc.)")
        except Exception as e:
            print(f"❌ System compatibility: {e}")
        
        # Import and register common aliases
        try:
            from kos.shell.commands.common_aliases import register_commands as register_aliases
            register_aliases(self)
            print("✅ Common aliases (ll, la, .., etc.)")
        except Exception as e:
            print(f"❌ Common aliases: {e}")
        
        # Import and register shell emulation
        try:
            from kos.shell.commands.shell_emulation import register_commands as register_shells
            register_shells(self)
            print("✅ Shell emulation (bash, zsh, source)")
        except Exception as e:
            print(f"❌ Shell emulation: {e}")
        
        print("🎉 Commands reloaded! Try: bash, source, python3, ll, ..")
        
    except Exception as e:
        print(f"❌ Error reloading: {e}")

# Monkey patch this method into any shell instance
import sys
sys.path.insert(0, '/home/kaededev/KOS')

try:
    from kos.shell.shell import KaedeShell
    
    # Add reload method to the class
    KaedeShell.do_reload = do_reload
    print("✅ Reload command added to KaedeShell class")
    print("Now type 'reload' in your KOS session to load all enhanced commands!")
    
except Exception as e:
    print(f"❌ Could not patch shell class: {e}")
'''
    
    exec(reload_content)

if __name__ == "__main__":
    print("🚀 Quick Command Loader for KOS")
    print("=" * 40)
    create_reload_command()
    print("\n💡 Now go to your KOS session and type: reload")