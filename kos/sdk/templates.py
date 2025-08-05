"""
KOS Application Templates - Starter templates for C, C++, and Python apps
"""

import os
from typing import Dict, Optional
from .compiler import Language

class ApplicationTemplate:
    """
    Application template generator for KOS
    """
    
    @staticmethod
    def create_project(name: str, language: Language, project_dir: Optional[str] = None) -> bool:
        """
        Create a new project from template
        
        Args:
            name: Project name
            language: Programming language
            project_dir: Directory to create project in (defaults to current dir)
            
        Returns:
            Success status
        """
        
        if project_dir is None:
            project_dir = name
            
        # Create project directory
        os.makedirs(project_dir, exist_ok=True)
        
        # Create project structure
        os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "include"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "docs"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "tests"), exist_ok=True)
        
        # Generate template files based on language
        if language == Language.C:
            ApplicationTemplate._create_c_template(name, project_dir)
        elif language == Language.CPP:
            ApplicationTemplate._create_cpp_template(name, project_dir)
        elif language == Language.PYTHON:
            ApplicationTemplate._create_python_template(name, project_dir)
        else:
            return False
            
        # Create README
        ApplicationTemplate._create_readme(name, language, project_dir)
        
        # Create project configuration
        ApplicationTemplate._create_project_config(name, language, project_dir)
        
        return True
        
    @staticmethod
    def _create_c_template(name: str, project_dir: str):
        """Create C application template"""
        
        # Main source file
        main_c = f"""/*
 * {name} - KOS (Kaede Operating System) C Application
 * 
 * This is a template application for the Kaede Operating System written in C.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// KOS API headers (when available)
// #include <kos/api.h>
// #include <kos/system.h>

// Application headers
#include "{name}.h"

// Function prototypes
void print_usage(const char *program_name);
int process_arguments(int argc, char *argv[]);

// Main entry point
int main(int argc, char *argv[]) {{
    printf("{name} - KOS C Application\\n");
    printf("==========================\\n\\n");
    
    // Process command line arguments
    if (process_arguments(argc, argv) != 0) {{
        print_usage(argv[0]);
        return 1;
    }}
    
    // Initialize KOS runtime (when available)
    // kos_init();
    
    // Your application logic here
    printf("Hello from {name}!\\n");
    printf("This is a KOS C application template.\\n");
    
    // Example: Get system information
    // KOSSystemInfo info;
    // if (kos_get_system_info(&info) == 0) {{
    //     printf("KOS Version: %s\\n", info.version);
    //     printf("Platform: %s\\n", info.platform);
    // }}
    
    // Cleanup
    // kos_cleanup();
    
    return 0;
}}

void print_usage(const char *program_name) {{
    printf("Usage: %s [options]\\n", program_name);
    printf("Options:\\n");
    printf("  -h, --help     Show this help message\\n");
    printf("  -v, --version  Show version information\\n");
}}

int process_arguments(int argc, char *argv[]) {{
    for (int i = 1; i < argc; i++) {{
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {{
            print_usage(argv[0]);
            exit(0);
        }} else if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--version") == 0) {{
            printf("{name} version 1.0.0\\n");
            exit(0);
        }} else {{
            fprintf(stderr, "Unknown option: %s\\n", argv[i]);
            return 1;
        }}
    }}
    return 0;
}}
"""
        
        # Header file
        header_h = f"""/*
 * {name}.h - Main header for {name}
 */

#ifndef {name.upper()}_H
#define {name.upper()}_H

#define APP_NAME "{name}"
#define APP_VERSION "1.0.0"

// Type definitions
typedef struct {{
    char name[256];
    char version[32];
    int debug_mode;
}} AppConfig;

// Function declarations
// Add your function prototypes here

#endif // {name.upper()}_H
"""
        
        # Write files
        with open(os.path.join(project_dir, "src", "main.c"), 'w') as f:
            f.write(main_c)
            
        with open(os.path.join(project_dir, "include", f"{name}.h"), 'w') as f:
            f.write(header_h)
            
    @staticmethod
    def _create_cpp_template(name: str, project_dir: str):
        """Create C++ application template"""
        
        # Main source file
        main_cpp = f"""/*
 * {name} - KOS (Kaede Operating System) C++ Application
 * 
 * This is a template application for the Kaede Operating System written in C++.
 */

#include <iostream>
#include <string>
#include <vector>
#include <memory>

// KOS API headers (when available)
// #include <kos/api.hpp>
// #include <kos/system.hpp>

// Application headers
#include "{name}.hpp"

using namespace std;

// Application class
class {name}App {{
private:
    string appName;
    string version;
    bool debugMode;
    
public:
    {name}App() : appName("{name}"), version("1.0.0"), debugMode(false) {{}}
    
    void printBanner() {{
        cout << appName << " - KOS C++ Application" << endl;
        cout << "============================" << endl << endl;
    }}
    
    int run(int argc, char* argv[]) {{
        // Process arguments
        if (!processArguments(argc, argv)) {{
            return 1;
        }}
        
        // Initialize KOS runtime (when available)
        // kos::Runtime::initialize();
        
        // Your application logic here
        cout << "Hello from " << appName << "!" << endl;
        cout << "This is a KOS C++ application template." << endl;
        
        // Example: Using KOS API
        // auto systemInfo = kos::System::getInfo();
        // cout << "KOS Version: " << systemInfo.version << endl;
        // cout << "Platform: " << systemInfo.platform << endl;
        
        // Cleanup
        // kos::Runtime::cleanup();
        
        return 0;
    }}
    
private:
    bool processArguments(int argc, char* argv[]) {{
        vector<string> args(argv + 1, argv + argc);
        
        for (const auto& arg : args) {{
            if (arg == "-h" || arg == "--help") {{
                printUsage();
                exit(0);
            }} else if (arg == "-v" || arg == "--version") {{
                cout << appName << " version " << version << endl;
                exit(0);
            }} else if (arg == "-d" || arg == "--debug") {{
                debugMode = true;
            }} else {{
                cerr << "Unknown option: " << arg << endl;
                printUsage();
                return false;
            }}
        }}
        return true;
    }}
    
    void printUsage() {{
        cout << "Usage: {name} [options]" << endl;
        cout << "Options:" << endl;
        cout << "  -h, --help     Show this help message" << endl;
        cout << "  -v, --version  Show version information" << endl;
        cout << "  -d, --debug    Enable debug mode" << endl;
    }}
}};

// Main entry point
int main(int argc, char* argv[]) {{
    {name}App app;
    app.printBanner();
    return app.run(argc, argv);
}}
"""
        
        # Header file
        header_hpp = f"""/*
 * {name}.hpp - Main header for {name}
 */

#ifndef {name.upper()}_HPP
#define {name.upper()}_HPP

#include <string>
#include <exception>

namespace {name.lower()} {{

// Constants
constexpr const char* APP_NAME = "{name}";
constexpr const char* APP_VERSION = "1.0.0";

// Custom exception class
class {name}Exception : public std::exception {{
private:
    std::string message;
    
public:
    explicit {name}Exception(const std::string& msg) : message(msg) {{}}
    
    const char* what() const noexcept override {{
        return message.c_str();
    }}
}};

// Application configuration
struct Config {{
    std::string name = APP_NAME;
    std::string version = APP_VERSION;
    bool debugMode = false;
}};

// Add your class declarations here

}} // namespace {name.lower()}

#endif // {name.upper()}_HPP
"""
        
        # Write files
        with open(os.path.join(project_dir, "src", "main.cpp"), 'w') as f:
            f.write(main_cpp)
            
        with open(os.path.join(project_dir, "include", f"{name}.hpp"), 'w') as f:
            f.write(header_hpp)
            
    @staticmethod
    def _create_python_template(name: str, project_dir: str):
        """Create Python application template"""
        
        # Main script
        main_py = f'''#!/usr/bin/env python3
"""
{name} - KOS (Kaede Operating System) Python Application

This is a template application for the Kaede Operating System written in Python.
"""

import sys
import argparse
import logging
from typing import Optional, List

# KOS API imports (when available)
# from kos import api
# from kos import system

# Application version
__version__ = "1.0.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class {name}App:
    """Main application class for {name}"""
    
    def __init__(self, debug: bool = False):
        self.app_name = "{name}"
        self.version = __version__
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
            
    def run(self, args: List[str]) -> int:
        """Run the application"""
        
        logger.info(f"Starting {{self.app_name}} v{{self.version}}")
        
        # Initialize KOS runtime (when available)
        # kos.initialize()
        
        # Your application logic here
        print(f"Hello from {{self.app_name}}!")
        print("This is a KOS Python application template.")
        
        # Example: Get system information
        # try:
        #     info = kos.system.get_info()
        #     print(f"KOS Version: {{info.version}}")
        #     print(f"Platform: {{info.platform}}")
        # except Exception as e:
        #     logger.error(f"Failed to get system info: {{e}}")
        
        # Process any additional arguments
        if args:
            print(f"Arguments received: {{args}}")
        
        # Cleanup
        # kos.cleanup()
        
        logger.info(f"{{self.app_name}} completed successfully")
        return 0


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description=f"{{name}} - KOS Python Application",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {{__version__}}'
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    parser.add_argument(
        'args',
        nargs='*',
        help='Additional arguments'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Create and run application
    app = {name}App(debug=args.debug)
    
    try:
        sys.exit(app.run(args.args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {{e}}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
        
        # Setup.py
        setup_py = f'''#!/usr/bin/env python3
"""
Setup script for {name}
"""

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="{name.lower()}",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A KOS Python application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/{name.lower()}",
    packages=find_packages(where="src"),
    package_dir={{"": "src"}},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.6",
    install_requires=[
        # Add your dependencies here
    ],
    entry_points={{
        'console_scripts': [
            '{name.lower()}={name.lower()}.main:main',
        ],
    }},
)
'''
        
        # Write files
        with open(os.path.join(project_dir, "src", "main.py"), 'w') as f:
            f.write(main_py)
            
        # Make executable
        os.chmod(os.path.join(project_dir, "src", "main.py"), 0o755)
        
        with open(os.path.join(project_dir, "setup.py"), 'w') as f:
            f.write(setup_py)
            
    @staticmethod
    def _create_readme(name: str, language: Language, project_dir: str):
        """Create README file"""
        
        readme = f"""# {name}

A KOS application written in {language.value.upper()}.

## Description

This is a template application for KOS (Kaede Operating System). It demonstrates the basic structure and conventions for developing KOS applications.

## Building

### Prerequisites

- KOS SDK installed
- {language.value.upper()} development tools

### Build Instructions

```bash
# Build the application
kos-build

# Or manually:
{'make' if language != Language.PYTHON else 'python setup.py build'}
```

## Running

```bash
# Run the application
./{name.lower()}

# Or through KOS runtime:
kos-run {name.lower()}
```

## Project Structure

```
{name}/
├── src/            # Source files
├── include/        # Header files (C/C++)
├── tests/          # Test files
├── docs/           # Documentation
├── kos-project.json  # Project configuration
└── README.md       # This file
```

## Development

### Adding New Features

1. Create new source files in `src/`
2. Add headers to `include/` (for C/C++)
3. Update `kos-project.json` with new files
4. Rebuild the project

### Testing

```bash
# Run tests
kos-test
```

## License

This is a template project. Add your license here.

## Contributing

Contributions are welcome! Please read the contributing guidelines first.
"""
        
        with open(os.path.join(project_dir, "README.md"), 'w') as f:
            f.write(readme)
            
    @staticmethod
    def _create_project_config(name: str, language: Language, project_dir: str):
        """Create project configuration file"""
        
        import json
        
        config = {
            "name": name,
            "version": "1.0.0",
            "language": language.value,
            "source_files": [f"src/main.{language.value}"],
            "include_dirs": ["include"] if language != Language.PYTHON else [],
            "libraries": [],
            "lib_dirs": [],
            "compiler_flags": [],
            "linker_flags": [],
            "output_type": "executable",
            "output_name": name.lower(),
            "dependencies": []
        }
        
        with open(os.path.join(project_dir, "kos-project.json"), 'w') as f:
            json.dump(config, f, indent=2)
            
        # Create a simple Makefile for C/C++ projects
        if language in [Language.C, Language.CPP]:
            makefile = f"""# Makefile for {name}

CC = {'gcc' if language == Language.C else 'g++'}
CFLAGS = -Wall -Wextra -O2 {'std=c11' if language == Language.C else '-std=c++17'} -Iinclude
TARGET = {name.lower()}
SOURCES = src/main.{language.value}
OBJECTS = $(SOURCES:.{language.value}=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
\t$(CC) $(CFLAGS) -o $@ $^

clean:
\trm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
"""
            
            with open(os.path.join(project_dir, "Makefile"), 'w') as f:
                f.write(makefile)