"""
Admission Controller Webhook for KOS Orchestration System

This module implements a webhook mechanism for the admission controller,
allowing external validation services to register with KOS and provide
additional validation capabilities.
"""

import os
import json
import logging
import threading
import time
import http.client
import urllib.parse
import ssl
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable

from kos.core.orchestration.admission import ValidationResult

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
WEBHOOK_CONFIG_PATH = os.path.join(ORCHESTRATION_ROOT, 'webhook_config.json')

# Logging setup
logger = logging.getLogger(__name__)


class WebhookConfiguration:
    """Configuration for an admission webhook."""
    
    def __init__(self, name: str, url: str, timeout_seconds: int = 10,
                 ca_bundle: Optional[str] = None, 
                 failure_policy: str = "Fail",
                 resource_kinds: Optional[List[str]] = None,
                 enabled: bool = True):
        """
        Initialize a webhook configuration.
        
        Args:
            name: Webhook name
            url: Webhook URL
            timeout_seconds: Webhook timeout in seconds
            ca_bundle: CA bundle for TLS verification (base64 encoded)
            failure_policy: Policy for handling webhook failures (Fail or Ignore)
            resource_kinds: Resource kinds this webhook applies to
            enabled: Whether the webhook is enabled
        """
        self.name = name
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.ca_bundle = ca_bundle
        self.failure_policy = failure_policy
        self.resource_kinds = resource_kinds or []
        self.enabled = enabled
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the webhook configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "url": self.url,
            "timeoutSeconds": self.timeout_seconds,
            "caBundle": self.ca_bundle,
            "failurePolicy": self.failure_policy,
            "resourceKinds": self.resource_kinds,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebhookConfiguration':
        """
        Create a webhook configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            WebhookConfiguration object
        """
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            timeout_seconds=data.get("timeoutSeconds", 10),
            ca_bundle=data.get("caBundle"),
            failure_policy=data.get("failurePolicy", "Fail"),
            resource_kinds=data.get("resourceKinds", []),
            enabled=data.get("enabled", True)
        )


class AdmissionWebhookManager:
    """
    Manager for admission webhooks in the KOS orchestration system.
    
    This class manages the registration and invocation of admission webhooks.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AdmissionWebhookManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the webhook manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._webhooks: Dict[str, WebhookConfiguration] = {}
        self._ssl_context = None
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load webhook configuration from disk."""
        try:
            if os.path.exists(WEBHOOK_CONFIG_PATH):
                with open(WEBHOOK_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                
                webhooks_data = data.get("webhooks", [])
                
                for webhook_data in webhooks_data:
                    webhook = WebhookConfiguration.from_dict(webhook_data)
                    self._webhooks[webhook.name] = webhook
        except Exception as e:
            logger.error(f"Failed to load webhook configuration: {e}")
    
    def _save_config(self) -> bool:
        """
        Save webhook configuration to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            os.makedirs(os.path.dirname(WEBHOOK_CONFIG_PATH), exist_ok=True)
            
            data = {
                "webhooks": [
                    webhook.to_dict() for webhook in self._webhooks.values()
                ]
            }
            
            with open(WEBHOOK_CONFIG_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save webhook configuration: {e}")
            return False
    
    def register_webhook(self, webhook: WebhookConfiguration) -> bool:
        """
        Register a webhook.
        
        Args:
            webhook: Webhook configuration
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            self._webhooks[webhook.name] = webhook
            return self._save_config()
    
    def unregister_webhook(self, name: str) -> bool:
        """
        Unregister a webhook.
        
        Args:
            name: Webhook name
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if name in self._webhooks:
                del self._webhooks[name]
                return self._save_config()
            
            return False
    
    def enable_webhook(self, name: str) -> bool:
        """
        Enable a webhook.
        
        Args:
            name: Webhook name
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if name in self._webhooks:
                self._webhooks[name].enabled = True
                return self._save_config()
            
            return False
    
    def disable_webhook(self, name: str) -> bool:
        """
        Disable a webhook.
        
        Args:
            name: Webhook name
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if name in self._webhooks:
                self._webhooks[name].enabled = False
                return self._save_config()
            
            return False
    
    def list_webhooks(self) -> List[WebhookConfiguration]:
        """
        List all webhooks.
        
        Returns:
            List of webhook configurations
        """
        with self._lock:
            return list(self._webhooks.values())
    
    def get_webhook(self, name: str) -> Optional[WebhookConfiguration]:
        """
        Get a webhook by name.
        
        Args:
            name: Webhook name
            
        Returns:
            Webhook configuration or None if not found
        """
        with self._lock:
            return self._webhooks.get(name)
    
    def validate_resource(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate a resource using webhooks.
        
        Args:
            resource: Resource to validate
            
        Returns:
            ValidationResult object
        """
        # Get resource kind
        kind = resource.get("kind")
        if not kind:
            return ValidationResult(False, "Resource kind is required")
        
        # Get webhooks for this kind
        webhooks = []
        for webhook in self._webhooks.values():
            if not webhook.enabled:
                continue
            
            if not webhook.resource_kinds or kind in webhook.resource_kinds:
                webhooks.append(webhook)
        
        # If no webhooks, resource is valid
        if not webhooks:
            return ValidationResult(True)
        
        # Validate resource with each webhook
        for webhook in webhooks:
            result = self._call_webhook(webhook, resource)
            
            # If webhook fails and failure policy is Fail, return failure
            if not result.allowed and webhook.failure_policy == "Fail":
                return result
        
        return ValidationResult(True)
    
    def _call_webhook(self, webhook: WebhookConfiguration, resource: Dict[str, Any]) -> ValidationResult:
        """
        Call a webhook to validate a resource.
        
        Args:
            webhook: Webhook configuration
            resource: Resource to validate
            
        Returns:
            ValidationResult object
        """
        try:
            # Prepare request
            url_parts = urllib.parse.urlparse(webhook.url)
            
            # Create SSL context if needed
            ssl_context = None
            if url_parts.scheme == 'https':
                ssl_context = self._get_ssl_context(webhook.ca_bundle)
            
            # Create connection
            if url_parts.scheme == 'https':
                conn = http.client.HTTPSConnection(
                    url_parts.netloc,
                    timeout=webhook.timeout_seconds,
                    context=ssl_context
                )
            else:
                conn = http.client.HTTPConnection(
                    url_parts.netloc,
                    timeout=webhook.timeout_seconds
                )
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Prepare body
            body = {
                "kind": "AdmissionReview",
                "apiVersion": "v1",
                "request": {
                    "uid": str(time.time()),
                    "kind": {
                        "kind": resource.get("kind", ""),
                        "apiVersion": resource.get("apiVersion", "v1")
                    },
                    "resource": {
                        "group": "",
                        "version": resource.get("apiVersion", "v1").split("/")[-1],
                        "resource": resource.get("kind", "").lower() + "s"
                    },
                    "namespace": resource.get("metadata", {}).get("namespace", "default"),
                    "operation": "CREATE",
                    "object": resource
                }
            }
            
            # Send request
            conn.request(
                'POST',
                url_parts.path + (f"?{url_parts.query}" if url_parts.query else ""),
                json.dumps(body),
                headers
            )
            
            # Get response
            response = conn.getresponse()
            response_data = response.read().decode('utf-8')
            
            # Parse response
            if response.status != 200:
                logger.error(f"Webhook {webhook.name} returned status {response.status}: {response_data}")
                
                if webhook.failure_policy == "Fail":
                    return ValidationResult(
                        False,
                        f"Webhook {webhook.name} failed with status {response.status}"
                    )
                else:
                    return ValidationResult(True)
            
            # Parse response data
            try:
                response_json = json.loads(response_data)
                
                response_data = response_json.get("response", {})
                allowed = response_data.get("allowed", True)
                reason = response_data.get("status", {}).get("message", "")
                
                return ValidationResult(allowed, reason)
            except Exception as e:
                logger.error(f"Failed to parse webhook response: {e}")
                
                if webhook.failure_policy == "Fail":
                    return ValidationResult(
                        False,
                        f"Failed to parse webhook {webhook.name} response: {e}"
                    )
                else:
                    return ValidationResult(True)
        except Exception as e:
            logger.error(f"Failed to call webhook {webhook.name}: {e}")
            
            if webhook.failure_policy == "Fail":
                return ValidationResult(
                    False,
                    f"Failed to call webhook {webhook.name}: {e}"
                )
            else:
                return ValidationResult(True)
    
    def _get_ssl_context(self, ca_bundle: Optional[str]) -> ssl.SSLContext:
        """
        Get an SSL context for HTTPS connections.
        
        Args:
            ca_bundle: CA bundle for TLS verification (base64 encoded)
            
        Returns:
            SSL context
        """
        # Use cached context if available
        if self._ssl_context:
            return self._ssl_context
        
        # Create a new context
        context = ssl.create_default_context()
        
        # If CA bundle is provided, load it
        if ca_bundle:
            import base64
            import tempfile
            
            # Decode CA bundle
            ca_data = base64.b64decode(ca_bundle)
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(ca_data)
                ca_file = f.name
            
            # Load CA file
            context.load_verify_locations(ca_file)
            
            # Clean up
            os.unlink(ca_file)
        
        # Cache context
        self._ssl_context = context
        
        return context
    
    @staticmethod
    def instance() -> 'AdmissionWebhookManager':
        """
        Get the singleton instance.
        
        Returns:
            AdmissionWebhookManager instance
        """
        return AdmissionWebhookManager()


def get_webhook_manager() -> AdmissionWebhookManager:
    """
    Get the webhook manager instance.
    
    Returns:
        AdmissionWebhookManager instance
    """
    return AdmissionWebhookManager.instance()


def register_webhook(name: str, url: str, timeout_seconds: int = 10,
                   ca_bundle: Optional[str] = None,
                   failure_policy: str = "Fail",
                   resource_kinds: Optional[List[str]] = None,
                   enabled: bool = True) -> bool:
    """
    Register a webhook.
    
    Args:
        name: Webhook name
        url: Webhook URL
        timeout_seconds: Webhook timeout in seconds
        ca_bundle: CA bundle for TLS verification (base64 encoded)
        failure_policy: Policy for handling webhook failures (Fail or Ignore)
        resource_kinds: Resource kinds this webhook applies to
        enabled: Whether the webhook is enabled
        
    Returns:
        bool: Success or failure
    """
    manager = AdmissionWebhookManager.instance()
    
    webhook = WebhookConfiguration(
        name=name,
        url=url,
        timeout_seconds=timeout_seconds,
        ca_bundle=ca_bundle,
        failure_policy=failure_policy,
        resource_kinds=resource_kinds,
        enabled=enabled
    )
    
    return manager.register_webhook(webhook)


def unregister_webhook(name: str) -> bool:
    """
    Unregister a webhook.
    
    Args:
        name: Webhook name
        
    Returns:
        bool: Success or failure
    """
    manager = AdmissionWebhookManager.instance()
    return manager.unregister_webhook(name)


def validate_resource_with_webhooks(resource: Dict[str, Any]) -> ValidationResult:
    """
    Validate a resource using webhooks.
    
    Args:
        resource: Resource to validate
        
    Returns:
        ValidationResult object
    """
    manager = AdmissionWebhookManager.instance()
    return manager.validate_resource(resource)
