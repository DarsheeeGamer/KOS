"""
kubectl.py - Command-line interface for managing KOS orchestration resources

This module provides the kubectl command-line interface, which is used to
manage resources in the KOS orchestration system, similar to Kubernetes kubectl.
"""

import os
import sys
import yaml
import json
import argparse
import logging
from typing import Dict, List, Any, Optional, Union

from .kubectl_core import (
    KubectlCore, KubectlException, OutputFormat,
    get_resource_by_name, list_resources, delete_resource, apply_resource
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args=None):
    """
    Main entry point for kubectl command.
    
    Args:
        args: Command-line arguments (sys.argv if None)
    """
    parser = create_parser()
    args = parser.parse_args(args)
    
    try:
        # Initialize kubectl core
        kubectl = KubectlCore(namespace=args.namespace)
        
        # Execute command
        if args.command == "get":
            cmd_get(kubectl, args)
        elif args.command == "describe":
            cmd_describe(kubectl, args)
        elif args.command == "create":
            cmd_create(kubectl, args)
        elif args.command == "apply":
            cmd_apply(kubectl, args)
        elif args.command == "delete":
            cmd_delete(kubectl, args)
        elif args.command == "scale":
            cmd_scale(kubectl, args)
        elif args.command == "config":
            cmd_config(kubectl, args)
        else:
            parser.print_help()
            
    except KubectlException as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


def create_parser():
    """
    Create command-line argument parser.
    
    Returns:
        ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="kubectl - Command-line interface for KOS orchestration",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Global options
    parser.add_argument(
        "-n", "--namespace",
        default="default",
        help="Namespace to use"
    )
    
    # Output format
    parser.add_argument(
        "-o", "--output",
        choices=[
            OutputFormat.YAML,
            OutputFormat.JSON,
            OutputFormat.TABLE,
            OutputFormat.WIDE,
            OutputFormat.NAME
        ],
        default=OutputFormat.TABLE,
        help="Output format"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # get command
    get_parser = subparsers.add_parser("get", help="Display one or many resources")
    get_parser.add_argument(
        "resource_type",
        help="Resource type (pod, service, deployment, etc.)"
    )
    get_parser.add_argument(
        "name",
        nargs="?",
        help="Resource name"
    )
    get_parser.add_argument(
        "-l", "--selector",
        help="Selector (label query) to filter on"
    )
    get_parser.add_argument(
        "-A", "--all-namespaces",
        action="store_true",
        help="List resources across all namespaces"
    )
    
    # describe command
    describe_parser = subparsers.add_parser("describe", help="Show details of a resource")
    describe_parser.add_argument(
        "resource_type",
        help="Resource type (pod, service, deployment, etc.)"
    )
    describe_parser.add_argument(
        "name",
        help="Resource name"
    )
    
    # create command
    create_parser = subparsers.add_parser("create", help="Create a resource")
    create_parser.add_argument(
        "-f", "--filename",
        required=True,
        help="Filename containing resource definition"
    )
    
    # apply command
    apply_parser = subparsers.add_parser("apply", help="Apply a configuration to a resource")
    apply_parser.add_argument(
        "-f", "--filename",
        required=True,
        help="Filename containing resource definition"
    )
    
    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete resources")
    delete_parser.add_argument(
        "resource_type",
        help="Resource type (pod, service, deployment, etc.)"
    )
    delete_parser.add_argument(
        "name",
        nargs="?",
        help="Resource name"
    )
    delete_parser.add_argument(
        "-l", "--selector",
        help="Selector (label query) to filter on"
    )
    delete_parser.add_argument(
        "--all",
        action="store_true",
        help="Delete all resources of the specified type"
    )
    
    # scale command
    scale_parser = subparsers.add_parser("scale", help="Set a new size for a resource")
    scale_parser.add_argument(
        "resource_type",
        choices=["deployment", "replicaset", "statefulset"],
        help="Resource type to scale"
    )
    scale_parser.add_argument(
        "name",
        help="Resource name"
    )
    scale_parser.add_argument(
        "--replicas",
        type=int,
        required=True,
        help="Number of replicas"
    )
    
    # config command
    config_parser = subparsers.add_parser("config", help="Modify kubeconfig files")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config command to execute")
    
    # config set-context command
    set_context_parser = config_subparsers.add_parser("set-context", help="Set a context entry in kubeconfig")
    set_context_parser.add_argument(
        "--current",
        action="store_true",
        help="Modify the current context"
    )
    set_context_parser.add_argument(
        "--namespace",
        help="Namespace to use"
    )
    
    return parser


def cmd_get(kubectl, args):
    """
    Execute get command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Handle namespace
    namespace = None if args.all_namespaces else args.namespace
    
    # Parse selector
    selector = {}
    if args.selector:
        for item in args.selector.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                selector[key] = value
    
    # Get resources
    if args.name:
        # Get a specific resource
        resource = get_resource_by_name(args.resource_type, args.name, namespace)
        if not resource:
            logger.error(f"{args.resource_type.capitalize()} '{args.name}' not found")
            sys.exit(1)
        
        resources = [resource]
    else:
        # List resources
        resources = list_resources(args.resource_type, namespace, selector)
    
    # Format output
    output = kubectl.format_output(resources, args.output)
    
    # Print output
    print(output)


def cmd_describe(kubectl, args):
    """
    Execute describe command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Get resource
    resource = get_resource_by_name(args.resource_type, args.name, args.namespace)
    if not resource:
        logger.error(f"{args.resource_type.capitalize()} '{args.name}' not found")
        sys.exit(1)
    
    # Format as YAML
    output = yaml.dump(resource, default_flow_style=False)
    
    # Print output
    print(output)


def cmd_create(kubectl, args):
    """
    Execute create command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Load resource from file
    if not os.path.exists(args.filename):
        logger.error(f"File '{args.filename}' not found")
        sys.exit(1)
    
    try:
        with open(args.filename, 'r') as f:
            if args.filename.endswith('.json'):
                resource = json.load(f)
            else:  # Assume YAML
                resource = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load resource from file: {e}")
        sys.exit(1)
    
    # Apply resource
    if apply_resource(resource):
        kind = resource.get("kind", "Resource")
        name = resource.get("metadata", {}).get("name", "")
        print(f"{kind} '{name}' created")
    else:
        logger.error("Failed to create resource")
        sys.exit(1)


def cmd_apply(kubectl, args):
    """
    Execute apply command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Load resource from file
    if not os.path.exists(args.filename):
        logger.error(f"File '{args.filename}' not found")
        sys.exit(1)
    
    try:
        with open(args.filename, 'r') as f:
            if args.filename.endswith('.json'):
                resource = json.load(f)
            else:  # Assume YAML
                resource = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load resource from file: {e}")
        sys.exit(1)
    
    # Apply resource
    if apply_resource(resource):
        kind = resource.get("kind", "Resource")
        name = resource.get("metadata", {}).get("name", "")
        print(f"{kind} '{name}' configured")
    else:
        logger.error("Failed to apply resource")
        sys.exit(1)


def cmd_delete(kubectl, args):
    """
    Execute delete command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Parse selector
    selector = {}
    if args.selector:
        for item in args.selector.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                selector[key] = value
    
    # Delete resources
    if args.name:
        # Delete a specific resource
        if delete_resource(args.resource_type, args.name, args.namespace):
            print(f"{args.resource_type.capitalize()} '{args.name}' deleted")
        else:
            logger.error(f"Failed to delete {args.resource_type} '{args.name}'")
            sys.exit(1)
    elif args.all or selector:
        # Delete multiple resources
        resources = list_resources(args.resource_type, args.namespace, selector)
        
        if not resources:
            logger.error(f"No {args.resource_type}s found matching criteria")
            sys.exit(1)
        
        for resource in resources:
            name = resource.get("metadata", {}).get("name", "")
            namespace = resource.get("metadata", {}).get("namespace", args.namespace)
            
            if delete_resource(args.resource_type, name, namespace):
                print(f"{args.resource_type.capitalize()} '{name}' deleted")
            else:
                logger.error(f"Failed to delete {args.resource_type} '{name}'")
    else:
        logger.error("You must specify a resource name, --all flag, or --selector")
        sys.exit(1)


def cmd_scale(kubectl, args):
    """
    Execute scale command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    # Load resource
    if args.resource_type == "deployment":
        from kos.core.orchestration import Deployment
        resource = Deployment.load(args.name, args.namespace)
    elif args.resource_type == "replicaset":
        from kos.core.orchestration import ReplicaSet
        resource = ReplicaSet.load(args.name, args.namespace)
    elif args.resource_type == "statefulset":
        from kos.core.orchestration import StatefulSet
        resource = StatefulSet.load(args.name, args.namespace)
    else:
        logger.error(f"Resource type '{args.resource_type}' cannot be scaled")
        sys.exit(1)
    
    if not resource:
        logger.error(f"{args.resource_type.capitalize()} '{args.name}' not found")
        sys.exit(1)
    
    # Scale resource
    if resource.scale(args.replicas):
        print(f"{args.resource_type.capitalize()} '{args.name}' scaled")
    else:
        logger.error(f"Failed to scale {args.resource_type} '{args.name}'")
        sys.exit(1)


def cmd_config(kubectl, args):
    """
    Execute config command.
    
    Args:
        kubectl: KubectlCore instance
        args: Command-line arguments
    """
    if args.config_command == "set-context":
        if args.namespace:
            kubectl.set_namespace(args.namespace)
            print(f"Namespace set to '{args.namespace}'")
    else:
        logger.error(f"Unknown config command: {args.config_command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
