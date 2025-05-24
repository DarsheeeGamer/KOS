"""
Container Utilities for KOS Shell

This module provides Docker-like container management commands for KOS.
"""

import os
import sys
import time
import logging
import json
import shlex
import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer
from kos.container import ContainerManager, ImageManager, Container, Image

# Set up logging
logger = logging.getLogger('KOS.shell.commands.container_utils')

class ContainerUtilities:
    """Container commands for KOS shell"""
    
    @staticmethod
    def do_docker(fs, cwd, arg):
        """
        Manage KOS containers and images
        
        Usage: docker COMMAND [options]
        
        Commands:
          run [options] IMAGE [COMMAND] [ARG...]    Run a command in a new container
          exec CONTAINER COMMAND [ARG...]           Run a command in a running container
          ps [options]                              List containers
          images [options]                          List images
          pull [options] NAME[:TAG]                 Pull an image from registry
          stop [options] CONTAINER [CONTAINER...]   Stop one or more containers
          start CONTAINER [CONTAINER...]            Start one or more containers
          restart CONTAINER [CONTAINER...]          Restart one or more containers
          rm [options] CONTAINER [CONTAINER...]     Remove one or more containers
          rmi [options] IMAGE [IMAGE...]            Remove one or more images
          logs [options] CONTAINER                  Fetch the logs of a container
          inspect OBJECT [OBJECT...]                Return detailed information on objects
          version                                   Show the Docker version information
        """
        args = shlex.split(arg)
        
        if not args:
            return ContainerUtilities.do_docker.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "run":
            return ContainerUtilities._docker_run(options)
        elif command == "exec":
            return ContainerUtilities._docker_exec(options)
        elif command == "ps":
            return ContainerUtilities._docker_ps(options)
        elif command == "images":
            return ContainerUtilities._docker_images(options)
        elif command == "pull":
            return ContainerUtilities._docker_pull(options)
        elif command == "stop":
            return ContainerUtilities._docker_stop(options)
        elif command == "start":
            return ContainerUtilities._docker_start(options)
        elif command == "restart":
            return ContainerUtilities._docker_restart(options)
        elif command == "rm":
            return ContainerUtilities._docker_rm(options)
        elif command == "rmi":
            return ContainerUtilities._docker_rmi(options)
        elif command == "logs":
            return ContainerUtilities._docker_logs(options)
        elif command == "inspect":
            return ContainerUtilities._docker_inspect(options)
        elif command == "version":
            return ContainerUtilities._docker_version(options)
        else:
            return f"docker: '{command}' is not a docker command.\nSee 'docker --help'"
    
    @staticmethod
    def _docker_run(options):
        """Run a command in a new container"""
        # Parse options
        detach = False
        name = None
        environment = {}
        volumes = []
        ports = {}
        
        i = 0
        while i < len(options):
            if options[i] == "-d" or options[i] == "--detach":
                detach = True
                i += 1
            elif options[i] == "--name":
                if i + 1 < len(options):
                    name = options[i+1]
                    i += 2
                else:
                    return "docker: option requires an argument -- '--name'"
            elif options[i] == "-e" or options[i] == "--env":
                if i + 1 < len(options):
                    env_var = options[i+1]
                    if "=" in env_var:
                        key, value = env_var.split("=", 1)
                        environment[key] = value
                    i += 2
                else:
                    return "docker: option requires an argument -- '-e'"
            elif options[i] == "-v" or options[i] == "--volume":
                if i + 1 < len(options):
                    volumes.append(options[i+1])
                    i += 2
                else:
                    return "docker: option requires an argument -- '-v'"
            elif options[i] == "-p" or options[i] == "--publish":
                if i + 1 < len(options):
                    port_mapping = options[i+1]
                    if ":" in port_mapping:
                        host_port, container_port = port_mapping.split(":", 1)
                        ports[host_port] = container_port
                    i += 2
                else:
                    return "docker: option requires an argument -- '-p'"
            else:
                break
            
        # Check if image is specified
        if i >= len(options):
            return "docker: 'run' requires at least 1 argument.\nSee 'docker run --help'"
        
        # Get image name and command
        image = options[i]
        i += 1
        command = " ".join(options[i:]) if i < len(options) else None
        
        # Generate container name if not specified
        if not name:
            import random
            adjectives = ["happy", "jolly", "dreamy", "sad", "angry", "pensive", "focused"]
            names = ["einstein", "newton", "tesla", "feynman", "turing", "hawking", "curie"]
            name = f"{random.choice(adjectives)}_{random.choice(names)}"
        
        # Create and start container
        success, message, container = ContainerManager.create_container(
            name=name,
            image=image,
            command=command,
            environment=environment,
            volumes=volumes,
            ports=ports
        )
        
        if not success:
            return f"docker: failed to create container: {message}"
        
        # Start container
        success, message = container.start()
        
        if not success:
            return f"docker: failed to start container: {message}"
        
        if detach:
            return container.id
        else:
            # Simulate container logs
            time.sleep(0.5)  # Pretend to run the command
            return f"Container {container.id} started\nCommand output would appear here"
    
    @staticmethod
    def _docker_exec(options):
        """Execute a command in a running container"""
        if len(options) < 2:
            return "docker: 'exec' requires at least 2 arguments.\nSee 'docker exec --help'"
        
        container_id = options[0]
        command = " ".join(options[1:])
        
        # Get container
        container = ContainerManager.get_container(container_id)
        if not container:
            container = ContainerManager.get_container_by_name(container_id)
        
        if not container:
            return f"docker: container '{container_id}' not found"
        
        # Execute command
        success, message, output = container.exec(command)
        
        if not success:
            return f"docker: failed to execute command: {message}"
        
        return output
    
    @staticmethod
    def _docker_ps(options):
        """List containers"""
        # Parse options
        all_containers = False
        quiet = False
        
        for option in options:
            if option == "-a" or option == "--all":
                all_containers = True
            elif option == "-q" or option == "--quiet":
                quiet = True
        
        # Get containers
        containers = ContainerManager.list_containers(all=all_containers)
        
        if quiet:
            return "\n".join([container.id for container in containers])
        
        # Format output
        result = ["CONTAINER ID   IMAGE          COMMAND       CREATED        STATUS         PORTS          NAMES"]
        
        for container in containers:
            # Format created time
            created_time = datetime.datetime.fromtimestamp(container.created_at)
            created_str = created_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Format command
            command = container.command if container.command else ""
            if len(command) > 20:
                command = command[:17] + "..."
            
            # Format ports
            ports_str = ", ".join([f"{host}:{container}" for host, container in container.ports.items()])
            
            # Format status
            status_str = container.status
            
            result.append(f"{container.id[:12]}   {container.image:<14} {command:<12} {created_str}   {status_str:<14} {ports_str:<14} {container.name}")
        
        return "\n".join(result)
    
    @staticmethod
    def _docker_images(options):
        """List images"""
        # Parse options
        quiet = False
        
        for option in options:
            if option == "-q" or option == "--quiet":
                quiet = True
        
        # Get images
        images = ImageManager.list_images()
        
        if quiet:
            return "\n".join([image.id for image in images])
        
        # Format output
        result = ["REPOSITORY          TAG          IMAGE ID       CREATED         SIZE"]
        
        for image in images:
            # Format created time
            created_time = datetime.datetime.fromtimestamp(image.created_at)
            created_str = created_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Format size
            size_str = ContainerUtilities._format_size(image.size)
            
            result.append(f"{image.name:<20} {image.tag:<12} {image.id[:12]}   {created_str}   {size_str}")
        
        return "\n".join(result)
    
    @staticmethod
    def _format_size(size_bytes):
        """Format size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
    
    @staticmethod
    def _docker_pull(options):
        """Pull an image from registry"""
        if not options:
            return "docker: 'pull' requires at least 1 argument.\nSee 'docker pull --help'"
        
        # Parse image name and tag
        image_spec = options[0]
        if ":" in image_spec:
            name, tag = image_spec.split(":", 1)
        else:
            name, tag = image_spec, "latest"
        
        # Pull image
        success, message, image = ImageManager.pull_image(name, tag)
        
        if not success:
            return f"docker: failed to pull image: {message}"
        
        return f"Downloaded {image.name}:{image.tag} ({ContainerUtilities._format_size(image.size)})"
    
    @staticmethod
    def _docker_stop(options):
        """Stop one or more containers"""
        if not options:
            return "docker: 'stop' requires at least 1 argument.\nSee 'docker stop --help'"
        
        results = []
        
        # Parse timeout if specified
        timeout = 10
        if options[0] == "-t" or options[0] == "--time":
            if len(options) < 2:
                return "docker: option requires an argument -- '-t'"
            try:
                timeout = int(options[1])
                options = options[2:]
            except ValueError:
                return f"docker: invalid timeout value: {options[1]}"
        
        # Stop containers
        for container_id in options:
            # Get container
            container = ContainerManager.get_container(container_id)
            if not container:
                container = ContainerManager.get_container_by_name(container_id)
            
            if not container:
                results.append(f"Error: container '{container_id}' not found")
                continue
            
            # Stop container
            success, message = container.stop(timeout=timeout)
            
            if success:
                results.append(container_id)
            else:
                results.append(f"Error: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_start(options):
        """Start one or more containers"""
        if not options:
            return "docker: 'start' requires at least 1 argument.\nSee 'docker start --help'"
        
        results = []
        
        # Start containers
        for container_id in options:
            # Get container
            container = ContainerManager.get_container(container_id)
            if not container:
                container = ContainerManager.get_container_by_name(container_id)
            
            if not container:
                results.append(f"Error: container '{container_id}' not found")
                continue
            
            # Start container
            success, message = container.start()
            
            if success:
                results.append(container_id)
            else:
                results.append(f"Error: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_restart(options):
        """Restart one or more containers"""
        if not options:
            return "docker: 'restart' requires at least 1 argument.\nSee 'docker restart --help'"
        
        results = []
        
        # Parse timeout if specified
        timeout = 10
        if options[0] == "-t" or options[0] == "--time":
            if len(options) < 2:
                return "docker: option requires an argument -- '-t'"
            try:
                timeout = int(options[1])
                options = options[2:]
            except ValueError:
                return f"docker: invalid timeout value: {options[1]}"
        
        # Restart containers
        for container_id in options:
            # Get container
            container = ContainerManager.get_container(container_id)
            if not container:
                container = ContainerManager.get_container_by_name(container_id)
            
            if not container:
                results.append(f"Error: container '{container_id}' not found")
                continue
            
            # Restart container
            success, message = container.restart()
            
            if success:
                results.append(container_id)
            else:
                results.append(f"Error: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_rm(options):
        """Remove one or more containers"""
        if not options:
            return "docker: 'rm' requires at least 1 argument.\nSee 'docker rm --help'"
        
        results = []
        
        # Parse options
        force = False
        if options[0] == "-f" or options[0] == "--force":
            force = True
            options = options[1:]
        
        # Remove containers
        for container_id in options:
            # Get container
            container = ContainerManager.get_container(container_id)
            if not container:
                container = ContainerManager.get_container_by_name(container_id)
            
            if not container:
                results.append(f"Error: container '{container_id}' not found")
                continue
            
            # Remove container
            success, message = container.remove(force=force)
            
            if success:
                results.append(container_id)
            else:
                results.append(f"Error: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_rmi(options):
        """Remove one or more images"""
        if not options:
            return "docker: 'rmi' requires at least 1 argument.\nSee 'docker rmi --help'"
        
        results = []
        
        # Parse options
        force = False
        if options[0] == "-f" or options[0] == "--force":
            force = True
            options = options[1:]
        
        # Remove images
        for image_spec in options:
            # Parse image name and tag
            if ":" in image_spec:
                name, tag = image_spec.split(":", 1)
            else:
                name, tag = image_spec, "latest"
            
            # Remove image
            success, message, _ = ImageManager.remove_image(name, tag, force=force)
            
            if success:
                results.append(f"Untagged: {name}:{tag}")
                results.append(f"Deleted: {name}:{tag}")
            else:
                results.append(f"Error: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_logs(options):
        """Fetch the logs of a container"""
        # Parse options
        follow = False
        tail = None
        
        i = 0
        while i < len(options):
            if options[i] == "-f" or options[i] == "--follow":
                follow = True
                i += 1
            elif options[i] == "--tail":
                if i + 1 < len(options):
                    try:
                        tail = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"docker: invalid tail value: {options[i+1]}"
                else:
                    return "docker: option requires an argument -- '--tail'"
            else:
                break
        
        if i >= len(options):
            return "docker: 'logs' requires at least 1 argument.\nSee 'docker logs --help'"
        
        container_id = options[i]
        
        # Get container
        container = ContainerManager.get_container(container_id)
        if not container:
            container = ContainerManager.get_container_by_name(container_id)
        
        if not container:
            return f"docker: container '{container_id}' not found"
        
        # Get logs
        logs = container.get_logs(tail=tail)
        
        if follow:
            # In a real implementation, we would follow logs in real-time
            logs.append("(following logs...)")
        
        return "\n".join(logs)
    
    @staticmethod
    def _docker_inspect(options):
        """Return detailed information on objects"""
        if not options:
            return "docker: 'inspect' requires at least 1 argument.\nSee 'docker inspect --help'"
        
        results = []
        
        for obj_id in options:
            # Try to find as container
            container = ContainerManager.get_container(obj_id)
            if not container:
                container = ContainerManager.get_container_by_name(obj_id)
            
            if container:
                results.append(json.dumps(container.to_dict(), indent=2))
                continue
            
            # Try to find as image
            if ":" in obj_id:
                name, tag = obj_id.split(":", 1)
            else:
                name, tag = obj_id, "latest"
            
            image = ImageManager.get_image(name, tag)
            if image:
                results.append(json.dumps(image.to_dict(), indent=2))
                continue
            
            results.append(f"Error: No such object: {obj_id}")
        
        return "\n".join(results)
    
    @staticmethod
    def _docker_version(options):
        """Show the Docker version information"""
        version_info = {
            "Client": {
                "Version": "1.0.0",
                "ApiVersion": "1.41",
                "GitCommit": "kos-1234",
                "GoVersion": "python3",
                "Os": "kos",
                "Arch": "amd64",
                "BuildTime": "2023-01-01T00:00:00.000000000+00:00"
            },
            "Server": {
                "Engine": {
                    "Version": "1.0.0",
                    "ApiVersion": "1.41",
                    "GitCommit": "kos-1234",
                    "GoVersion": "python3",
                    "Os": "kos",
                    "Arch": "amd64",
                    "BuildTime": "2023-01-01T00:00:00.000000000+00:00"
                }
            }
        }
        
        return json.dumps(version_info, indent=2)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("docker", ContainerUtilities.do_docker)
