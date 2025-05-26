"""
regctl.py - Registry control command for KOS

This module provides the regctl command-line interface for managing the KOS registry,
including pushing, pulling, and managing container images.
"""

import os
import sys
import json
import yaml
import argparse
import logging
import tempfile
import tarfile
from typing import Dict, List, Optional, Any

from kos.core.registry import (
    Registry, RegistryConfig, Image, ImageConfig,
    RegistrySecurity, AccessLevel
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(args=None):
    """
    Main entry point for regctl command.
    
    Args:
        args: Command-line arguments (sys.argv if None)
    """
    parser = create_parser()
    args = parser.parse_args(args)
    
    try:
        # Execute command
        if args.command == "images":
            cmd_images(args)
        elif args.command == "pull":
            cmd_pull(args)
        elif args.command == "push":
            cmd_push(args)
        elif args.command == "tag":
            cmd_tag(args)
        elif args.command == "rmi":
            cmd_rmi(args)
        elif args.command == "search":
            cmd_search(args)
        elif args.command == "inspect":
            cmd_inspect(args)
        elif args.command == "login":
            cmd_login(args)
        elif args.command == "logout":
            cmd_logout(args)
        elif args.command == "user":
            cmd_user(args)
        elif args.command == "acl":
            cmd_acl(args)
        elif args.command == "gc":
            cmd_gc(args)
        elif args.command == "import":
            cmd_import(args)
        elif args.command == "export":
            cmd_export(args)
        else:
            parser.print_help()
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def create_parser():
    """
    Create command-line argument parser.
    
    Returns:
        ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="regctl - Command-line interface for KOS registry",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # images command
    images_parser = subparsers.add_parser("images", help="List images")
    images_parser.add_argument(
        "--format",
        choices=["table", "json", "yaml"],
        default="table",
        help="Output format"
    )
    
    # pull command
    pull_parser = subparsers.add_parser("pull", help="Pull an image")
    pull_parser.add_argument(
        "image",
        help="Image to pull (name:tag)"
    )
    
    # push command
    push_parser = subparsers.add_parser("push", help="Push an image")
    push_parser.add_argument(
        "image",
        help="Image to push (name:tag)"
    )
    
    # tag command
    tag_parser = subparsers.add_parser("tag", help="Tag an image")
    tag_parser.add_argument(
        "source",
        help="Source image (name:tag)"
    )
    tag_parser.add_argument(
        "target",
        help="Target image (name:tag)"
    )
    
    # rmi command
    rmi_parser = subparsers.add_parser("rmi", help="Remove an image")
    rmi_parser.add_argument(
        "image",
        help="Image to remove (name:tag)"
    )
    rmi_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force removal"
    )
    
    # search command
    search_parser = subparsers.add_parser("search", help="Search for images")
    search_parser.add_argument(
        "query",
        help="Search query"
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of results"
    )
    search_parser.add_argument(
        "--format",
        choices=["table", "json", "yaml"],
        default="table",
        help="Output format"
    )
    
    # inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect an image")
    inspect_parser.add_argument(
        "image",
        help="Image to inspect (name:tag)"
    )
    inspect_parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="Output format"
    )
    
    # login command
    login_parser = subparsers.add_parser("login", help="Log in to the registry")
    login_parser.add_argument(
        "username",
        help="Username"
    )
    login_parser.add_argument(
        "--password",
        help="Password (will prompt if not provided)"
    )
    
    # logout command
    logout_parser = subparsers.add_parser("logout", help="Log out from the registry")
    
    # user command
    user_parser = subparsers.add_parser("user", help="Manage users")
    user_subparsers = user_parser.add_subparsers(dest="user_command", help="User command")
    
    # user add command
    user_add_parser = user_subparsers.add_parser("add", help="Add a user")
    user_add_parser.add_argument(
        "username",
        help="Username"
    )
    user_add_parser.add_argument(
        "--password",
        help="Password (will prompt if not provided)"
    )
    user_add_parser.add_argument(
        "--access-level",
        choices=["none", "read", "write", "admin"],
        default="read",
        help="Access level"
    )
    
    # user delete command
    user_delete_parser = user_subparsers.add_parser("delete", help="Delete a user")
    user_delete_parser.add_argument(
        "username",
        help="Username"
    )
    
    # user update command
    user_update_parser = user_subparsers.add_parser("update", help="Update a user")
    user_update_parser.add_argument(
        "username",
        help="Username"
    )
    user_update_parser.add_argument(
        "--password",
        help="New password (will prompt if not provided)"
    )
    user_update_parser.add_argument(
        "--access-level",
        choices=["none", "read", "write", "admin"],
        help="New access level"
    )
    
    # user list command
    user_list_parser = user_subparsers.add_parser("list", help="List users")
    user_list_parser.add_argument(
        "--format",
        choices=["table", "json", "yaml"],
        default="table",
        help="Output format"
    )
    
    # acl command
    acl_parser = subparsers.add_parser("acl", help="Manage access control")
    acl_subparsers = acl_parser.add_subparsers(dest="acl_command", help="ACL command")
    
    # acl set command
    acl_set_parser = acl_subparsers.add_parser("set", help="Set access control")
    acl_set_parser.add_argument(
        "resource",
        help="Resource name (e.g., 'image/nginx')"
    )
    acl_set_parser.add_argument(
        "username",
        help="Username"
    )
    acl_set_parser.add_argument(
        "access_level",
        choices=["none", "read", "write", "admin"],
        help="Access level"
    )
    
    # gc command
    gc_parser = subparsers.add_parser("gc", help="Run garbage collection")
    
    # import command
    import_parser = subparsers.add_parser("import", help="Import an image from a tar file")
    import_parser.add_argument(
        "tarfile",
        help="Tar file to import"
    )
    import_parser.add_argument(
        "image",
        help="Image name and tag (name:tag)"
    )
    
    # export command
    export_parser = subparsers.add_parser("export", help="Export an image to a directory")
    export_parser.add_argument(
        "image",
        help="Image to export (name:tag)"
    )
    export_parser.add_argument(
        "directory",
        help="Directory to export to"
    )
    
    return parser


def parse_image_arg(image_arg: str) -> Tuple[str, str]:
    """
    Parse an image argument into name and tag.
    
    Args:
        image_arg: Image argument (name:tag)
        
    Returns:
        Tuple of (name, tag)
    """
    if ":" in image_arg:
        name, tag = image_arg.split(":", 1)
    else:
        name = image_arg
        tag = "latest"
    
    return name, tag


def cmd_images(args):
    """
    Execute images command.
    
    Args:
        args: Command-line arguments
    """
    registry = Registry()
    images = registry.list_images()
    
    if args.format == "json":
        # Format as JSON
        result = []
        for name, tag in images:
            info = registry.get_image_info(name, tag)
            if info:
                result.append(info)
        
        print(json.dumps(result, indent=2))
    elif args.format == "yaml":
        # Format as YAML
        result = []
        for name, tag in images:
            info = registry.get_image_info(name, tag)
            if info:
                result.append(info)
        
        print(yaml.dump(result, default_flow_style=False))
    else:
        # Format as table
        print(f"{'REPOSITORY':<30} {'TAG':<15} {'IMAGE ID':<15} {'SIZE':<10} {'CREATED':<20}")
        
        for name, tag in sorted(images):
            info = registry.get_image_info(name, tag)
            if info:
                digest = info.get("digest", "").split(":")[-1][:12]
                size = _format_size(info.get("size", 0))
                created = _format_time(info.get("created", 0))
                
                print(f"{name:<30} {tag:<15} {digest:<15} {size:<10} {created:<20}")


def cmd_pull(args):
    """
    Execute pull command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    registry = Registry()
    result = registry.pull_image(name, tag)
    
    if result:
        print(f"Successfully pulled image {name}:{tag}")
    else:
        logger.error(f"Failed to pull image {name}:{tag}")
        sys.exit(1)


def cmd_push(args):
    """
    Execute push command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    # Check if image exists locally
    image = Image(name, tag)
    if not image.exists():
        logger.error(f"Image not found: {name}:{tag}")
        sys.exit(1)
    
    # Check authentication
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    # Check authorization
    security = RegistrySecurity()
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    resource = f"image/{name}"
    if not security.check_access(resource, username, AccessLevel.WRITE):
        logger.error(f"Access denied for {resource}")
        sys.exit(1)
    
    # Image is already in the registry, nothing to do
    print(f"Successfully pushed image {name}:{tag}")


def cmd_tag(args):
    """
    Execute tag command.
    
    Args:
        args: Command-line arguments
    """
    source_name, source_tag = parse_image_arg(args.source)
    target_name, target_tag = parse_image_arg(args.target)
    
    # Check if source image exists
    source_image = Image(source_name, source_tag)
    if not source_image.exists():
        logger.error(f"Source image not found: {source_name}:{source_tag}")
        sys.exit(1)
    
    # Check authentication
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    # Check authorization
    security = RegistrySecurity()
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    resource = f"image/{target_name}"
    if not security.check_access(resource, username, AccessLevel.WRITE):
        logger.error(f"Access denied for {resource}")
        sys.exit(1)
    
    # Pull source image
    result = source_image.pull()
    if not result:
        logger.error(f"Failed to pull source image {source_name}:{source_tag}")
        sys.exit(1)
    
    layers, config = result
    
    # Push target image
    target_image = Image(target_name, target_tag)
    if target_image.push(layers, config):
        print(f"Successfully tagged {source_name}:{source_tag} as {target_name}:{target_tag}")
    else:
        logger.error(f"Failed to tag image")
        sys.exit(1)


def cmd_rmi(args):
    """
    Execute rmi command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    # Check if image exists
    image = Image(name, tag)
    if not image.exists():
        logger.error(f"Image not found: {name}:{tag}")
        sys.exit(1)
    
    # Check authentication
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    # Check authorization
    security = RegistrySecurity()
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    resource = f"image/{name}"
    if not security.check_access(resource, username, AccessLevel.WRITE):
        logger.error(f"Access denied for {resource}")
        sys.exit(1)
    
    # Delete image
    registry = Registry()
    if registry.delete_image(name, tag):
        print(f"Successfully removed image {name}:{tag}")
    else:
        logger.error(f"Failed to remove image {name}:{tag}")
        sys.exit(1)


def cmd_search(args):
    """
    Execute search command.
    
    Args:
        args: Command-line arguments
    """
    registry = Registry()
    results = registry.search_images(args.query, args.limit)
    
    if args.format == "json":
        # Format as JSON
        print(json.dumps(results, indent=2))
    elif args.format == "yaml":
        # Format as YAML
        print(yaml.dump(results, default_flow_style=False))
    else:
        # Format as table
        print(f"{'NAME':<30} {'DESCRIPTION':<50} {'STARS':<5}")
        
        for result in results:
            name = f"{result.get('name')}:{result.get('tag')}"
            description = result.get("labels", {}).get("description", "")
            if len(description) > 47:
                description = description[:47] + "..."
            
            stars = result.get("labels", {}).get("stars", "0")
            
            print(f"{name:<30} {description:<50} {stars:<5}")


def cmd_inspect(args):
    """
    Execute inspect command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    registry = Registry()
    info = registry.get_image_info(name, tag)
    
    if not info:
        logger.error(f"Image not found: {name}:{tag}")
        sys.exit(1)
    
    if args.format == "json":
        # Format as JSON
        print(json.dumps(info, indent=2))
    else:
        # Format as YAML
        print(yaml.dump(info, default_flow_style=False))


def cmd_login(args):
    """
    Execute login command.
    
    Args:
        args: Command-line arguments
    """
    username = args.username
    password = args.password
    
    if not password:
        import getpass
        password = getpass.getpass("Password: ")
    
    security = RegistrySecurity()
    token = security.authenticate(username, password)
    
    if not token:
        logger.error("Authentication failed")
        sys.exit(1)
    
    # Save token to file
    token_file = os.path.expanduser("~/.kos/registry/token")
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    
    with open(token_file, 'w') as f:
        f.write(token)
    
    print(f"Login succeeded for user {username}")


def cmd_logout(args):
    """
    Execute logout command.
    
    Args:
        args: Command-line arguments
    """
    token = _get_token()
    if not token:
        logger.error("Not logged in")
        sys.exit(1)
    
    security = RegistrySecurity()
    username = security.validate_token(token)
    
    if security.invalidate_token(token):
        # Remove token file
        token_file = os.path.expanduser("~/.kos/registry/token")
        if os.path.exists(token_file):
            os.remove(token_file)
        
        print(f"Logout succeeded for user {username}")
    else:
        logger.error("Logout failed")
        sys.exit(1)


def cmd_user(args):
    """
    Execute user command.
    
    Args:
        args: Command-line arguments
    """
    security = RegistrySecurity()
    
    # Check authentication for admin operations
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    # Check admin access
    if not security.check_access("admin", username, AccessLevel.ADMIN):
        logger.error("Admin access required")
        sys.exit(1)
    
    if args.user_command == "add":
        # Add user
        password = args.password
        if not password:
            import getpass
            password = getpass.getpass("Password: ")
        
        access_level = AccessLevel(args.access_level)
        
        if security.create_user(args.username, password, access_level):
            print(f"Successfully added user {args.username}")
        else:
            logger.error(f"Failed to add user {args.username}")
            sys.exit(1)
    
    elif args.user_command == "delete":
        # Delete user
        if security.delete_user(args.username):
            print(f"Successfully deleted user {args.username}")
        else:
            logger.error(f"Failed to delete user {args.username}")
            sys.exit(1)
    
    elif args.user_command == "update":
        # Update user
        password = args.password
        if password is not None and not password:
            import getpass
            password = getpass.getpass("New password: ")
        
        access_level = None
        if args.access_level:
            access_level = AccessLevel(args.access_level)
        
        if security.update_user(args.username, password, access_level):
            print(f"Successfully updated user {args.username}")
        else:
            logger.error(f"Failed to update user {args.username}")
            sys.exit(1)
    
    elif args.user_command == "list":
        # List users
        users = security.list_users()
        
        if args.format == "json":
            # Format as JSON
            print(json.dumps(users, indent=2))
        elif args.format == "yaml":
            # Format as YAML
            print(yaml.dump(users, default_flow_style=False))
        else:
            # Format as table
            print(f"{'USERNAME':<20} {'ACCESS LEVEL':<15} {'LAST LOGIN':<20}")
            
            for user in users:
                username = user.get("username", "")
                access_level = user.get("access_level", "none")
                last_login = _format_time(user.get("last_login", 0))
                
                print(f"{username:<20} {access_level:<15} {last_login:<20}")
    
    else:
        logger.error(f"Unknown user command: {args.user_command}")
        sys.exit(1)


def cmd_acl(args):
    """
    Execute acl command.
    
    Args:
        args: Command-line arguments
    """
    security = RegistrySecurity()
    
    # Check authentication for admin operations
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    # Check admin access
    if not security.check_access("admin", username, AccessLevel.ADMIN):
        logger.error("Admin access required")
        sys.exit(1)
    
    if args.acl_command == "set":
        # Set ACL
        access_level = AccessLevel(args.access_level)
        
        if security.set_acl(args.resource, args.username, access_level):
            print(f"Successfully set ACL for {args.resource}: {args.username} -> {access_level}")
        else:
            logger.error(f"Failed to set ACL")
            sys.exit(1)
    
    else:
        logger.error(f"Unknown ACL command: {args.acl_command}")
        sys.exit(1)


def cmd_gc(args):
    """
    Execute gc command.
    
    Args:
        args: Command-line arguments
    """
    registry = Registry()
    removed = registry.run_gc()
    
    print(f"Garbage collection complete. Removed {removed} unused blobs.")


def cmd_import(args):
    """
    Execute import command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    # Check if tar file exists
    if not os.path.exists(args.tarfile):
        logger.error(f"Tar file not found: {args.tarfile}")
        sys.exit(1)
    
    # Check authentication
    token = _get_token()
    if not token:
        logger.error("Authentication required. Please run 'regctl login' first.")
        sys.exit(1)
    
    # Check authorization
    security = RegistrySecurity()
    username = security.validate_token(token)
    if not username:
        logger.error("Invalid or expired token. Please run 'regctl login' again.")
        sys.exit(1)
    
    resource = f"image/{name}"
    if not security.check_access(resource, username, AccessLevel.WRITE):
        logger.error(f"Access denied for {resource}")
        sys.exit(1)
    
    # Import image
    registry = Registry()
    image = Image(name, tag)
    
    if image.create_from_tar(args.tarfile):
        print(f"Successfully imported {args.tarfile} as {name}:{tag}")
    else:
        logger.error(f"Failed to import image")
        sys.exit(1)


def cmd_export(args):
    """
    Execute export command.
    
    Args:
        args: Command-line arguments
    """
    name, tag = parse_image_arg(args.image)
    
    # Check if image exists
    image = Image(name, tag)
    if not image.exists():
        logger.error(f"Image not found: {name}:{tag}")
        sys.exit(1)
    
    # Check if directory exists
    if not os.path.exists(args.directory):
        os.makedirs(args.directory, exist_ok=True)
    
    # Export image
    if image.extract_to_dir(args.directory):
        print(f"Successfully exported {name}:{tag} to {args.directory}")
    else:
        logger.error(f"Failed to export image")
        sys.exit(1)


def _get_token() -> Optional[str]:
    """
    Get authentication token.
    
    Returns:
        Token or None if not found
    """
    token_file = os.path.expanduser("~/.kos/registry/token")
    if not os.path.exists(token_file):
        return None
    
    try:
        with open(token_file, 'r') as f:
            return f.read().strip()
    except Exception:
        return None


def _format_size(size_bytes: int) -> str:
    """
    Format size in bytes to human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _format_time(timestamp: float) -> str:
    """
    Format timestamp to human-readable string.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Human-readable time string
    """
    import datetime
    
    if not timestamp:
        return "N/A"
    
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    main()
