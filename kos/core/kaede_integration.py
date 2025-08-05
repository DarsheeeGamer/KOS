"""
Kaede Integration Module
========================

Integrates Kaede programming language with KOS system for:
- Cross-platform compilation and execution
- Host system communication
- Resource management
- Security and sandboxing
- Performance optimization
"""

import os
import sys
import time
import logging
import asyncio
import threading
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from .host_bridge import (
    HostBridgeClient, CompilationRequest, ExecutionRequest, ExecutionResult,
    HostPlatform, HostArchitecture, SecurityLevel, get_host_bridge_client
)
from .platform_compat import (
    PlatformCompatibilityLayer, PlatformType, ArchitectureType,
    get_platform_compatibility_layer, adapt_kaede_code
)
from ..kaede.compiler import KaedeCompiler, TargetArch, OptimizationLevel
from ..kaede.runtime_executor import KaedeRuntimeExecutor, ExecutionMode

logger = logging.getLogger('KOS.core.kaede_integration')

class KaedeExecutionTarget(Enum):
    """Kaede execution targets"""
    LOCAL_VM = auto()           # Local Kaede VM
    LOCAL_NATIVE = auto()       # Local native compilation
    REMOTE_HOST = auto()        # Remote host execution
    CONTAINER = auto()          # Container execution
    HYBRID = auto()            # Hybrid execution

class KaedeProjectType(Enum):
    """Kaede project types"""
    APPLICATION = "application"
    LIBRARY = "library"
    MODULE = "module"
    SCRIPT = "script"
    SERVICE = "service"

@dataclass
class KaedeProject:
    """Kaede project configuration"""
    name: str
    type: KaedeProjectType
    version: str = "1.0.0"
    source_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    target_platforms: List[PlatformType] = field(default_factory=list)
    optimization_level: int = 2
    output_directory: str = "build"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class KaedeExecutionConfig:
    """Kaede execution configuration"""
    target: KaedeExecutionTarget = KaedeExecutionTarget.LOCAL_VM
    host_address: Optional[str] = None
    host_port: int = 8900
    security_level: SecurityLevel = SecurityLevel.SANDBOX
    resource_limits: Dict[str, int] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    timeout: int = 300
    optimization_enabled: bool = True

class KaedeIntegrationEngine:
    """Main Kaede integration engine"""
    
    def __init__(self):
        self.compiler = KaedeCompiler()
        self.runtime = KaedeRuntimeExecutor()
        self.platform_compat = get_platform_compatibility_layer()
        self.host_bridge_client = None
        
        # Project cache
        self.project_cache = {}
        
        # Execution history
        self.execution_history = []
        
        # Performance metrics
        self.metrics = {
            'compilations': 0,
            'executions': 0,
            'total_compile_time': 0.0,
            'total_execution_time': 0.0,
            'cache_hits': 0
        }
        
    def create_project(self, project_config: KaedeProject) -> bool:
        """Create a new Kaede project"""
        try:
            project_dir = Path(project_config.name)
            project_dir.mkdir(exist_ok=True)
            
            # Create project structure
            (project_dir / "src").mkdir(exist_ok=True)
            (project_dir / project_config.output_directory).mkdir(exist_ok=True)
            (project_dir / "tests").mkdir(exist_ok=True)
            
            # Create project file
            project_file = project_dir / "kaede_project.json"
            project_data = {
                "name": project_config.name,
                "type": project_config.type.value,
                "version": project_config.version,
                "source_files": project_config.source_files,
                "dependencies": project_config.dependencies,
                "target_platforms": [p.value for p in project_config.target_platforms],
                "optimization_level": project_config.optimization_level,
                "output_directory": project_config.output_directory,
                "metadata": project_config.metadata
            }
            
            import json
            with open(project_file, 'w') as f:
                json.dump(project_data, f, indent=2)
            
            # Create main source file if it doesn't exist
            main_file = project_dir / "src" / "main.kaede"
            if not main_file.exists():
                main_file.write_text(self._get_template_code(project_config.type))
            
            logger.info(f"Created Kaede project: {project_config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create project {project_config.name}: {e}")
            return False
    
    def load_project(self, project_path: str) -> Optional[KaedeProject]:
        """Load a Kaede project"""
        try:
            project_dir = Path(project_path)
            project_file = project_dir / "kaede_project.json"
            
            if not project_file.exists():
                logger.error(f"Project file not found: {project_file}")
                return None
            
            import json
            with open(project_file, 'r') as f:
                project_data = json.load(f)
            
            project = KaedeProject(
                name=project_data["name"],
                type=KaedeProjectType(project_data["type"]),
                version=project_data.get("version", "1.0.0"),
                source_files=project_data.get("source_files", []),
                dependencies=project_data.get("dependencies", []),
                target_platforms=[PlatformType(p) for p in project_data.get("target_platforms", [])],
                optimization_level=project_data.get("optimization_level", 2),
                output_directory=project_data.get("output_directory", "build"),
                metadata=project_data.get("metadata", {})
            )
            
            self.project_cache[project.name] = project
            logger.info(f"Loaded Kaede project: {project.name}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to load project from {project_path}: {e}")
            return None
    
    def compile_project(self, project: KaedeProject, target_platform: PlatformType = None) -> bool:
        """Compile a Kaede project"""
        try:
            start_time = time.time()
            
            project_dir = Path(project.name)
            output_dir = project_dir / project.output_directory
            output_dir.mkdir(exist_ok=True)
            
            # Determine target platform
            if target_platform is None:
                target_platform = self.platform_compat.get_platform_info().platform
            
            # Compile each source file
            compiled_modules = {}
            
            for source_file in project.source_files:
                source_path = project_dir / "src" / source_file
                
                if not source_path.exists():
                    logger.warning(f"Source file not found: {source_path}")
                    continue
                
                # Read source code
                with open(source_path, 'r') as f:
                    source_code = f.read()
                
                # Adapt for target platform
                adapted_code = adapt_kaede_code(source_code, target_platform)
                
                # Compile to module
                module = self.compiler.compile_source(adapted_code, source_path.stem)
                compiled_modules[source_path.stem] = module
                
                # Generate bytecode
                bytecode = self.compiler.compile_to_bytecode(module)
                
                # Save bytecode
                bytecode_file = output_dir / f"{source_path.stem}.kbc"
                with open(bytecode_file, 'wb') as f:
                    f.write(bytecode)
            
            # Create executable if it's an application
            if project.type == KaedeProjectType.APPLICATION:
                self._create_executable(project, compiled_modules, output_dir, target_platform)
            
            compile_time = time.time() - start_time
            self.metrics['compilations'] += 1
            self.metrics['total_compile_time'] += compile_time
            
            logger.info(f"Compiled project {project.name} in {compile_time:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to compile project {project.name}: {e}")
            return False
    
    def execute_project(self, project: KaedeProject, config: KaedeExecutionConfig, args: List[str] = None) -> ExecutionResult:
        """Execute a Kaede project"""
        try:
            start_time = time.time()
            
            if config.target == KaedeExecutionTarget.LOCAL_VM:
                result = self._execute_local_vm(project, config, args or [])
            elif config.target == KaedeExecutionTarget.LOCAL_NATIVE:
                result = self._execute_local_native(project, config, args or [])
            elif config.target == KaedeExecutionTarget.REMOTE_HOST:
                result = self._execute_remote_host(project, config, args or [])
            elif config.target == KaedeExecutionTarget.CONTAINER:
                result = self._execute_container(project, config, args or [])
            else:
                result = ExecutionResult(-1, "", "Unsupported execution target")
            
            execution_time = time.time() - start_time
            self.metrics['executions'] += 1
            self.metrics['total_execution_time'] += execution_time
            
            # Add to execution history
            self.execution_history.append({
                'project': project.name,
                'target': config.target,
                'timestamp': time.time(),
                'execution_time': execution_time,
                'result': result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute project {project.name}: {e}")
            return ExecutionResult(-1, "", str(e))
    
    def execute_code(self, source_code: str, config: KaedeExecutionConfig) -> ExecutionResult:
        """Execute Kaede code directly"""
        try:
            # Create temporary project
            temp_project = KaedeProject(
                name="temp_execution",
                type=KaedeProjectType.SCRIPT,
                source_files=["main.kaede"]
            )
            
            # Create temporary directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Write source code
                src_dir = temp_path / "src"
                src_dir.mkdir()
                
                main_file = src_dir / "main.kaede"
                main_file.write_text(source_code)
                
                # Set project path
                temp_project.name = str(temp_path / "temp_execution")
                
                # Compile and execute
                if self.compile_project(temp_project):
                    return self.execute_project(temp_project, config)
                else:
                    return ExecutionResult(-1, "", "Compilation failed")
                    
        except Exception as e:
            logger.error(f"Failed to execute code: {e}")
            return ExecutionResult(-1, "", str(e))
    
    def _execute_local_vm(self, project: KaedeProject, config: KaedeExecutionConfig, args: List[str]) -> ExecutionResult:
        """Execute project in local Kaede VM"""
        try:
            project_dir = Path(project.name)
            output_dir = project_dir / project.output_directory
            
            # Find main bytecode file
            main_bytecode = output_dir / "main.kbc"
            if not main_bytecode.exists():
                return ExecutionResult(-1, "", "Main bytecode file not found")
            
            # Load bytecode
            with open(main_bytecode, 'rb') as f:
                bytecode = f.read()
            
            # Create mock module for execution
            class MockModule:
                def __init__(self, name, bytecode):
                    self.name = name
                    self.bytecode = bytecode
                    self.functions = {}
            
            module = MockModule("main", bytecode)
            
            # Set execution mode
            if config.optimization_enabled:
                self.runtime.set_execution_mode(ExecutionMode.HYBRID)
            else:
                self.runtime.set_execution_mode(ExecutionMode.BYTECODE)
            
            # Execute
            result = self.runtime.execute_module(module)
            
            return ExecutionResult(
                return_code=0,
                stdout=str(result) if result is not None else "",
                stderr=""
            )
            
        except Exception as e:
            return ExecutionResult(-1, "", str(e))
    
    def _execute_local_native(self, project: KaedeProject, config: KaedeExecutionConfig, args: List[str]) -> ExecutionResult:
        """Execute project as native binary"""
        try:
            project_dir = Path(project.name)
            output_dir = project_dir / project.output_directory
            
            # Find executable
            platform_info = self.platform_compat.get_platform_info()
            exe_name = project.name
            if platform_info.platform == PlatformType.WINDOWS:
                exe_name += ".exe"
            
            executable = output_dir / exe_name
            if not executable.exists():
                return ExecutionResult(-1, "", "Executable not found")
            
            # Execute
            import subprocess
            process = subprocess.Popen(
                [str(executable)] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=config.timeout)
                return ExecutionResult(
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr
                )
            except subprocess.TimeoutExpired:
                process.kill()
                return ExecutionResult(
                    return_code=-1,
                    stdout="",
                    stderr="Execution timed out",
                    timed_out=True
                )
                
        except Exception as e:
            return ExecutionResult(-1, "", str(e))
    
    def _execute_remote_host(self, project: KaedeProject, config: KaedeExecutionConfig, args: List[str]) -> ExecutionResult:
        """Execute project on remote host"""
        try:
            # Connect to host bridge
            if self.host_bridge_client is None:
                self.host_bridge_client = HostBridgeClient(
                    config.host_address or "localhost",
                    config.host_port
                )
            
            if not self.host_bridge_client.connected:
                if not self.host_bridge_client.connect():
                    return ExecutionResult(-1, "", "Failed to connect to host bridge")
            
            # Read main source file
            project_dir = Path(project.name)
            main_source = project_dir / "src" / "main.kaede"
            
            if not main_source.exists():
                return ExecutionResult(-1, "", "Main source file not found")
            
            with open(main_source, 'r') as f:
                source_code = f.read()
            
            # Create compilation request
            compile_request = CompilationRequest(
                source_code=source_code,
                language="kaede",
                optimization_level=project.optimization_level,
                security_level=config.security_level
            )
            
            # Compile on host
            success, message, binary_data = self.host_bridge_client.compile_kaede_application(compile_request)
            
            if not success:
                return ExecutionResult(-1, "", f"Remote compilation failed: {message}")
            
            # Execute on host
            execute_request = ExecutionRequest(
                binary_data=binary_data,
                arguments=args,
                environment=config.environment,
                timeout=config.timeout,
                security_level=config.security_level,
                resource_limits=config.resource_limits
            )
            
            return self.host_bridge_client.execute_application(execute_request)
            
        except Exception as e:
            return ExecutionResult(-1, "", str(e))
    
    def _execute_container(self, project: KaedeProject, config: KaedeExecutionConfig, args: List[str]) -> ExecutionResult:
        """Execute project in container"""
        # This would implement container execution
        # For now, fall back to local VM
        return self._execute_local_vm(project, config, args)
    
    def _create_executable(self, project: KaedeProject, modules: Dict[str, Any], output_dir: Path, target_platform: PlatformType):
        """Create executable from compiled modules"""
        try:
            # For now, just copy the main bytecode as the executable
            # In a real implementation, this would create a proper executable wrapper
            
            if "main" in modules:
                main_module = modules["main"]
                bytecode = self.compiler.compile_to_bytecode(main_module)
                
                exe_name = project.name
                if target_platform == PlatformType.WINDOWS:
                    exe_name += ".exe"
                
                exe_path = output_dir / exe_name
                with open(exe_path, 'wb') as f:
                    f.write(bytecode)
                
                # Make executable on Unix systems
                if target_platform != PlatformType.WINDOWS:
                    exe_path.chmod(0o755)
                    
        except Exception as e:
            logger.error(f"Failed to create executable: {e}")
    
    def _get_template_code(self, project_type: KaedeProjectType) -> str:
        """Get template code for project type"""
        if project_type == KaedeProjectType.APPLICATION:
            return '''func main() {
    println("Hello, Kaede!");
}
'''
        elif project_type == KaedeProjectType.LIBRARY:
            return '''// Kaede Library
export func hello_world() -> String {
    return "Hello from Kaede library!";
}
'''
        elif project_type == KaedeProjectType.MODULE:
            return '''// Kaede Module
export var MODULE_VERSION = "1.0.0";

export func get_version() -> String {
    return MODULE_VERSION;
}
'''
        elif project_type == KaedeProjectType.SERVICE:
            return '''// Kaede Service
import kos.service;

func main() {
    var service = Service.new("kaede_service");
    service.start();
    service.wait();
}
'''
        else:  # SCRIPT
            return '''// Kaede Script
println("Hello, Kaede!");
'''
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        avg_compile_time = self.metrics['total_compile_time'] / max(self.metrics['compilations'], 1)
        avg_execution_time = self.metrics['total_execution_time'] / max(self.metrics['executions'], 1)
        
        return {
            'compilations': self.metrics['compilations'],
            'executions': self.metrics['executions'],
            'cache_hits': self.metrics['cache_hits'],
            'average_compile_time': avg_compile_time,
            'average_execution_time': avg_execution_time,
            'total_compile_time': self.metrics['total_compile_time'],
            'total_execution_time': self.metrics['total_execution_time']
        }
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get execution history"""
        return self.execution_history.copy()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.host_bridge_client:
            self.host_bridge_client.disconnect()

# Global instance
_kaede_engine = None

def get_kaede_integration_engine() -> KaedeIntegrationEngine:
    """Get the global Kaede integration engine"""
    global _kaede_engine
    if _kaede_engine is None:
        _kaede_engine = KaedeIntegrationEngine()
    return _kaede_engine

# Convenience functions
def create_kaede_project(name: str, project_type: KaedeProjectType = KaedeProjectType.APPLICATION) -> bool:
    """Create a new Kaede project"""
    project = KaedeProject(name=name, type=project_type)
    return get_kaede_integration_engine().create_project(project)

def compile_kaede_project(project_path: str, target_platform: PlatformType = None) -> bool:
    """Compile a Kaede project"""
    engine = get_kaede_integration_engine()
    project = engine.load_project(project_path)
    if project:
        return engine.compile_project(project, target_platform)
    return False

def execute_kaede_code(source_code: str, target: KaedeExecutionTarget = KaedeExecutionTarget.LOCAL_VM) -> ExecutionResult:
    """Execute Kaede code"""
    config = KaedeExecutionConfig(target=target)
    return get_kaede_integration_engine().execute_code(source_code, config)

def execute_kaede_on_host(source_code: str, host_address: str = "localhost", host_port: int = 8900) -> ExecutionResult:
    """Execute Kaede code on remote host"""
    config = KaedeExecutionConfig(
        target=KaedeExecutionTarget.REMOTE_HOST,
        host_address=host_address,
        host_port=host_port
    )
    return get_kaede_integration_engine().execute_code(source_code, config)

__all__ = [
    'KaedeExecutionTarget', 'KaedeProjectType', 'KaedeProject', 'KaedeExecutionConfig',
    'KaedeIntegrationEngine', 'get_kaede_integration_engine',
    'create_kaede_project', 'compile_kaede_project', 'execute_kaede_code', 'execute_kaede_on_host'
]