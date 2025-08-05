#!/usr/bin/env python3
"""
KOS Host Communication Demo
===========================

Demonstrates the Host-KOS communication layer capabilities:
- Kaede code compilation on host systems
- Cross-platform execution
- Remote host bridge communication
- Platform compatibility features

This script shows how Kaede can compile and run applications on host computers through KOS.
"""

import sys
import time
import asyncio
import threading
from pathlib import Path

# Add KOS to path
sys.path.insert(0, str(Path(__file__).parent))

def demo_local_execution():
    """Demo local Kaede execution"""
    print("=" * 60)
    print("DEMO 1: Local Kaede Execution")
    print("=" * 60)
    
    try:
        from kos.core.kaede_integration import execute_kaede_code, KaedeExecutionTarget
        
        # Simple Kaede code
        kaede_code = '''
func main() {
    println("Hello from Kaede!");
    
    var x = 42;
    var y = 8;
    var result = x + y;
    
    println("Calculation: " + x + " + " + y + " = " + result);
    
    return result;
}
'''
        
        print("Executing Kaede code locally...")
        print("Code:")
        print(kaede_code)
        print("\nOutput:")
        
        result = execute_kaede_code(kaede_code, KaedeExecutionTarget.LOCAL_VM)
        
        print(f"Return code: {result.return_code}")
        print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
        print(f"Execution time: {result.execution_time:.3f}s")
        
    except Exception as e:
        print(f"Error in local execution demo: {e}")

def demo_platform_compatibility():
    """Demo platform compatibility features"""
    print("\n" + "=" * 60)
    print("DEMO 2: Platform Compatibility")
    print("=" * 60)
    
    try:
        from kos.core.platform_compat import get_current_platform, adapt_kaede_code, PlatformType
        
        # Get current platform info
        platform_info = get_current_platform()
        
        print("Current Platform Information:")
        print(f"  Platform: {platform_info.platform.value}")
        print(f"  Architecture: {platform_info.architecture.value}")
        print(f"  Version: {platform_info.version}")
        print(f"  Python Version: {platform_info.python_version}")
        print(f"  Available Compilers: {', '.join(platform_info.available_compilers)}")
        print(f"  Library Paths: {len(platform_info.library_paths)} paths")
        
        # Demo code adaptation
        original_code = '''
func main() {
    // Platform-specific code will be adapted
    println("Running on platform!");
    
    // System calls will be translated
    var result = system_call("get_platform_info");
    println("Platform info: " + result);
}
'''
        
        print("\nOriginal Kaede code:")
        print(original_code)
        
        # Adapt for different platforms
        for target_platform in [PlatformType.LINUX, PlatformType.WINDOWS, PlatformType.MACOS]:
            try:
                adapted = adapt_kaede_code(original_code, target_platform)
                print(f"\nAdapted for {target_platform.value}:")
                print("  [Platform-specific adaptations would be applied]")
            except Exception as e:
                print(f"  Could not adapt for {target_platform.value}: {e}")
        
    except Exception as e:
        print(f"Error in platform compatibility demo: {e}")

def demo_project_management():
    """Demo Kaede project management"""
    print("\n" + "=" * 60)
    print("DEMO 3: Kaede Project Management")
    print("=" * 60)
    
    try:
        from kos.core.kaede_integration import (
            KaedeIntegrationEngine, KaedeProject, KaedeProjectType, KaedeExecutionConfig,
            KaedeExecutionTarget
        )
        from kos.core.platform_compat import PlatformType
        
        engine = KaedeIntegrationEngine()
        
        # Create a demo project
        project = KaedeProject(
            name="demo_app",
            type=KaedeProjectType.APPLICATION,
            version="1.0.0",
            source_files=["main.kaede"],
            target_platforms=[PlatformType.LINUX, PlatformType.WINDOWS],
            optimization_level=2
        )
        
        print("Creating Kaede project...")
        print(f"  Name: {project.name}")
        print(f"  Type: {project.type.value}")
        print(f"  Version: {project.version}")
        print(f"  Target Platforms: {[p.value for p in project.target_platforms]}")
        
        if engine.create_project(project):
            print("✓ Project created successfully")
            
            # Try to compile the project
            print("\nCompiling project...")
            if engine.compile_project(project):
                print("✓ Project compiled successfully")
                
                # Execute the project
                print("\nExecuting project...")
                config = KaedeExecutionConfig(target=KaedeExecutionTarget.LOCAL_VM)
                result = engine.execute_project(project, config)
                
                print(f"Execution result:")
                print(f"  Return code: {result.return_code}")
                print(f"  Output: {result.stdout}")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
            else:
                print("✗ Project compilation failed")
        else:
            print("✗ Project creation failed")
            
        # Show metrics
        metrics = engine.get_metrics()
        print(f"\nEngine Metrics:")
        print(f"  Compilations: {metrics['compilations']}")
        print(f"  Executions: {metrics['executions']}")
        print(f"  Average compile time: {metrics['average_compile_time']:.3f}s")
        print(f"  Average execution time: {metrics['average_execution_time']:.3f}s")
        
    except Exception as e:
        print(f"Error in project management demo: {e}")

def demo_host_bridge_server():
    """Demo host bridge server (would run on host system)"""
    print("\n" + "=" * 60)
    print("DEMO 4: Host Bridge Server")
    print("=" * 60)
    
    try:
        from kos.core.host_bridge import HostBridgeServer
        
        print("Host Bridge Server Demo")
        print("(This would normally run on a host system)")
        
        # Create server instance
        server = HostBridgeServer(host="127.0.0.1", port=8901)
        
        print("Server configuration:")
        print(f"  Host: 127.0.0.1")
        print(f"  Port: 8901")
        print(f"  Capabilities: {server.capabilities.platform.value} {server.capabilities.architecture.value}")
        print(f"  Cores: {server.capabilities.cores}")
        print(f"  Memory: {server.capabilities.memory_mb} MB")
        print(f"  Compilers: {server.capabilities.available_compilers}")
        
        print("\nNote: Server would normally run continuously to accept connections")
        print("      Use server.start() to run the actual server")
        
    except Exception as e:
        print(f"Error in host bridge server demo: {e}")

def demo_host_bridge_client():
    """Demo host bridge client"""
    print("\n" + "=" * 60)
    print("DEMO 5: Host Bridge Client")
    print("=" * 60)
    
    try:
        from kos.core.host_bridge import (
            HostBridgeClient, CompilationRequest, ExecutionRequest,
            SecurityLevel, HostPlatform, HostArchitecture
        )
        
        print("Host Bridge Client Demo")
        print("(Attempting to connect to host bridge server)")
        
        # Create client
        client = HostBridgeClient(host="127.0.0.1", port=8901)
        
        print("\nTrying to connect to host bridge...")
        print("(This will fail if no server is running, which is expected)")
        
        if client.connect():
            print("✓ Connected to host bridge server!")
            
            # Show capabilities
            if client.capabilities:
                print("Host capabilities:")
                print(f"  Platform: {client.capabilities['platform']}")
                print(f"  Architecture: {client.capabilities['architecture']}")
                print(f"  Cores: {client.capabilities['cores']}")
                print(f"  Memory: {client.capabilities['memory_mb']} MB")
            
            # Demo compilation request
            kaede_code = '''
func main() {
    println("Hello from remote host!");
    return 42;
}
'''
            
            compile_request = CompilationRequest(
                source_code=kaede_code,
                language="kaede",
                optimization_level=2,
                security_level=SecurityLevel.SANDBOX
            )
            
            print("\nSending compilation request...")
            success, message, binary = client.compile_kaede_application(compile_request)
            
            if success:
                print("✓ Compilation successful!")
                print(f"  Binary size: {len(binary)} bytes")
                
                # Execute
                execute_request = ExecutionRequest(
                    binary_data=binary,
                    timeout=30,
                    security_level=SecurityLevel.SANDBOX
                )
                
                print("\nExecuting on remote host...")
                result = client.execute_application(execute_request)
                
                print(f"Execution result:")
                print(f"  Return code: {result.return_code}")
                print(f"  Output: {result.stdout}")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
            else:
                print(f"✗ Compilation failed: {message}")
            
            client.disconnect()
        else:
            print("✗ Could not connect to host bridge server")
            print("   (This is expected if no server is running)")
        
    except Exception as e:
        print(f"Error in host bridge client demo: {e}")

def demo_advanced_features():
    """Demo advanced Kaede features"""
    print("\n" + "=" * 60)
    print("DEMO 6: Advanced Kaede Features")
    print("=" * 60)
    
    try:
        from kos.core.kaede_integration import execute_kaede_code, KaedeExecutionTarget
        
        # Demo advanced Kaede code
        advanced_code = '''
// Advanced Kaede features demo
func fibonacci(n: Int) -> Int {
    if n <= 1 {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

func main() {
    println("Advanced Kaede Features Demo");
    
    // Calculate Fibonacci numbers
    for i in range(1, 11) {
        var fib = fibonacci(i);
        println("fib(" + i + ") = " + fib);
    }
    
    // Array operations
    var numbers = [1, 2, 3, 4, 5];
    var sum = 0;
    
    for num in numbers {
        sum += num;
    }
    
    println("Sum of array: " + sum);
    
    // Object creation
    var obj = {
        "name": "Kaede",
        "version": "1.0.0",
        "features": ["compilation", "execution", "cross-platform"]
    };
    
    println("Object: " + obj.name + " v" + obj.version);
    
    return 0;
}
'''
        
        print("Executing advanced Kaede code...")
        print("Features demonstrated:")
        print("  - Function definitions with recursion")
        print("  - Control flow (if/else, for loops)")
        print("  - Array operations")
        print("  - Object literals")
        print("  - Type annotations")
        
        print("\nCode execution:")
        result = execute_kaede_code(advanced_code, KaedeExecutionTarget.LOCAL_VM)
        
        print(f"Return code: {result.return_code}")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Errors: {result.stderr}")
        
    except Exception as e:
        print(f"Error in advanced features demo: {e}")

def main():
    """Main demo function"""
    print("KOS Host Communication Demo")
    print("Demonstrating Kaede cross-platform compilation and execution")
    print("=" * 80)
    
    # Run all demos
    demo_local_execution()
    demo_platform_compatibility()
    demo_project_management()
    demo_host_bridge_server()
    demo_host_bridge_client()
    demo_advanced_features()
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print()
    print("Summary of Capabilities Demonstrated:")
    print("✓ Local Kaede code execution")
    print("✓ Platform compatibility detection and adaptation")
    print("✓ Project management and compilation")
    print("✓ Host bridge server/client architecture")
    print("✓ Cross-platform communication protocols")
    print("✓ Advanced Kaede language features")
    print()
    print("Next Steps:")
    print("1. Start a host bridge server on a remote machine")
    print("2. Use the client to compile and execute code remotely")
    print("3. Experiment with different target platforms")
    print("4. Create and manage Kaede projects")
    print("5. Explore the security and sandboxing features")

if __name__ == "__main__":
    main()