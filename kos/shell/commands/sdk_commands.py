"""
KOS SDK Shell Commands - Commands for C/C++/Python development
"""

import os
import sys
import shutil
from typing import Optional

from kos.sdk import KOSCompiler, KOSBuilder, KOSRuntime, ApplicationTemplate
from kos.sdk.compiler import Language

def register_commands(shell):
    """Register SDK commands with the shell"""
    
    # Development commands
    shell.do_kos_new = create_new_project
    shell.do_kos_build = build_project
    shell.do_kos_run = run_application
    shell.do_kos_compile = compile_file
    shell.do_kos_clean = clean_project
    shell.do_kos_install = install_application
    
    # Compiler info
    shell.do_cc = show_compiler_info
    
    # Set help messages
    shell.help_kos_new = lambda: print("Create a new KOS application project")
    shell.help_kos_build = lambda: print("Build the current KOS project")
    shell.help_kos_run = lambda: print("Run a KOS application")
    shell.help_kos_compile = lambda: print("Compile a source file")
    shell.help_kos_clean = lambda: print("Clean build artifacts")
    shell.help_kos_install = lambda: print("Install the built application")
    shell.help_cc = lambda: print("Show compiler information")
    
    return True

def create_new_project(self, args):
    """Create a new KOS application project
    Usage: kos-new <name> [language]
    Languages: c, cpp, python (default: c)
    """
    parts = args.split()
    if not parts:
        print("Usage: kos-new <name> [language]")
        print("Languages: c, cpp, python")
        return
        
    name = parts[0]
    language_str = parts[1] if len(parts) > 1 else "c"
    
    # Map language string to enum
    language_map = {
        "c": Language.C,
        "cpp": Language.CPP,
        "c++": Language.CPP,
        "python": Language.PYTHON,
        "py": Language.PYTHON
    }
    
    if language_str not in language_map:
        print(f"Unknown language: {language_str}")
        print("Available languages: c, cpp, python")
        return
        
    language = language_map[language_str]
    
    # Check if project already exists
    if os.path.exists(name):
        print(f"Directory '{name}' already exists")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            return
            
    # Create project
    try:
        success = ApplicationTemplate.create_project(name, language)
        if success:
            print(f"Created {language.value.upper()} project: {name}")
            print(f"To get started:")
            print(f"  cd {name}")
            print(f"  kos-build")
            print(f"  kos-run {name.lower()}")
        else:
            print("Failed to create project")
    except Exception as e:
        print(f"Error creating project: {e}")

def build_project(self, args):
    """Build the current KOS project
    Usage: kos-build [options]
    Options:
      -c, --clean    Clean before building
      -r, --release  Build in release mode
    """
    builder = KOSBuilder()
    
    # Parse options
    clean_first = "-c" in args or "--clean" in args
    release_mode = "-r" in args or "--release" in args
    
    # Load project
    config = builder.load_project()
    if not config:
        print("No kos-project.json found in current directory")
        return
        
    # Clean if requested
    if clean_first:
        builder.clean()
        
    # Add release flags if needed
    if release_mode and config.language != Language.PYTHON:
        config.compiler_flags.extend(["-O3", "-DNDEBUG"])
        
    # Build
    try:
        success = builder.build(config)
        if success:
            print("Build successful!")
        else:
            print("Build failed!")
    except Exception as e:
        print(f"Build error: {e}")

def run_application(self, args):
    """Run a KOS application
    Usage: kos-run <application> [arguments...]
    """
    if not args:
        print("Usage: kos-run <application> [arguments...]")
        return
        
    parts = args.split(maxsplit=1)
    app_name = parts[0]
    app_args = parts[1].split() if len(parts) > 1 else []
    
    # Get runtime
    runtime = KOSRuntime()
    
    # Look for application
    search_paths = [
        app_name,  # Direct path
        f"./build/{app_name}",  # Build directory
        f"./{app_name}",  # Current directory
        f"/usr/local/bin/{app_name}",  # System install
        f"/usr/bin/{app_name}"  # System install
    ]
    
    app_path = None
    for path in search_paths:
        if os.path.exists(path):
            app_path = path
            break
            
    if not app_path:
        # Check if it's a Python script
        if os.path.exists(f"{app_name}.py"):
            app_path = f"{app_name}.py"
        else:
            print(f"Application not found: {app_name}")
            return
            
    # Run application
    try:
        print(f"Running: {app_path} {' '.join(app_args)}")
        
        if app_path.endswith('.py'):
            # Python application
            process = runtime.execute_python(app_path, app_args)
        else:
            # Binary application
            process = runtime.execute(app_path, app_args, capture_output=True)
            
        # Wait for completion
        exit_code = process.wait()
        
        # Show output
        stdout, stderr = process.get_output()
        if stdout:
            print(stdout, end='')
        if stderr:
            print(stderr, end='', file=sys.stderr)
            
        if exit_code != 0:
            print(f"\nApplication exited with code: {exit_code}")
            
    except Exception as e:
        print(f"Error running application: {e}")

def compile_file(self, args):
    """Compile a source file
    Usage: kos-compile <source_file> [-o output] [-l library] [-I include_dir]
    """
    if not args:
        print("Usage: kos-compile <source_file> [-o output] [-l library] [-I include_dir]")
        return
        
    # Parse arguments
    parts = args.split()
    source_file = None
    output_file = None
    libraries = []
    include_dirs = []
    flags = []
    
    i = 0
    while i < len(parts):
        if parts[i] == "-o" and i + 1 < len(parts):
            output_file = parts[i + 1]
            i += 2
        elif parts[i] == "-l" and i + 1 < len(parts):
            libraries.append(parts[i + 1])
            i += 2
        elif parts[i] == "-I" and i + 1 < len(parts):
            include_dirs.append(parts[i + 1])
            i += 2
        elif parts[i].startswith("-"):
            flags.append(parts[i])
            i += 1
        else:
            if source_file is None:
                source_file = parts[i]
            i += 1
            
    if not source_file:
        print("No source file specified")
        return
        
    if not os.path.exists(source_file):
        print(f"Source file not found: {source_file}")
        return
        
    # Compile
    compiler = KOSCompiler()
    
    try:
        success, message = compiler.compile(
            source_file=source_file,
            output_file=output_file,
            flags=flags,
            libs=libraries,
            include_dirs=include_dirs
        )
        
        print(message)
        
    except Exception as e:
        print(f"Compilation error: {e}")

def clean_project(self, args):
    """Clean build artifacts
    Usage: kos-clean
    """
    builder = KOSBuilder()
    
    try:
        builder.clean()
        print("Clean complete")
    except Exception as e:
        print(f"Clean error: {e}")

def install_application(self, args):
    """Install the built application
    Usage: kos-install [prefix]
    Default prefix: /usr/local
    """
    builder = KOSBuilder()
    
    prefix = args.strip() if args else "/usr/local"
    
    try:
        success = builder.install(prefix=prefix)
        if success:
            print("Installation complete")
        else:
            print("Installation failed")
    except Exception as e:
        print(f"Installation error: {e}")

def show_compiler_info(self, args):
    """Show compiler information"""
    compiler = KOSCompiler()
    
    print("KOS SDK Compiler Information")
    print("============================")
    print()
    print("Available compilers:")
    
    for comp_type, comp_path in compiler.compilers.items():
        if comp_path:
            # Get version
            try:
                import subprocess
                result = subprocess.run([comp_path, "--version"], 
                                      capture_output=True, text=True)
                version = result.stdout.split('\n')[0] if result.stdout else "Unknown"
                print(f"  {comp_type.name}: {comp_path}")
                print(f"    Version: {version}")
            except:
                print(f"  {comp_type.name}: {comp_path}")
                
    print()
    print("Supported languages:")
    print("  - C (.c)")
    print("  - C++ (.cpp, .cc, .cxx)")
    print("  - Python (.py)")
    print()
    print("Default compiler flags:")
    for lang, flags in compiler.default_flags.items():
        if flags:
            print(f"  {lang.name}: {' '.join(flags)}")
            
    print()
    print("KOS include paths:")
    for inc in compiler.kos_includes:
        exists = "✓" if os.path.exists(inc) else "✗"
        print(f"  {exists} {inc}")
        
    print()
    print("KOS libraries:")
    for lib in compiler.kos_libs:
        print(f"  - lib{lib}")

# Additional helper functions can be added here