"""
Kaede Shell Integration for KOS
==============================

Integration of Kaede language with KOS shell environment.
Provides commands for executing Kaede code, managing Kaede projects,
and debugging Kaede applications.
"""

import os
import sys
import traceback
from typing import Dict, Any, List, Optional
from .lexer import KaedeLexer
from .parser import KaedeParser
from .interpreter import KaedeInterpreter
from .runtime import KaedeRuntime
from .stdlib import KaedeStandardLibrary
from .exceptions import KaedeError
from .repl import KaedeREPL

class KaedeShellCommands:
    """Kaede language commands for KOS shell"""
    
    def __init__(self, kos_shell):
        self.kos_shell = kos_shell
        self.kaede_runtime = None
        self.kaede_repl = None
        self.project_context = {}
        self.initialize_kaede()
    
    def initialize_kaede(self):
        """Initialize Kaede runtime environment"""
        try:
            self.kaede_runtime = KaedeRuntime()
            self.kaede_stdlib = KaedeStandardLibrary(self.kaede_runtime)
            
            # Integrate with KOS
            self.kaede_runtime.set_kos_shell(self.kos_shell)
            
            # Set up basic environment
            self.setup_environment()
            
            print("Kaede language environment initialized.")
            
        except Exception as e:
            print(f"Failed to initialize Kaede: {e}")
    
    def setup_environment(self):
        """Set up Kaede environment with KOS integration"""
        # Add KOS system functions to Kaede namespace
        kos_functions = {
            'kos_fs': self.kos_shell.fs,
            'kos_user': self.kos_shell.us,
            'kos_process': self.kos_shell.process_mgr,
            'print': print,  # Basic print function
            'input': input,  # Basic input function
        }
        
        for name, func in kos_functions.items():
            self.kaede_runtime.global_scope[name] = func
    
    def do_kaede(self, arg: str):
        """
        Execute Kaede code or enter Kaede REPL
        
        Usage:
            kaede                    - Enter interactive Kaede REPL
            kaede -f <file>         - Execute Kaede file
            kaede -c "<code>"       - Execute Kaede code string
            kaede -p <project>      - Load Kaede project
            kaede --help            - Show help
        """
        args = arg.strip().split() if arg.strip() else []
        
        if not args:
            # Enter REPL mode
            self.enter_kaede_repl()
            return
        
        if args[0] == '--help':
            self.show_kaede_help()
            return
        
        if args[0] == '-f' and len(args) > 1:
            # Execute file
            filename = args[1]
            self.execute_kaede_file(filename)
            return
        
        if args[0] == '-c' and len(args) > 1:
            # Execute code string
            code = ' '.join(args[1:])
            self.execute_kaede_code(code)
            return
        
        if args[0] == '-p' and len(args) > 1:
            # Load project
            project_name = args[1]
            self.load_kaede_project(project_name)
            return
        
        # Default: execute as code
        code = arg
        self.execute_kaede_code(code)
    
    def enter_kaede_repl(self):
        """Enter interactive Kaede REPL"""
        if not self.kaede_repl:
            self.kaede_repl = KaedeREPL(self.kaede_runtime)
        
        print("Entering Kaede REPL. Type 'exit()' or press Ctrl+D to return to KOS.")
        print("Type 'help()' for Kaede language help.")
        
        try:
            self.kaede_repl.run()
        except KeyboardInterrupt:
            print("\nReturning to KOS shell...")
        except EOFError:
            print("\nReturning to KOS shell...")
    
    def execute_kaede_file(self, filename: str):
        """Execute a Kaede source file"""
        try:
            # Check if file exists in KOS filesystem
            if not self.kos_shell.fs.exists(filename):
                print(f"Error: File '{filename}' not found")
                return
            
            # Read file content
            try:
                content = self.kos_shell.fs.read_file(filename)
            except Exception as e:
                print(f"Error reading file '{filename}': {e}")
                return
            
            # Execute the code
            self.execute_kaede_code(content, filename)
            
        except Exception as e:
            print(f"Error executing Kaede file '{filename}': {e}")
    
    def execute_kaede_code(self, code: str, filename: str = "<shell>"):
        """Execute Kaede code string"""
        try:
            # Tokenize
            lexer = KaedeLexer()
            tokens = lexer.tokenize(code)
            
            # Parse
            parser = KaedeParser()
            ast = parser.parse(tokens, filename)
            
            # Execute
            interpreter = KaedeInterpreter(self.kaede_runtime)
            result = interpreter.execute(ast)
            
            # Display result if not None
            if result is not None:
                print(f"Result: {result}")
                
        except KaedeError as e:
            print(f"Kaede Error: {e}")
            if hasattr(e, 'line') and e.line > 0:
                self.show_error_context(code, e)
        except Exception as e:
            print(f"Internal Error: {e}")
            traceback.print_exc()
    
    def show_error_context(self, code: str, error: KaedeError):
        """Show error context with source code"""
        lines = code.split('\n')
        if error.line <= len(lines):
            start_line = max(1, error.line - 2)
            end_line = min(len(lines), error.line + 2)
            
            print("\nSource context:")
            for i in range(start_line, end_line + 1):
                line_content = lines[i - 1] if i <= len(lines) else ""
                marker = ">>> " if i == error.line else "    "
                print(f"{marker}{i:4d}: {line_content}")
                
                if i == error.line and error.column > 0:
                    # Add pointer to error column
                    pointer = " " * (8 + error.column - 1) + "^"
                    print(pointer)
    
    def load_kaede_project(self, project_name: str):
        """Load a Kaede project"""
        project_file = f"{project_name}.kproj"
        
        if not self.kos_shell.fs.exists(project_file):
            print(f"Error: Project file '{project_file}' not found")
            return
        
        try:
            # Load project configuration
            import json
            project_config = json.loads(self.kos_shell.fs.read_file(project_file))
            
            self.project_context = project_config
            
            print(f"Loaded Kaede project: {project_name}")
            print(f"  Name: {project_config.get('name', 'Unknown')}")
            print(f"  Version: {project_config.get('version', '1.0.0')}")
            print(f"  Description: {project_config.get('description', 'No description')}")
            
            # Execute main file if specified
            main_file = project_config.get('main')
            if main_file:
                print(f"Executing main file: {main_file}")
                self.execute_kaede_file(main_file)
                
        except Exception as e:
            print(f"Error loading project '{project_name}': {e}")
    
    def do_kaedeinfo(self, arg: str):
        """
        Show information about Kaede language and runtime
        
        Usage:
            kaedeinfo              - Show general information
            kaedeinfo version      - Show version information
            kaedeinfo runtime      - Show runtime statistics
            kaedeinfo memory       - Show memory usage
            kaedeinfo globals      - Show global variables
        """
        arg = arg.strip().lower()
        
        if not arg or arg == "general":
            self.show_general_info()
        elif arg == "version":
            self.show_version_info()
        elif arg == "runtime":
            self.show_runtime_info()
        elif arg == "memory":
            self.show_memory_info()
        elif arg == "globals":
            self.show_globals_info()
        else:
            print(f"Unknown info type: {arg}")
            print("Available types: general, version, runtime, memory, globals")
    
    def show_general_info(self):
        """Show general Kaede information"""
        print("Kaede Programming Language")
        print("=" * 25)
        print("A hybrid language combining Python's simplicity with C++'s performance")
        print()
        print("Features:")
        print("  • Static and dynamic typing")
        print("  • Memory management control")
        print("  • High-level abstractions")
        print("  • Low-level system access")
        print("  • Template/generic programming")
        print("  • Concurrent programming primitives")
        print("  • Direct KOS system integration")
    
    def show_version_info(self):
        """Show version information"""
        from . import __version__, __author__
        print(f"Kaede Language Version: {__version__}")
        print(f"Author: {__author__}")
        print(f"Runtime: {'Active' if self.kaede_runtime else 'Inactive'}")
    
    def show_runtime_info(self):
        """Show runtime statistics"""
        if not self.kaede_runtime:
            print("Kaede runtime not initialized")
            return
        
        stats = self.kaede_runtime.get_statistics()
        print("Kaede Runtime Statistics")
        print("=" * 24)
        print(f"  Objects created: {stats.get('objects_created', 0)}")
        print(f"  Objects destroyed: {stats.get('objects_destroyed', 0)}")
        print(f"  Function calls: {stats.get('function_calls', 0)}")
        print(f"  GC collections: {stats.get('gc_collections', 0)}")
        print(f"  Execution time: {stats.get('execution_time', 0.0):.2f}s")
    
    def show_memory_info(self):
        """Show memory usage information"""
        if not self.kaede_runtime:
            print("Kaede runtime not initialized")
            return
        
        memory_info = self.kaede_runtime.get_memory_info()
        print("Kaede Memory Usage")
        print("=" * 18)
        print(f"  Allocated: {memory_info.get('allocated', 0)} bytes")
        print(f"  In use: {memory_info.get('in_use', 0)} bytes")
        print(f"  Available: {memory_info.get('available', 0)} bytes")
        print(f"  Peak usage: {memory_info.get('peak_usage', 0)} bytes")
    
    def show_globals_info(self):
        """Show global variables and functions"""
        if not self.kaede_runtime:
            print("Kaede runtime not initialized")
            return
        
        globals_dict = self.kaede_runtime.global_scope
        print("Kaede Global Scope")
        print("=" * 18)
        
        for name, value in sorted(globals_dict.items()):
            value_type = type(value).__name__
            if callable(value):
                print(f"  {name}: <function {value_type}>")
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                print(f"  {name}: {value_str} ({value_type})")
    
    def do_kaedeproject(self, arg: str):
        """
        Manage Kaede projects
        
        Usage:
            kaedeproject new <name>        - Create new project
            kaedeproject build [target]    - Build current project
            kaedeproject run              - Run current project
            kaedeproject test             - Run project tests
            kaedeproject clean            - Clean build artifacts
        """
        args = arg.strip().split() if arg.strip() else []
        
        if not args:
            print("Current project:", self.project_context.get('name', 'None'))
            return
        
        command = args[0].lower()
        
        if command == "new" and len(args) > 1:
            self.create_new_project(args[1])
        elif command == "build":
            target = args[1] if len(args) > 1 else "default"
            self.build_project(target)
        elif command == "run":
            self.run_project()
        elif command == "test":
            self.test_project()
        elif command == "clean":
            self.clean_project()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: new, build, run, test, clean")
    
    def create_new_project(self, name: str):
        """Create a new Kaede project"""
        project_dir = name
        project_file = f"{name}.kproj"
        main_file = f"{name}/main.kd"
        
        try:
            # Create project directory
            self.kos_shell.fs.create_directory(project_dir)
            
            # Create project configuration
            project_config = {
                "name": name,
                "version": "1.0.0",
                "description": f"Kaede project: {name}",
                "main": "main.kd",
                "dependencies": [],
                "build": {
                    "target": "executable",
                    "output": f"{name}"
                }
            }
            
            import json
            config_json = json.dumps(project_config, indent=2)
            self.kos_shell.fs.write_file(project_file, config_json)
            
            # Create main source file
            main_code = f'''// {name} - Main Kaede application
// Generated by KOS Kaede project creator

def main() -> int:
    print("Hello from Kaede project: {name}")
    return 0

// Entry point
if __name__ == "__main__":
    main()
'''
            
            self.kos_shell.fs.write_file(main_file, main_code)
            
            print(f"Created Kaede project: {name}")
            print(f"  Project file: {project_file}")
            print(f"  Main file: {main_file}")
            
            # Load the new project
            self.load_kaede_project(name)
            
        except Exception as e:
            print(f"Error creating project '{name}': {e}")
    
    def build_project(self, target: str = "default"):
        """Build current Kaede project"""
        if not self.project_context:
            print("No project loaded. Use 'kaedeproject new' or 'kaede -p <project>'")
            return
        
        print(f"Building project: {self.project_context['name']} (target: {target})")
        
        # For now, just validate syntax by parsing
        main_file = self.project_context.get('main')
        if main_file:
            try:
                content = self.kos_shell.fs.read_file(main_file)
                lexer = KaedeLexer()
                tokens = lexer.tokenize(content)
                parser = KaedeParser()
                ast = parser.parse(tokens, main_file)
                print("Build successful: Syntax validation passed")
            except Exception as e:
                print(f"Build failed: {e}")
        else:
            print("No main file specified in project")
    
    def run_project(self):
        """Run current Kaede project"""
        if not self.project_context:
            print("No project loaded")
            return
        
        main_file = self.project_context.get('main')
        if main_file:
            print(f"Running project: {self.project_context['name']}")
            self.execute_kaede_file(main_file)
        else:
            print("No main file specified in project")
    
    def test_project(self):
        """Run project tests"""
        if not self.project_context:
            print("No project loaded")
            return
        
        # Look for test files
        test_files = []
        try:
            files = self.kos_shell.fs.list_directory(".")
            test_files = [f for f in files if f.startswith("test_") and f.endswith(".kd")]
        except:
            pass
        
        if not test_files:
            print("No test files found (test_*.kd)")
            return
        
        print(f"Running tests for project: {self.project_context['name']}")
        for test_file in test_files:
            print(f"  Running {test_file}...")
            self.execute_kaede_file(test_file)
    
    def clean_project(self):
        """Clean project build artifacts"""
        if not self.project_context:
            print("No project loaded")
            return
        
        print(f"Cleaning project: {self.project_context['name']}")
        # For now, just report that cleaning would happen
        print("Build artifacts cleaned (no build artifacts to clean yet)")
    
    def show_kaede_help(self):
        """Show Kaede language help"""
        help_text = """
Kaede Programming Language Help
===============================

Basic Syntax:
  // Variables
  let x: int = 42              // Immutable variable with type
  var y = "hello"              // Mutable variable with type inference
  const PI: float = 3.14159    // Compile-time constant

  // Functions
  def add(a: int, b: int) -> int:
      return a + b

  // Classes
  class Point:
      x: float
      y: float
      
      def __init__(self, x: float, y: float):
          self.x = x
          self.y = y

  // Control flow
  if condition:
      // Python-style blocks
      pass
  else {
      // C++-style blocks also supported
  }

Memory Management:
  ptr<int> p = new int(42)     // Explicit allocation
  shared<vector<int>> vec      // Shared ownership
  unique<string> str           // Unique ownership
  delete p                     // Explicit deallocation

Templates/Generics:
  template<typename T>
  def max(a: T, b: T) -> T:
      return a if a > b else b

Built-in Types:
  int, float, double, char, bool, string
  list<T>, dict<K, V>, set<T>, tuple<T...>

KOS Integration:
  kos_fs.read_file("path")     // Access KOS filesystem
  kos_user.current_user        // Access KOS user system
  kos_process.create("cmd")    // Access KOS process system

Commands:
  kaede                        // Enter REPL
  kaede -f file.kd            // Execute file
  kaede -c "code"             // Execute code string
  kaedeinfo                   // Show language info
  kaedeproject new myproject  // Create project
"""
        print(help_text) 