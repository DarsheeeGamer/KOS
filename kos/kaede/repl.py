"""
Kaede REPL
==========

Clean REPL for Kaede programming language with features from:
- Python: Interactive shell, dynamic typing, built-ins
- C++: STL containers, templates, memory management  
- Rust: Option/Result types, pattern matching, ownership
"""

import sys
import os
import readline
import traceback
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import deque

from .lexer import KaedeLexer
from .parser import KaedeParser
from .interpreter import KaedeInterpreter
from .runtime import KaedeRuntime, RuntimeMode
from .exceptions import KaedeError

@dataclass
class REPLHistory:
    """Simple REPL command history"""
    commands: List[str]
    results: List[Any]
    timestamps: List[float]
    
    def __init__(self):
        self.commands = []
        self.results = []
        self.timestamps = []
    
    def add_entry(self, command: str, result: Any):
        """Add entry to history"""
        self.commands.append(command)
        self.results.append(result)
        self.timestamps.append(time.time())
    
    def get_recent(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent history entries"""
        start_idx = max(0, len(self.commands) - count)
        return [
            {
                'command': self.commands[i],
                'result': self.results[i],
                'timestamp': self.timestamps[i]
            }
            for i in range(start_idx, len(self.commands))
        ]

class KaedeREPL:
    """Clean Kaede REPL with all language features"""
    
    def __init__(self, runtime: KaedeRuntime = None):
        self.runtime = runtime or KaedeRuntime(RuntimeMode.DEVELOPMENT)
        self.interpreter = KaedeInterpreter(self.runtime)
        self.lexer = KaedeLexer()
        self.parser = KaedeParser()
        
        # REPL state
        self.history = REPLHistory()
        self.continuation_lines = []
        self.prompt = "kaede>>> "
        self.continuation_prompt = "kaede... "
        self.running = False
        
        # Commands
        self.commands = {
            'help': self._cmd_help,
            'history': self._cmd_history,
            'clear': self._cmd_clear,
            'stats': self._cmd_stats,
            'memory': self._cmd_memory,
            'demo_python': self._demo_python,
            'demo_cpp': self._demo_cpp,
            'demo_rust': self._demo_rust,
            'demo_all': self._demo_all,
            'features': self._cmd_features,
        }
        
        self._setup_readline()
    
    def _setup_readline(self):
        """Setup readline for command history and completion"""
        try:
            readline.parse_and_bind("tab: complete")
            readline.set_completer_delims(' \t\n`!@#$%^&*()=+[{]}\\|;:\'",<>?')
            
            # Load history
            history_file = os.path.expanduser("~/.kaede_history")
            try:
                readline.read_history_file(history_file)
            except FileNotFoundError:
                pass
            
            readline.set_history_length(1000)
            
            # Save history on exit
            import atexit
            atexit.register(readline.write_history_file, history_file)
        except ImportError:
            pass  # readline not available
    
    def run(self):
        """Run the REPL"""
        self.running = True
        
        print("🚀 Welcome to Kaede Programming Language")
        print("Combining the best of Python, C++, and Rust")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Type 'help' for commands or 'demo_all' to see all features")
        print("Type 'exit' to quit")
        print()
        
        while self.running:
            try:
                if self.continuation_lines:
                    prompt = self.continuation_prompt
                else:
                    prompt = self.prompt
                
                line = input(prompt)
                
                # Handle special commands
                if line.strip() in ['exit', 'quit']:
                    break
                
                if line.startswith(':'):
                    self._handle_command(line[1:])
                    continue
                
                # Handle multi-line input
                if self._needs_continuation(line):
                    self.continuation_lines.append(line)
                    continue
                
                # Execute code
                if self.continuation_lines:
                    full_code = '\n'.join(self.continuation_lines + [line])
                    self.continuation_lines = []
                else:
                    full_code = line
                
                if full_code.strip():
                    self._execute_code(full_code)
                
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt")
                self.continuation_lines = []
            except EOFError:
                break
            except Exception as e:
                print(f"REPL Error: {e}")
        
        print("\n👋 Goodbye!")
        self.runtime.shutdown()
    
    def _needs_continuation(self, line: str) -> bool:
        """Check if line needs continuation"""
        stripped = line.strip()
        
        # Check for incomplete constructs
        if stripped.endswith(':'):
            return True
        
        # Check for unclosed brackets
        open_brackets = line.count('(') - line.count(')')
        open_square = line.count('[') - line.count(']')
        open_curly = line.count('{') - line.count('}')
        
        return open_brackets > 0 or open_square > 0 or open_curly > 0
    
    def _execute_code(self, code: str):
        """Execute Kaede code"""
        start_time = time.time()
        
        try:
            # Tokenize and parse
            tokens = self.lexer.tokenize(code)
            ast = self.parser.parse(tokens, "<repl>")
            
            # Execute
            result = self.interpreter.execute(ast)
            
            # Display result
            if result is not None:
                print(f"=> {result}")
            
            # Add to history
            self.history.add_entry(code, result)
            
        except KaedeError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
    
    def _handle_command(self, command: str):
        """Handle REPL commands"""
        parts = command.split()
        cmd_name = parts[0] if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd_name in self.commands:
            self.commands[cmd_name](args)
        else:
            print(f"Unknown command: {cmd_name}")
            print("Type ':help' for available commands")
    
    # Command implementations
    def _cmd_help(self, args):
        """Show help information"""
        print("""
🚀 Kaede REPL Commands
━━━━━━━━━━━━━━━━━━━━━

:help           - Show this help
:history        - Show command history  
:clear          - Clear screen
:stats          - Show runtime statistics
:memory         - Show memory usage
:features       - List all available features

🌟 Language Demos:
:demo_python    - Demonstrate Python features
:demo_cpp       - Demonstrate C++ features
:demo_rust      - Demonstrate Rust features
:demo_all       - Demonstrate all features

📝 Examples:
  # Python-style
  numbers = [1, 2, 3, 4, 5]
  squared = [x * x for x in numbers]
  
  # C++ STL-style
  vec = vector([1, 2, 3])
  vec.push_back(4)
  
  # Rust-style
  option = Some(42)
  result = Ok("success")
""")
    
    def _cmd_history(self, args):
        """Show command history"""
        recent = self.history.get_recent(10)
        print("📚 Recent Command History:")
        for i, entry in enumerate(recent, 1):
            cmd = entry['command'][:50] + "..." if len(entry['command']) > 50 else entry['command']
            print(f"  [{i}] {cmd}")
    
    def _cmd_clear(self, args):
        """Clear screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _cmd_stats(self, args):
        """Show runtime statistics"""
        stats = self.runtime.get_statistics()
        print("📊 Runtime Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    def _cmd_memory(self, args):
        """Show memory usage"""
        memory_info = self.runtime._get_memory_info()
        print("💾 Memory Usage:")
        for key, value in memory_info.items():
            print(f"  {key}: {value}")
    
    def _cmd_features(self, args):
        """List all available features"""
        print("""
🌟 Kaede Language Features
━━━━━━━━━━━━━━━━━━━━━━━━━━

🐍 Python Features:
• Dynamic typing: x = 42, x = "hello"  
• Built-ins: len(), range(), map(), filter()
• List comprehensions: [x*2 for x in range(10)]
• Iterators: enumerate(), zip(), reversed()
• Context managers: with file_context() as f:
• Duck typing: any object with required methods

⚡ C++ Features:  
• STL containers: vector(), map(), set()
• Smart pointers: unique_ptr(), shared_ptr()
• Templates: create_template("Vector", ["T"])
• RAII: automatic resource management
• Algorithms: find(), sort(), transform(), unique()
• Memory management: manual allocation/deallocation

🦀 Rust Features:
• Option types: Some(value), None
• Result types: Ok(value), Err(error)
• Pattern matching: match expressions
• Ownership system: borrow checking
• Traits: behavior definitions
• Iterators: collect(), fold(), take(), skip()
• Memory safety: no null pointers, no dangling refs

🔧 Unified Features:
• Cross-language compatibility
• Unified type system
• Memory management combining all approaches
• Threading and async support
• File I/O with all paradigms
• Math, string, and JSON operations
""")
    
    # Demo functions
    def _demo_python(self, args):
        """Demonstrate Python features"""
        print("🐍 Demonstrating Python Features:")
        
        demos = [
            "# List comprehension",
            "numbers = [1, 2, 3, 4, 5]",
            "squared = [x * x for x in numbers]",
            "print('Squared:', squared)",
            "",
            "# Built-in functions", 
            "print('Sum:', sum(numbers))",
            "print('Max:', max(numbers))",
            "print('Length:', len(numbers))",
            "",
            "# Iterators",
            "for i, num in enumerate(numbers):",
            "    if i < 3:",
            "        print(f'Index {i}: {num}')",
        ]
        
        for demo in demos:
            if demo.strip():
                print(f">>> {demo}")
                try:
                    self._execute_code(demo)
                except:
                    pass
            else:
                print()
    
    def _demo_cpp(self, args):
        """Demonstrate C++ features"""
        print("⚡ Demonstrating C++ Features:")
        
        demos = [
            "# STL vector",
            "vec = vector([1, 2, 3])",
            "vec.push_back(4)",
            "vec.push_back(5)",
            "print('Vector size:', vec.size())",
            "",
            "# STL algorithms",
            "data = [3, 1, 4, 1, 5, 9, 2, 6]",
            "print('Original:', data)",
            "sorted_data = sort(data)",
            "print('Sorted:', sorted_data)",
            "",
            "# Find and transform",
            "pos = find(data, 4)",
            "print('Position of 4:', pos)",
            "doubled = transform(data, lambda x: x * 2)",
            "print('Doubled:', doubled)",
        ]
        
        for demo in demos:
            if demo.strip():
                print(f">>> {demo}")
                try:
                    self._execute_code(demo)
                except:
                    pass
            else:
                print()
    
    def _demo_rust(self, args):
        """Demonstrate Rust features"""
        print("🦀 Demonstrating Rust Features:")
        
        demos = [
            "# Option types",
            "some_value = Some(42)",
            "none_value = None",
            "print('Some value:', some_value.unwrap())",
            "print('Is some:', some_value.is_some())",
            "print('Is none:', none_value.is_none())",
            "",
            "# Result types", 
            "success = Ok('All good!')",
            "failure = Err('Something went wrong')",
            "print('Success:', success.unwrap())",
            "print('Is ok:', success.is_ok())",
            "",
            "# Iterator operations",
            "data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
            "taken = collect(take(data, 5))",
            "print('First 5:', taken)",
            "folded = fold(data, 0, lambda acc, x: acc + x)",
            "print('Sum via fold:', folded)",
        ]
        
        for demo in demos:
            if demo.strip():
                print(f">>> {demo}")
                try:
                    self._execute_code(demo)
                except:
                    pass
            else:
                print()
    
    def _demo_all(self, args):
        """Demonstrate all features"""
        print("🌟 Demonstrating ALL Kaede Features:")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        self._demo_python(args)
        print()
        self._demo_cpp(args)  
        print()
        self._demo_rust(args)
        
        print("\n🎉 That's Kaede - Python + C++ + Rust in one language!")

# Main REPL entry point
def main():
    """Main entry point for Kaede REPL"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kaede REPL")
    parser.add_argument('--mode', choices=['development', 'production', 'debug'], 
                       default='development', help='Runtime mode')
    
    args = parser.parse_args()
    
    # Create runtime with specified mode
    runtime_mode = RuntimeMode(args.mode)
    runtime = KaedeRuntime(runtime_mode)
    
    # Create and run REPL
    repl = KaedeREPL(runtime)
    repl.run()

if __name__ == "__main__":
    main() 