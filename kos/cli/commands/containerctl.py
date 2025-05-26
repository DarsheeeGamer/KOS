#!/usr/bin/env python3
"""
KOS containerctl - Container Management Command

This command provides comprehensive container management capabilities:
- Container lifecycle management (create, start, stop, remove)
- Image management (pull, build, list, remove)
- Container monitoring and inspection
- Network and volume management
"""

import argparse
import os
import sys
import time
import json
from typing import List, Dict, Any, Optional

from ...core import container
from ...utils import formatting, logging

# Initialize the container subsystem
container.initialize()

def format_bytes(bytes_value):
    """Format bytes into human-readable form"""
    if bytes_value is None:
        return "n/a"
    
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"

def format_duration(seconds):
    """Format duration in seconds to human-readable form"""
    if seconds is None:
        return "n/a"
    
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{int(days)}d {int(hours)}h {int(minutes)}m"
    elif hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

def create_container(args):
    """Create a new container"""
    # Parse ports
    ports = []
    if args.publish:
        for port_mapping in args.publish:
            if ':' in port_mapping:
                host_port, container_port = port_mapping.split(':', 1)
                protocol = 'tcp'
                
                if '/' in container_port:
                    container_port, protocol = container_port.split('/', 1)
                
                try:
                    ports.append({
                        'host_port': int(host_port),
                        'container_port': int(container_port),
                        'protocol': protocol
                    })
                except ValueError:
                    print(f"Invalid port mapping: {port_mapping}", file=sys.stderr)
                    return 1
            else:
                try:
                    port = int(port_mapping)
                    ports.append({
                        'host_port': port,
                        'container_port': port,
                        'protocol': 'tcp'
                    })
                except ValueError:
                    print(f"Invalid port: {port_mapping}", file=sys.stderr)
                    return 1
    
    # Parse environment variables
    env = {}
    if args.env:
        for env_var in args.env:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                env[key] = value
            else:
                # If no value provided, get from environment
                if env_var in os.environ:
                    env[env_var] = os.environ[env_var]
    
    # Parse command
    command = []
    if args.command:
        command = args.command
    
    # Parse resource limits
    resource_limits = {}
    if args.memory:
        # Convert memory limit to bytes
        if args.memory.endswith('m'):
            memory = int(args.memory[:-1]) * 1024 * 1024
        elif args.memory.endswith('g'):
            memory = int(args.memory[:-1]) * 1024 * 1024 * 1024
        elif args.memory.endswith('k'):
            memory = int(args.memory[:-1]) * 1024
        else:
            memory = int(args.memory)
        
        resource_limits['memory'] = memory
    
    if args.cpus:
        resource_limits['cpu'] = float(args.cpus)
    
    # Create container
    if container.create_container(
        args.name,
        args.image,
        command=command,
        env=env,
        volumes=args.volume,
        ports=ports,
        network=args.network,
        restart_policy=args.restart,
        resource_limits=resource_limits
    ):
        print(f"Created container: {args.name}")
        
        # Start the container if requested
        if args.run:
            if container.start_container(args.name):
                print(f"Started container: {args.name}")
            else:
                print(f"Failed to start container: {args.name}", file=sys.stderr)
                return 1
        
        return 0
    else:
        print(f"Failed to create container: {args.name}", file=sys.stderr)
        return 1

def list_containers(args):
    """List containers"""
    containers = container.list_containers()
    
    if not containers:
        print("No containers found")
        return 0
    
    # Filter containers
    if args.filter:
        filtered_containers = []
        for c in containers:
            for filter_str in args.filter:
                if '=' in filter_str:
                    key, value = filter_str.split('=', 1)
                    
                    if key == 'name' and value in c.name:
                        filtered_containers.append(c)
                    elif key == 'status' and value == c.state:
                        filtered_containers.append(c)
                    elif key == 'network' and value == c.network:
                        filtered_containers.append(c)
                    elif key == 'image' and value == c.image:
                        filtered_containers.append(c)
        
        containers = filtered_containers
    
    # Show only running containers if requested
    if args.running:
        containers = [c for c in containers if c.state == 'running']
    
    # Sort containers
    containers.sort(key=lambda c: c.name)
    
    # Format as a table
    headers = ["CONTAINER ID", "NAME", "IMAGE", "COMMAND", "STATUS", "PORTS"]
    rows = []
    
    for c in containers:
        # Format command
        command = " ".join(c.command) if c.command else ""
        if len(command) > 20:
            command = command[:17] + "..."
        
        # Format ports
        ports_str = ""
        for port in c.ports:
            ports_str += f"{port['host_port']}:{port['container_port']}/{port['protocol']} "
        
        # Format status
        if c.state == 'running':
            status = f"Up {format_duration(time.time() - c.start_time)}"
        elif c.state == 'exited':
            status = f"Exited ({c.exit_code}) {format_duration(time.time() - c.exit_time)} ago"
        else:
            status = c.state
        
        rows.append([
            c.id[:12],
            c.name,
            c.image,
            command,
            status,
            ports_str.strip()
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def start_container(args):
    """Start a container"""
    if container.start_container(args.name):
        print(f"Started container: {args.name}")
        return 0
    else:
        print(f"Failed to start container: {args.name}", file=sys.stderr)
        return 1

def stop_container(args):
    """Stop a container"""
    if container.stop_container(args.name, args.time):
        print(f"Stopped container: {args.name}")
        return 0
    else:
        print(f"Failed to stop container: {args.name}", file=sys.stderr)
        return 1

def restart_container(args):
    """Restart a container"""
    if container.restart_container(args.name, args.time):
        print(f"Restarted container: {args.name}")
        return 0
    else:
        print(f"Failed to restart container: {args.name}", file=sys.stderr)
        return 1

def remove_container(args):
    """Remove a container"""
    if container.remove_container(args.name, args.force):
        print(f"Removed container: {args.name}")
        return 0
    else:
        print(f"Failed to remove container: {args.name}", file=sys.stderr)
        return 1

def inspect_container(args):
    """Inspect a container"""
    c = container.get_container_status(args.name)
    
    if not c:
        print(f"Container not found: {args.name}", file=sys.stderr)
        return 1
    
    if args.format:
        # Custom format not implemented
        print(json.dumps(c, indent=2))
    else:
        print(f"Container: {c['name']} ({c['image']})")
        print(f"ID: {c['id']}")
        print(f"State: {c['state']}")
        print(f"PID: {c['pid'] or 'n/a'}")
        print(f"IP Address: {c['ip_address'] or 'n/a'}")
        
        if c['started']:
            print(f"Started: {time.ctime(c['started'])}")
        
        if c['exited']:
            print(f"Exited: {time.ctime(c['exited'])}")
            print(f"Exit Code: {c['exit_code']}")
        
        print(f"Restart Count: {c['restart_count']}")
        
        if c['ports']:
            print("\nPorts:")
            for port in c['ports']:
                print(f"  {port['host_port']}:{port['container_port']}/{port['protocol']}")
        
        metrics = container.get_container_metrics(args.name)
        if metrics:
            print("\nMetrics:")
            print(f"  CPU: {metrics.get('cpu_usage', 0):.1f}%")
            print(f"  Memory: {format_bytes(metrics.get('memory_usage', 0))}")
            print(f"  Memory Limit: {format_bytes(metrics.get('memory_limit', 0)) if metrics.get('memory_limit') else 'unlimited'}")
            print(f"  Network: {format_bytes(metrics.get('network_rx', 0))} received, {format_bytes(metrics.get('network_tx', 0))} sent")
            print(f"  I/O: {format_bytes(metrics.get('io_read', 0))} read, {format_bytes(metrics.get('io_write', 0))} written")
    
    return 0

def logs_container(args):
    """Show container logs"""
    logs = container.get_container_logs(args.name, args.tail)
    
    if logs is None:
        print(f"Container not found: {args.name}", file=sys.stderr)
        return 1
    
    # Output format depends on options
    if args.follow:
        # Not fully implemented, just print current logs
        print("=== STDOUT ===")
        print(logs['stdout'])
        
        print("\n=== STDERR ===")
        print(logs['stderr'])
        
        print("\nLog following not fully implemented.")
    else:
        if not args.stderr:
            print(logs['stdout'])
        elif not args.stdout:
            print(logs['stderr'])
        else:
            print("=== STDOUT ===")
            print(logs['stdout'])
            
            print("\n=== STDERR ===")
            print(logs['stderr'])
    
    return 0

def exec_container(args):
    """Execute a command in a container"""
    result = container.exec_in_container(args.name, args.command, args.interactive)
    
    if not result:
        print(f"Failed to execute command in container: {args.name}", file=sys.stderr)
        return 1
    
    if not result['success']:
        print(f"Command failed: {result['error']}", file=sys.stderr)
        print(result['stderr'], file=sys.stderr)
        return result['exit_code']
    
    print(result['stdout'])
    
    if result['stderr']:
        print(result['stderr'], file=sys.stderr)
    
    return 0

def pull_image(args):
    """Pull an image"""
    tag = 'latest'
    image_name = args.image
    
    if ':' in image_name:
        image_name, tag = image_name.split(':', 1)
    
    if container.pull_image(image_name, tag):
        print(f"Pulled image: {image_name}:{tag}")
        return 0
    else:
        print(f"Failed to pull image: {image_name}:{tag}", file=sys.stderr)
        return 1

def build_image(args):
    """Build an image"""
    tag = args.tag or 'latest'
    
    if container.build_image(args.name, args.path, tag):
        print(f"Built image: {args.name}:{tag}")
        return 0
    else:
        print(f"Failed to build image: {args.name}:{tag}", file=sys.stderr)
        return 1

def list_images(args):
    """List images"""
    images = container.list_images()
    
    if not images:
        print("No images found")
        return 0
    
    # Format as a table
    headers = ["IMAGE ID", "REPOSITORY", "TAG", "SIZE", "CREATED"]
    rows = []
    
    for image in images:
        rows.append([
            image['id'][:12],
            image['name'],
            image['tag'],
            format_bytes(image['size']),
            format_duration(time.time() - image['created']) + " ago"
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def remove_image(args):
    """Remove an image"""
    if container.remove_image(args.image, args.force):
        print(f"Removed image: {args.image}")
        return 0
    else:
        print(f"Failed to remove image: {args.image}", file=sys.stderr)
        return 1

def create_network(args):
    """Create a network"""
    if container.create_network(args.name, args.subnet, args.gateway):
        print(f"Created network: {args.name}")
        return 0
    else:
        print(f"Failed to create network: {args.name}", file=sys.stderr)
        return 1

def list_networks(args):
    """List networks"""
    networks = container.list_networks()
    
    if not networks:
        print("No networks found")
        return 0
    
    # Format as a table
    headers = ["NETWORK ID", "NAME", "TYPE", "SUBNET", "GATEWAY", "CONTAINERS"]
    rows = []
    
    for network in networks:
        rows.append([
            network['id'][:12],
            network['name'],
            network['type'],
            network.get('subnet', 'n/a'),
            network.get('gateway', 'n/a'),
            str(network['container_count'])
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def remove_network(args):
    """Remove a network"""
    if container.remove_network(args.name):
        print(f"Removed network: {args.name}")
        return 0
    else:
        print(f"Failed to remove network: {args.name}", file=sys.stderr)
        return 1

def create_volume(args):
    """Create a volume"""
    if container.create_volume(args.name, args.path):
        print(f"Created volume: {args.name}")
        return 0
    else:
        print(f"Failed to create volume: {args.name}", file=sys.stderr)
        return 1

def list_volumes(args):
    """List volumes"""
    volumes = container.list_volumes()
    
    if not volumes:
        print("No volumes found")
        return 0
    
    # Format as a table
    headers = ["VOLUME NAME", "MOUNTPOINT", "CREATED", "STATUS"]
    rows = []
    
    for volume in volumes:
        rows.append([
            volume['name'],
            volume['mountpoint'],
            format_duration(time.time() - volume['created']) + " ago",
            "In use" if volume['in_use'] else "Available"
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def remove_volume(args):
    """Remove a volume"""
    if container.remove_volume(args.name, args.force):
        print(f"Removed volume: {args.name}")
        return 0
    else:
        print(f"Failed to remove volume: {args.name}", file=sys.stderr)
        return 1

def main(args=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS containerctl - Container Management Command")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Container commands
    container_parser = subparsers.add_parser("container", help="Container management")
    container_subparsers = container_parser.add_subparsers(dest="container_command", help="Container command")
    
    # Create container
    create_parser = container_subparsers.add_parser("create", help="Create a new container")
    create_parser.add_argument("--name", "-n", required=True, help="Container name")
    create_parser.add_argument("--image", "-i", required=True, help="Image name")
    create_parser.add_argument("--publish", "-p", action="append", help="Publish a container's port(s) (host:container)")
    create_parser.add_argument("--volume", "-v", action="append", default=[], help="Bind mount a volume")
    create_parser.add_argument("--env", "-e", action="append", help="Set environment variables")
    create_parser.add_argument("--network", help="Connect to a network", default="bridge")
    create_parser.add_argument("--restart", choices=["no", "on-failure", "always", "unless-stopped"],
                               default="no", help="Restart policy")
    create_parser.add_argument("--memory", "-m", help="Memory limit (e.g. 512m, 1g)")
    create_parser.add_argument("--cpus", help="Number of CPUs")
    create_parser.add_argument("--run", action="store_true", help="Start the container after creation")
    create_parser.add_argument("command", nargs="*", help="Command to run")
    create_parser.set_defaults(func=create_container)
    
    # List containers
    list_parser = container_subparsers.add_parser("list", help="List containers")
    list_parser.add_argument("--filter", "-f", action="append", help="Filter output based on conditions")
    list_parser.add_argument("--running", "-r", action="store_true", help="Show only running containers")
    list_parser.set_defaults(func=list_containers)
    
    # Start container
    start_parser = container_subparsers.add_parser("start", help="Start a container")
    start_parser.add_argument("name", help="Container name")
    start_parser.set_defaults(func=start_container)
    
    # Stop container
    stop_parser = container_subparsers.add_parser("stop", help="Stop a container")
    stop_parser.add_argument("name", help="Container name")
    stop_parser.add_argument("--time", "-t", type=int, default=10, help="Seconds to wait before killing the container")
    stop_parser.set_defaults(func=stop_container)
    
    # Restart container
    restart_parser = container_subparsers.add_parser("restart", help="Restart a container")
    restart_parser.add_argument("name", help="Container name")
    restart_parser.add_argument("--time", "-t", type=int, default=10, help="Seconds to wait before killing the container")
    restart_parser.set_defaults(func=restart_container)
    
    # Remove container
    remove_parser = container_subparsers.add_parser("remove", help="Remove a container")
    remove_parser.add_argument("name", help="Container name")
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force the removal of a running container")
    remove_parser.set_defaults(func=remove_container)
    
    # Inspect container
    inspect_parser = container_subparsers.add_parser("inspect", help="Display detailed information on a container")
    inspect_parser.add_argument("name", help="Container name")
    inspect_parser.add_argument("--format", help="Format the output using the given template")
    inspect_parser.set_defaults(func=inspect_container)
    
    # Container logs
    logs_parser = container_subparsers.add_parser("logs", help="Fetch the logs of a container")
    logs_parser.add_argument("name", help="Container name")
    logs_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output")
    logs_parser.add_argument("--tail", "-n", type=int, help="Number of lines to show from the end of the logs")
    logs_parser.add_argument("--stdout", action="store_true", default=True, help="Show stdout logs")
    logs_parser.add_argument("--stderr", action="store_true", default=True, help="Show stderr logs")
    logs_parser.set_defaults(func=logs_container)
    
    # Execute in container
    exec_parser = container_subparsers.add_parser("exec", help="Execute a command in a running container")
    exec_parser.add_argument("name", help="Container name")
    exec_parser.add_argument("--interactive", "-i", action="store_true", help="Keep STDIN open even if not attached")
    exec_parser.add_argument("command", nargs="+", help="Command to execute")
    exec_parser.set_defaults(func=exec_container)
    
    # Image commands
    image_parser = subparsers.add_parser("image", help="Image management")
    image_subparsers = image_parser.add_subparsers(dest="image_command", help="Image command")
    
    # Pull image
    pull_parser = image_subparsers.add_parser("pull", help="Pull an image from a registry")
    pull_parser.add_argument("image", help="Image name (e.g. ubuntu:latest)")
    pull_parser.set_defaults(func=pull_image)
    
    # Build image
    build_parser = image_subparsers.add_parser("build", help="Build an image from a Dockerfile")
    build_parser.add_argument("--name", "-n", required=True, help="Image name")
    build_parser.add_argument("--tag", "-t", help="Image tag")
    build_parser.add_argument("path", help="Path to the build context")
    build_parser.set_defaults(func=build_image)
    
    # List images
    list_images_parser = image_subparsers.add_parser("list", help="List images")
    list_images_parser.set_defaults(func=list_images)
    
    # Remove image
    remove_image_parser = image_subparsers.add_parser("remove", help="Remove an image")
    remove_image_parser.add_argument("image", help="Image name or ID")
    remove_image_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    remove_image_parser.set_defaults(func=remove_image)
    
    # Network commands
    network_parser = subparsers.add_parser("network", help="Network management")
    network_subparsers = network_parser.add_subparsers(dest="network_command", help="Network command")
    
    # Create network
    create_network_parser = network_subparsers.add_parser("create", help="Create a network")
    create_network_parser.add_argument("name", help="Network name")
    create_network_parser.add_argument("--subnet", help="Subnet in CIDR format")
    create_network_parser.add_argument("--gateway", help="Gateway IP address")
    create_network_parser.set_defaults(func=create_network)
    
    # List networks
    list_networks_parser = network_subparsers.add_parser("list", help="List networks")
    list_networks_parser.set_defaults(func=list_networks)
    
    # Remove network
    remove_network_parser = network_subparsers.add_parser("remove", help="Remove a network")
    remove_network_parser.add_argument("name", help="Network name")
    remove_network_parser.set_defaults(func=remove_network)
    
    # Volume commands
    volume_parser = subparsers.add_parser("volume", help="Volume management")
    volume_subparsers = volume_parser.add_subparsers(dest="volume_command", help="Volume command")
    
    # Create volume
    create_volume_parser = volume_subparsers.add_parser("create", help="Create a volume")
    create_volume_parser.add_argument("name", help="Volume name")
    create_volume_parser.add_argument("--path", help="Host path for bind mount")
    create_volume_parser.set_defaults(func=create_volume)
    
    # List volumes
    list_volumes_parser = volume_subparsers.add_parser("list", help="List volumes")
    list_volumes_parser.set_defaults(func=list_volumes)
    
    # Remove volume
    remove_volume_parser = volume_subparsers.add_parser("remove", help="Remove a volume")
    remove_volume_parser.add_argument("name", help="Volume name")
    remove_volume_parser.add_argument("--force", "-f", action="store_true", help="Force removal")
    remove_volume_parser.set_defaults(func=remove_volume)
    
    # Convenience commands (shortcuts)
    run_parser = subparsers.add_parser("run", help="Create and start a container")
    run_parser.add_argument("--name", "-n", required=True, help="Container name")
    run_parser.add_argument("--publish", "-p", action="append", help="Publish a container's port(s) (host:container)")
    run_parser.add_argument("--volume", "-v", action="append", default=[], help="Bind mount a volume")
    run_parser.add_argument("--env", "-e", action="append", help="Set environment variables")
    run_parser.add_argument("--network", help="Connect to a network", default="bridge")
    run_parser.add_argument("--restart", choices=["no", "on-failure", "always", "unless-stopped"],
                           default="no", help="Restart policy")
    run_parser.add_argument("--memory", "-m", help="Memory limit (e.g. 512m, 1g)")
    run_parser.add_argument("--cpus", help="Number of CPUs")
    run_parser.add_argument("image", help="Image name")
    run_parser.add_argument("command", nargs="*", help="Command to run")
    run_parser.set_defaults(func=lambda args: create_container(argparse.Namespace(
        name=args.name,
        image=args.image,
        publish=args.publish,
        volume=args.volume,
        env=args.env,
        network=args.network,
        restart=args.restart,
        memory=args.memory,
        cpus=args.cpus,
        command=args.command,
        run=True
    )))
    
    ps_parser = subparsers.add_parser("ps", help="List containers")
    ps_parser.add_argument("--filter", "-f", action="append", help="Filter output based on conditions")
    ps_parser.add_argument("--running", "-r", action="store_true", help="Show only running containers")
    ps_parser.set_defaults(func=list_containers)
    
    images_parser = subparsers.add_parser("images", help="List images")
    images_parser.set_defaults(func=list_images)
    
    # Parse arguments
    args = parser.parse_args(args)
    
    # Special case for container command with no subcommand
    if args.command == "container" and not args.container_command:
        return list_containers(argparse.Namespace(filter=None, running=False))
    
    # Special case for image command with no subcommand
    if args.command == "image" and not args.image_command:
        return list_images(argparse.Namespace())
    
    # Special case for network command with no subcommand
    if args.command == "network" and not args.network_command:
        return list_networks(argparse.Namespace())
    
    # Special case for volume command with no subcommand
    if args.command == "volume" and not args.volume_command:
        return list_volumes(argparse.Namespace())
    
    # Default command is to list containers
    if not args.command or not hasattr(args, 'func'):
        return list_containers(argparse.Namespace(filter=None, running=False))
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
