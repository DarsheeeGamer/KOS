"""
KOS Platform Compatibility Layer
===============================

Provides cross-platform compatibility for Kaede applications, enabling:
- Platform-specific code generation
- API abstraction across different operating systems
- Runtime adaptation for different environments
- Library and dependency management
- System call translation
"""

import os
import sys
import platform
import subprocess
import tempfile
import shutil
import logging
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
import importlib.util
import ctypes
import struct

logger = logging.getLogger('KOS.core.platform_compat')

class PlatformType(Enum):
    """Platform types"""
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"
    BSD = "bsd"
    ANDROID = "android"
    IOS = "ios"
    EMBEDDED = "embedded"

class ArchitectureType(Enum):
    """Architecture types"""
    X86_64 = "x86_64"
    X86_32 = "x86_32"
    ARM64 = "arm64"
    ARM32 = "arm32"
    RISCV64 = "riscv64"
    RISCV32 = "riscv32"
    MIPS = "mips"
    POWERPC = "powerpc"

class LibraryType(Enum):
    """Library types"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    HEADER_ONLY = "header_only"
    PYTHON_MODULE = "python_module"
    NATIVE_MODULE = "native_module"

@dataclass
class PlatformInfo:
    """Platform information"""
    platform: PlatformType
    architecture: ArchitectureType
    version: str
    kernel_version: str
    libc_version: str
    python_version: str
    available_compilers: List[str]
    library_paths: List[str]
    executable_formats: List[str]
    
class SystemCallTranslator:
    """Translates system calls between platforms"""
    
    def __init__(self, target_platform: PlatformType):
        self.target_platform = target_platform
        self.syscall_map = self._build_syscall_map()
    
    def _build_syscall_map(self) -> Dict[str, Dict[PlatformType, Any]]:
        """Build system call mapping table"""
        return {
            # File operations
            'open': {
                PlatformType.LINUX: self._linux_open,
                PlatformType.WINDOWS: self._windows_open,
                PlatformType.MACOS: self._macos_open,
            },
            'read': {
                PlatformType.LINUX: self._linux_read,
                PlatformType.WINDOWS: self._windows_read,
                PlatformType.MACOS: self._macos_read,
            },
            'write': {
                PlatformType.LINUX: self._linux_write,
                PlatformType.WINDOWS: self._windows_write,
                PlatformType.MACOS: self._macos_write,
            },
            'close': {
                PlatformType.LINUX: self._linux_close,
                PlatformType.WINDOWS: self._windows_close,
                PlatformType.MACOS: self._macos_close,
            },
            
            # Memory operations
            'malloc': {
                PlatformType.LINUX: self._linux_malloc,
                PlatformType.WINDOWS: self._windows_malloc,
                PlatformType.MACOS: self._macos_malloc,
            },
            'free': {
                PlatformType.LINUX: self._linux_free,
                PlatformType.WINDOWS: self._windows_free,
                PlatformType.MACOS: self._macos_free,
            },
            
            # Process operations
            'fork': {
                PlatformType.LINUX: self._linux_fork,
                PlatformType.WINDOWS: self._windows_create_process,
                PlatformType.MACOS: self._macos_fork,
            },
            'exec': {
                PlatformType.LINUX: self._linux_exec,
                PlatformType.WINDOWS: self._windows_exec,
                PlatformType.MACOS: self._macos_exec,
            },
            
            # Threading operations
            'thread_create': {
                PlatformType.LINUX: self._linux_pthread_create,
                PlatformType.WINDOWS: self._windows_create_thread,
                PlatformType.MACOS: self._macos_pthread_create,
            },
            
            # Network operations
            'socket': {
                PlatformType.LINUX: self._linux_socket,
                PlatformType.WINDOWS: self._windows_socket,
                PlatformType.MACOS: self._macos_socket,
            },
        }
    
    def translate_syscall(self, syscall_name: str, *args, **kwargs) -> Any:
        """Translate and execute system call for target platform"""
        if syscall_name not in self.syscall_map:
            raise NotImplementedError(f"System call '{syscall_name}' not supported")
        
        platform_map = self.syscall_map[syscall_name]
        if self.target_platform not in platform_map:
            raise NotImplementedError(f"System call '{syscall_name}' not implemented for {self.target_platform}")
        
        func = platform_map[self.target_platform]
        return func(*args, **kwargs)
    
    # Linux system call implementations
    def _linux_open(self, path: str, flags: int, mode: int = 0o644) -> int:
        """Linux open system call"""
        return os.open(path, flags, mode)
    
    def _linux_read(self, fd: int, size: int) -> bytes:
        """Linux read system call"""
        return os.read(fd, size)
    
    def _linux_write(self, fd: int, data: bytes) -> int:
        """Linux write system call"""
        return os.write(fd, data)
    
    def _linux_close(self, fd: int) -> None:
        """Linux close system call"""
        os.close(fd)
    
    def _linux_malloc(self, size: int) -> int:
        """Linux malloc wrapper"""
        # Use ctypes to interface with libc
        libc = ctypes.CDLL("libc.so.6")
        return libc.malloc(size)
    
    def _linux_free(self, ptr: int) -> None:
        """Linux free wrapper"""
        libc = ctypes.CDLL("libc.so.6")
        libc.free(ptr)
    
    def _linux_fork(self) -> int:
        """Linux fork system call"""
        return os.fork()
    
    def _linux_exec(self, path: str, args: List[str], env: Dict[str, str] = None) -> None:
        """Linux exec system call"""
        if env:
            os.execve(path, args, env)
        else:
            os.execv(path, args)
    
    def _linux_pthread_create(self, func: Callable, args: Tuple = ()) -> int:
        """Linux pthread_create wrapper"""
        import threading
        thread = threading.Thread(target=func, args=args)
        thread.start()
        return thread.ident
    
    def _linux_socket(self, family: int, type_: int, proto: int = 0) -> int:
        """Linux socket system call"""
        import socket
        sock = socket.socket(family, type_, proto)
        return sock.fileno()
    
    # Windows system call implementations
    def _windows_open(self, path: str, flags: int, mode: int = 0o644) -> int:
        """Windows open implementation"""
        # Convert Unix flags to Windows flags
        win_flags = 0
        if flags & os.O_RDONLY:
            win_flags |= os.O_RDONLY
        if flags & os.O_WRONLY:
            win_flags |= os.O_WRONLY
        if flags & os.O_RDWR:
            win_flags |= os.O_RDWR
        if flags & os.O_CREAT:
            win_flags |= os.O_CREAT
        
        return os.open(path, win_flags, mode)
    
    def _windows_read(self, fd: int, size: int) -> bytes:
        """Windows read implementation"""
        return os.read(fd, size)
    
    def _windows_write(self, fd: int, data: bytes) -> int:
        """Windows write implementation"""
        return os.write(fd, data)
    
    def _windows_close(self, fd: int) -> None:
        """Windows close implementation"""
        os.close(fd)
    
    def _windows_malloc(self, size: int) -> int:
        """Windows malloc wrapper"""
        kernel32 = ctypes.windll.kernel32
        return kernel32.GlobalAlloc(0, size)
    
    def _windows_free(self, ptr: int) -> None:
        """Windows free wrapper"""
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalFree(ptr)
    
    def _windows_create_process(self) -> int:
        """Windows CreateProcess (fork equivalent)"""
        # Windows doesn't have fork, use CreateProcess instead
        import subprocess
        # This is a simplified implementation
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        return proc.pid
    
    def _windows_exec(self, path: str, args: List[str], env: Dict[str, str] = None) -> None:
        """Windows exec implementation"""
        if env:
            os.execve(path, args, env)
        else:
            os.execv(path, args)
    
    def _windows_create_thread(self, func: Callable, args: Tuple = ()) -> int:
        """Windows CreateThread wrapper"""
        import threading
        thread = threading.Thread(target=func, args=args)
        thread.start()
        return thread.ident
    
    def _windows_socket(self, family: int, type_: int, proto: int = 0) -> int:
        """Windows socket implementation"""
        import socket
        sock = socket.socket(family, type_, proto)
        return sock.fileno()
    
    # macOS system call implementations (similar to Linux for most calls)
    def _macos_open(self, path: str, flags: int, mode: int = 0o644) -> int:
        return self._linux_open(path, flags, mode)
    
    def _macos_read(self, fd: int, size: int) -> bytes:
        return self._linux_read(fd, size)
    
    def _macos_write(self, fd: int, data: bytes) -> int:
        return self._linux_write(fd, data)
    
    def _macos_close(self, fd: int) -> None:
        return self._linux_close(fd)
    
    def _macos_malloc(self, size: int) -> int:
        libc = ctypes.CDLL("libc.dylib")
        return libc.malloc(size)
    
    def _macos_free(self, ptr: int) -> None:
        libc = ctypes.CDLL("libc.dylib")
        libc.free(ptr)
    
    def _macos_fork(self) -> int:
        return self._linux_fork()
    
    def _macos_exec(self, path: str, args: List[str], env: Dict[str, str] = None) -> None:
        return self._linux_exec(path, args, env)
    
    def _macos_pthread_create(self, func: Callable, args: Tuple = ()) -> int:
        return self._linux_pthread_create(func, args)
    
    def _macos_socket(self, family: int, type_: int, proto: int = 0) -> int:
        return self._linux_socket(family, type_, proto)

class LibraryManager:
    """Manages platform-specific libraries and dependencies"""
    
    def __init__(self, platform_info: PlatformInfo):
        self.platform_info = platform_info
        self.library_cache = {}
        self.dependency_graph = {}
        
    def find_library(self, library_name: str, library_type: LibraryType = None) -> Optional[str]:
        """Find library on the system"""
        if library_name in self.library_cache:
            return self.library_cache[library_name]
        
        # Check standard library paths
        search_paths = self.platform_info.library_paths + [
            "/usr/lib", "/usr/local/lib", "/lib",
            "/usr/lib64", "/usr/local/lib64", "/lib64"
        ]
        
        # Platform-specific library extensions
        extensions = self._get_library_extensions()
        
        for search_path in search_paths:
            if not os.path.exists(search_path):
                continue
                
            for ext in extensions:
                full_name = f"{library_name}{ext}"
                lib_path = os.path.join(search_path, full_name)
                
                if os.path.exists(lib_path):
                    self.library_cache[library_name] = lib_path
                    return lib_path
        
        return None
    
    def _get_library_extensions(self) -> List[str]:
        """Get platform-specific library extensions"""
        if self.platform_info.platform == PlatformType.WINDOWS:
            return [".dll", ".lib"]
        elif self.platform_info.platform == PlatformType.MACOS:
            return [".dylib", ".a", ".so"]
        else:
            return [".so", ".a"]
    
    def load_library(self, library_path: str) -> Any:
        """Load dynamic library"""
        try:
            if self.platform_info.platform == PlatformType.WINDOWS:
                return ctypes.CDLL(library_path)
            else:
                return ctypes.CDLL(library_path)
        except Exception as e:
            logger.error(f"Failed to load library {library_path}: {e}")
            return None
    
    def resolve_dependencies(self, library_name: str) -> List[str]:
        """Resolve library dependencies"""
        if library_name in self.dependency_graph:
            return self.dependency_graph[library_name]
        
        library_path = self.find_library(library_name)
        if not library_path:
            return []
        
        dependencies = []
        
        try:
            if self.platform_info.platform in [PlatformType.LINUX, PlatformType.MACOS]:
                # Use ldd to find dependencies
                result = subprocess.run(
                    ["ldd", library_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if '=>' in line:
                            parts = line.strip().split('=>')
                            if len(parts) > 1:
                                dep_path = parts[1].strip().split()[0]
                                if dep_path and dep_path != '(0x':
                                    dependencies.append(dep_path)
            
            elif self.platform_info.platform == PlatformType.WINDOWS:
                # Use dumpbin or similar tool for Windows
                pass
                
        except Exception as e:
            logger.warning(f"Failed to resolve dependencies for {library_name}: {e}")
        
        self.dependency_graph[library_name] = dependencies
        return dependencies

class CodeGenerator:
    """Generates platform-specific code"""
    
    def __init__(self, platform_info: PlatformInfo):
        self.platform_info = platform_info
        self.syscall_translator = SystemCallTranslator(platform_info.platform)
    
    def generate_platform_wrapper(self, kaede_code: str) -> str:
        """Generate platform-specific wrapper for Kaede code"""
        wrapper_template = self._get_wrapper_template()
        
        # Replace placeholders with platform-specific code
        wrapper_code = wrapper_template.format(
            platform=self.platform_info.platform.value,
            architecture=self.platform_info.architecture.value,
            kaede_code=kaede_code,
            platform_init=self._generate_platform_init(),
            platform_cleanup=self._generate_platform_cleanup()
        )
        
        return wrapper_code
    
    def _get_wrapper_template(self) -> str:
        """Get platform-specific wrapper template"""
        return """
// Platform: {platform}
// Architecture: {architecture}
// Generated by KOS Platform Compatibility Layer

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

{platform_init}

// Kaede runtime integration
int main(int argc, char* argv[]) {{
    // Initialize platform-specific components
    platform_init();
    
    // Execute Kaede code
    {kaede_code}
    
    // Cleanup
    {platform_cleanup}
    
    return 0;
}}

{platform_cleanup}
"""
    
    def _generate_platform_init(self) -> str:
        """Generate platform-specific initialization code"""
        if self.platform_info.platform == PlatformType.WINDOWS:
            return """
void platform_init() {
    // Windows-specific initialization
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
}
"""
        elif self.platform_info.platform == PlatformType.MACOS:
            return """
void platform_init() {
    // macOS-specific initialization
    setlocale(LC_ALL, "");
}
"""
        else:
            return """
void platform_init() {
    // Linux/Unix-specific initialization
    setlocale(LC_ALL, "");
}
"""
    
    def _generate_platform_cleanup(self) -> str:
        """Generate platform-specific cleanup code"""
        return """
void platform_cleanup() {
    // Platform-specific cleanup
}
"""
    
    def generate_build_script(self, source_files: List[str], output_name: str) -> str:
        """Generate platform-specific build script"""
        if self.platform_info.platform == PlatformType.WINDOWS:
            return self._generate_windows_build_script(source_files, output_name)
        else:
            return self._generate_unix_build_script(source_files, output_name)
    
    def _generate_windows_build_script(self, source_files: List[str], output_name: str) -> str:
        """Generate Windows batch build script"""
        script = "@echo off\n"
        script += "echo Building for Windows...\n"
        
        # Find available compiler
        if "gcc" in self.platform_info.available_compilers:
            compiler = "gcc"
        elif "clang" in self.platform_info.available_compilers:
            compiler = "clang"
        elif "cl" in self.platform_info.available_compilers:
            compiler = "cl"
        else:
            compiler = "gcc"  # Default
        
        if compiler == "cl":
            # MSVC compiler
            script += f"cl /Fe:{output_name}.exe " + " ".join(source_files) + "\n"
        else:
            # GCC/Clang
            script += f"{compiler} -o {output_name}.exe " + " ".join(source_files) + "\n"
        
        script += "echo Build complete.\n"
        return script
    
    def _generate_unix_build_script(self, source_files: List[str], output_name: str) -> str:
        """Generate Unix shell build script"""
        script = "#!/bin/bash\n"
        script += "echo Building for Unix/Linux...\n"
        
        # Find available compiler
        if "gcc" in self.platform_info.available_compilers:
            compiler = "gcc"
        elif "clang" in self.platform_info.available_compilers:
            compiler = "clang"
        else:
            compiler = "gcc"  # Default
        
        # Compiler flags
        flags = ["-std=c99", "-O2"]
        
        if self.platform_info.platform == PlatformType.LINUX:
            flags.extend(["-D_GNU_SOURCE", "-pthread"])
        elif self.platform_info.platform == PlatformType.MACOS:
            flags.extend(["-D_DARWIN_C_SOURCE"])
        
        script += f"{compiler} {' '.join(flags)} -o {output_name} " + " ".join(source_files) + "\n"
        script += "echo Build complete.\n"
        return script

class PlatformCompatibilityLayer:
    """Main platform compatibility layer"""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.syscall_translator = SystemCallTranslator(self.platform_info.platform)
        self.library_manager = LibraryManager(self.platform_info)
        self.code_generator = CodeGenerator(self.platform_info)
        
    def _detect_platform(self) -> PlatformInfo:
        """Detect current platform information"""
        system = platform.system().lower()
        
        if system == "linux":
            platform_type = PlatformType.LINUX
        elif system == "windows":
            platform_type = PlatformType.WINDOWS
        elif system == "darwin":
            platform_type = PlatformType.MACOS
        elif "bsd" in system:
            platform_type = PlatformType.BSD
        else:
            platform_type = PlatformType.LINUX  # Default
        
        # Detect architecture
        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            arch = ArchitectureType.X86_64
        elif machine == "i386":
            arch = ArchitectureType.X86_32
        elif machine in ["arm64", "aarch64"]:
            arch = ArchitectureType.ARM64
        elif machine.startswith("arm"):
            arch = ArchitectureType.ARM32
        elif machine.startswith("riscv64"):
            arch = ArchitectureType.RISCV64
        elif machine.startswith("riscv"):
            arch = ArchitectureType.RISCV32
        else:
            arch = ArchitectureType.X86_64  # Default
        
        # Detect available compilers
        compilers = []
        for compiler in ["gcc", "clang", "cl", "icc"]:
            if self._check_executable(compiler):
                compilers.append(compiler)
        
        # Detect library paths
        library_paths = []
        if platform_type == PlatformType.WINDOWS:
            library_paths = [
                "C:\\Windows\\System32",
                "C:\\Windows\\SysWOW64",
                "C:\\Program Files\\Common Files"
            ]
        else:
            library_paths = [
                "/usr/lib", "/usr/local/lib", "/lib",
                "/usr/lib64", "/usr/local/lib64", "/lib64"
            ]
        
        # Filter existing paths
        library_paths = [path for path in library_paths if os.path.exists(path)]
        
        # Detect executable formats
        executable_formats = []
        if platform_type == PlatformType.WINDOWS:
            executable_formats = ["PE", "PE32+"]
        elif platform_type == PlatformType.MACOS:
            executable_formats = ["Mach-O"]
        else:
            executable_formats = ["ELF"]
        
        return PlatformInfo(
            platform=platform_type,
            architecture=arch,
            version=platform.version(),
            kernel_version=platform.release(),
            libc_version=self._get_libc_version(),
            python_version=platform.python_version(),
            available_compilers=compilers,
            library_paths=library_paths,
            executable_formats=executable_formats
        )
    
    def _check_executable(self, name: str) -> bool:
        """Check if executable is available"""
        try:
            subprocess.run(
                [name, "--version"],
                capture_output=True,
                timeout=5
            )
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _get_libc_version(self) -> str:
        """Get libc version"""
        try:
            if self.platform_info.platform == PlatformType.LINUX:
                # Try to get glibc version
                result = subprocess.run(
                    ["ldd", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    if lines:
                        return lines[0]
            
        except Exception:
            pass
        
        return "unknown"
    
    def adapt_kaede_for_platform(self, kaede_code: str, target_platform: PlatformType = None) -> str:
        """Adapt Kaede code for specific platform"""
        if target_platform is None:
            target_platform = self.platform_info.platform
        
        # Generate platform-specific wrapper
        wrapper_code = self.code_generator.generate_platform_wrapper(kaede_code)
        
        # Apply platform-specific transformations
        adapted_code = self._apply_platform_transformations(wrapper_code, target_platform)
        
        return adapted_code
    
    def _apply_platform_transformations(self, code: str, target_platform: PlatformType) -> str:
        """Apply platform-specific code transformations"""
        # This would contain actual transformation logic
        # For now, return the code as-is
        return code
    
    def compile_for_platform(self, source_code: str, output_name: str, target_platform: PlatformType = None) -> bool:
        """Compile code for specific platform"""
        if target_platform is None:
            target_platform = self.platform_info.platform
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Write source code
                source_file = temp_path / "main.c"
                source_file.write_text(source_code)
                
                # Generate build script
                build_script_content = self.code_generator.generate_build_script(
                    [str(source_file)], output_name
                )
                
                # Write and execute build script
                if target_platform == PlatformType.WINDOWS:
                    build_script = temp_path / "build.bat"
                    build_script.write_text(build_script_content)
                    result = subprocess.run(
                        ["cmd", "/c", str(build_script)],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True
                    )
                else:
                    build_script = temp_path / "build.sh"
                    build_script.write_text(build_script_content)
                    build_script.chmod(0o755)
                    result = subprocess.run(
                        ["bash", str(build_script)],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True
                    )
                
                if result.returncode == 0:
                    # Copy output file
                    output_ext = ".exe" if target_platform == PlatformType.WINDOWS else ""
                    output_file = temp_path / f"{output_name}{output_ext}"
                    
                    if output_file.exists():
                        shutil.copy2(output_file, f"{output_name}{output_ext}")
                        return True
                
                logger.error(f"Compilation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Compilation error: {e}")
            return False
    
    def get_platform_info(self) -> PlatformInfo:
        """Get platform information"""
        return self.platform_info
    
    def translate_syscall(self, syscall_name: str, *args, **kwargs) -> Any:
        """Translate system call for current platform"""
        return self.syscall_translator.translate_syscall(syscall_name, *args, **kwargs)
    
    def find_library(self, library_name: str) -> Optional[str]:
        """Find library on current platform"""
        return self.library_manager.find_library(library_name)
    
    def load_library(self, library_path: str) -> Any:
        """Load library on current platform"""
        return self.library_manager.load_library(library_path)

# Global instance
_compat_layer = None

def get_platform_compatibility_layer() -> PlatformCompatibilityLayer:
    """Get the global platform compatibility layer"""
    global _compat_layer
    if _compat_layer is None:
        _compat_layer = PlatformCompatibilityLayer()
    return _compat_layer

# Convenience functions
def get_current_platform() -> PlatformInfo:
    """Get current platform information"""
    return get_platform_compatibility_layer().get_platform_info()

def adapt_kaede_code(kaede_code: str, target_platform: PlatformType = None) -> str:
    """Adapt Kaede code for target platform"""
    return get_platform_compatibility_layer().adapt_kaede_for_platform(kaede_code, target_platform)

def compile_kaede_for_platform(source_code: str, output_name: str, target_platform: PlatformType = None) -> bool:
    """Compile Kaede code for target platform"""
    return get_platform_compatibility_layer().compile_for_platform(source_code, output_name, target_platform)

__all__ = [
    'PlatformType', 'ArchitectureType', 'LibraryType',
    'PlatformInfo', 'SystemCallTranslator', 'LibraryManager', 'CodeGenerator',
    'PlatformCompatibilityLayer', 'get_platform_compatibility_layer',
    'get_current_platform', 'adapt_kaede_code', 'compile_kaede_for_platform'
]