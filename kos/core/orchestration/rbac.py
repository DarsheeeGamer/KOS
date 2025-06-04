"""
Role-Based Access Control for KOS Orchestration

This module implements RBAC for the KOS orchestration system,
providing authorization mechanisms for resources.
"""

import os
import json
import logging
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Set, Tuple, Union

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
RBAC_PATH = os.path.join(ORCHESTRATION_ROOT, 'rbac')
ROLES_PATH = os.path.join(RBAC_PATH, 'roles')
ROLE_BINDINGS_PATH = os.path.join(RBAC_PATH, 'rolebindings')
CLUSTER_ROLES_PATH = os.path.join(RBAC_PATH, 'clusterroles')
CLUSTER_ROLE_BINDINGS_PATH = os.path.join(RBAC_PATH, 'clusterrolebindings')

# Ensure directories exist
os.makedirs(ROLES_PATH, exist_ok=True)
os.makedirs(ROLE_BINDINGS_PATH, exist_ok=True)
os.makedirs(CLUSTER_ROLES_PATH, exist_ok=True)
os.makedirs(CLUSTER_ROLE_BINDINGS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class PolicyRule:
    """Rule for RBAC policies."""
    
    def __init__(self, api_groups: List[str] = None,
                 resources: List[str] = None,
                 verbs: List[str] = None,
                 resource_names: List[str] = None):
        """
        Initialize a policy rule.
        
        Args:
            api_groups: API groups this rule applies to
            resources: Resources this rule applies to
            verbs: Verbs this rule applies to
            resource_names: Resource names this rule applies to
        """
        self.api_groups = api_groups or [""]
        self.resources = resources or []
        self.verbs = verbs or []
        self.resource_names = resource_names or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the policy rule to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "apiGroups": self.api_groups,
            "resources": self.resources,
            "verbs": self.verbs,
            "resourceNames": self.resource_names
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyRule':
        """
        Create a policy rule from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PolicyRule object
        """
        return cls(
            api_groups=data.get("apiGroups", [""]),
            resources=data.get("resources", []),
            verbs=data.get("verbs", []),
            resource_names=data.get("resourceNames", [])
        )


class Role:
    """
    Role in the KOS orchestration system.
    
    A Role contains rules that represent a set of permissions.
    Roles are namespace-scoped.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 rules: List[PolicyRule] = None):
        """
        Initialize a Role.
        
        Args:
            name: Role name
            namespace: Namespace
            rules: Policy rules
        """
        self.name = name
        self.namespace = namespace
        self.rules = rules or []
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this Role."""
        return os.path.join(ROLES_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the Role from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update rules
            rules_data = data.get("rules", [])
            self.rules = [PolicyRule.from_dict(rule) for rule in rules_data]
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Role {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Role to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "Role",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "rules": [rule.to_dict() for rule in self.rules]
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Role {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Role.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Role {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_roles(namespace: Optional[str] = None) -> List['Role']:
        """
        List all Roles.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of Roles
        """
        roles = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = ROLES_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List Roles in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(ROLES_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    role_name = filename[:-5]  # Remove .json extension
                    role = Role(role_name, ns)
                    roles.append(role)
        except Exception as e:
            logger.error(f"Failed to list Roles: {e}")
        
        return roles
    
    @staticmethod
    def get_role(name: str, namespace: str = "default") -> Optional['Role']:
        """
        Get a Role by name and namespace.
        
        Args:
            name: Role name
            namespace: Namespace
            
        Returns:
            Role object or None if not found
        """
        role = Role(name, namespace)
        
        if os.path.exists(role._file_path()):
            return role
        
        return None


class ClusterRole:
    """
    ClusterRole in the KOS orchestration system.
    
    A ClusterRole contains rules that represent a set of permissions.
    ClusterRoles are cluster-scoped, not namespace-scoped.
    """
    
    def __init__(self, name: str, rules: List[PolicyRule] = None):
        """
        Initialize a ClusterRole.
        
        Args:
            name: ClusterRole name
            rules: Policy rules
        """
        self.name = name
        self.rules = rules or []
        self.metadata = {
            "name": name,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this ClusterRole."""
        return os.path.join(CLUSTER_ROLES_PATH, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the ClusterRole from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update rules
            rules_data = data.get("rules", [])
            self.rules = [PolicyRule.from_dict(rule) for rule in rules_data]
            
            return True
        except Exception as e:
            logger.error(f"Failed to load ClusterRole {self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the ClusterRole to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "ClusterRole",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "rules": [rule.to_dict() for rule in self.rules]
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save ClusterRole {self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the ClusterRole.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete ClusterRole {self.name}: {e}")
            return False
    
    @staticmethod
    def list_cluster_roles() -> List['ClusterRole']:
        """
        List all ClusterRoles.
        
        Returns:
            List of ClusterRoles
        """
        cluster_roles = []
        
        try:
            if os.path.exists(CLUSTER_ROLES_PATH):
                for filename in os.listdir(CLUSTER_ROLES_PATH):
                    if not filename.endswith('.json'):
                        continue
                    
                    role_name = filename[:-5]  # Remove .json extension
                    role = ClusterRole(role_name)
                    cluster_roles.append(role)
        except Exception as e:
            logger.error(f"Failed to list ClusterRoles: {e}")
        
        return cluster_roles
    
    @staticmethod
    def get_cluster_role(name: str) -> Optional['ClusterRole']:
        """
        Get a ClusterRole by name.
        
        Args:
            name: ClusterRole name
            
        Returns:
            ClusterRole object or None if not found
        """
        role = ClusterRole(name)
        
        if os.path.exists(role._file_path()):
            return role
        
        return None


class RoleBinding:
    """
    RoleBinding in the KOS orchestration system.
    
    A RoleBinding grants permissions defined in a Role to a user or set of users.
    RoleBindings are namespace-scoped.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 role_ref: Dict[str, str] = None,
                 subjects: List[Dict[str, str]] = None):
        """
        Initialize a RoleBinding.
        
        Args:
            name: RoleBinding name
            namespace: Namespace
            role_ref: Reference to the role being granted
            subjects: List of subjects being granted the role
        """
        self.name = name
        self.namespace = namespace
        self.role_ref = role_ref or {"kind": "Role", "name": ""}
        self.subjects = subjects or []
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this RoleBinding."""
        return os.path.join(ROLE_BINDINGS_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the RoleBinding from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update role ref
            self.role_ref = data.get("roleRef", {"kind": "Role", "name": ""})
            
            # Update subjects
            self.subjects = data.get("subjects", [])
            
            return True
        except Exception as e:
            logger.error(f"Failed to load RoleBinding {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the RoleBinding to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "RoleBinding",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "roleRef": self.role_ref,
                    "subjects": self.subjects
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save RoleBinding {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the RoleBinding.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete RoleBinding {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_role_bindings(namespace: Optional[str] = None) -> List['RoleBinding']:
        """
        List all RoleBindings.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of RoleBindings
        """
        role_bindings = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = ROLE_BINDINGS_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List RoleBindings in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(ROLE_BINDINGS_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    binding_name = filename[:-5]  # Remove .json extension
                    binding = RoleBinding(binding_name, ns)
                    role_bindings.append(binding)
        except Exception as e:
            logger.error(f"Failed to list RoleBindings: {e}")
        
        return role_bindings
    
    @staticmethod
    def get_role_binding(name: str, namespace: str = "default") -> Optional['RoleBinding']:
        """
        Get a RoleBinding by name and namespace.
        
        Args:
            name: RoleBinding name
            namespace: Namespace
            
        Returns:
            RoleBinding object or None if not found
        """
        binding = RoleBinding(name, namespace)
        
        if os.path.exists(binding._file_path()):
            return binding
        
        return None


class ClusterRoleBinding:
    """
    ClusterRoleBinding in the KOS orchestration system.
    
    A ClusterRoleBinding grants permissions defined in a ClusterRole to a user or set of users.
    ClusterRoleBindings are cluster-scoped, not namespace-scoped.
    """
    
    def __init__(self, name: str, role_ref: Dict[str, str] = None,
                 subjects: List[Dict[str, str]] = None):
        """
        Initialize a ClusterRoleBinding.
        
        Args:
            name: ClusterRoleBinding name
            role_ref: Reference to the role being granted
            subjects: List of subjects being granted the role
        """
        self.name = name
        self.role_ref = role_ref or {"kind": "ClusterRole", "name": ""}
        self.subjects = subjects or []
        self.metadata = {
            "name": name,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this ClusterRoleBinding."""
        return os.path.join(CLUSTER_ROLE_BINDINGS_PATH, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the ClusterRoleBinding from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update role ref
            self.role_ref = data.get("roleRef", {"kind": "ClusterRole", "name": ""})
            
            # Update subjects
            self.subjects = data.get("subjects", [])
            
            return True
        except Exception as e:
            logger.error(f"Failed to load ClusterRoleBinding {self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the ClusterRoleBinding to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "ClusterRoleBinding",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "roleRef": self.role_ref,
                    "subjects": self.subjects
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save ClusterRoleBinding {self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the ClusterRoleBinding.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete ClusterRoleBinding {self.name}: {e}")
            return False
    
    @staticmethod
    def list_cluster_role_bindings() -> List['ClusterRoleBinding']:
        """
        List all ClusterRoleBindings.
        
        Returns:
            List of ClusterRoleBindings
        """
        bindings = []
        
        try:
            if os.path.exists(CLUSTER_ROLE_BINDINGS_PATH):
                for filename in os.listdir(CLUSTER_ROLE_BINDINGS_PATH):
                    if not filename.endswith('.json'):
                        continue
                    
                    binding_name = filename[:-5]  # Remove .json extension
                    binding = ClusterRoleBinding(binding_name)
                    bindings.append(binding)
        except Exception as e:
            logger.error(f"Failed to list ClusterRoleBindings: {e}")
        
        return bindings
    
    @staticmethod
    def get_cluster_role_binding(name: str) -> Optional['ClusterRoleBinding']:
        """
        Get a ClusterRoleBinding by name.
        
        Args:
            name: ClusterRoleBinding name
            
        Returns:
            ClusterRoleBinding object or None if not found
        """
        binding = ClusterRoleBinding(name)
        
        if os.path.exists(binding._file_path()):
            return binding
        
        return None


class RBACAuthorizer:
    """
    RBAC authorizer for the KOS orchestration system.
    
    This class checks if a user is authorized to perform an action on a resource.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RBACAuthorizer, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the RBAC authorizer."""
        if self._initialized:
            return
        
        self._initialized = True
    
    def is_authorized(self, user: str, verb: str, resource: str, 
                     namespace: Optional[str] = None,
                     resource_name: Optional[str] = None,
                     api_group: str = "") -> bool:
        """
        Check if a user is authorized to perform an action.
        
        Args:
            user: User name
            verb: Verb (e.g., get, list, create)
            resource: Resource (e.g., pods, services)
            namespace: Namespace (None for cluster-scoped resources)
            resource_name: Resource name
            api_group: API group
            
        Returns:
            bool: True if authorized
        """
        # Check namespace-scoped permissions
        if namespace:
            # Check RoleBindings in the namespace
            role_bindings = RoleBinding.list_role_bindings(namespace)
            
            for binding in role_bindings:
                # Check if the binding applies to the user
                if not self._binding_applies_to_user(binding.subjects, user):
                    continue
                
                # Get the referenced role
                role_ref = binding.role_ref
                if role_ref.get("kind") == "Role":
                    role = Role.get_role(role_ref.get("name", ""), namespace)
                    if role and self._role_allows(role.rules, verb, resource, resource_name, api_group):
                        return True
                elif role_ref.get("kind") == "ClusterRole":
                    role = ClusterRole.get_cluster_role(role_ref.get("name", ""))
                    if role and self._role_allows(role.rules, verb, resource, resource_name, api_group):
                        return True
        
        # Check cluster-scoped permissions
        cluster_role_bindings = ClusterRoleBinding.list_cluster_role_bindings()
        
        for binding in cluster_role_bindings:
            # Check if the binding applies to the user
            if not self._binding_applies_to_user(binding.subjects, user):
                continue
            
            # Get the referenced role
            role_ref = binding.role_ref
            if role_ref.get("kind") == "ClusterRole":
                role = ClusterRole.get_cluster_role(role_ref.get("name", ""))
                if role and self._role_allows(role.rules, verb, resource, resource_name, api_group):
                    return True
        
        return False
    
    def _binding_applies_to_user(self, subjects: List[Dict[str, str]], user: str) -> bool:
        """
        Check if a binding applies to a user.
        
        Args:
            subjects: List of subjects
            user: User name
            
        Returns:
            bool: True if the binding applies to the user
        """
        for subject in subjects:
            if subject.get("kind") == "User" and subject.get("name") == user:
                return True
            
            # Handle groups
            if subject.get("kind") == "Group":
                group_name = subject.get("name", "")
                # TODO: Check if user is in group
                # For now, assume no group membership
        
        return False
    
    def _role_allows(self, rules: List[PolicyRule], verb: str, resource: str,
                    resource_name: Optional[str] = None,
                    api_group: str = "") -> bool:
        """
        Check if a role allows an action.
        
        Args:
            rules: Policy rules
            verb: Verb
            resource: Resource
            resource_name: Resource name
            api_group: API group
            
        Returns:
            bool: True if allowed
        """
        for rule in rules:
            # Check API group
            if api_group not in rule.api_groups and "*" not in rule.api_groups:
                continue
            
            # Check resource
            if resource not in rule.resources and "*" not in rule.resources:
                continue
            
            # Check verb
            if verb not in rule.verbs and "*" not in rule.verbs:
                continue
            
            # Check resource name
            if resource_name and rule.resource_names:
                if resource_name not in rule.resource_names:
                    continue
            
            return True
        
        return False
    
    @staticmethod
    def instance() -> 'RBACAuthorizer':
        """
        Get the singleton instance.
        
        Returns:
            RBACAuthorizer instance
        """
        return RBACAuthorizer()


def create_default_roles() -> None:
    """Create default roles and role bindings."""
    # Create cluster-admin role
    admin_role = ClusterRole("cluster-admin")
    admin_role.rules = [
        PolicyRule(
            api_groups=["*"],
            resources=["*"],
            verbs=["*"]
        )
    ]
    admin_role.save()
    
    # Create view role
    view_role = ClusterRole("view")
    view_role.rules = [
        PolicyRule(
            api_groups=[""],
            resources=["pods", "services", "configmaps", "persistentvolumeclaims"],
            verbs=["get", "list", "watch"]
        )
    ]
    view_role.save()
    
    # Create edit role
    edit_role = ClusterRole("edit")
    edit_role.rules = [
        PolicyRule(
            api_groups=[""],
            resources=["pods", "services", "configmaps", "persistentvolumeclaims"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"]
        )
    ]
    edit_role.save()
    
    # Create admin binding
    admin_binding = ClusterRoleBinding("cluster-admin")
    admin_binding.role_ref = {
        "kind": "ClusterRole",
        "name": "cluster-admin"
    }
    admin_binding.subjects = [
        {
            "kind": "User",
            "name": "admin"
        }
    ]
    admin_binding.save()


def authorize(user: str, verb: str, resource: str, 
             namespace: Optional[str] = None,
             resource_name: Optional[str] = None,
             api_group: str = "") -> bool:
    """
    Check if a user is authorized to perform an action.
    
    Args:
        user: User name
        verb: Verb (e.g., get, list, create)
        resource: Resource (e.g., pods, services)
        namespace: Namespace (None for cluster-scoped resources)
        resource_name: Resource name
        api_group: API group
        
    Returns:
        bool: True if authorized
    """
    authorizer = RBACAuthorizer.instance()
    return authorizer.is_authorized(user, verb, resource, namespace, resource_name, api_group)


# Create default roles when module is imported
if not os.listdir(CLUSTER_ROLES_PATH):
    create_default_roles()
