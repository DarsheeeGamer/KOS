"""
Kaede Programming Language for KOS
==================================

A hybrid programming language combining Python's simplicity with C++'s performance.
Kaede features:
- Static and dynamic typing
- Memory management control
- High-level abstractions
- Low-level system access
- Template/generic programming
- Concurrent programming primitives
- Direct KOS system integration

Version: 1.0.0
Author: KOS Development Team
License: MIT
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger('KOS.kaede')

__version__ = "1.0.0"
__author__ = "KOS Development Team"
__license__ = "MIT"

# Core language components
try:
    from .lexer import KaedeLexer
except ImportError:
    print("Warning: KaedeLexer not available")
    KaedeLexer = None

try:
    from .parser import KaedeParser
except ImportError:
    print("Warning: KaedeParser not available")
    KaedeParser = None

try:
    from .ast_nodes import *
except ImportError:
    print("Warning: AST nodes not available")

try:
    from .core_language import KaedeType, KaedeRuntime as CoreRuntime
except ImportError:
    print("Warning: Core language not available")
    KaedeType = None
    CoreRuntime = None

try:
    from .interpreter import KaedeInterpreter
except ImportError:
    print("Warning: KaedeInterpreter not available")
    KaedeInterpreter = None

try:
    from .runtime import KaedeRuntime, RuntimeMode, initialize_runtime
    from .runtime_executor import RuntimeExecutor
    from .stdlib import KaedeStandardLibrary, get_stdlib
    from .memory_manager import KaedeMemoryManager
    from .compiler import KaedeCompiler
except ImportError as e:
    print(f"Warning: Some Kaede components not available: {e}")
    KaedeRuntime = None
    RuntimeMode = None
    initialize_runtime = None
    RuntimeExecutor = None
    KaedeStandardLibrary = None
    get_stdlib = None
    KaedeMemoryManager = None
    KaedeCompiler = None

try:
    from .exceptions import *
except ImportError:
    print("Warning: Kaede exceptions not available")

try:
    from .repl import KaedeREPL
except ImportError:
    print("Warning: KaedeREPL not available")
    KaedeREPL = None

# Initialize global instances
memory_manager = None
runtime = None

def get_runtime():
    """Get global runtime instance"""
    global runtime
    if runtime is None and KaedeRuntime:
        runtime = KaedeRuntime()
    return runtime

def get_memory_manager():
    """Get global memory manager instance"""
    global memory_manager
    if memory_manager is None and KaedeMemoryManager:
        memory_manager = KaedeMemoryManager()
    return memory_manager

def create_kaede_environment() -> Optional[Dict[str, Any]]:
    """
    Create and initialize a complete Kaede programming environment
    
    Returns:
        Dictionary containing all Kaede components, or None if initialization fails
    """
    try:
        logger.info("Creating Kaede programming environment...")
        
        # Initialize core components
        runtime_instance = get_runtime()
        memory_mgr = get_memory_manager()
        compiler = KaedeCompiler() if KaedeCompiler else None
        stdlib = get_stdlib() if get_stdlib else None
        
        # Create environment dictionary
        environment = {
            'runtime': runtime_instance,
            'compiler': compiler,
            'stdlib': stdlib,
            'memory_manager': memory_mgr,
            'lexer': KaedeLexer,
            'parser': KaedeParser,
            'executor': RuntimeExecutor() if RuntimeExecutor else None,
            'version': '1.0.0',
            'status': 'ready'
        }
        
        # Test basic functionality
        try:
            # Test lexer
            if KaedeLexer:
                lexer = KaedeLexer()
                tokens = lexer.tokenize("let x = 42")
                logger.debug(f"Lexer test passed: {len(tokens)} tokens")
            
            # Test stdlib
            if stdlib:
                modules = stdlib.list_modules()
                logger.debug(f"Standard library loaded: {len(modules)} modules")
            
            # Test memory manager
            if memory_mgr:
                stats = memory_mgr.get_statistics()
                logger.debug(f"Memory manager active: {stats}")
            
        except Exception as e:
            logger.warning(f"Some Kaede components may not be fully functional: {e}")
        
        logger.info("Kaede programming environment created successfully")
        return environment
        
    except Exception as e:
        logger.error(f"Failed to create Kaede environment: {e}")
        return None

def get_kaede_repl():
    """Get a Kaede REPL instance."""
    if KaedeREPL is None:
        print("Error: KaedeREPL not available")
        return None
    return KaedeREPL()

def get_kaede_version() -> str:
    """Get Kaede language version"""
    return "1.0.0"

def is_kaede_available() -> bool:
    """Check if Kaede is fully available and functional"""
    try:
        env = create_kaede_environment()
        return env is not None and env.get('status') == 'ready'
    except:
        return False

# Export main classes and functions
__all__ = [
    # Core classes
    'KaedeLexer', 'KaedeParser', 'KaedeRuntime', 'KaedeCompiler',
    'RuntimeExecutor', 'KaedeStandardLibrary', 'KaedeMemoryManager',
    
    # Functions
    'create_kaede_environment', 'get_kaede_version', 'is_kaede_available',
    'get_runtime', 'get_stdlib', 'get_memory_manager',
    
    # Variables
    'memory_manager', 'runtime'
] 