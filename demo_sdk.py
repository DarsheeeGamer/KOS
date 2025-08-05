#!/usr/bin/env python3
"""
KOS SDK Demonstration
Shows how to develop C, C++, and Python applications for KOS
"""

import os
import sys
from kos.sdk import KOSCompiler, KOSBuilder, KOSRuntime, ApplicationTemplate
from kos.sdk.compiler import Language
from kos.sdk.builder import BuildConfig

def demo_c_application():
    """Demonstrate C application development"""
    print("\n=== C Application Demo ===")
    
    # Create a simple C application
    c_code = """
#include <stdio.h>

int main(int argc, char *argv[]) {
    printf("Hello from KOS C Application!\\n");
    printf("Arguments received: %d\\n", argc - 1);
    
    for (int i = 1; i < argc; i++) {
        printf("  Arg %d: %s\\n", i, argv[i]);
    }
    
    return 0;
}
"""
    
    # Write the C file
    with open("demo.c", "w") as f:
        f.write(c_code)
    
    # Compile it
    compiler = KOSCompiler()
    success, message = compiler.compile("demo.c", "demo_c")
    print(f"Compilation: {message}")
    
    if success and os.path.exists("demo_c"):
        # Run it
        runtime = KOSRuntime()
        process = runtime.execute("./demo_c", ["arg1", "arg2"])
        process.wait()
        stdout, stderr = process.get_output()
        print(f"Output:\n{stdout}")
    
    # Cleanup
    for f in ["demo.c", "demo_c"]:
        if os.path.exists(f):
            os.remove(f)

def demo_cpp_application():
    """Demonstrate C++ application development"""
    print("\n=== C++ Application Demo ===")
    
    # Create a simple C++ application
    cpp_code = """
#include <iostream>
#include <vector>
#include <string>

class KOSDemo {
private:
    std::string name;
    
public:
    KOSDemo(const std::string& appName) : name(appName) {}
    
    void greet() {
        std::cout << "Hello from " << name << "!" << std::endl;
        std::cout << "This is a KOS C++ application." << std::endl;
    }
    
    void processArgs(const std::vector<std::string>& args) {
        std::cout << "Received " << args.size() << " arguments:" << std::endl;
        for (size_t i = 0; i < args.size(); i++) {
            std::cout << "  [" << i << "] " << args[i] << std::endl;
        }
    }
};

int main(int argc, char* argv[]) {
    KOSDemo app("KOS C++ Demo");
    app.greet();
    
    std::vector<std::string> args;
    for (int i = 1; i < argc; i++) {
        args.push_back(argv[i]);
    }
    
    if (!args.empty()) {
        app.processArgs(args);
    }
    
    return 0;
}
"""
    
    # Write the C++ file
    with open("demo.cpp", "w") as f:
        f.write(cpp_code)
    
    # Compile it
    compiler = KOSCompiler()
    success, message = compiler.compile("demo.cpp", "demo_cpp")
    print(f"Compilation: {message}")
    
    if success and os.path.exists("demo_cpp"):
        # Run it
        runtime = KOSRuntime()
        process = runtime.execute("./demo_cpp", ["hello", "world"])
        process.wait()
        stdout, stderr = process.get_output()
        print(f"Output:\n{stdout}")
    
    # Cleanup
    for f in ["demo.cpp", "demo_cpp"]:
        if os.path.exists(f):
            os.remove(f)

def demo_python_application():
    """Demonstrate Python application development"""
    print("\n=== Python Application Demo ===")
    
    # Create a simple Python application
    py_code = '''#!/usr/bin/env python3
import sys

class KOSPythonDemo:
    def __init__(self, name):
        self.name = name
        
    def run(self, args):
        print(f"Hello from {self.name}!")
        print("This is a KOS Python application.")
        
        if args:
            print(f"Received {len(args)} arguments:")
            for i, arg in enumerate(args):
                print(f"  [{i}] {arg}")

if __name__ == "__main__":
    app = KOSPythonDemo("KOS Python Demo")
    app.run(sys.argv[1:])
'''
    
    # Write the Python file
    with open("demo.py", "w") as f:
        f.write(py_code)
    
    # Make it executable
    os.chmod("demo.py", 0o755)
    
    # Run it
    runtime = KOSRuntime()
    process = runtime.execute_python("demo.py", ["python", "rocks"])
    process.wait()
    stdout, stderr = process.get_output()
    print(f"Output:\n{stdout}")
    
    # Cleanup
    if os.path.exists("demo.py"):
        os.remove("demo.py")

def demo_project_build():
    """Demonstrate project build system"""
    print("\n=== Project Build System Demo ===")
    
    # Create a project configuration
    config = BuildConfig(
        name="kos_demo",
        version="1.0.0",
        language=Language.C,
        source_files=["main.c"],
        output_type="executable"
    )
    
    # Create source file
    os.makedirs("demo_project/src", exist_ok=True)
    with open("demo_project/src/main.c", "w") as f:
        f.write("""
#include <stdio.h>

int main() {
    printf("KOS Demo Project Built Successfully!\\n");
    return 0;
}
""")
    
    # Save project config
    builder = KOSBuilder()
    os.chdir("demo_project")
    builder.save_project(config)
    
    # Build the project
    print("Building project...")
    success = builder.build(config)
    
    if success:
        print("Project built successfully!")
        
        # Run the built executable
        if os.path.exists("build/kos_demo"):
            runtime = KOSRuntime()
            process = runtime.execute("./build/kos_demo")
            process.wait()
            stdout, stderr = process.get_output()
            print(f"Output: {stdout}")
    
    # Cleanup
    os.chdir("..")
    import shutil
    if os.path.exists("demo_project"):
        shutil.rmtree("demo_project")

def main():
    """Run all demonstrations"""
    print("KOS SDK Demonstration")
    print("=====================")
    print("This demo shows C, C++, and Python development on KOS")
    
    # Check for compiler availability
    compiler = KOSCompiler()
    print("\nDetected Compilers:")
    for comp_type, comp_path in compiler.compilers.items():
        if comp_path:
            print(f"  - {comp_type.name}: {comp_path}")
    
    # Run demos based on available compilers
    if compiler.compilers.get(compiler._get_compiler_for_language(Language.C)):
        demo_c_application()
    else:
        print("\nSkipping C demo - no C compiler found")
    
    if compiler.compilers.get(compiler._get_compiler_for_language(Language.CPP)):
        demo_cpp_application()
    else:
        print("\nSkipping C++ demo - no C++ compiler found")
    
    # Python is always available
    demo_python_application()
    
    # Demonstrate project build system
    if compiler.compilers.get(compiler._get_compiler_for_language(Language.C)):
        demo_project_build()
    
    print("\n=== Demo Complete ===")
    print("KOS SDK supports full C, C++, and Python development!")

if __name__ == "__main__":
    main()