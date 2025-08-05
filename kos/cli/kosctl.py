#!/usr/bin/env python3
"""
KOS Control (kosctl) - Command-line tool for KOS orchestration system
"""

import os
import sys
import json
import argparse
import tabulate
import yaml
from typing import Dict, List, Any, Optional, Tuple, Union

# Add KOS module to Python path
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import KOS modules
from kos.core.orchestration import pod
from kos.core.orchestration import service
from kos.core.orchestration.controllers import deployment
from kos.core.orchestration.controllers import replicaset
from kos.core.orchestration.controllers import statefulset
from kos.core.orchestration.controllers import job
from kos.core.orchestration.controllers import cronjob
from kos.core.orchestration import configmap
from kos.core.orchestration import secret
from kos.core.orchestration import rbac
from kos.core.orchestration import node
from kos.core.orchestration import events
from kos.core.orchestration import volume


class ResourceKind:
    """Resource kinds."""
    POD = "Pod"
    SERVICE = "Service"
    DEPLOYMENT = "Deployment"
    REPLICASET = "ReplicaSet"
    STATEFULSET = "StatefulSet"
    JOB = "Job"
    CRONJOB = "CronJob"
    CONFIGMAP = "ConfigMap"
    SECRET = "Secret"
    ROLE = "Role"
    ROLEBINDING = "RoleBinding"
    CLUSTERROLE = "ClusterRole"
    CLUSTERROLEBINDING = "ClusterRoleBinding"
    NODE = "Node"
    EVENT = "Event"
    PERSISTENTVOLUME = "PersistentVolume"
    PERSISTENTVOLUMECLAIM = "PersistentVolumeClaim"


class OutputFormat:
    """Output formats."""
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    WIDE = "wide"


def get_resource_module(kind: str) -> Tuple[Any, str]:
    """
    Get the module and function for a resource kind.
    
    Args:
        kind: Resource kind
        
    Returns:
        Tuple of module and function name
    """
    kind = kind.lower()
    
    # Map resource kinds to modules and functions
    if kind in ["pod", "pods", "po"]:
        return pod, "list_pods"
    elif kind in ["service", "services", "svc"]:
        return service, "list_services"
    elif kind in ["deployment", "deployments", "deploy"]:
        return deployment, "list_deployments"
    elif kind in ["replicaset", "replicasets", "rs"]:
        return replicaset, "list_replicasets"
    elif kind in ["statefulset", "statefulsets", "sts"]:
        return statefulset, "list_statefulsets"
    elif kind in ["job", "jobs"]:
        return job, "list_jobs"
    elif kind in ["cronjob", "cronjobs", "cj"]:
        return cronjob, "list_cronjobs"
    elif kind in ["configmap", "configmaps", "cm"]:
        return configmap, "list_configmaps"
    elif kind in ["secret", "secrets"]:
        return secret, "list_secrets"
    elif kind in ["role", "roles"]:
        return rbac, "list_roles"
    elif kind in ["rolebinding", "rolebindings"]:
        return rbac, "list_role_bindings"
    elif kind in ["clusterrole", "clusterroles"]:
        return rbac, "list_cluster_roles"
    elif kind in ["clusterrolebinding", "clusterrolebindings"]:
        return rbac, "list_cluster_role_bindings"
    elif kind in ["node", "nodes", "no"]:
        return node, "list_nodes"
    elif kind in ["event", "events", "ev"]:
        return events, "list_events"
    elif kind in ["persistentvolume", "persistentvolumes", "pv"]:
        return volume, "list_persistent_volumes"
    elif kind in ["persistentvolumeclaim", "persistentvolumeclaims", "pvc"]:
        return volume, "list_persistent_volume_claims"
    else:
        raise ValueError(f"Unknown resource kind: {kind}")


def get_resource_instance(kind: str, name: str, namespace: str = "default") -> Any:
    """
    Get a resource instance.
    
    Args:
        kind: Resource kind
        name: Resource name
        namespace: Namespace
        
    Returns:
        Resource instance
    """
    kind = kind.lower()
    
    # Map resource kinds to get functions
    if kind in ["pod", "pods", "po"]:
        return pod.get_pod(name, namespace)
    elif kind in ["service", "services", "svc"]:
        return service.get_service(name, namespace)
    elif kind in ["deployment", "deployments", "deploy"]:
        return deployment.get_deployment(name, namespace)
    elif kind in ["replicaset", "replicasets", "rs"]:
        return replicaset.get_replicaset(name, namespace)
    elif kind in ["statefulset", "statefulsets", "sts"]:
        return statefulset.get_statefulset(name, namespace)
    elif kind in ["job", "jobs"]:
        return job.get_job(name, namespace)
    elif kind in ["cronjob", "cronjobs", "cj"]:
        return cronjob.get_cronjob(name, namespace)
    elif kind in ["configmap", "configmaps", "cm"]:
        return configmap.get_configmap(name, namespace)
    elif kind in ["secret", "secrets"]:
        return secret.get_secret(name, namespace)
    elif kind in ["role", "roles"]:
        return rbac.get_role(name, namespace)
    elif kind in ["rolebinding", "rolebindings"]:
        return rbac.get_role_binding(name, namespace)
    elif kind in ["clusterrole", "clusterroles"]:
        return rbac.get_cluster_role(name)
    elif kind in ["clusterrolebinding", "clusterrolebindings"]:
        return rbac.get_cluster_role_binding(name)
    elif kind in ["node", "nodes", "no"]:
        return node.get_node(name)
    elif kind in ["event", "events", "ev"]:
        return events.get_event(name, namespace)
    elif kind in ["persistentvolume", "persistentvolumes", "pv"]:
        return volume.get_persistent_volume(name)
    elif kind in ["persistentvolumeclaim", "persistentvolumeclaims", "pvc"]:
        return volume.get_persistent_volume_claim(name, namespace)
    else:
        raise ValueError(f"Unknown resource kind: {kind}")


def format_resource_list(resources: List[Any], kind: str, output_format: str) -> str:
    """
    Format a list of resources for output.
    
    Args:
        resources: List of resources
        kind: Resource kind
        output_format: Output format
        
    Returns:
        Formatted output
    """
    if output_format == OutputFormat.JSON:
        data = []
        for resource in resources:
            if hasattr(resource, '__dict__'):
                data.append(resource.__dict__)
            else:
                data.append(resource)
        return json.dumps(data, indent=2)
    
    elif output_format == OutputFormat.YAML:
        data = []
        for resource in resources:
            if hasattr(resource, '__dict__'):
                data.append(resource.__dict__)
            else:
                data.append(resource)
        return yaml.dump(data, default_flow_style=False)
    
    else:  # OutputFormat.TABLE or OutputFormat.WIDE
        headers = []
        rows = []
        
        # Format table headers and rows based on resource kind
        if kind.lower() in ["pod", "pods", "po"]:
            headers = ["NAME", "READY", "STATUS", "RESTARTS", "AGE"]
            if output_format == OutputFormat.WIDE:
                headers.extend(["IP", "NODE"])
            
            for resource in resources:
                row = [
                    resource.name,
                    f"{resource.status.get('ready_containers', 0)}/{resource.spec.get('containers', [])}",
                    resource.status.get("phase", "Unknown"),
                    resource.status.get("restart_count", 0),
                    format_age(resource.metadata.get("created", 0))
                ]
                
                if output_format == OutputFormat.WIDE:
                    row.extend([
                        resource.status.get("pod_ip", ""),
                        resource.spec.get("node_name", "")
                    ])
                
                rows.append(row)
        
        elif kind.lower() in ["service", "services", "svc"]:
            headers = ["NAME", "TYPE", "CLUSTER-IP", "EXTERNAL-IP", "PORT(S)", "AGE"]
            
            for resource in resources:
                ports = []
                for port in resource.spec.get("ports", []):
                    port_str = f"{port.get('port')}/{port.get('protocol', 'TCP')}"
                    ports.append(port_str)
                
                row = [
                    resource.name,
                    resource.spec.get("type", "ClusterIP"),
                    resource.spec.get("cluster_ip", ""),
                    resource.spec.get("external_ip", ""),
                    ", ".join(ports),
                    format_age(resource.metadata.get("created", 0))
                ]
                
                rows.append(row)
        
        elif kind.lower() in ["deployment", "deployments", "deploy"]:
            headers = ["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"]
            
            for resource in resources:
                row = [
                    resource.name,
                    f"{resource.status.get('ready_replicas', 0)}/{resource.spec.get('replicas', 0)}",
                    resource.status.get("updated_replicas", 0),
                    resource.status.get("available_replicas", 0),
                    format_age(resource.metadata.get("created", 0))
                ]
                
                rows.append(row)
        
        elif kind.lower() in ["node", "nodes", "no"]:
            headers = ["NAME", "STATUS", "ROLES", "AGE", "VERSION"]
            if output_format == OutputFormat.WIDE:
                headers.extend(["INTERNAL-IP", "OS-IMAGE", "KERNEL-VERSION"])
            
            for resource in resources:
                # Check if Ready condition is True
                ready = "NotReady"
                for condition in resource.status.conditions:
                    if condition.type == "Ready":
                        if condition.status == "True":
                            ready = "Ready"
                        break
                
                row = [
                    resource.name,
                    ready,
                    "master" if resource.metadata.get("labels", {}).get("node-role.kubernetes.io/master") else "worker",
                    format_age(resource.metadata.get("created", 0)),
                    resource.status.node_info.get("kubeletVersion", "")
                ]
                
                if output_format == OutputFormat.WIDE:
                    internal_ip = ""
                    for address in resource.status.addresses:
                        if address.get("type") == "InternalIP":
                            internal_ip = address.get("address", "")
                            break
                    
                    row.extend([
                        internal_ip,
                        resource.status.node_info.get("osImage", ""),
                        resource.status.node_info.get("kernelVersion", "")
                    ])
                
                rows.append(row)
        
        # Add more resource types as needed...
        
        else:
            # Generic table format for other resource types
            headers = ["NAME", "NAMESPACE", "AGE"]
            
            for resource in resources:
                row = [
                    resource.name,
                    resource.metadata.get("namespace", "default"),
                    format_age(resource.metadata.get("created", 0))
                ]
                
                rows.append(row)
        
        return tabulate.tabulate(rows, headers=headers, tablefmt="plain")


def format_age(timestamp: float) -> str:
    """
    Format a timestamp as an age string.
    
    Args:
        timestamp: Timestamp in seconds since epoch
        
    Returns:
        Age string
    """
    import time
    
    age_seconds = time.time() - timestamp
    
    if age_seconds < 60:
        return f"{int(age_seconds)}s"
    elif age_seconds < 3600:
        return f"{int(age_seconds / 60)}m"
    elif age_seconds < 86400:
        return f"{int(age_seconds / 3600)}h"
    else:
        return f"{int(age_seconds / 86400)}d"


def cmd_get(args):
    """
    Get resources.
    
    Args:
        args: Command-line arguments
    """
    kind = args.resource_type
    name = args.name
    namespace = args.namespace
    output = args.output
    
    try:
        # Get module and function
        module, func_name = get_resource_module(kind)
        func = getattr(module, func_name)
        
        if name:
            # Get specific resource
            resource = get_resource_instance(kind, name, namespace)
            if resource:
                resources = [resource]
            else:
                print(f"Error: {kind} '{name}' not found in namespace '{namespace}'")
                return
        else:
            # List resources
            if namespace:
                resources = func(namespace=namespace)
            else:
                resources = func()
        
        # Format output
        print(format_resource_list(resources, kind, output))
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_describe(args):
    """
    Describe a resource.
    
    Args:
        args: Command-line arguments
    """
    kind = args.resource_type
    name = args.name
    namespace = args.namespace
    
    try:
        # Get resource instance
        resource = get_resource_instance(kind, name, namespace)
        
        if not resource:
            print(f"Error: {kind} '{name}' not found in namespace '{namespace}'")
            return
        
        # Format as YAML for now
        if hasattr(resource, '__dict__'):
            data = resource.__dict__
        else:
            data = resource
        
        print(yaml.dump(data, default_flow_style=False))
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_delete(args):
    """
    Delete a resource.
    
    Args:
        args: Command-line arguments
    """
    kind = args.resource_type
    name = args.name
    namespace = args.namespace
    
    try:
        # Get resource instance
        resource = get_resource_instance(kind, name, namespace)
        
        if not resource:
            print(f"Error: {kind} '{name}' not found in namespace '{namespace}'")
            return
        
        # Delete resource
        if hasattr(resource, 'delete'):
            result = resource.delete()
            if result:
                print(f"{kind} '{name}' deleted")
            else:
                print(f"Error: Failed to delete {kind} '{name}'")
        else:
            print(f"Error: Cannot delete {kind} '{name}', no delete method")
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_create(args):
    """
    Create a resource.
    
    Args:
        args: Command-line arguments
    """
    filename = args.filename
    
    try:
        # Read file
        with open(filename, 'r') as f:
            content = f.read()
        
        # Parse YAML
        data = yaml.safe_load(content)
        
        # Extract resource information
        kind = data.get('kind', '').lower()
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        
        name = metadata.get('name')
        namespace = metadata.get('namespace', 'default')
        
        if not kind or not name:
            print("Error: Resource must have 'kind' and 'metadata.name'")
            return
        
        # Create resource based on kind
        if kind in ["pod", "pods"]:
            result = pod.create_pod(name, namespace, spec)
        elif kind in ["service", "services"]:
            result = service.create_service(name, namespace, spec)
        elif kind in ["deployment", "deployments"]:
            result = deployment.create_deployment(name, namespace, spec)
        elif kind in ["replicaset", "replicasets"]:
            result = replicaset.create_replicaset(name, namespace, spec)
        elif kind in ["statefulset", "statefulsets"]:
            result = statefulset.create_statefulset(name, namespace, spec)
        elif kind in ["job", "jobs"]:
            result = job.create_job(name, namespace, spec)
        elif kind in ["cronjob", "cronjobs"]:
            result = cronjob.create_cronjob(name, namespace, spec)
        elif kind in ["configmap", "configmaps"]:
            result = configmap.create_configmap(name, namespace, data.get('data', {}))
        elif kind in ["secret", "secrets"]:
            result = secret.create_secret(name, namespace, data.get('data', {}))
        elif kind == "role":
            result = rbac.create_role(name, namespace, spec.get('rules', []))
        elif kind == "rolebinding":
            result = rbac.create_role_binding(name, namespace, spec)
        elif kind == "clusterrole":
            result = rbac.create_cluster_role(name, spec.get('rules', []))
        elif kind == "clusterrolebinding":
            result = rbac.create_cluster_role_binding(name, spec)
        elif kind in ["persistentvolume", "persistentvolumes"]:
            result = volume.create_persistent_volume(name, spec)
        elif kind in ["persistentvolumeclaim", "persistentvolumeclaims"]:
            result = volume.create_persistent_volume_claim(name, namespace, spec)
        else:
            print(f"Error: Unknown resource kind: {kind}")
            return
        
        if result:
            print(f"{kind} '{name}' created")
        else:
            print(f"Error: Failed to create {kind} '{name}'")
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_apply(args):
    """
    Apply a resource (create or update).
    
    Args:
        args: Command-line arguments
    """
    filename = args.filename
    
    try:
        # Read file
        with open(filename, 'r') as f:
            content = f.read()
        
        # Parse YAML/JSON
        if filename.endswith('.json'):
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)
        
        # Extract resource information
        kind = data.get('kind', '').lower()
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        
        name = metadata.get('name')
        namespace = metadata.get('namespace', 'default')
        
        if not kind or not name:
            print("Error: Resource must have 'kind' and 'metadata.name'")
            return
        
        # Check if resource exists
        existing = None
        try:
            existing = get_resource_instance(kind, name, namespace)
        except:
            pass
        
        # Apply resource based on kind
        if existing:
            # Update existing resource
            if hasattr(existing, 'update'):
                result = existing.update(spec)
                action = "configured"
            else:
                print(f"Error: Cannot update {kind} '{name}', no update method")
                return
        else:
            # Create new resource
            if kind in ["pod", "pods"]:
                result = pod.create_pod(name, namespace, spec)
            elif kind in ["service", "services"]:
                result = service.create_service(name, namespace, spec)
            elif kind in ["deployment", "deployments"]:
                result = deployment.create_deployment(name, namespace, spec)
            elif kind in ["replicaset", "replicasets"]:
                result = replicaset.create_replicaset(name, namespace, spec)
            elif kind in ["statefulset", "statefulsets"]:
                result = statefulset.create_statefulset(name, namespace, spec)
            elif kind in ["job", "jobs"]:
                result = job.create_job(name, namespace, spec)
            elif kind in ["cronjob", "cronjobs"]:
                result = cronjob.create_cronjob(name, namespace, spec)
            elif kind in ["configmap", "configmaps"]:
                result = configmap.create_configmap(name, namespace, data.get('data', {}))
            elif kind in ["secret", "secrets"]:
                result = secret.create_secret(name, namespace, data.get('data', {}))
            elif kind == "role":
                result = rbac.create_role(name, namespace, spec.get('rules', []))
            elif kind == "rolebinding":
                result = rbac.create_role_binding(name, namespace, spec)
            elif kind == "clusterrole":
                result = rbac.create_cluster_role(name, spec.get('rules', []))
            elif kind == "clusterrolebinding":
                result = rbac.create_cluster_role_binding(name, spec)
            elif kind in ["persistentvolume", "persistentvolumes"]:
                result = volume.create_persistent_volume(name, spec)
            elif kind in ["persistentvolumeclaim", "persistentvolumeclaims"]:
                result = volume.create_persistent_volume_claim(name, namespace, spec)
            else:
                print(f"Error: Unknown resource kind: {kind}")
                return
            
            action = "created"
        
        if result:
            print(f"{kind} '{name}' {action}")
        else:
            print(f"Error: Failed to apply {kind} '{name}'")
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_logs(args):
    """
    Get logs from a pod.
    
    Args:
        args: Command-line arguments
    """
    name = args.name
    namespace = args.namespace
    container = args.container
    follow = args.follow
    
    try:
        # Get pod instance
        pod_instance = pod.get_pod(name, namespace)
        
        if not pod_instance:
            print(f"Error: Pod '{name}' not found in namespace '{namespace}'")
            return
        
        # Get logs
        if hasattr(pod_instance, 'get_logs'):
            logs = pod_instance.get_logs(container)
            print(logs)
        else:
            print(f"Error: Cannot get logs for Pod '{name}', no get_logs method")
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_exec(args):
    """
    Execute a command in a container.
    
    Args:
        args: Command-line arguments
    """
    name = args.name
    namespace = args.namespace
    container = args.container
    command = args.command
    
    try:
        # Get pod instance
        pod_instance = pod.get_pod(name, namespace)
        
        if not pod_instance:
            print(f"Error: Pod '{name}' not found in namespace '{namespace}'")
            return
        
        # Execute command
        if hasattr(pod_instance, 'exec'):
            output = pod_instance.exec(command, container)
            print(output)
        else:
            print(f"Error: Cannot execute command in Pod '{name}', no exec method")
    
    except Exception as e:
        print(f"Error: {e}")


def cmd_version(args):
    """
    Show version information.
    
    Args:
        args: Command-line arguments
    """
    print("KOS Control (kosctl) v1.0.0")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="KOS Control (kosctl)")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # get command
    get_parser = subparsers.add_parser("get", help="Get resources")
    get_parser.add_argument("resource_type", help="Resource type")
    get_parser.add_argument("name", nargs="?", help="Resource name")
    get_parser.add_argument("-n", "--namespace", help="Namespace")
    get_parser.add_argument("-o", "--output", choices=["table", "json", "yaml", "wide"], default="table", help="Output format")
    get_parser.set_defaults(func=cmd_get)
    
    # describe command
    describe_parser = subparsers.add_parser("describe", help="Describe a resource")
    describe_parser.add_argument("resource_type", help="Resource type")
    describe_parser.add_argument("name", help="Resource name")
    describe_parser.add_argument("-n", "--namespace", help="Namespace")
    describe_parser.set_defaults(func=cmd_describe)
    
    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a resource")
    delete_parser.add_argument("resource_type", help="Resource type")
    delete_parser.add_argument("name", help="Resource name")
    delete_parser.add_argument("-n", "--namespace", help="Namespace")
    delete_parser.set_defaults(func=cmd_delete)
    
    # create command
    create_parser = subparsers.add_parser("create", help="Create a resource")
    create_parser.add_argument("-f", "--filename", required=True, help="Filename")
    create_parser.set_defaults(func=cmd_create)
    
    # apply command
    apply_parser = subparsers.add_parser("apply", help="Apply a resource")
    apply_parser.add_argument("-f", "--filename", required=True, help="Filename")
    apply_parser.set_defaults(func=cmd_apply)
    
    # logs command
    logs_parser = subparsers.add_parser("logs", help="Get logs from a pod")
    logs_parser.add_argument("name", help="Pod name")
    logs_parser.add_argument("-n", "--namespace", help="Namespace")
    logs_parser.add_argument("-c", "--container", help="Container name")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow logs")
    logs_parser.set_defaults(func=cmd_logs)
    
    # exec command
    exec_parser = subparsers.add_parser("exec", help="Execute a command in a container")
    exec_parser.add_argument("name", help="Pod name")
    exec_parser.add_argument("command", help="Command")
    exec_parser.add_argument("-n", "--namespace", help="Namespace")
    exec_parser.add_argument("-c", "--container", help="Container name")
    exec_parser.set_defaults(func=cmd_exec)
    
    # version command
    version_parser = subparsers.add_parser("version", help="Show version information")
    version_parser.set_defaults(func=cmd_version)
    
    # Parse arguments
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
