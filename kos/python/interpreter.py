"""
Python Interpreter Integration for KOS
Provides full Python runtime with VFS isolation and pip support
"""

import sys
import os
import io
import ast
import code
import types
import importlib
import importlib.util
import importlib.machinery
import zipfile
import json
import subprocess
import tempfile
import shutil
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import builtins
import traceback

class VFSImporter:
    """Import hook for VFS-based modules"""
    
    def __init__(self, vfs, python_env):
        self.vfs = vfs
        self.python_env = python_env
        self.module_cache = {}
    
    def find_spec(self, fullname, path, target=None):
        """Find module spec in VFS"""
        # Convert module name to path
        module_path = fullname.replace('.', '/')
        
        # Check for package
        package_path = f"/usr/lib/python/{module_path}/__init__.py"
        if self.vfs.exists(package_path):
            return self._create_spec(fullname, package_path, is_package=True)
        
        # Check for module
        module_file = f"/usr/lib/python/{module_path}.py"
        if self.vfs.exists(module_file):
            return self._create_spec(fullname, module_file, is_package=False)
        
        # Check in site-packages
        for site_dir in ["/usr/lib/python/site-packages", "/usr/local/lib/python/site-packages"]:
            package_path = f"{site_dir}/{module_path}/__init__.py"
            if self.vfs.exists(package_path):
                return self._create_spec(fullname, package_path, is_package=True)
            
            module_file = f"{site_dir}/{module_path}.py"
            if self.vfs.exists(module_file):
                return self._create_spec(fullname, module_file, is_package=False)
        
        return None
    
    def _create_spec(self, fullname, path, is_package):
        """Create module spec"""
        loader = VFSLoader(self.vfs, path, is_package)
        spec = importlib.machinery.ModuleSpec(
            fullname,
            loader,
            origin=path,
            is_package=is_package
        )
        if is_package:
            spec.submodule_search_locations = [os.path.dirname(path)]
        return spec

class VFSLoader:
    """Loader for VFS-based modules"""
    
    def __init__(self, vfs, path, is_package):
        self.vfs = vfs
        self.path = path
        self.is_package = is_package
    
    def create_module(self, spec):
        """Create module object"""
        return None  # Use default module creation
    
    def exec_module(self, module):
        """Execute module code"""
        # Read source from VFS
        with self.vfs.open(self.path, 'r') as f:
            source = f.read()
            if isinstance(source, bytes):
                source = source.decode('utf-8')
        
        # Compile and execute
        code = compile(source, self.path, 'exec')
        
        # Set module attributes
        module.__file__ = self.path
        if self.is_package:
            module.__path__ = [os.path.dirname(self.path)]
            module.__package__ = module.__name__
        else:
            module.__package__ = module.__name__.rpartition('.')[0]
        
        # Execute in module namespace
        exec(code, module.__dict__)

class VFSPipInstaller:
    """Pip installer for VFS"""
    
    def __init__(self, vfs, python_env):
        self.vfs = vfs
        self.python_env = python_env
        self.packages_dir = "/usr/lib/python/site-packages"
        self.pip_cache = "/var/cache/pip"
        self.installed_packages = {}
        
        self._init_pip()
    
    def _init_pip(self):
        """Initialize pip in VFS"""
        # Create directories
        for dir_path in [self.packages_dir, self.pip_cache, "/var/lib/pip"]:
            if not self.vfs.exists(dir_path):
                self.vfs.mkdir(dir_path)
        
        # Load installed packages database
        db_file = "/var/lib/pip/installed.json"
        if self.vfs.exists(db_file):
            try:
                with self.vfs.open(db_file, 'r') as f:
                    self.installed_packages = json.loads(f.read().decode())
            except:
                self.installed_packages = {}
    
    def install(self, package_name: str, version: Optional[str] = None,
                upgrade: bool = False, dependencies: bool = True) -> bool:
        """Install Python package to VFS"""
        try:
            # Create temp directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                # Construct pip command
                cmd = [sys.executable, '-m', 'pip', 'download', 
                       '--dest', temp_dir, '--no-deps']
                
                if version:
                    cmd.append(f"{package_name}=={version}")
                else:
                    cmd.append(package_name)
                
                # Download package
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Failed to download {package_name}: {result.stderr}")
                    return False
                
                # Find downloaded file
                files = list(Path(temp_dir).glob('*.whl')) + list(Path(temp_dir).glob('*.tar.gz'))
                if not files:
                    print(f"No package file found for {package_name}")
                    return False
                
                package_file = files[0]
                
                # Install to VFS
                if package_file.suffix == '.whl':
                    return self._install_wheel(package_file, package_name)
                else:
                    return self._install_tarball(package_file, package_name)
                
        except Exception as e:
            print(f"Installation error: {e}")
            return False
    
    def _install_wheel(self, wheel_path: Path, package_name: str) -> bool:
        """Install wheel package to VFS"""
        try:
            with zipfile.ZipFile(wheel_path, 'r') as wheel:
                # Extract to VFS
                for member in wheel.namelist():
                    # Skip metadata for now
                    if member.endswith('/') or '.dist-info/' in member:
                        continue
                    
                    # Determine target path
                    target_path = f"{self.packages_dir}/{member}"
                    
                    # Create parent directory
                    parent_dir = os.path.dirname(target_path)
                    if not self.vfs.exists(parent_dir):
                        self._create_dirs(parent_dir)
                    
                    # Write file to VFS
                    data = wheel.read(member)
                    with self.vfs.open(target_path, 'wb') as f:
                        f.write(data)
            
            # Update installed packages
            self.installed_packages[package_name] = {
                'version': wheel_path.stem.split('-')[1],
                'files': [],
                'installed_at': self._get_timestamp()
            }
            self._save_installed_packages()
            
            return True
            
        except Exception as e:
            print(f"Failed to install wheel: {e}")
            return False
    
    def _install_tarball(self, tar_path: Path, package_name: str) -> bool:
        """Install tarball package to VFS"""
        try:
            import tarfile
            
            with tempfile.TemporaryDirectory() as extract_dir:
                # Extract tarball
                with tarfile.open(tar_path, 'r:*') as tar:
                    tar.extractall(extract_dir)
                
                # Find setup.py
                setup_dirs = list(Path(extract_dir).glob('*/setup.py'))
                if not setup_dirs:
                    print("No setup.py found")
                    return False
                
                package_dir = setup_dirs[0].parent
                
                # Copy Python files to VFS
                for py_file in package_dir.rglob('*.py'):
                    rel_path = py_file.relative_to(package_dir)
                    
                    # Skip setup files
                    if rel_path.name in ['setup.py', 'setup.cfg']:
                        continue
                    
                    target_path = f"{self.packages_dir}/{rel_path}"
                    
                    # Create parent directory
                    parent_dir = os.path.dirname(target_path)
                    if not self.vfs.exists(parent_dir):
                        self._create_dirs(parent_dir)
                    
                    # Copy file to VFS
                    with open(py_file, 'rb') as src:
                        data = src.read()
                    with self.vfs.open(target_path, 'wb') as dst:
                        dst.write(data)
                
                # Update installed packages
                self.installed_packages[package_name] = {
                    'version': 'unknown',
                    'files': [],
                    'installed_at': self._get_timestamp()
                }
                self._save_installed_packages()
                
                return True
                
        except Exception as e:
            print(f"Failed to install tarball: {e}")
            return False
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall package from VFS"""
        if package_name not in self.installed_packages:
            print(f"Package {package_name} not installed")
            return False
        
        # Remove package files
        package_info = self.installed_packages[package_name]
        for file_path in package_info.get('files', []):
            if self.vfs.exists(file_path):
                self.vfs.remove(file_path)
        
        # Remove from database
        del self.installed_packages[package_name]
        self._save_installed_packages()
        
        return True
    
    def list_installed(self) -> List[Dict[str, Any]]:
        """List installed packages"""
        return [
            {
                'name': name,
                'version': info.get('version', 'unknown'),
                'installed_at': info.get('installed_at', 'unknown')
            }
            for name, info in self.installed_packages.items()
        ]
    
    def _create_dirs(self, path: str):
        """Create directory tree"""
        parts = path.split('/')
        current = ''
        for part in parts:
            if not part:
                continue
            current = f"{current}/{part}" if current else f"/{part}"
            if not self.vfs.exists(current):
                self.vfs.mkdir(current)
    
    def _save_installed_packages(self):
        """Save installed packages database"""
        db_file = "/var/lib/pip/installed.json"
        with self.vfs.open(db_file, 'w') as f:
            f.write(json.dumps(self.installed_packages, indent=2).encode())
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        import datetime
        return datetime.datetime.now().isoformat()


class PythonEnvironment:
    """Python execution environment for KOS"""
    
    def __init__(self, vfs, memory_manager=None):
        self.vfs = vfs
        self.memory_manager = memory_manager
        self.namespaces: Dict[str, dict] = {}
        self.current_namespace = '__main__'
        self.importer = VFSImporter(vfs, self)
        self.pip = VFSPipInstaller(vfs, self)
        
        # Setup Python paths
        self.python_paths = [
            "/usr/lib/python",
            "/usr/lib/python/site-packages",
            "/usr/local/lib/python",
            "/usr/local/lib/python/site-packages",
            "/home/user/.local/lib/python"
        ]
        
        self._init_environment()
    
    def _init_environment(self):
        """Initialize Python environment"""
        # Create Python directories in VFS
        for path in self.python_paths:
            if not self.vfs.exists(path):
                self._create_directory_tree(path)
        
        # Install import hook
        if self.importer not in sys.meta_path:
            sys.meta_path.insert(0, self.importer)
        
        # Create main namespace
        self.namespaces['__main__'] = self._create_namespace()
    
    def _create_namespace(self) -> dict:
        """Create new execution namespace"""
        namespace = {
            '__name__': '__main__',
            '__doc__': None,
            '__package__': None,
            '__loader__': None,
            '__spec__': None,
            '__builtins__': builtins,
            'vfs': self.vfs,
            'memory': self.memory_manager,
            'pip': self.pip
        }
        
        # Add VFS-aware functions
        namespace['open'] = self._vfs_open
        namespace['__import__'] = self._vfs_import
        
        return namespace
    
    def execute(self, code: str, namespace: Optional[str] = None) -> Any:
        """Execute Python code in isolated namespace"""
        if namespace is None:
            namespace = self.current_namespace
        
        if namespace not in self.namespaces:
            self.namespaces[namespace] = self._create_namespace()
        
        ns = self.namespaces[namespace]
        
        try:
            # Parse code
            tree = ast.parse(code, mode='exec')
            
            # Compile and execute
            code_obj = compile(tree, '<vfs>', 'exec')
            
            # Capture output
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout = io.StringIO()
            stderr = io.StringIO()
            
            try:
                sys.stdout = stdout
                sys.stderr = stderr
                
                exec(code_obj, ns)
                
                result = {
                    'success': True,
                    'stdout': stdout.getvalue(),
                    'stderr': stderr.getvalue(),
                    'namespace': namespace
                }
                
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
                'namespace': namespace
            }
    
    def execute_file(self, filepath: str, namespace: Optional[str] = None) -> Any:
        """Execute Python file from VFS"""
        if not self.vfs.exists(filepath):
            return {
                'success': False,
                'error': f"File not found: {filepath}"
            }
        
        # Read file from VFS
        with self.vfs.open(filepath, 'r') as f:
            code = f.read()
            if isinstance(code, bytes):
                code = code.decode('utf-8')
        
        # Execute code
        result = self.execute(code, namespace)
        result['file'] = filepath
        
        return result
    
    def create_virtualenv(self, name: str, path: str = None) -> bool:
        """Create virtual environment in VFS"""
        if path is None:
            path = f"/home/user/venvs/{name}"
        
        try:
            # Create venv structure
            venv_dirs = [
                path,
                f"{path}/bin",
                f"{path}/lib",
                f"{path}/lib/python",
                f"{path}/lib/python/site-packages",
                f"{path}/include",
                f"{path}/share"
            ]
            
            for dir_path in venv_dirs:
                if not self.vfs.exists(dir_path):
                    self.vfs.mkdir(dir_path)
            
            # Create activation script
            activate_script = f"""
# Virtual environment activation script
export VIRTUAL_ENV="{path}"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PYTHONPATH="$VIRTUAL_ENV/lib/python/site-packages:$PYTHONPATH"
unset PYTHONDONTWRITEBYTECODE

# Prompt modification
export PS1="({name}) $PS1"

echo "Virtual environment '{name}' activated"
"""
            
            with self.vfs.open(f"{path}/bin/activate", 'w') as f:
                f.write(activate_script.encode())
            
            # Create pip wrapper
            pip_wrapper = f"""#!/usr/bin/env python
import sys
sys.path.insert(0, '{path}/lib/python/site-packages')

from kos.python.interpreter import VFSPipInstaller
installer = VFSPipInstaller(vfs, None)
installer.packages_dir = '{path}/lib/python/site-packages'

# Handle pip commands
if len(sys.argv) > 1:
    if sys.argv[1] == 'install':
        for package in sys.argv[2:]:
            installer.install(package)
    elif sys.argv[1] == 'uninstall':
        for package in sys.argv[2:]:
            installer.uninstall(package)
    elif sys.argv[1] == 'list':
        for pkg in installer.list_installed():
            print(f"{{pkg['name']}} {{pkg['version']}}")
"""
            
            with self.vfs.open(f"{path}/bin/pip", 'w') as f:
                f.write(pip_wrapper.encode())
            
            # Create pyvenv.cfg
            config = f"""
home = /usr/bin
include-system-site-packages = false
version = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
"""
            
            with self.vfs.open(f"{path}/pyvenv.cfg", 'w') as f:
                f.write(config.encode())
            
            return True
            
        except Exception as e:
            print(f"Failed to create virtualenv: {e}")
            return False
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install Python package using pip"""
        return self.pip.install(package_name, version)
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall Python package"""
        return self.pip.uninstall(package_name)
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """List installed packages"""
        return self.pip.list_installed()
    
    def _vfs_open(self, file, mode='r', buffering=-1, encoding=None, 
                  errors=None, newline=None, closefd=True, opener=None):
        """VFS-aware open function"""
        # Check if file exists in VFS
        if self.vfs.exists(file):
            return self.vfs.open(file, mode)
        
        # Fall back to regular open for system files
        return builtins.open(file, mode, buffering, encoding, errors, 
                            newline, closefd, opener)
    
    def _vfs_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """VFS-aware import function"""
        # Try VFS import first
        try:
            return importlib.import_module(name)
        except ImportError:
            # Fall back to regular import
            return builtins.__import__(name, globals, locals, fromlist, level)
    
    def _create_directory_tree(self, path: str):
        """Create directory tree in VFS"""
        parts = path.split('/')
        current = ''
        for part in parts:
            if not part:
                continue
            current = f"{current}/{part}" if current else f"/{part}"
            if not self.vfs.exists(current):
                self.vfs.mkdir(current)
    
    def create_repl(self) -> code.InteractiveConsole:
        """Create interactive Python REPL"""
        namespace = self.namespaces[self.current_namespace]
        
        class VFSConsole(code.InteractiveConsole):
            def __init__(self, locals, vfs):
                super().__init__(locals)
                self.vfs = vfs
            
            def raw_input(self, prompt=""):
                # Could integrate with KOS shell here
                return input(prompt)
        
        return VFSConsole(namespace, self.vfs)
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get Python memory usage"""
        import tracemalloc
        
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics('lineno')
        
        total = sum(stat.size for stat in stats)
        
        return {
            'total': total,
            'peak': tracemalloc.get_traced_memory()[1],
            'current': tracemalloc.get_traced_memory()[0],
            'num_objects': len(stats)
        }