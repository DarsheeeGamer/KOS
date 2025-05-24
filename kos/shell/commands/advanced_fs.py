"""
Advanced Filesystem Commands for KOS Shell

This module provides powerful virtual filesystem and memory management commands
that leverage the advanced components of KOS for better filesystem control.
"""

import os
import sys
import time
import logging
import json
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.advanced_fs')

class AdvancedFilesystemCommands:
    """Advanced filesystem commands for KOS shell"""
    
    @staticmethod
    def do_vfs(fs, cwd, arg):
        """
        Virtual filesystem commands
        
        Usage: vfs [command] [args...]
        
        Commands:
          list <path>            List directory contents in virtual filesystem
          mkdir <path>           Create directory in virtual filesystem
          rm <path>              Remove file from virtual filesystem
          rmdir <path>           Remove directory from virtual filesystem
          cat <path>             Display file contents from virtual filesystem
          cp <src> <dst>         Copy file or directory
          mv <src> <dst>         Move file or directory
          import <real> <vfs>    Import from real filesystem to virtual filesystem
          export <vfs> <real>    Export from virtual filesystem to real filesystem
          info <path>            Get file/directory metadata
          stats                  Show virtual filesystem statistics
          
        Options:
          --json                 Output in JSON format
          --recursive            Operate recursively (for rmdir, export, import)
          --binary               Treat file as binary (for cat)
        """
        args = arg.split()
        
        if not args:
            return AdvancedFilesystemCommands.do_vfs.__doc__
        
        # Get virtual filesystem
        virtual_fs = klayer.get_virtual_fs()
        if not virtual_fs:
            return "Error: Virtual filesystem not available"
        
        command = args[0]
        options = args[1:]
        
        # Parse common options
        json_output = '--json' in options
        recursive = '--recursive' in options
        binary = '--binary' in options
        
        # Remove options from arguments
        options = [o for o in options if not o.startswith('--')]
        
        if command == "list":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.list_dir(path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                output = [f"Directory listing of {path}:"]
                output.append(f"Total items: {result['count']}")
                output.append("")
                
                # Format columns
                if result["contents"]:
                    output.append(f"{'Type':<6} {'Size':<10} {'Modified':<20} {'Name':<30}")
                    output.append("-" * 70)
                    
                    for item in result["contents"]:
                        item_type = "DIR" if item["is_dir"] else "FILE"
                        size = item["size"] if not item["is_dir"] else ""
                        
                        # Format timestamp
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", 
                                                time.localtime(item["modified"]))
                        
                        output.append(f"{item_type:<6} {size:<10} {timestamp:<20} {item['name']:<30}")
                
                return "\n".join(output)
        
        elif command == "mkdir":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.create_dir(path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if result.get("already_exists", False):
                    return f"Directory already exists: {path}"
                else:
                    return f"Directory created: {path}"
        
        elif command == "rm":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.delete_file(path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"File deleted: {path}"
        
        elif command == "rmdir":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.remove_dir(path, recursive=recursive)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if recursive:
                    return f"Directory recursively deleted: {path}"
                else:
                    return f"Directory deleted: {path}"
        
        elif command == "cat":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.read_file(path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                content = result["content"]
                
                # Handle binary content
                if binary:
                    return f"Binary file: {path}, Size: {len(content)} bytes"
                else:
                    try:
                        return content.decode('utf-8')
                    except UnicodeDecodeError:
                        return f"Binary file: {path}, Size: {len(content)} bytes"
        
        elif command == "cp":
            if len(options) < 2:
                return "Error: Missing source or destination path"
            
            source_path = options[0]
            target_path = options[1]
            
            result = virtual_fs.copy(source_path, target_path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if result["is_dir"]:
                    return f"Directory copied: {source_path} -> {target_path}"
                else:
                    return f"File copied: {source_path} -> {target_path}"
        
        elif command == "mv":
            if len(options) < 2:
                return "Error: Missing source or destination path"
            
            source_path = options[0]
            target_path = options[1]
            
            result = virtual_fs.move(source_path, target_path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if result["is_dir"]:
                    return f"Directory moved: {source_path} -> {target_path}"
                else:
                    return f"File moved: {source_path} -> {target_path}"
        
        elif command == "import":
            if len(options) < 2:
                return "Error: Missing real or virtual path"
            
            real_path = options[0]
            vfs_path = options[1]
            
            result = virtual_fs.import_from_real_fs(real_path, vfs_path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if result["is_dir"]:
                    return f"Directory imported: {real_path} -> {vfs_path}"
                else:
                    return f"File imported: {real_path} -> {vfs_path} ({result['size']} bytes)"
        
        elif command == "export":
            if len(options) < 2:
                return "Error: Missing virtual or real path"
            
            vfs_path = options[0]
            real_path = options[1]
            
            result = virtual_fs.export_to_real_fs(vfs_path, real_path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                if result["is_dir"]:
                    return f"Directory exported: {vfs_path} -> {real_path}"
                else:
                    return f"File exported: {vfs_path} -> {real_path} ({result['size']} bytes)"
        
        elif command == "info":
            if not options:
                return "Error: Missing path"
            path = options[0]
            
            result = virtual_fs.get_metadata(path)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                metadata = result["metadata"]
                output = [f"Information for {path}:"]
                output.append(f"Type: {'Directory' if result['is_dir'] else 'File'}")
                output.append(f"Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metadata['created']))}")
                output.append(f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metadata['modified']))}")
                output.append(f"Accessed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metadata['accessed']))}")
                
                if not result["is_dir"]:
                    output.append(f"Size: {metadata['size']} bytes")
                
                output.append(f"Permissions: {oct(metadata['permissions'])[2:]}")
                output.append(f"Owner: {metadata['owner']}")
                output.append(f"Group: {metadata['group']}")
                
                return "\n".join(output)
        
        elif command == "stats":
            result = virtual_fs.get_stats()
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                output = ["Virtual Filesystem Statistics:"]
                output.append(f"Total Files: {result['total_files']}")
                output.append(f"Total Directories: {result['total_directories']}")
                
                # Format total size
                size = result['total_size_bytes']
                if size < 1024:
                    size_str = f"{size} bytes"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.2f} KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
                
                output.append(f"Total Size: {size_str}")
                
                return "\n".join(output)
        
        else:
            return f"Error: Unknown command '{command}'"
    
    @staticmethod
    def do_memman(fs, cwd, arg):
        """
        Memory manager commands
        
        Usage: memman [command] [args...]
        
        Commands:
          stats                  Show memory statistics
          cache <id> <data>      Cache data in memory
          get <id>               Get cached data
          delete <id>            Delete cached data
          list [pattern]         List cached objects
          info <id>              Get information about a cached object
          lock <id>              Lock an object to prevent eviction
          unlock <id>            Unlock an object
          clean                  Clean expired cache entries
          gc                     Force garbage collection
          policy <policy>        Set eviction policy (lru, lfu, fifo)
          
        Options:
          --ttl=<seconds>        Time to live for cached data
          --json                 Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return AdvancedFilesystemCommands.do_memman.__doc__
        
        # Get memory manager
        memory_manager = klayer.get_memory_manager()
        if not memory_manager:
            return "Error: Memory manager not available"
        
        command = args[0]
        options = args[1:]
        
        # Parse common options
        json_output = '--json' in options
        ttl = None
        
        for opt in options:
            if opt.startswith('--ttl='):
                try:
                    ttl = int(opt[6:])
                except ValueError:
                    return f"Error: Invalid TTL value in '{opt}'"
        
        # Remove options from arguments
        options = [o for o in options if not o.startswith('--')]
        
        if command == "stats":
            result = memory_manager.get_stats()
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                output = ["Memory Manager Statistics:"]
                output.append(f"Allocated Memory: {result['allocated_memory']} bytes")
                output.append(f"Maximum Memory: {result['max_memory']} bytes")
                output.append(f"Usage: {result['usage_percent']:.2f}%")
                output.append(f"Cache Entries: {result['cache_entries']}")
                output.append(f"Policy: {result['policy']}")
                output.append(f"GC Threshold: {result['gc_threshold'] * 100:.2f}%")
                output.append("")
                
                # Memory Pools
                output.append("Memory Pools:")
                for pool_name, pool_stats in result['pools'].items():
                    output.append(f"  {pool_name}:")
                    output.append(f"    Max Size: {pool_stats['max_size']} bytes")
                    output.append(f"    Block Size: {pool_stats['block_size']} bytes")
                    output.append(f"    Used Blocks: {pool_stats['used_blocks']} / {pool_stats['total_blocks']}")
                    output.append(f"    Usage: {pool_stats['usage_percent']:.2f}%")
                    output.append(f"    Objects: {pool_stats['object_count']}")
                    output.append("")
                
                # System Memory
                if 'system_memory' in result and result['system_memory']:
                    sys_mem = result['system_memory']
                    output.append("System Memory:")
                    output.append(f"  Total: {sys_mem['total'] / (1024*1024*1024):.2f} GB")
                    output.append(f"  Available: {sys_mem['available'] / (1024*1024*1024):.2f} GB")
                    output.append(f"  Used: {sys_mem['used'] / (1024*1024*1024):.2f} GB ({sys_mem['percent']}%)")
                
                return "\n".join(output)
        
        elif command == "cache":
            if len(options) < 2:
                return "Error: Missing object ID or data"
            
            object_id = options[0]
            data = " ".join(options[1:])
            
            success = memory_manager.cache_data(object_id, data, ttl)
            
            if success:
                return f"Data cached with ID: {object_id}" + (f" (TTL: {ttl}s)" if ttl else "")
            else:
                return f"Error: Failed to cache data with ID: {object_id}"
        
        elif command == "get":
            if not options:
                return "Error: Missing object ID"
            
            object_id = options[0]
            success, data = memory_manager.get_cached_data(object_id)
            
            if success:
                if json_output:
                    return json.dumps({"success": True, "object_id": object_id, "data": data}, indent=2)
                else:
                    return f"Data for {object_id}: {data}"
            else:
                return f"Error: No data found for ID: {object_id}"
        
        elif command == "delete":
            if not options:
                return "Error: Missing object ID"
            
            object_id = options[0]
            success = memory_manager.deallocate(object_id)
            
            if success:
                return f"Object deleted: {object_id}"
            else:
                return f"Error: Failed to delete object: {object_id}"
        
        elif command == "list":
            pattern = options[0] if options else None
            result = memory_manager.list_objects(pattern)
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                output = [f"Cached Objects ({result['count']} found):"]
                
                if result['objects']:
                    output.append(f"{'ID':<20} {'Size':<10} {'Age (s)':<10} {'Access':<10} {'Locked':<8}")
                    output.append("-" * 60)
                    
                    for obj in result['objects']:
                        object_id = obj['object_id']
                        size = obj['size']
                        age = obj['age']
                        access_count = obj['access_count']
                        locked = "Yes" if obj['locked'] else "No"
                        
                        output.append(f"{object_id[:20]:<20} {size:<10} {age:.1f}s {access_count:<10} {locked:<8}")
                
                return "\n".join(output)
        
        elif command == "info":
            if not options:
                return "Error: Missing object ID"
            
            object_id = options[0]
            result = memory_manager.get_object_info(object_id)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                info = result['info']
                output = [f"Information for {object_id}:"]
                output.append(f"Size: {info['size']} bytes")
                output.append(f"Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['creation_time']))}")
                output.append(f"Last Access: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['last_access_time']))}")
                output.append(f"Age: {info['age']:.2f} seconds")
                output.append(f"Last Access Age: {info['last_access_age']:.2f} seconds")
                output.append(f"Access Count: {info['access_count']}")
                output.append(f"Locked: {'Yes' if info['locked'] else 'No'}")
                
                if 'ttl' in info:
                    if info['ttl'] is None:
                        output.append("TTL: No expiration")
                    else:
                        output.append(f"TTL: {info['ttl']} seconds")
                        output.append(f"Expired: {'Yes' if info['expired'] else 'No'}")
                
                return "\n".join(output)
        
        elif command == "lock":
            if not options:
                return "Error: Missing object ID"
            
            object_id = options[0]
            success = memory_manager.lock_object(object_id)
            
            if success:
                return f"Object locked: {object_id}"
            else:
                return f"Error: Failed to lock object: {object_id}"
        
        elif command == "unlock":
            if not options:
                return "Error: Missing object ID"
            
            object_id = options[0]
            success = memory_manager.unlock_object(object_id)
            
            if success:
                return f"Object unlocked: {object_id}"
            else:
                return f"Error: Failed to unlock object: {object_id}"
        
        elif command == "clean":
            cleaned = memory_manager.clean_expired()
            return f"Cleaned {cleaned} expired entries"
        
        elif command == "gc":
            collected = memory_manager.garbage_collect()
            return f"Collected {collected} entries during garbage collection"
        
        elif command == "policy":
            if not options:
                return "Error: Missing policy name (lru, lfu, fifo)"
            
            policy = options[0].lower()
            if policy not in ["lru", "lfu", "fifo"]:
                return f"Error: Invalid policy '{policy}'. Must be one of: lru, lfu, fifo"
            
            success = memory_manager.set_policy(policy)
            
            if success:
                return f"Memory eviction policy set to: {policy}"
            else:
                return f"Error: Failed to set policy to {policy}"
        
        else:
            return f"Error: Unknown command '{command}'"
    
    @staticmethod
    def do_resmon(fs, cwd, arg):
        """
        Resource monitoring and management commands
        
        Usage: resmon [command] [args...]
        
        Commands:
          stats                             Show resource statistics
          list                              List resource allocations
          add <consumer> <resource> <min> <max> [priority]  Add resource allocation
          remove <consumer>                 Remove resource allocation
          update <consumer> <resource> <min> <max> [priority]  Update resource allocation
          throttle <consumer> <resource> <value>  Throttle resource usage
          prioritize <on|off>               Enable/disable prioritization
          
        Options:
          --json                 Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return AdvancedFilesystemCommands.do_resmon.__doc__
        
        # Get resource orchestrator from KADVLayer
        from kos.advlayer import kadvlayer
        if not kadvlayer or not kadvlayer.resource_orchestrator:
            return "Error: Resource orchestrator not available"
        
        resource_orchestrator = kadvlayer.resource_orchestrator
        command = args[0]
        options = args[1:]
        
        # Parse common options
        json_output = '--json' in options
        
        # Remove options from arguments
        options = [o for o in options if not o.startswith('--')]
        
        if command == "stats":
            result = resource_orchestrator.get_total_usage()
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                output = ["Resource Usage Statistics:"]
                
                for resource_type, usage in result["total_usage"].items():
                    available = result["available_resources"][resource_type]
                    percent = result["usage_percent"][resource_type]
                    
                    output.append(f"{resource_type}:")
                    output.append(f"  Used: {usage:.2f}")
                    output.append(f"  Available: {available:.2f}")
                    output.append(f"  Usage: {percent:.2f}%")
                
                return "\n".join(output)
        
        elif command == "list":
            result = resource_orchestrator.list_allocations()
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                allocations = result["allocations"]
                output = [f"Resource Allocations ({result['count']} found):"]
                
                for allocation in allocations:
                    consumer_id = allocation["consumer_id"]
                    output.append(f"Consumer: {consumer_id}")
                    output.append(f"  Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(allocation['creation_time']))}")
                    output.append(f"  Last Update: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(allocation['last_update']))}")
                    output.append(f"  Active: {'Yes' if allocation['active'] else 'No'}")
                    output.append("  Constraints:")
                    
                    for resource_type, constraint in allocation["constraints"].items():
                        output.append(f"    {resource_type}:")
                        output.append(f"      Min: {constraint['min_value']}")
                        output.append(f"      Max: {constraint['max_value']}")
                        output.append(f"      Current: {constraint['current_value']}")
                        output.append(f"      Priority: {constraint['priority']}")
                    
                    output.append("")
                
                return "\n".join(output)
        
        elif command == "add":
            if len(options) < 4:
                return "Error: Missing arguments. Usage: resmon add <consumer> <resource> <min> <max> [priority]"
            
            consumer_id = options[0]
            resource_type = options[1]
            
            try:
                min_value = float(options[2])
                max_value = float(options[3])
                priority = int(options[4]) if len(options) > 4 else 0
            except ValueError:
                return "Error: Min, max, and priority must be numeric values"
            
            constraints = {
                resource_type: {
                    "min_value": min_value,
                    "max_value": max_value,
                    "priority": priority
                }
            }
            
            result = resource_orchestrator.add_allocation(consumer_id, constraints)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"Resource allocation added for {consumer_id}"
        
        elif command == "remove":
            if not options:
                return "Error: Missing consumer ID"
            
            consumer_id = options[0]
            result = resource_orchestrator.remove_allocation(consumer_id)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"Resource allocation removed for {consumer_id}"
        
        elif command == "update":
            if len(options) < 4:
                return "Error: Missing arguments. Usage: resmon update <consumer> <resource> <min> <max> [priority]"
            
            consumer_id = options[0]
            resource_type = options[1]
            
            try:
                min_value = float(options[2])
                max_value = float(options[3])
                priority = int(options[4]) if len(options) > 4 else None
            except ValueError:
                return "Error: Min, max, and priority must be numeric values"
            
            constraints = {
                resource_type: {
                    "min_value": min_value,
                    "max_value": max_value
                }
            }
            
            if priority is not None:
                constraints[resource_type]["priority"] = priority
            
            result = resource_orchestrator.update_allocation(consumer_id, constraints)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"Resource allocation updated for {consumer_id}"
        
        elif command == "throttle":
            if len(options) < 3:
                return "Error: Missing arguments. Usage: resmon throttle <consumer> <resource> <value>"
            
            consumer_id = options[0]
            resource_type = options[1]
            
            try:
                value = float(options[2])
            except ValueError:
                return "Error: Throttle value must be numeric"
            
            result = resource_orchestrator.throttle_consumer(consumer_id, resource_type, value)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"Resource {resource_type} throttled to {value} for {consumer_id}"
        
        elif command == "prioritize":
            if not options:
                return "Error: Missing on/off argument"
            
            enabled = options[0].lower() == "on"
            result = resource_orchestrator.set_prioritization(enabled)
            
            if not result["success"]:
                return f"Error: {result['error']}"
            
            if json_output:
                return json.dumps(result, indent=2)
            else:
                return f"Resource prioritization {'enabled' if enabled else 'disabled'}"
        
        else:
            return f"Error: Unknown command '{command}'"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("vfs", AdvancedFilesystemCommands.do_vfs)
    shell.register_command("memman", AdvancedFilesystemCommands.do_memman)
    shell.register_command("resmon", AdvancedFilesystemCommands.do_resmon)
