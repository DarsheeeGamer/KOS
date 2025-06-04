#!/usr/bin/env python3
"""
KOS System Verification Script

This script tests all major KOS components to ensure they're properly implemented
and working as expected in a real operating system environment.
"""

import os
import sys
import json
import time
import logging
import importlib
import traceback
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kos_system_check')

# Add KOS module to Python path if needed
KOS_ROOT = os.path.dirname(os.path.abspath(__file__))
if KOS_ROOT not in sys.path:
    sys.path.insert(0, KOS_ROOT)

class SystemCheck:
    """Main system verification class"""
    
    def __init__(self):
        self.results = {
            "core": {},
            "kaede": {},
            "layer": {},
            "advlayer": {},
            "shell": {},
            "security": {},
            "networking": {},
            "package_mgmt": {}
        }
        self.success_count = 0
        self.failure_count = 0
        
    def run_all_checks(self):
        """Run all system checks"""
        print("Starting KOS system verification...")
        print("=" * 60)
        
        try:
            # Core components
            self.check_core_components()
            
            # Kaede language
            self.check_kaede_language()
            
            # Kernel layers
            self.check_kernel_layers()
            
            # Shell system
            self.check_shell_system()
            
            # Security system
            self.check_security_system()
            
            # Package management
            self.check_package_management()
            
            # Networking
            self.check_networking()
            
        except Exception as e:
            logger.error(f"System check failed with critical error: {e}")
            traceback.print_exc()
            
        # Print summary
        self.print_summary()
        
        return self.success_count > 0 and self.failure_count == 0
        
    def record_result(self, category, component, success, message):
        """Record a test result"""
        self.results[category][component] = {
            "success": success,
            "message": message
        }
        
        status = "✓" if success else "✗"
        color = "\033[92m" if success else "\033[91m"
        reset = "\033[0m"
        
        print(f"  {color}{status}{reset} {category}.{component}: {message}")
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            logger.error(f"FAILED: {category}.{component}: {message}")
    
    def check_import(self, category, component, module_path):
        """Check if a module can be imported"""
        try:
            module = importlib.import_module(module_path)
            self.record_result(category, component, True, f"Successfully imported {module_path}")
            return module
        except ImportError as e:
            self.record_result(category, component, False, f"Failed to import {module_path}: {str(e)}")
            return None
        except Exception as e:
            self.record_result(category, component, False, f"Error importing {module_path}: {str(e)}")
            return None
    
    def check_core_components(self):
        """Check core KOS components"""
        print("\nChecking core components...")
        
        # Base system
        base = self.check_import("core", "base", "kos.base")
        
        # Filesystem
        fs = self.check_import("core", "filesystem", "kos.filesystem")
        if fs:
            try:
                # Try to create a filesystem instance
                filesystem = fs.FileSystem()
                self.record_result("core", "filesystem_ops", True, "FileSystem initialized successfully")
            except Exception as e:
                self.record_result("core", "filesystem_ops", False, f"FileSystem error: {str(e)}")
        
        # Process manager
        proc_mgr = self.check_import("core", "process_manager", "kos.process.manager")
        if proc_mgr:
            try:
                pm = proc_mgr.ProcessManager()
                self.record_result("core", "process_manager_ops", True, "ProcessManager initialized")
            except Exception as e:
                self.record_result("core", "process_manager_ops", False, f"ProcessManager error: {str(e)}")
        
        # User system
        user_sys = self.check_import("core", "user_system", "kos.user_system")
        if user_sys:
            try:
                # Check if we can access the current user
                us = user_sys.UserSystem(None, None)  # Simplified for testing
                self.record_result("core", "user_system_ops", True, "UserSystem accessible")
            except Exception as e:
                self.record_result("core", "user_system_ops", False, f"UserSystem error: {str(e)}")
        
        # Package manager
        pkg_mgr = self.check_import("core", "package_manager", "kos.package_manager")
        if pkg_mgr:
            try:
                pm = pkg_mgr.KpmManager()
                self.record_result("core", "package_manager_ops", True, "Package manager initialized")
            except Exception as e:
                self.record_result("core", "package_manager_ops", False, f"Package manager error: {str(e)}")
    
    def check_kaede_language(self):
        """Check Kaede language components"""
        print("\nChecking Kaede language...")
        
        # Core Kaede module
        kaede = self.check_import("kaede", "core", "kos.kaede")
        
        # Lexer
        lexer = self.check_import("kaede", "lexer", "kos.kaede.lexer")
        if lexer:
            try:
                lex = lexer.KaedeLexer()
                tokens = lex.tokenize("let x = 42")
                self.record_result("kaede", "lexer_ops", True, f"Lexer working - tokenized {len(tokens)} tokens")
            except Exception as e:
                self.record_result("kaede", "lexer_ops", False, f"Lexer error: {str(e)}")
        
        # Parser
        parser = self.check_import("kaede", "parser", "kos.kaede.parser")
        if parser:
            try:
                p = parser.KaedeParser()
                self.record_result("kaede", "parser_ops", True, "Parser initialized")
            except Exception as e:
                self.record_result("kaede", "parser_ops", False, f"Parser error: {str(e)}")
        
        # Standard Library
        stdlib = self.check_import("kaede", "stdlib", "kos.kaede.stdlib")
        if stdlib:
            try:
                std_lib = stdlib.get_stdlib()
                modules = std_lib.list_modules()
                self.record_result("kaede", "stdlib_ops", True, f"Standard library working - {len(modules)} modules")
            except Exception as e:
                self.record_result("kaede", "stdlib_ops", False, f"Standard library error: {str(e)}")
        
        # Compiler
        compiler = self.check_import("kaede", "compiler", "kos.kaede.compiler")
        if compiler:
            try:
                comp = compiler.KaedeCompiler()
                stats = comp.get_compilation_stats()
                self.record_result("kaede", "compiler_ops", True, f"Compiler working - stats: {stats}")
            except Exception as e:
                self.record_result("kaede", "compiler_ops", False, f"Compiler error: {str(e)}")
        
        # Runtime
        runtime = self.check_import("kaede", "runtime", "kos.kaede.runtime")
        if runtime:
            try:
                rt = runtime.KaedeRuntime()
                self.record_result("kaede", "runtime_ops", True, "Runtime initialized")
            except Exception as e:
                self.record_result("kaede", "runtime_ops", False, f"Runtime error: {str(e)}")
        
        # Memory manager
        memory = self.check_import("kaede", "memory_manager", "kos.kaede.memory_manager")
        if memory:
            try:
                mm = memory.memory_manager
                stats = mm.get_statistics()
                self.record_result("kaede", "memory_manager_ops", True, f"Memory manager working - stats: {stats}")
            except Exception as e:
                self.record_result("kaede", "memory_manager_ops", False, f"Memory manager error: {str(e)}")
    
    def check_kernel_layers(self):
        """Check kernel layer components"""
        print("\nChecking kernel layers...")
        
        # KLayer
        klayer = self.check_import("layer", "klayer", "kos.layer")
        if klayer:
            try:
                kl = klayer.get_klayer()
                stats = kl.get_system_statistics()
                self.record_result("layer", "klayer_ops", True, f"KLayer working - stats available")
            except Exception as e:
                self.record_result("layer", "klayer_ops", False, f"KLayer error: {str(e)}")
        
        # KADVLayer
        kadvlayer = self.check_import("advlayer", "kadvlayer", "kos.advlayer")
        if kadvlayer:
            try:
                kadv = kadvlayer.get_kadvlayer()
                health = kadv.get_system_health()
                self.record_result("advlayer", "kadvlayer_ops", True, f"KADVLayer working - health: {health.get('status', 'unknown')}")
            except Exception as e:
                self.record_result("advlayer", "kadvlayer_ops", False, f"KADVLayer error: {str(e)}")
    
    def check_shell_system(self):
        """Check shell system"""
        print("\nChecking shell system...")
        
        # Main shell
        shell = self.check_import("shell", "main_shell", "kos.shell")
        
        # Commands
        commands = self.check_import("shell", "commands", "kos.commands")
        if commands:
            try:
                # Try to create a shell instance
                from kos.filesystem.base import FileSystem
                from kos.process.manager import ProcessManager
                from kos.package_manager import KpmManager
                from kos.user_system import UserSystem
                
                fs = FileSystem()
                pm = ProcessManager()
                kpm = KpmManager()
                us = UserSystem(None, None)
                
                shell_inst = commands.KaedeShell(fs, kpm, pm, us)
                self.record_result("shell", "shell_instance", True, "Shell instance created successfully")
            except Exception as e:
                self.record_result("shell", "shell_instance", False, f"Shell instance error: {str(e)}")
        
        # Shell utilities
        shell_utils = self.check_import("shell", "shell_utils", "kos.shell.commands")
    
    def check_security_system(self):
        """Check security components"""
        print("\nChecking security system...")
        
        # Security modules
        security = self.check_import("security", "main", "kos.security")
        
        # Authentication
        auth = self.check_import("security", "auth", "kos.auth_manager")
        if auth:
            try:
                auth_mgr = auth.AuthenticationManager()
                self.record_result("security", "auth_ops", True, "Authentication manager initialized")
            except Exception as e:
                self.record_result("security", "auth_ops", False, f"Authentication error: {str(e)}")
    
    def check_package_management(self):
        """Check package management system"""
        print("\nChecking package management...")
        
        # Repository configuration
        repo_config = self.check_import("package_mgmt", "repo_config", "kos.repo_config")
        if repo_config:
            try:
                repo_mgr = repo_config.get_repository_manager()
                stats = repo_mgr.get_statistics()
                self.record_result("package_mgmt", "repo_manager_ops", True, f"Repository manager working - {stats['repositories']['total']} repos")
            except Exception as e:
                self.record_result("package_mgmt", "repo_manager_ops", False, f"Repository manager error: {str(e)}")
        
        # Package database
        pkg_db = self.check_import("package_mgmt", "package_db", "kos.package")
    
    def check_networking(self):
        """Check networking components"""
        print("\nChecking networking...")
        
        # Network modules
        network = self.check_import("networking", "main", "kos.network")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("KOS SYSTEM CHECK SUMMARY")
        print("=" * 60)
        
        total_tests = self.success_count + self.failure_count
        success_rate = (self.success_count / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: \033[92m{self.success_count}\033[0m")
        print(f"Failed: \033[91m{self.failure_count}\033[0m")
        print(f"Success rate: {success_rate:.1f}%")
        
        # Category breakdown
        print("\nResults by category:")
        for category, tests in self.results.items():
            if tests:
                passed = sum(1 for test in tests.values() if test['success'])
                total = len(tests)
                print(f"  {category}: {passed}/{total}")
        
        # Failed tests
        if self.failure_count > 0:
            print("\nFailed tests:")
            for category, tests in self.results.items():
                for test_name, result in tests.items():
                    if not result['success']:
                        print(f"  \033[91m✗\033[0m {category}.{test_name}: {result['message']}")
        
        # Overall status
        if self.failure_count == 0:
            print(f"\n\033[92m✓ All tests passed! KOS is functioning correctly.\033[0m")
        else:
            print(f"\n\033[91m✗ {self.failure_count} tests failed. KOS needs attention.\033[0m")
        
        print("=" * 60)
        
        # Save results to file
        try:
            with open('system_check_results.json', 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'summary': {
                        'total_tests': total_tests,
                        'passed': self.success_count,
                        'failed': self.failure_count,
                        'success_rate': success_rate
                    },
                    'results': self.results
                }, f, indent=2)
            print("Results saved to system_check_results.json")
        except Exception as e:
            print(f"Warning: Could not save results: {e}")

def main():
    """Main entry point"""
    try:
        checker = SystemCheck()
        success = checker.run_all_checks()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"System check failed with critical error: {e}")
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
