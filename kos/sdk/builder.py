"""
KOS Build System - Project builder for C/C++/Python applications
"""

import os
import json
import shutil
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from .compiler import KOSCompiler, Language

@dataclass
class BuildConfig:
    """Build configuration for a KOS project"""
    name: str
    version: str = "1.0.0"
    language: Language = Language.C
    source_files: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    libraries: List[str] = field(default_factory=list)
    lib_dirs: List[str] = field(default_factory=list)
    compiler_flags: List[str] = field(default_factory=list)
    linker_flags: List[str] = field(default_factory=list)
    output_type: str = "executable"  # executable, library, module
    output_name: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "language": self.language.value,
            "source_files": self.source_files,
            "include_dirs": self.include_dirs,
            "libraries": self.libraries,
            "lib_dirs": self.lib_dirs,
            "compiler_flags": self.compiler_flags,
            "linker_flags": self.linker_flags,
            "output_type": self.output_type,
            "output_name": self.output_name,
            "dependencies": self.dependencies
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BuildConfig':
        """Create from dictionary"""
        data = data.copy()
        if 'language' in data:
            data['language'] = Language(data['language'])
        return cls(**data)

class KOSBuilder:
    """
    KOS Build System
    Manages building of C/C++/Python projects
    """
    
    def __init__(self):
        self.compiler = KOSCompiler()
        self.build_dir = "build"
        self.dist_dir = "dist"
        
    def load_project(self, config_file: str = "kos-project.json") -> Optional[BuildConfig]:
        """Load project configuration from file"""
        if not os.path.exists(config_file):
            return None
            
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                return BuildConfig.from_dict(data)
        except Exception as e:
            print(f"Error loading project config: {e}")
            return None
            
    def save_project(self, config: BuildConfig, config_file: str = "kos-project.json"):
        """Save project configuration to file"""
        with open(config_file, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)
            
    def init_project(self, name: str, language: Language = Language.C) -> BuildConfig:
        """Initialize a new project"""
        config = BuildConfig(
            name=name,
            language=language,
            source_files=[f"src/main.{language.value}"],
            include_dirs=["include"],
            output_name=name
        )
        
        # Create project structure
        os.makedirs("src", exist_ok=True)
        os.makedirs("include", exist_ok=True)
        os.makedirs(self.build_dir, exist_ok=True)
        
        # Save configuration
        self.save_project(config)
        
        return config
        
    def build(self, config: Optional[BuildConfig] = None) -> bool:
        """Build the project"""
        if config is None:
            config = self.load_project()
            if config is None:
                print("No project configuration found")
                return False
                
        print(f"Building {config.name} v{config.version}...")
        
        # Create build directory
        os.makedirs(self.build_dir, exist_ok=True)
        
        # Determine output file
        if config.output_name:
            output_file = os.path.join(self.build_dir, config.output_name)
        else:
            output_file = os.path.join(self.build_dir, config.name)
            
        # Build based on language
        if config.language == Language.PYTHON:
            return self._build_python(config, output_file)
        else:
            return self._build_compiled(config, output_file)
            
    def _build_compiled(self, config: BuildConfig, output_file: str) -> bool:
        """Build C/C++ project"""
        
        if config.output_type == "library":
            # Build as library
            return self._build_library(config, output_file)
        else:
            # Build as executable
            all_flags = config.compiler_flags + config.linker_flags
            
            success, message = self.compiler.compile(
                source_file=" ".join(config.source_files),
                output_file=output_file,
                language=config.language,
                flags=all_flags,
                libs=config.libraries,
                include_dirs=config.include_dirs,
                lib_dirs=config.lib_dirs
            )
            
            print(message)
            return success
            
    def _build_library(self, config: BuildConfig, output_file: str) -> bool:
        """Build as library"""
        # First compile to object files
        object_files = []
        
        for source_file in config.source_files:
            obj_file = os.path.join(self.build_dir, 
                                   os.path.basename(source_file).replace(f'.{config.language.value}', '.o'))
            
            # Compile to object file
            flags = config.compiler_flags + ["-c", "-fPIC"]
            success, message = self.compiler.compile(
                source_file=source_file,
                output_file=obj_file,
                language=config.language,
                flags=flags,
                include_dirs=config.include_dirs
            )
            
            if not success:
                print(f"Failed to compile {source_file}: {message}")
                return False
                
            object_files.append(obj_file)
            
        # Link into library
        lib_name = output_file + (".so" if not output_file.endswith(".so") else "")
        
        # Use compiler to create shared library
        compiler_type = self.compiler._get_compiler_for_language(config.language)
        compiler = self.compiler.compilers[compiler_type]
        
        cmd = [compiler, "-shared", "-o", lib_name] + object_files
        cmd.extend([f"-L{lib_dir}" for lib_dir in config.lib_dirs])
        cmd.extend([f"-l{lib}" for lib in config.libraries])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Successfully built library: {lib_name}")
                return True
            else:
                print(f"Library build failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"Build error: {e}")
            return False
            
    def _build_python(self, config: BuildConfig, output_file: str) -> bool:
        """Build Python project"""
        
        if config.output_type == "module":
            # Create Python module structure
            return self._build_python_module(config, output_file)
        else:
            # Create executable Python script
            return self._build_python_executable(config, output_file)
            
    def _build_python_module(self, config: BuildConfig, output_file: str) -> bool:
        """Build Python module"""
        module_dir = os.path.join(self.dist_dir, config.name)
        os.makedirs(module_dir, exist_ok=True)
        
        # Copy source files
        for source_file in config.source_files:
            if os.path.exists(source_file):
                dest = os.path.join(module_dir, os.path.basename(source_file))
                shutil.copy2(source_file, dest)
                
        # Create __init__.py
        init_file = os.path.join(module_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write(f'"""\\n{config.name} - KOS Python Module\\nVersion: {config.version}\\n"""\\n')
                
        print(f"Python module built in {module_dir}")
        return True
        
    def _build_python_executable(self, config: BuildConfig, output_file: str) -> bool:
        """Build Python executable"""
        
        # For single file, just copy and make executable
        if len(config.source_files) == 1:
            shutil.copy2(config.source_files[0], output_file)
            os.chmod(output_file, 0o755)
            
            # Add shebang if not present
            with open(output_file, 'r') as f:
                content = f.read()
                
            if not content.startswith('#!'):
                with open(output_file, 'w') as f:
                    f.write('#!/usr/bin/env python3\n')
                    f.write(content)
                    
        else:
            # Create a launcher script
            with open(output_file, 'w') as f:
                f.write('#!/usr/bin/env python3\n')
                f.write(f'"""\\n{config.name} - KOS Python Application\\n"""\\n\n')
                f.write('import sys\n')
                f.write('import os\n\n')
                f.write('# Add source directory to path\n')
                f.write('sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n\n')
                f.write(f'# Import and run main module\n')
                f.write(f'from {os.path.basename(config.source_files[0]).replace(".py", "")} import main\n')
                f.write('if __name__ == "__main__":\n')
                f.write('    main()\n')
                
            os.chmod(output_file, 0o755)
            
        print(f"Python executable built: {output_file}")
        return True
        
    def clean(self):
        """Clean build artifacts"""
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir)
            print(f"Cleaned {self.build_dir}")
            
        if os.path.exists(self.dist_dir):
            shutil.rmtree(self.dist_dir)
            print(f"Cleaned {self.dist_dir}")
            
    def install(self, config: Optional[BuildConfig] = None, prefix: str = "/usr/local"):
        """Install the built application"""
        if config is None:
            config = self.load_project()
            if config is None:
                print("No project configuration found")
                return False
                
        # Determine built file
        if config.output_name:
            built_file = os.path.join(self.build_dir, config.output_name)
        else:
            built_file = os.path.join(self.build_dir, config.name)
            
        if not os.path.exists(built_file):
            print(f"Built file {built_file} not found. Run build first.")
            return False
            
        # Install based on type
        if config.output_type == "executable":
            install_dir = os.path.join(prefix, "bin")
            os.makedirs(install_dir, exist_ok=True)
            install_path = os.path.join(install_dir, os.path.basename(built_file))
            shutil.copy2(built_file, install_path)
            os.chmod(install_path, 0o755)
            print(f"Installed executable to {install_path}")
            
        elif config.output_type == "library":
            install_dir = os.path.join(prefix, "lib")
            os.makedirs(install_dir, exist_ok=True)
            install_path = os.path.join(install_dir, os.path.basename(built_file))
            shutil.copy2(built_file, install_path)
            print(f"Installed library to {install_path}")
            
            # Install headers if present
            if os.path.exists("include"):
                include_dir = os.path.join(prefix, "include", config.name)
                shutil.copytree("include", include_dir, dirs_exist_ok=True)
                print(f"Installed headers to {include_dir}")
                
        return True