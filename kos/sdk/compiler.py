"""
KOS Compiler Interface - Supports C, C++, and Python compilation
"""

import os
import subprocess
import shutil
import tempfile
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path

class Language(Enum):
    """Supported programming languages"""
    C = "c"
    CPP = "cpp"
    PYTHON = "python"

class CompilerType(Enum):
    """Available compilers"""
    GCC = "gcc"
    CLANG = "clang"
    GPP = "g++"
    CLANGPP = "clang++"
    PYTHON = "python3"

class KOSCompiler:
    """
    KOS Compiler for building applications
    Supports C, C++, and Python
    """
    
    def __init__(self):
        self.compilers = self._detect_compilers()
        self.default_flags = {
            Language.C: ["-Wall", "-Wextra", "-O2", "-std=c11"],
            Language.CPP: ["-Wall", "-Wextra", "-O2", "-std=c++17"],
            Language.PYTHON: []
        }
        
        # KOS specific include paths
        self.kos_includes = [
            "/usr/include/kos",
            "/usr/local/include/kos"
        ]
        
        # KOS specific libraries
        self.kos_libs = [
            "kosrt",  # KOS runtime library
            "kosapi"  # KOS API library
        ]
        
    def _detect_compilers(self) -> Dict[CompilerType, Optional[str]]:
        """Detect available compilers on the system"""
        compilers = {}
        
        # Check for C compilers
        for compiler in ["gcc", "clang"]:
            if shutil.which(compiler):
                compilers[CompilerType.GCC if compiler == "gcc" else CompilerType.CLANG] = compiler
                
        # Check for C++ compilers
        for compiler in ["g++", "clang++"]:
            if shutil.which(compiler):
                compilers[CompilerType.GPP if compiler == "g++" else CompilerType.CLANGPP] = compiler
                
        # Python is always available in KOS
        compilers[CompilerType.PYTHON] = "python3"
        
        return compilers
        
    def compile(self, source_file: str, output_file: Optional[str] = None,
                language: Optional[Language] = None,
                flags: Optional[List[str]] = None,
                libs: Optional[List[str]] = None,
                include_dirs: Optional[List[str]] = None,
                lib_dirs: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Compile a source file
        
        Args:
            source_file: Path to source file
            output_file: Output executable path (optional)
            language: Programming language (auto-detected if not specified)
            flags: Additional compiler flags
            libs: Additional libraries to link
            include_dirs: Additional include directories
            lib_dirs: Additional library directories
            
        Returns:
            (success, message) tuple
        """
        
        # Auto-detect language if not specified
        if language is None:
            language = self._detect_language(source_file)
            if language is None:
                return False, f"Cannot detect language for {source_file}"
                
        # For Python, just check syntax
        if language == Language.PYTHON:
            return self._compile_python(source_file, output_file)
            
        # Select compiler
        compiler_type = self._get_compiler_for_language(language)
        if compiler_type not in self.compilers:
            return False, f"No compiler available for {language.value}"
            
        compiler = self.compilers[compiler_type]
        
        # Build command
        cmd = [compiler]
        
        # Add default flags
        cmd.extend(self.default_flags[language])
        
        # Add custom flags
        if flags:
            cmd.extend(flags)
            
        # Add include directories
        for inc_dir in self.kos_includes:
            if os.path.exists(inc_dir):
                cmd.extend(["-I", inc_dir])
                
        if include_dirs:
            for inc_dir in include_dirs:
                cmd.extend(["-I", inc_dir])
                
        # Add source file
        cmd.append(source_file)
        
        # Add output file
        if output_file:
            cmd.extend(["-o", output_file])
        else:
            # Default output name
            base_name = os.path.splitext(os.path.basename(source_file))[0]
            output_file = base_name
            cmd.extend(["-o", output_file])
            
        # Add library directories
        if lib_dirs:
            for lib_dir in lib_dirs:
                cmd.extend(["-L", lib_dir])
                
        # Add libraries
        for lib in self.kos_libs:
            cmd.extend(["-l", lib])
            
        if libs:
            for lib in libs:
                cmd.extend(["-l", lib])
                
        # Execute compilation
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True, f"Successfully compiled to {output_file}"
            else:
                return False, f"Compilation failed:\n{result.stderr}"
        except Exception as e:
            return False, f"Compilation error: {str(e)}"
            
    def _compile_python(self, source_file: str, output_file: Optional[str]) -> Tuple[bool, str]:
        """Compile Python file (syntax check and optional bytecode generation)"""
        try:
            # Check syntax
            with open(source_file, 'r') as f:
                code = f.read()
                
            compile(code, source_file, 'exec')
            
            # Optionally create bytecode
            if output_file and output_file.endswith('.pyc'):
                import py_compile
                py_compile.compile(source_file, output_file)
                
            return True, f"Python file {source_file} is valid"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Error: {e}"
            
    def _detect_language(self, source_file: str) -> Optional[Language]:
        """Detect language from file extension"""
        ext = os.path.splitext(source_file)[1].lower()
        
        if ext in ['.c']:
            return Language.C
        elif ext in ['.cpp', '.cc', '.cxx', '.c++']:
            return Language.CPP
        elif ext in ['.py']:
            return Language.PYTHON
            
        return None
        
    def _get_compiler_for_language(self, language: Language) -> Optional[CompilerType]:
        """Get appropriate compiler for language"""
        if language == Language.C:
            # Prefer GCC, fallback to Clang
            if CompilerType.GCC in self.compilers:
                return CompilerType.GCC
            elif CompilerType.CLANG in self.compilers:
                return CompilerType.CLANG
        elif language == Language.CPP:
            # Prefer G++, fallback to Clang++
            if CompilerType.GPP in self.compilers:
                return CompilerType.GPP
            elif CompilerType.CLANGPP in self.compilers:
                return CompilerType.CLANGPP
        elif language == Language.PYTHON:
            return CompilerType.PYTHON
            
        return None
        
    def create_makefile(self, project_name: str, source_files: List[str],
                       language: Language, output_file: str,
                       additional_flags: Optional[List[str]] = None) -> str:
        """Generate a Makefile for the project"""
        
        compiler_type = self._get_compiler_for_language(language)
        if not compiler_type or compiler_type not in self.compilers:
            raise ValueError(f"No compiler available for {language.value}")
            
        compiler = self.compilers[compiler_type]
        
        makefile_content = f"""# Makefile for {project_name}
# Generated by KOS SDK

CC = {compiler}
CFLAGS = {' '.join(self.default_flags[language])}
"""
        
        if additional_flags:
            makefile_content += f"CFLAGS += {' '.join(additional_flags)}\n"
            
        makefile_content += f"""
INCLUDES = {' '.join([f'-I{inc}' for inc in self.kos_includes if os.path.exists(inc)])}
LIBS = {' '.join([f'-l{lib}' for lib in self.kos_libs])}
TARGET = {output_file}
SOURCES = {' '.join(source_files)}
OBJECTS = $(SOURCES:.{language.value}=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
\t$(CC) $(CFLAGS) $(INCLUDES) -o $@ $^ $(LIBS)

%.o: %.{language.value}
\t$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

clean:
\trm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
"""
        
        return makefile_content