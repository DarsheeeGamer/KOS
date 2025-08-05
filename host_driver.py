#!/usr/bin/env python3
"""
KOS Host Driver Script
Manages communication between host OS and KOS virtual environment
"""

import os
import sys
import time
import json
import socket
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kos.kadcm.host_driver import KADCMHostDriver
from kos.kadcm.messages import MessageType
from kos.security.fingerprint import FingerprintManager


class KOSHostDriver:
    """Main host driver for KOS communication"""
    
    def __init__(self, config_file: str = "/etc/kos/host_driver.conf"):
        self.config = self._load_config(config_file)
        self.kadcm_driver = None
        self.fingerprint_mgr = FingerprintManager()
        self._setup_logging()
        
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from file"""
        default_config = {
            "pipe_path": "/var/run/kos/kadcm.pipe",
            "cert_path": "/etc/kos/certs/host.crt",
            "key_path": "/etc/kos/certs/host.key",
            "ca_path": "/etc/kos/certs/ca.crt",
            "log_level": "INFO",
            "reconnect_interval": 5,
            "heartbeat_interval": 30
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
                
        return default_config
        
    def _setup_logging(self):
        """Setup logging"""
        log_level = getattr(logging, self.config["log_level"].upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('kos.host_driver')
        
    def connect(self):
        """Connect to KOS instance"""
        self.logger.info("Connecting to KOS instance...")
        
        # Initialize KADCM driver
        self.kadcm_driver = KADCMHostDriver(
            pipe_path=self.config["pipe_path"],
            cert_path=self.config["cert_path"],
            key_path=self.config["key_path"],
            ca_path=self.config["ca_path"]
        )
        
        # Connect with retry
        max_retries = 5
        for i in range(max_retries):
            try:
                self.kadcm_driver.connect()
                self.logger.info("Connected to KOS successfully")
                return True
            except Exception as e:
                self.logger.warning(f"Connection attempt {i+1} failed: {e}")
                if i < max_retries - 1:
                    time.sleep(self.config["reconnect_interval"])
                    
        return False
        
    def authenticate(self, entity_id: str = None):
        """Authenticate with KOS"""
        if not entity_id:
            entity_id = f"host-{socket.gethostname()}"
            
        self.logger.info(f"Authenticating as {entity_id}")
        
        # Generate or retrieve fingerprint
        fingerprint = self._get_or_create_fingerprint(entity_id)
        
        # Authenticate via KADCM
        if self.kadcm_driver:
            success = self.kadcm_driver.authenticate(
                fingerprint=fingerprint,
                entity_id=entity_id,
                entity_type="host"
            )
            
            if success:
                self.logger.info("Authentication successful")
            else:
                self.logger.error("Authentication failed")
                
            return success
            
        return False
        
    def _get_or_create_fingerprint(self, entity_id: str) -> str:
        """Get existing or create new fingerprint"""
        # Check if we have a stored fingerprint
        fingerprint_file = Path.home() / ".kos" / "host_fingerprint"
        
        if fingerprint_file.exists():
            with open(fingerprint_file, 'r') as f:
                return f.read().strip()
                
        # Create new fingerprint
        import platform
        identifying_data = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }
        
        fingerprint = self.fingerprint_mgr.create_fingerprint(
            entity_id=entity_id,
            entity_type="host",
            identifying_data=identifying_data
        )
        
        # Store it
        fingerprint_file.parent.mkdir(exist_ok=True, mode=0o700)
        with open(fingerprint_file, 'w') as f:
            f.write(fingerprint)
        os.chmod(fingerprint_file, 0o600)
        
        return fingerprint
        
    def _get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics for monitoring"""
        try:
            import psutil
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get network connections (approximate)
            connections = len(psutil.net_connections())
            
            # Get system uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            
            # Format uptime
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime = f"{hours:02d}:{minutes:02d}"
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'connections': connections,
                'uptime': uptime
            }
            
        except ImportError:
            # psutil not available, use basic stats
            with open('/proc/loadavg', 'r') as f:
                load_avg = float(f.read().split()[0])
            
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    key, value = line.split()[:2]
                    meminfo[key.rstrip(':')] = int(value)
                
            total_mem = meminfo['MemTotal']
            free_mem = meminfo['MemFree'] + meminfo.get('Buffers', 0) + meminfo.get('Cached', 0)
            memory_percent = ((total_mem - free_mem) / total_mem) * 100
            
            # Approximate uptime from /proc/uptime
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime = f"{hours:02d}:{minutes:02d}"
            
            return {
                'cpu_percent': load_avg * 100,  # Approximate
                'memory_percent': memory_percent,
                'connections': 0,  # Unknown without psutil
                'uptime': uptime
            }
            
        except Exception as e:
            self.logger.debug(f"Failed to get system stats: {e}")
            return {
                'cpu_percent': 0.0,
                'memory_percent': 0.0,
                'connections': 0,
                'uptime': "00:00"
            }
        
    def execute_command(self, command: str, args: list = None) -> Dict[str, Any]:
        """Execute command in KOS"""
        if not self.kadcm_driver:
            return {"success": False, "error": "Not connected"}
            
        self.logger.info(f"Executing command: {command} {args}")
        
        result = self.kadcm_driver.execute_command(
            command=command,
            args=args,
            cwd=os.getcwd()
        )
        
        return result
        
    def transfer_file(self, operation: str, local_path: str, 
                     remote_path: str) -> Dict[str, Any]:
        """Transfer file to/from KOS"""
        if not self.kadcm_driver:
            return {"success": False, "error": "Not connected"}
            
        self.logger.info(f"File transfer: {operation} {local_path} -> {remote_path}")
        
        if operation == "upload":
            with open(local_path, 'r') as f:
                content = f.read()
                
            result = self.kadcm_driver.transfer_data(
                operation="write",
                path=remote_path,
                content=content
            )
            
        elif operation == "download":
            result = self.kadcm_driver.transfer_data(
                operation="read",
                path=remote_path
            )
            
            if result.get("success") and result.get("content"):
                with open(local_path, 'w') as f:
                    f.write(result["content"])
                    
        else:
            result = {"success": False, "error": f"Unknown operation: {operation}"}
            
        return result
        
    def interactive_shell(self):
        """Start interactive shell session"""
        print("KOS Interactive Shell - Type 'exit' to quit")
        print("=" * 50)
        
        while True:
            try:
                # Get command
                cmd_line = input("kos> ").strip()
                
                if not cmd_line:
                    continue
                    
                if cmd_line.lower() in ['exit', 'quit']:
                    break
                    
                # Parse command
                parts = cmd_line.split()
                command = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                # Special commands
                if command == "upload":
                    if len(args) < 2:
                        print("Usage: upload <local_file> <remote_path>")
                        continue
                    result = self.transfer_file("upload", args[0], args[1])
                    
                elif command == "download":
                    if len(args) < 2:
                        print("Usage: download <remote_path> <local_file>")
                        continue
                    result = self.transfer_file("download", args[1], args[0])
                    
                else:
                    # Execute in KOS
                    result = self.execute_command(command, args)
                    
                # Display result
                if result.get("success"):
                    if result.get("output"):
                        print(result["output"])
                    if result.get("error"):
                        print(f"Error: {result['error']}", file=sys.stderr)
                else:
                    print(f"Command failed: {result.get('error', 'Unknown error')}")
                    
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
                
    def monitor_mode(self):
        """Monitor KOS instance"""
        print("KOS Monitor Mode - Press Ctrl+C to stop")
        print("=" * 50)
        
        try:
            while True:
                # Send heartbeat
                self.kadcm_driver.send_heartbeat()
                
                # Display system stats
                stats = self._get_system_stats()
                print(f"\r[{time.strftime('%H:%M:%S')}] CPU: {stats['cpu_percent']:.1f}% | "
                      f"Memory: {stats['memory_percent']:.1f}% | "
                      f"Connections: {stats['connections']} | "
                      f"Uptime: {stats['uptime']}", end='', flush=True)
                
                time.sleep(self.config["heartbeat_interval"])
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
            
    def disconnect(self):
        """Disconnect from KOS"""
        if self.kadcm_driver:
            self.kadcm_driver.disconnect()
            self.logger.info("Disconnected from KOS")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS Host Driver")
    parser.add_argument('-c', '--config', default="/etc/kos/host_driver.conf",
                       help="Configuration file path")
    parser.add_argument('-m', '--mode', choices=['shell', 'monitor', 'execute'],
                       default='shell', help="Operation mode")
    parser.add_argument('-e', '--execute', help="Command to execute (for execute mode)")
    parser.add_argument('-v', '--verbose', action='store_true',
                       help="Enable verbose logging")
    parser.add_argument('args', nargs='*', help="Command arguments")
    
    args = parser.parse_args()
    
    # Create driver
    driver = KOSHostDriver(args.config)
    
    if args.verbose:
        driver.config["log_level"] = "DEBUG"
        driver._setup_logging()
        
    try:
        # Connect
        if not driver.connect():
            print("Failed to connect to KOS")
            sys.exit(1)
            
        # Authenticate
        if not driver.authenticate():
            print("Failed to authenticate with KOS")
            sys.exit(1)
            
        # Execute based on mode
        if args.mode == 'shell':
            driver.interactive_shell()
            
        elif args.mode == 'monitor':
            driver.monitor_mode()
            
        elif args.mode == 'execute':
            if not args.execute:
                print("No command specified for execute mode")
                sys.exit(1)
                
            result = driver.execute_command(args.execute, args.args)
            
            if result.get("success"):
                if result.get("output"):
                    print(result["output"])
                sys.exit(0)
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", 
                      file=sys.stderr)
                sys.exit(1)
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    finally:
        driver.disconnect()


if __name__ == "__main__":
    main()