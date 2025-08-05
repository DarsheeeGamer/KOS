"""
KOS Host Bridge - Communication Layer between KOS and Host Systems
================================================================

This module provides a robust communication bridge that enables:
- Cross-platform app compilation and execution via Kaede
- Secure host system integration
- Resource sharing and management
- Remote execution capabilities
- Platform abstraction layer
"""

import os
import sys
import json
import time
import socket
import threading
import subprocess
import platform
import tempfile
import logging
import hashlib
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import ssl
import base64
import queue
import weakref

logger = logging.getLogger('KOS.core.host_bridge')

class HostPlatform(Enum):
    """Supported host platforms"""
    LINUX = "linux"
    WINDOWS = "windows" 
    MACOS = "macos"
    BSD = "bsd"
    UNIX = "unix"

class HostArchitecture(Enum):
    """Supported architectures"""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    ARM32 = "arm32"
    RISCV = "riscv"

class ExecutionMode(Enum):
    """Execution modes for host applications"""
    NATIVE = auto()           # Compile to native binary
    INTERPRETED = auto()      # Run via Kaede interpreter
    CONTAINER = auto()        # Run in container/sandbox
    HYBRID = auto()          # Mix of native and interpreted

class SecurityLevel(Enum):
    """Security levels for host execution"""
    SANDBOX = auto()         # Full sandboxing
    RESTRICTED = auto()      # Limited access
    NORMAL = auto()         # Standard permissions
    PRIVILEGED = auto()     # Elevated permissions

@dataclass
class HostCapabilities:
    """Host system capabilities"""
    platform: HostPlatform
    architecture: HostArchitecture
    cores: int
    memory_mb: int
    disk_space_mb: int
    network_available: bool
    compiler_available: bool
    container_support: bool
    supported_languages: List[str] = field(default_factory=list)
    installed_runtimes: List[str] = field(default_factory=list)

@dataclass
class CompilationRequest:
    """Request for compilation on host"""
    source_code: str
    language: str = "kaede"
    target_platform: HostPlatform = None
    target_arch: HostArchitecture = None
    optimization_level: int = 2
    output_type: str = "executable"  # executable, library, module
    dependencies: List[str] = field(default_factory=list)
    compile_flags: List[str] = field(default_factory=list)
    security_level: SecurityLevel = SecurityLevel.SANDBOX

@dataclass
class ExecutionRequest:
    """Request for execution on host"""
    executable_path: str = None
    binary_data: bytes = None
    arguments: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    working_directory: str = None
    timeout: int = 300  # seconds
    security_level: SecurityLevel = SecurityLevel.SANDBOX
    resource_limits: Dict[str, int] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """Result of execution on host"""
    return_code: int
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    peak_memory_usage: int = 0
    exit_signal: Optional[int] = None
    timed_out: bool = False

class HostBridgeProtocol:
    """Communication protocol for host bridge"""
    
    # Message types
    MSG_HANDSHAKE = "handshake"
    MSG_CAPABILITIES = "capabilities"
    MSG_COMPILE_REQUEST = "compile_request"
    MSG_COMPILE_RESPONSE = "compile_response"
    MSG_EXECUTE_REQUEST = "execute_request"
    MSG_EXECUTE_RESPONSE = "execute_response"
    MSG_FILE_TRANSFER = "file_transfer"
    MSG_HEARTBEAT = "heartbeat"
    MSG_ERROR = "error"
    
    @staticmethod
    def create_message(msg_type: str, data: Any, session_id: str = None) -> Dict:
        """Create a protocol message"""
        return {
            "type": msg_type,
            "timestamp": time.time(),
            "session_id": session_id,
            "data": data
        }
    
    @staticmethod
    def validate_message(message: Dict) -> bool:
        """Validate a protocol message"""
        required_fields = ["type", "timestamp", "data"]
        return all(field in message for field in required_fields)

class SecureChannel:
    """Secure communication channel"""
    
    def __init__(self, socket_obj: socket.socket, use_tls: bool = True):
        self.socket = socket_obj
        self.use_tls = use_tls
        self.tls_context = None
        self.session_key = None
        
        if use_tls:
            self._setup_tls()
    
    def _setup_tls(self):
        """Setup TLS encryption"""
        self.tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.tls_context.check_hostname = False
        self.tls_context.verify_mode = ssl.CERT_NONE  # For development
    
    def send_message(self, message: Dict) -> bool:
        """Send encrypted message"""
        try:
            data = json.dumps(message).encode('utf-8')
            
            if self.use_tls and self.session_key:
                data = self._encrypt_data(data)
            
            # Send length prefix
            length = len(data)
            self.socket.sendall(length.to_bytes(4, 'big'))
            
            # Send data
            self.socket.sendall(data)
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def receive_message(self) -> Optional[Dict]:
        """Receive and decrypt message"""
        try:
            # Receive length prefix
            length_data = self._receive_all(4)
            if not length_data:
                return None
            
            length = int.from_bytes(length_data, 'big')
            
            # Receive data
            data = self._receive_all(length)
            if not data:
                return None
            
            if self.use_tls and self.session_key:
                data = self._decrypt_data(data)
            
            return json.loads(data.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None
    
    def _receive_all(self, size: int) -> bytes:
        """Receive exact amount of data"""
        data = b''
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data (simplified implementation)"""
        # In production, use proper encryption like AES
        return base64.b64encode(data)
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data (simplified implementation)"""
        # In production, use proper decryption
        return base64.b64decode(data)

class HostBridgeClient:
    """Client side of the host bridge"""
    
    def __init__(self, host: str = "localhost", port: int = 8900):
        self.host = host
        self.port = port
        self.socket = None
        self.channel = None
        self.session_id = None
        self.connected = False
        self.capabilities = None
        
    def connect(self) -> bool:
        """Connect to host bridge server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            
            self.channel = SecureChannel(self.socket)
            
            # Perform handshake
            if self._handshake():
                self.connected = True
                self._get_capabilities()
                logger.info(f"Connected to host bridge at {self.host}:{self.port}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to connect to host bridge: {e}")
            self._cleanup()
        
        return False
    
    def disconnect(self):
        """Disconnect from host bridge"""
        self.connected = False
        self._cleanup()
    
    def _cleanup(self):
        """Clean up connection resources"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.channel = None
    
    def _handshake(self) -> bool:
        """Perform connection handshake"""
        try:
            # Send handshake
            handshake_data = {
                "version": "1.0",
                "client_type": "KOS",
                "supported_protocols": ["json", "binary"]
            }
            
            message = HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_HANDSHAKE,
                handshake_data
            )
            
            if not self.channel.send_message(message):
                return False
            
            # Receive response
            response = self.channel.receive_message()
            if not response or response["type"] != HostBridgeProtocol.MSG_HANDSHAKE:
                return False
            
            self.session_id = response.get("session_id")
            return True
            
        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            return False
    
    def _get_capabilities(self) -> bool:
        """Get host capabilities"""
        try:
            message = HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_CAPABILITIES,
                {},
                self.session_id
            )
            
            if not self.channel.send_message(message):
                return False
            
            response = self.channel.receive_message()
            if response and response["type"] == HostBridgeProtocol.MSG_CAPABILITIES:
                self.capabilities = response["data"]
                return True
            
        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
        
        return False
    
    def compile_kaede_application(self, request: CompilationRequest) -> Tuple[bool, str, bytes]:
        """Compile Kaede application on host"""
        if not self.connected:
            return False, "Not connected to host bridge", b""
        
        try:
            message = HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_COMPILE_REQUEST,
                {
                    "source_code": request.source_code,
                    "language": request.language,
                    "target_platform": request.target_platform.value if request.target_platform else None,
                    "target_arch": request.target_arch.value if request.target_arch else None,
                    "optimization_level": request.optimization_level,
                    "output_type": request.output_type,
                    "dependencies": request.dependencies,
                    "compile_flags": request.compile_flags,
                    "security_level": request.security_level.value
                },
                self.session_id
            )
            
            if not self.channel.send_message(message):
                return False, "Failed to send compilation request", b""
            
            # Wait for response
            response = self.channel.receive_message()
            if not response:
                return False, "No response received", b""
            
            if response["type"] == HostBridgeProtocol.MSG_ERROR:
                return False, response["data"]["message"], b""
            
            if response["type"] == HostBridgeProtocol.MSG_COMPILE_RESPONSE:
                data = response["data"]
                success = data["success"]
                message = data.get("message", "")
                binary_data = base64.b64decode(data.get("binary", "")) if data.get("binary") else b""
                
                return success, message, binary_data
            
        except Exception as e:
            logger.error(f"Compilation request failed: {e}")
            return False, str(e), b""
        
        return False, "Unknown error", b""
    
    def execute_application(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute application on host"""
        if not self.connected:
            return ExecutionResult(-1, "", "Not connected to host bridge")
        
        try:
            message = HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_EXECUTE_REQUEST,
                {
                    "executable_path": request.executable_path,
                    "binary_data": base64.b64encode(request.binary_data).decode() if request.binary_data else None,
                    "arguments": request.arguments,
                    "environment": request.environment,
                    "working_directory": request.working_directory,
                    "timeout": request.timeout,
                    "security_level": request.security_level.value,
                    "resource_limits": request.resource_limits
                },
                self.session_id
            )
            
            if not self.channel.send_message(message):
                return ExecutionResult(-1, "", "Failed to send execution request")
            
            # Wait for response
            response = self.channel.receive_message()
            if not response:
                return ExecutionResult(-1, "", "No response received")
            
            if response["type"] == HostBridgeProtocol.MSG_ERROR:
                return ExecutionResult(-1, "", response["data"]["message"])
            
            if response["type"] == HostBridgeProtocol.MSG_EXECUTE_RESPONSE:
                data = response["data"]
                return ExecutionResult(
                    return_code=data["return_code"],
                    stdout=data.get("stdout", ""),
                    stderr=data.get("stderr", ""),
                    execution_time=data.get("execution_time", 0.0),
                    peak_memory_usage=data.get("peak_memory_usage", 0),
                    exit_signal=data.get("exit_signal"),
                    timed_out=data.get("timed_out", False)
                )
            
        except Exception as e:
            logger.error(f"Execution request failed: {e}")
            return ExecutionResult(-1, "", str(e))
        
        return ExecutionResult(-1, "", "Unknown error")

class HostBridgeServer:
    """Server side of the host bridge (runs on host system)"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8900):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}
        self.capabilities = self._detect_capabilities()
        
    def start(self):
        """Start the host bridge server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            logger.info(f"Host bridge server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"Client connected from {address}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting client: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to start host bridge server: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the host bridge server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("Host bridge server stopped")
    
    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle individual client connection"""
        channel = SecureChannel(client_socket)
        session_id = hashlib.md5(f"{address[0]}:{address[1]}:{time.time()}".encode()).hexdigest()[:16]
        
        try:
            self.clients[session_id] = {
                "socket": client_socket,
                "channel": channel,
                "address": address,
                "connected_at": time.time()
            }
            
            while self.running:
                message = channel.receive_message()
                if not message:
                    break
                
                if not HostBridgeProtocol.validate_message(message):
                    continue
                
                response = self._process_message(message, session_id)
                if response and not channel.send_message(response):
                    break
                    
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
        finally:
            if session_id in self.clients:
                del self.clients[session_id]
            try:
                client_socket.close()
            except:
                pass
            logger.info(f"Client {address} disconnected")
    
    def _process_message(self, message: Dict, session_id: str) -> Optional[Dict]:
        """Process incoming message from client"""
        msg_type = message["type"]
        data = message["data"]
        
        try:
            if msg_type == HostBridgeProtocol.MSG_HANDSHAKE:
                return self._handle_handshake(data, session_id)
            
            elif msg_type == HostBridgeProtocol.MSG_CAPABILITIES:
                return self._handle_capabilities(data, session_id)
            
            elif msg_type == HostBridgeProtocol.MSG_COMPILE_REQUEST:
                return self._handle_compile_request(data, session_id)
            
            elif msg_type == HostBridgeProtocol.MSG_EXECUTE_REQUEST:
                return self._handle_execute_request(data, session_id)
            
            else:
                return HostBridgeProtocol.create_message(
                    HostBridgeProtocol.MSG_ERROR,
                    {"message": f"Unknown message type: {msg_type}"},
                    session_id
                )
                
        except Exception as e:
            logger.error(f"Error processing message {msg_type}: {e}")
            return HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_ERROR,
                {"message": str(e)},
                session_id
            )
    
    def _handle_handshake(self, data: Dict, session_id: str) -> Dict:
        """Handle handshake message"""
        return HostBridgeProtocol.create_message(
            HostBridgeProtocol.MSG_HANDSHAKE,
            {
                "version": "1.0",
                "server_type": "HostBridge",
                "session_id": session_id,
                "supported_protocols": ["json", "binary"]
            },
            session_id
        )
    
    def _handle_capabilities(self, data: Dict, session_id: str) -> Dict:
        """Handle capabilities request"""
        return HostBridgeProtocol.create_message(
            HostBridgeProtocol.MSG_CAPABILITIES,
            {
                "platform": self.capabilities.platform.value,
                "architecture": self.capabilities.architecture.value,
                "cores": self.capabilities.cores,
                "memory_mb": self.capabilities.memory_mb,
                "disk_space_mb": self.capabilities.disk_space_mb,
                "network_available": self.capabilities.network_available,
                "compiler_available": self.capabilities.compiler_available,
                "container_support": self.capabilities.container_support,
                "supported_languages": self.capabilities.supported_languages,
                "installed_runtimes": self.capabilities.installed_runtimes
            },
            session_id
        )
    
    def _handle_compile_request(self, data: Dict, session_id: str) -> Dict:
        """Handle compilation request"""
        try:
            # Create compilation request
            request = CompilationRequest(
                source_code=data["source_code"],
                language=data.get("language", "kaede"),
                target_platform=HostPlatform(data["target_platform"]) if data.get("target_platform") else self.capabilities.platform,
                target_arch=HostArchitecture(data["target_arch"]) if data.get("target_arch") else self.capabilities.architecture,
                optimization_level=data.get("optimization_level", 2),
                output_type=data.get("output_type", "executable"),
                dependencies=data.get("dependencies", []),
                compile_flags=data.get("compile_flags", []),
                security_level=SecurityLevel(data.get("security_level", "SANDBOX"))
            )
            
            # Perform compilation
            success, message, binary_data = self._compile_application(request)
            
            response_data = {
                "success": success,
                "message": message
            }
            
            if binary_data:
                response_data["binary"] = base64.b64encode(binary_data).decode()
            
            return HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_COMPILE_RESPONSE,
                response_data,
                session_id
            )
            
        except Exception as e:
            return HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_ERROR,
                {"message": f"Compilation failed: {e}"},
                session_id
            )
    
    def _handle_execute_request(self, data: Dict, session_id: str) -> Dict:
        """Handle execution request"""
        try:
            # Create execution request
            request = ExecutionRequest(
                executable_path=data.get("executable_path"),
                binary_data=base64.b64decode(data["binary_data"]) if data.get("binary_data") else None,
                arguments=data.get("arguments", []),
                environment=data.get("environment", {}),
                working_directory=data.get("working_directory"),
                timeout=data.get("timeout", 300),
                security_level=SecurityLevel(data.get("security_level", "SANDBOX")),
                resource_limits=data.get("resource_limits", {})
            )
            
            # Execute application
            result = self._execute_application(request)
            
            return HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_EXECUTE_RESPONSE,
                {
                    "return_code": result.return_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time": result.execution_time,
                    "peak_memory_usage": result.peak_memory_usage,
                    "exit_signal": result.exit_signal,
                    "timed_out": result.timed_out
                },
                session_id
            )
            
        except Exception as e:
            return HostBridgeProtocol.create_message(
                HostBridgeProtocol.MSG_ERROR,
                {"message": f"Execution failed: {e}"},
                session_id
            )
    
    def _detect_capabilities(self) -> HostCapabilities:
        """Detect host system capabilities"""
        # Detect platform
        system = platform.system().lower()
        if system == "linux":
            host_platform = HostPlatform.LINUX
        elif system == "windows":
            host_platform = HostPlatform.WINDOWS
        elif system == "darwin":
            host_platform = HostPlatform.MACOS
        else:
            host_platform = HostPlatform.UNIX
        
        # Detect architecture
        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            arch = HostArchitecture.X86_64
        elif machine in ["arm64", "aarch64"]:
            arch = HostArchitecture.ARM64
        elif machine.startswith("arm"):
            arch = HostArchitecture.ARM32
        else:
            arch = HostArchitecture.X86_64  # Default
        
        # Detect resources
        try:
            import psutil
            cores = psutil.cpu_count()
            memory_mb = psutil.virtual_memory().total // (1024 * 1024)
            disk_space_mb = psutil.disk_usage('/').free // (1024 * 1024)
        except ImportError:
            cores = os.cpu_count() or 1
            memory_mb = 1024  # Default 1GB
            disk_space_mb = 10240  # Default 10GB
        
        # Detect available compilers and runtimes
        supported_languages = ["kaede"]
        installed_runtimes = ["kaede_vm"]
        
        # Check for common compilers
        compilers = ["gcc", "clang", "python", "node", "java", "go", "rust"]
        for compiler in compilers:
            if self._check_executable(compiler):
                supported_languages.append(compiler)
                installed_runtimes.append(compiler)
        
        return HostCapabilities(
            platform=host_platform,
            architecture=arch,
            cores=cores,
            memory_mb=memory_mb,
            disk_space_mb=disk_space_mb,
            network_available=True,
            compiler_available=self._check_executable("gcc") or self._check_executable("clang"),
            container_support=self._check_executable("docker") or self._check_executable("podman"),
            supported_languages=supported_languages,
            installed_runtimes=installed_runtimes
        )
    
    def _check_executable(self, name: str) -> bool:
        """Check if executable is available"""
        try:
            subprocess.run([name, "--version"], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _compile_application(self, request: CompilationRequest) -> Tuple[bool, str, bytes]:
        """Compile application on host system"""
        try:
            # Create temporary directory for compilation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Write source code to file
                if request.language == "kaede":
                    source_file = temp_path / "main.kaede"
                    source_file.write_text(request.source_code)
                    
                    # Use Kaede compiler from KOS
                    return self._compile_kaede(source_file, temp_path, request)
                else:
                    return False, f"Unsupported language: {request.language}", b""
                    
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False, str(e), b""
    
    def _compile_kaede(self, source_file: Path, temp_path: Path, request: CompilationRequest) -> Tuple[bool, str, bytes]:
        """Compile Kaede source code"""
        try:
            # Import Kaede compiler
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from kaede.compiler import KaedeCompiler, TargetArch, OptimizationLevel
            
            # Create compiler instance
            target_arch = TargetArch.X86_64 if request.target_arch == HostArchitecture.X86_64 else TargetArch.ARM64
            opt_level = getattr(OptimizationLevel, f"O{request.optimization_level}", OptimizationLevel.O2)
            
            compiler = KaedeCompiler(target_arch=target_arch, optimization_level=opt_level)
            
            # Compile source file
            module = compiler.compile_file(str(source_file))
            
            if request.output_type == "executable":
                # Generate executable bytecode
                bytecode = compiler.compile_to_bytecode(module)
                return True, "Compilation successful", bytecode
            else:
                return False, f"Unsupported output type: {request.output_type}", b""
                
        except Exception as e:
            logger.error(f"Kaede compilation failed: {e}")
            return False, str(e), b""
    
    def _execute_application(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute application on host system"""
        try:
            start_time = time.time()
            
            if request.binary_data:
                # Execute Kaede bytecode
                return self._execute_kaede_bytecode(request, start_time)
            elif request.executable_path:
                # Execute native binary
                return self._execute_native_binary(request, start_time)
            else:
                return ExecutionResult(-1, "", "No executable specified")
                
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return ExecutionResult(-1, "", str(e))
    
    def _execute_kaede_bytecode(self, request: ExecutionRequest, start_time: float) -> ExecutionResult:
        """Execute Kaede bytecode"""
        try:
            # Import Kaede runtime
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from kaede.runtime_executor import KaedeRuntimeExecutor
            
            # Create runtime instance
            executor = KaedeRuntimeExecutor()
            
            # Create a mock module from bytecode
            # In a real implementation, this would properly deserialize the bytecode
            class MockModule:
                def __init__(self, bytecode):
                    self.name = "compiled_app"
                    self.bytecode = bytecode
                    self.functions = {}
            
            module = MockModule(request.binary_data)
            
            # Execute with timeout
            try:
                result = executor.execute_module(module)
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    return_code=0,
                    stdout=str(result) if result is not None else "",
                    stderr="",
                    execution_time=execution_time
                )
                
            except Exception as e:
                execution_time = time.time() - start_time
                return ExecutionResult(
                    return_code=1,
                    stdout="",
                    stderr=str(e),
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(-1, "", str(e), execution_time)
    
    def _execute_native_binary(self, request: ExecutionRequest, start_time: float) -> ExecutionResult:
        """Execute native binary"""
        try:
            # Prepare command
            cmd = [request.executable_path] + request.arguments
            
            # Prepare environment
            env = os.environ.copy()
            env.update(request.environment)
            
            # Execute with security restrictions based on security level
            if request.security_level == SecurityLevel.SANDBOX:
                # Add sandboxing (simplified - in production use proper sandboxing)
                pass
            
            # Run process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=request.working_directory
            )
            
            try:
                stdout, stderr = process.communicate(timeout=request.timeout)
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time=execution_time,
                    timed_out=False
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    return_code=-1,
                    stdout=stdout,
                    stderr=stderr + "\nProcess timed out",
                    execution_time=execution_time,
                    timed_out=True
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(-1, "", str(e), execution_time)

# Singleton instances
_bridge_client = None
_bridge_server = None

def get_host_bridge_client() -> HostBridgeClient:
    """Get the global host bridge client instance"""
    global _bridge_client
    if _bridge_client is None:
        _bridge_client = HostBridgeClient()
    return _bridge_client

def get_host_bridge_server() -> HostBridgeServer:
    """Get the global host bridge server instance"""
    global _bridge_server
    if _bridge_server is None:
        _bridge_server = HostBridgeServer()
    return _bridge_server

# Convenience functions
def compile_and_run_on_host(source_code: str, host: str = "localhost", port: int = 8900, **kwargs) -> ExecutionResult:
    """Compile and run Kaede code on host system"""
    client = HostBridgeClient(host, port)
    
    try:
        if not client.connect():
            return ExecutionResult(-1, "", "Failed to connect to host")
        
        # Compile
        compile_request = CompilationRequest(source_code=source_code, **kwargs)
        success, message, binary_data = client.compile_kaede_application(compile_request)
        
        if not success:
            return ExecutionResult(-1, "", f"Compilation failed: {message}")
        
        # Execute
        execute_request = ExecutionRequest(binary_data=binary_data)
        result = client.execute_application(execute_request)
        
        return result
        
    finally:
        client.disconnect()

__all__ = [
    'HostPlatform', 'HostArchitecture', 'ExecutionMode', 'SecurityLevel',
    'HostCapabilities', 'CompilationRequest', 'ExecutionRequest', 'ExecutionResult',
    'HostBridgeClient', 'HostBridgeServer', 
    'get_host_bridge_client', 'get_host_bridge_server',
    'compile_and_run_on_host'
]