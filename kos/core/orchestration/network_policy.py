"""
Network Policies for KOS Orchestration System

This module implements network policies for the KOS orchestration system,
allowing fine-grained control over pod-to-pod communication.
"""

import os
import json
import time
import logging
import threading
import ipaddress
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from kos.core.orchestration.pod import Pod
from kos.core.network.firewall import FirewallRule, FirewallManager

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
NETWORK_POLICIES_PATH = os.path.join(ORCHESTRATION_ROOT, 'network_policies')

# Ensure directories exist
os.makedirs(NETWORK_POLICIES_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class NetworkPolicyPort:
    """Port selector for a network policy."""
    
    def __init__(self, protocol: str = "TCP", port: Optional[int] = None,
                 port_range: Optional[Tuple[int, int]] = None):
        """
        Initialize a network policy port.
        
        Args:
            protocol: Protocol (TCP or UDP)
            port: Port number
            port_range: Port range (min, max)
        """
        self.protocol = protocol.upper()
        self.port = port
        self.port_range = port_range
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the network policy port to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {"protocol": self.protocol}
        
        if self.port is not None:
            result["port"] = self.port
        
        if self.port_range is not None:
            result["portRange"] = list(self.port_range)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkPolicyPort':
        """
        Create a network policy port from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            NetworkPolicyPort object
        """
        port_range = None
        if "portRange" in data:
            port_range = tuple(data["portRange"])
        
        return cls(
            protocol=data.get("protocol", "TCP"),
            port=data.get("port"),
            port_range=port_range
        )
    
    def matches_port(self, port: int) -> bool:
        """
        Check if this policy port matches a given port.
        
        Args:
            port: Port number to check
            
        Returns:
            bool: True if matches
        """
        if self.port is not None:
            return self.port == port
        
        if self.port_range is not None:
            return self.port_range[0] <= port <= self.port_range[1]
        
        return True  # Match all ports


class NetworkPolicyPeer:
    """Peer selector for a network policy."""
    
    def __init__(self, pod_selector: Optional[Dict[str, str]] = None,
                 namespace_selector: Optional[Dict[str, str]] = None,
                 ip_block: Optional[Dict[str, Any]] = None):
        """
        Initialize a network policy peer.
        
        Args:
            pod_selector: Label selector for pods
            namespace_selector: Label selector for namespaces
            ip_block: IP block configuration
        """
        self.pod_selector = pod_selector
        self.namespace_selector = namespace_selector
        self.ip_block = ip_block
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the network policy peer to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {}
        
        if self.pod_selector is not None:
            result["podSelector"] = self.pod_selector
        
        if self.namespace_selector is not None:
            result["namespaceSelector"] = self.namespace_selector
        
        if self.ip_block is not None:
            result["ipBlock"] = self.ip_block
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkPolicyPeer':
        """
        Create a network policy peer from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            NetworkPolicyPeer object
        """
        return cls(
            pod_selector=data.get("podSelector"),
            namespace_selector=data.get("namespaceSelector"),
            ip_block=data.get("ipBlock")
        )
    
    def matches_pod(self, pod: Pod, namespace_labels: Dict[str, str]) -> bool:
        """
        Check if this policy peer matches a given pod.
        
        Args:
            pod: Pod to check
            namespace_labels: Labels for the pod's namespace
            
        Returns:
            bool: True if matches
        """
        # Check pod selector
        if self.pod_selector is not None:
            for key, value in self.pod_selector.items():
                if pod.metadata.get("labels", {}).get(key) != value:
                    return False
        
        # Check namespace selector
        if self.namespace_selector is not None:
            for key, value in self.namespace_selector.items():
                if namespace_labels.get(key) != value:
                    return False
        
        # Check IP block
        if self.ip_block is not None:
            pod_ip = pod.status.pod_ip
            if not pod_ip:
                return False
            
            cidr = self.ip_block.get("cidr")
            if not cidr:
                return False
            
            try:
                network = ipaddress.ip_network(cidr)
                pod_ip_obj = ipaddress.ip_address(pod_ip)
                
                if pod_ip_obj not in network:
                    return False
                
                # Check except
                except_list = self.ip_block.get("except", [])
                for except_cidr in except_list:
                    try:
                        except_network = ipaddress.ip_network(except_cidr)
                        if pod_ip_obj in except_network:
                            return False
                    except ValueError:
                        continue
            except ValueError:
                return False
        
        return True


class NetworkPolicyRule:
    """Rule for a network policy."""
    
    def __init__(self, ports: Optional[List[NetworkPolicyPort]] = None,
                 peers: Optional[List[NetworkPolicyPeer]] = None):
        """
        Initialize a network policy rule.
        
        Args:
            ports: List of port selectors
            peers: List of peer selectors
        """
        self.ports = ports or []
        self.peers = peers or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the network policy rule to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "ports": [port.to_dict() for port in self.ports],
            "peers": [peer.to_dict() for peer in self.peers]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], key: str) -> 'NetworkPolicyRule':
        """
        Create a network policy rule from a dictionary.
        
        Args:
            data: Dictionary representation
            key: Key for the rule ('ingress' or 'egress')
            
        Returns:
            NetworkPolicyRule object
        """
        rule_data = data.get(key, {})
        
        ports = []
        for port_data in rule_data.get("ports", []):
            ports.append(NetworkPolicyPort.from_dict(port_data))
        
        peers = []
        peer_key = "from" if key == "ingress" else "to"
        for peer_data in rule_data.get(peer_key, []):
            peers.append(NetworkPolicyPeer.from_dict(peer_data))
        
        return cls(ports=ports, peers=peers)


class NetworkPolicySpec:
    """Specification for a network policy."""
    
    def __init__(self, pod_selector: Dict[str, str] = None,
                 ingress_rules: Optional[List[NetworkPolicyRule]] = None,
                 egress_rules: Optional[List[NetworkPolicyRule]] = None,
                 policy_types: Optional[List[str]] = None):
        """
        Initialize a network policy specification.
        
        Args:
            pod_selector: Label selector for pods
            ingress_rules: List of ingress rules
            egress_rules: List of egress rules
            policy_types: List of policy types ('Ingress', 'Egress')
        """
        self.pod_selector = pod_selector or {}
        self.ingress_rules = ingress_rules or []
        self.egress_rules = egress_rules or []
        self.policy_types = policy_types or ["Ingress"]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the network policy specification to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "podSelector": self.pod_selector,
            "policyTypes": self.policy_types
        }
        
        if self.ingress_rules:
            result["ingress"] = [rule.to_dict() for rule in self.ingress_rules]
        
        if self.egress_rules:
            result["egress"] = [rule.to_dict() for rule in self.egress_rules]
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkPolicySpec':
        """
        Create a network policy specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            NetworkPolicySpec object
        """
        ingress_rules = []
        for rule_data in data.get("ingress", []):
            ingress_rules.append(NetworkPolicyRule.from_dict(rule_data, "ingress"))
        
        egress_rules = []
        for rule_data in data.get("egress", []):
            egress_rules.append(NetworkPolicyRule.from_dict(rule_data, "egress"))
        
        return cls(
            pod_selector=data.get("podSelector", {}),
            ingress_rules=ingress_rules,
            egress_rules=egress_rules,
            policy_types=data.get("policyTypes", ["Ingress"])
        )


class NetworkPolicy:
    """
    Network policy resource in the KOS orchestration system.
    
    A NetworkPolicy specifies how groups of pods are allowed to communicate with each
    other and with other network endpoints.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[NetworkPolicySpec] = None):
        """
        Initialize a network policy.
        
        Args:
            name: Policy name
            namespace: Namespace
            spec: Policy specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or NetworkPolicySpec()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": "",
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this network policy."""
        return os.path.join(NETWORK_POLICIES_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the network policy from disk.
        
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
            
            # Update spec
            spec_data = data.get("spec", {})
            self.spec = NetworkPolicySpec.from_dict(spec_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load NetworkPolicy {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the network policy to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "NetworkPolicy",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save NetworkPolicy {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the network policy.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete NetworkPolicy {self.namespace}/{self.name}: {e}")
            return False
    
    def applies_to_pod(self, pod: Pod, namespace_labels: Dict[str, str]) -> bool:
        """
        Check if this policy applies to a given pod.
        
        Args:
            pod: Pod to check
            namespace_labels: Labels for the pod's namespace
            
        Returns:
            bool: True if applies
        """
        # Check namespace
        if pod.namespace != self.namespace:
            return False
        
        # Check pod selector
        for key, value in self.spec.pod_selector.items():
            if pod.metadata.get("labels", {}).get(key) != value:
                return False
        
        return True
    
    def create_firewall_rules(self, pod: Pod) -> List[FirewallRule]:
        """
        Create firewall rules for a pod based on this policy.
        
        Args:
            pod: Pod to create rules for
            
        Returns:
            List of firewall rules
        """
        rules = []
        
        # Get pod IP
        pod_ip = pod.status.pod_ip
        if not pod_ip:
            return []
        
        # Create ingress rules
        if "Ingress" in self.spec.policy_types:
            for rule in self.spec.ingress_rules:
                for port in rule.ports:
                    # Create rule for each port
                    if port.port is not None:
                        # Single port
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="IN",
                            destination=pod_ip,
                            dest_port=port.port,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
                    elif port.port_range is not None:
                        # Port range
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="IN",
                            destination=pod_ip,
                            dest_port_range=port.port_range,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
                    else:
                        # All ports
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="IN",
                            destination=pod_ip,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
        
        # Create egress rules
        if "Egress" in self.spec.policy_types:
            for rule in self.spec.egress_rules:
                for port in rule.ports:
                    # Create rule for each port
                    if port.port is not None:
                        # Single port
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="OUT",
                            source=pod_ip,
                            dest_port=port.port,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
                    elif port.port_range is not None:
                        # Port range
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="OUT",
                            source=pod_ip,
                            dest_port_range=port.port_range,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
                    else:
                        # All ports
                        rules.append(FirewallRule(
                            action="ACCEPT",
                            direction="OUT",
                            source=pod_ip,
                            protocol=port.protocol,
                            comment=f"NetworkPolicy:{self.namespace}/{self.name}"
                        ))
        
        return rules
    
    @staticmethod
    def list_network_policies(namespace: Optional[str] = None) -> List['NetworkPolicy']:
        """
        List all network policies.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of network policies
        """
        policies = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespace_dir = NETWORK_POLICIES_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
                else:
                    namespaces = []
            
            # List policies in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(NETWORK_POLICIES_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    policy_name = filename[:-5]  # Remove .json extension
                    policy = NetworkPolicy(policy_name, ns)
                    policies.append(policy)
        except Exception as e:
            logger.error(f"Failed to list NetworkPolicies: {e}")
        
        return policies
    
    @staticmethod
    def get_network_policy(name: str, namespace: str = "default") -> Optional['NetworkPolicy']:
        """
        Get a network policy by name and namespace.
        
        Args:
            name: Policy name
            namespace: Namespace
            
        Returns:
            NetworkPolicy or None if not found
        """
        policy = NetworkPolicy(name, namespace)
        
        if os.path.exists(policy._file_path()):
            return policy
        
        return None


class NetworkPolicyController:
    """
    Controller for network policies in the KOS orchestration system.
    
    This class manages the application of network policies to pods, creating
    and updating firewall rules as needed.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(NetworkPolicyController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the network policy controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._firewall_manager = FirewallManager()
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the network policy controller.
        
        Returns:
            bool: Success or failure
        """
        if self._reconcile_thread and self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.clear()
        self._reconcile_thread = threading.Thread(
            target=self._reconcile_loop,
            daemon=True
        )
        self._reconcile_thread.start()
        
        return True
    
    def stop(self) -> bool:
        """
        Stop the network policy controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the network policy controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in network policy reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(30)  # Check every 30 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile network policies with pods.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Get all pods
            pods = Pod.list_pods()
            
            # Get all network policies
            policies = NetworkPolicy.list_network_policies()
            
            # Group policies by namespace
            namespace_policies = {}
            for policy in policies:
                if policy.namespace not in namespace_policies:
                    namespace_policies[policy.namespace] = []
                
                namespace_policies[policy.namespace].append(policy)
            
            # Get namespace labels
            namespace_labels = {}  # Simplified, should get from Namespace API
            
            # Process each pod
            for pod in pods:
                # Skip pods without IPs
                if not pod.status.pod_ip:
                    continue
                
                # Get policies for this pod
                pod_policies = []
                if pod.namespace in namespace_policies:
                    for policy in namespace_policies[pod.namespace]:
                        if policy.applies_to_pod(pod, namespace_labels.get(pod.namespace, {})):
                            pod_policies.append(policy)
                
                # Create firewall rules
                self._apply_policies_to_pod(pod, pod_policies)
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile network policies: {e}")
            return False
    
    def _apply_policies_to_pod(self, pod: Pod, policies: List[NetworkPolicy]) -> bool:
        """
        Apply network policies to a pod.
        
        Args:
            pod: Pod to apply policies to
            policies: List of policies to apply
            
        Returns:
            bool: Success or failure
        """
        try:
            # Get pod IP
            pod_ip = pod.status.pod_ip
            if not pod_ip:
                return False
            
            # Remove existing rules for this pod
            self._firewall_manager.remove_rules_by_comment(f"NetworkPolicy:{pod.namespace}/{pod.name}")
            
            # Create new rules
            rules = []
            for policy in policies:
                rules.extend(policy.create_firewall_rules(pod))
            
            # Add default deny rules if needed
            has_ingress_policy = any("Ingress" in policy.spec.policy_types for policy in policies)
            has_egress_policy = any("Egress" in policy.spec.policy_types for policy in policies)
            
            if has_ingress_policy:
                rules.append(FirewallRule(
                    action="DROP",
                    direction="IN",
                    destination=pod_ip,
                    comment=f"NetworkPolicy:DefaultDeny:{pod.namespace}/{pod.name}"
                ))
            
            if has_egress_policy:
                rules.append(FirewallRule(
                    action="DROP",
                    direction="OUT",
                    source=pod_ip,
                    comment=f"NetworkPolicy:DefaultDeny:{pod.namespace}/{pod.name}"
                ))
            
            # Apply rules
            for rule in rules:
                self._firewall_manager.add_rule(rule)
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply network policies to pod {pod.namespace}/{pod.name}: {e}")
            return False
    
    @staticmethod
    def instance() -> 'NetworkPolicyController':
        """
        Get the singleton instance.
        
        Returns:
            NetworkPolicyController instance
        """
        return NetworkPolicyController()
