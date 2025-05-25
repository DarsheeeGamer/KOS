"""
KOS Security Manager

This module provides a centralized manager for all KOS security components,
including FIM, IDS, Network Monitor, Audit, and Security Policy systems.
"""

import os
import sys
import time
import json
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Import KOS security components
from kos.security.fim import FIMManager
from kos.security.ids import IDSManager
from kos.security.network_monitor import NetworkMonitor
from kos.security.audit import AuditSystem
from kos.security.policy import PolicyManager
from kos.security.acl import ACLManager
from kos.security.mac import MACManager
from kos.security.auth import AuthManager
from kos.security.users import UserManager

# Set up logging
logger = logging.getLogger('KOS.security.security_manager')

class SecurityManager:
    """Central manager for KOS security components"""
    
    # Singleton instance
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SecurityManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize the security manager"""
        with self._lock:
            if self._initialized:
                return
            
            # Initialize state
            self._status = {}
            self._components = {}
            self._event_handlers = {}
            self._alert_handlers = []
            
            # Register components
            self._register_components()
            
            # Register policy handlers
            self._register_policy_handlers()
            
            # Register event handlers
            self._register_event_handlers()
            
            # Set initialization flag
            self._initialized = True
            
            logger.info("Security manager initialized")
    
    def _register_components(self):
        """Register security components"""
        self._components = {
            'fim': FIMManager,
            'ids': IDSManager,
            'network_monitor': NetworkMonitor,
            'audit': AuditSystem,
            'policy': PolicyManager,
            'acl': ACLManager,
            'mac': MACManager,
            'auth': AuthManager,
            'users': UserManager
        }
    
    def _register_policy_handlers(self):
        """Register policy handlers for each component"""
        # FIM policy handler
        def fim_policy_handler(rules):
            try:
                # Apply FIM rules
                if 'monitored_paths' in rules:
                    # Clear existing monitored paths
                    FIMManager.clear_monitored_files()
                    
                    # Add monitored paths
                    for path_info in rules['monitored_paths']:
                        path = path_info.get('path')
                        recursive = path_info.get('recursive', False)
                        priority = path_info.get('priority', 'medium')
                        
                        if recursive:
                            FIMManager.add_directory(path, recursive=True)
                        else:
                            FIMManager.add_file(path)
                
                # Set hash algorithm
                if 'hash_algorithm' in rules:
                    FIMManager.set_hash_algorithm(rules['hash_algorithm'])
                
                # Set check interval
                if 'check_interval' in rules:
                    FIMManager.set_check_interval(rules['check_interval'])
                
                return True, "FIM policy applied"
            except Exception as e:
                logger.error(f"Error applying FIM policy: {e}")
                return False, str(e)
        
        # IDS policy handler
        def ids_policy_handler(rules):
            try:
                # Apply IDS rules
                if 'rules' in rules:
                    # Clear existing rules
                    IDSManager.clear_rules()
                    
                    # Add rules
                    for rule_info in rules['rules']:
                        name = rule_info.get('name')
                        pattern = rule_info.get('pattern')
                        severity = rule_info.get('severity', 'medium')
                        
                        IDSManager.add_rule(name, pattern, severity=severity)
                
                # Set scan interval
                if 'scan_interval' in rules:
                    IDSManager.set_scan_interval(rules['scan_interval'])
                
                return True, "IDS policy applied"
            except Exception as e:
                logger.error(f"Error applying IDS policy: {e}")
                return False, str(e)
        
        # Network monitor policy handler
        def network_monitor_policy_handler(rules):
            try:
                # Apply network monitor rules
                if 'monitored_ports' in rules:
                    # Update monitored ports
                    NetworkMonitor.set_monitored_ports(rules['monitored_ports'])
                
                # Update blacklisted IPs
                if 'blacklisted_ips' in rules:
                    # Clear existing blacklist
                    NetworkMonitor.clear_blacklist()
                    
                    # Add blacklisted IPs
                    for ip in rules['blacklisted_ips']:
                        NetworkMonitor.add_to_blacklist(ip)
                
                # Set monitor interval
                if 'monitor_interval' in rules:
                    NetworkMonitor.set_monitor_interval(rules['monitor_interval'])
                
                return True, "Network monitor policy applied"
            except Exception as e:
                logger.error(f"Error applying network monitor policy: {e}")
                return False, str(e)
        
        # ACL policy handler
        def acl_policy_handler(rules):
            try:
                # Apply ACL rules
                if 'default_permission' in rules:
                    ACLManager.set_default_permission(rules['default_permission'])
                
                # Apply restricted paths
                if 'restricted_paths' in rules:
                    for path_info in rules['restricted_paths']:
                        path = path_info.get('path')
                        permission = path_info.get('permission')
                        recursive = path_info.get('recursive', False)
                        
                        if path and permission:
                            ACLManager.set_acl_permission(path, permission, recursive=recursive)
                
                return True, "ACL policy applied"
            except Exception as e:
                logger.error(f"Error applying ACL policy: {e}")
                return False, str(e)
        
        # MAC policy handler
        def mac_policy_handler(rules):
            try:
                # Apply MAC rules
                if 'default_context' in rules:
                    MACManager.set_default_context(rules['default_context'])
                
                # Apply contexts
                if 'contexts' in rules:
                    for context_info in rules['contexts']:
                        path = context_info.get('path')
                        context = context_info.get('context')
                        recursive = context_info.get('recursive', False)
                        
                        if path and context:
                            MACManager.set_context(path, context, recursive=recursive)
                
                # Apply transitions
                if 'transitions' in rules:
                    for transition in rules['transitions']:
                        source = transition.get('source')
                        target = transition.get('target')
                        class_name = transition.get('class')
                        permission = transition.get('permission')
                        
                        if source and target and class_name and permission:
                            MACManager.add_policy_rule(source, target, class_name, permission)
                
                return True, "MAC policy applied"
            except Exception as e:
                logger.error(f"Error applying MAC policy: {e}")
                return False, str(e)
        
        # Audit policy handler
        def audit_policy_handler(rules):
            try:
                # Apply audit rules
                if 'enabled' in rules:
                    if rules['enabled']:
                        AuditSystem.enable()
                    else:
                        AuditSystem.disable()
                
                # Apply sync write
                if 'sync_write' in rules:
                    AuditSystem.set_sync_write(rules['sync_write'])
                
                # Apply hash chain
                if 'hash_chain' in rules:
                    AuditSystem.set_hash_chain(rules['hash_chain'])
                
                return True, "Audit policy applied"
            except Exception as e:
                logger.error(f"Error applying audit policy: {e}")
                return False, str(e)
        
        # Register policy handlers
        PolicyManager.register_handler('fim', fim_policy_handler)
        PolicyManager.register_handler('ids', ids_policy_handler)
        PolicyManager.register_handler('network_monitor', network_monitor_policy_handler)
        PolicyManager.register_handler('acl', acl_policy_handler)
        PolicyManager.register_handler('mac', mac_policy_handler)
        PolicyManager.register_handler('audit', audit_policy_handler)
    
    def _register_event_handlers(self):
        """Register event handlers for security components"""
        # FIM event handler
        def fim_event_handler(event_type, file_path, details):
            # Log to audit system
            AuditSystem.add_event(
                category='file_access',
                event_type=f'fim_{event_type}',
                user='system',
                source='fim',
                details={
                    'path': file_path,
                    'details': details
                },
                severity=8 if event_type == 'integrity_violation' else 3,
                outcome='failure' if event_type == 'integrity_violation' else 'success'
            )
            
            # Process alert if necessary
            if event_type == 'integrity_violation':
                self._process_alert('fim', 'integrity_violation', {
                    'path': file_path,
                    'details': details
                }, severity=8)
        
        # IDS event handler
        def ids_event_handler(rule_name, event_data, severity):
            # Map severity string to number
            severity_map = {
                'low': 3,
                'medium': 5,
                'high': 8,
                'critical': 10
            }
            severity_num = severity_map.get(severity, 5)
            
            # Log to audit system
            AuditSystem.add_event(
                category='security',
                event_type='ids_event',
                user='system',
                source='ids',
                details={
                    'rule': rule_name,
                    'data': event_data,
                    'severity': severity
                },
                severity=severity_num,
                outcome='failure'
            )
            
            # Process alert
            self._process_alert('ids', rule_name, {
                'data': event_data,
                'severity': severity
            }, severity=severity_num)
        
        # Network monitor event handler
        def network_monitor_event_handler(event_type, connection_info):
            # Determine severity
            severity = 3
            if event_type == 'suspicious_connection':
                severity = 7
            elif event_type == 'blacklisted_connection':
                severity = 9
            
            # Log to audit system
            AuditSystem.add_event(
                category='network',
                event_type=event_type,
                user='system',
                source='network_monitor',
                details=connection_info,
                severity=severity,
                outcome='failure' if event_type in ['suspicious_connection', 'blacklisted_connection'] else 'success'
            )
            
            # Process alert if necessary
            if event_type in ['suspicious_connection', 'blacklisted_connection']:
                self._process_alert('network_monitor', event_type, connection_info, severity=severity)
        
        # Register event handlers with components
        FIMManager.register_event_handler(fim_event_handler)
        IDSManager.register_event_handler(ids_event_handler)
        NetworkMonitor.register_event_handler(network_monitor_event_handler)
    
    def _process_alert(self, source: str, alert_type: str, details: Dict[str, Any], severity: int = 5) -> None:
        """
        Process a security alert
        
        Args:
            source: Alert source
            alert_type: Alert type
            details: Alert details
            severity: Alert severity (1-10)
        """
        # Create alert object
        alert = {
            'timestamp': time.time(),
            'source': source,
            'type': alert_type,
            'details': details,
            'severity': severity
        }
        
        # Call alert handlers
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    def register_alert_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register an alert handler
        
        Args:
            handler: Alert handler function
        """
        self._alert_handlers.append(handler)
    
    def get_security_status(self) -> Dict[str, Any]:
        """
        Get the status of all security components
        
        Returns:
            Dictionary of component statuses
        """
        status = {}
        
        # Get FIM status
        status['fim'] = {
            'enabled': FIMManager.is_enabled(),
            'monitored_files': len(FIMManager.get_monitored_files()),
            'check_interval': FIMManager.get_check_interval(),
            'hash_algorithm': FIMManager.get_hash_algorithm(),
            'alerts': len(FIMManager.get_alerts())
        }
        
        # Get IDS status
        status['ids'] = {
            'enabled': IDSManager.is_enabled(),
            'rules_count': len(IDSManager.get_rules()),
            'events_count': len(IDSManager.get_events()),
            'scan_interval': IDSManager.get_scan_interval()
        }
        
        # Get network monitor status
        status['network_monitor'] = {
            'enabled': NetworkMonitor.is_enabled(),
            'monitored_ports': NetworkMonitor.get_monitored_ports(),
            'blacklist_count': len(NetworkMonitor.get_blacklist()),
            'whitelist_count': len(NetworkMonitor.get_whitelist()),
            'connections_count': len(NetworkMonitor.get_connections())
        }
        
        # Get audit status
        status['audit'] = {
            'enabled': AuditSystem._audit_config['enabled'],
            'hash_chain': AuditSystem._audit_config['hash_chain'],
            'sync_write': AuditSystem._audit_config['sync_write'],
            'events_count': len(AuditSystem._audit_events)
        }
        
        # Get policy status
        active_policy = PolicyManager.get_active_policy()
        status['policy'] = {
            'active_policy': active_policy.name if active_policy else None,
            'policies_count': len(PolicyManager.list_policies())
        }
        
        return status
    
    def enable_all_components(self) -> Dict[str, Tuple[bool, str]]:
        """
        Enable all security components
        
        Returns:
            Dictionary of component names to (success, message) tuples
        """
        results = {}
        
        # Enable FIM
        try:
            FIMManager.enable()
            results['fim'] = (True, "FIM enabled")
        except Exception as e:
            results['fim'] = (False, str(e))
        
        # Enable IDS
        try:
            IDSManager.enable()
            results['ids'] = (True, "IDS enabled")
        except Exception as e:
            results['ids'] = (False, str(e))
        
        # Enable network monitor
        try:
            NetworkMonitor.start_monitoring()
            results['network_monitor'] = (True, "Network monitor enabled")
        except Exception as e:
            results['network_monitor'] = (False, str(e))
        
        # Enable audit
        try:
            AuditSystem.enable()
            results['audit'] = (True, "Audit enabled")
        except Exception as e:
            results['audit'] = (False, str(e))
        
        return results
    
    def disable_all_components(self) -> Dict[str, Tuple[bool, str]]:
        """
        Disable all security components
        
        Returns:
            Dictionary of component names to (success, message) tuples
        """
        results = {}
        
        # Disable FIM
        try:
            FIMManager.disable()
            results['fim'] = (True, "FIM disabled")
        except Exception as e:
            results['fim'] = (False, str(e))
        
        # Disable IDS
        try:
            IDSManager.disable()
            results['ids'] = (True, "IDS disabled")
        except Exception as e:
            results['ids'] = (False, str(e))
        
        # Disable network monitor
        try:
            NetworkMonitor.stop_monitoring()
            results['network_monitor'] = (True, "Network monitor disabled")
        except Exception as e:
            results['network_monitor'] = (False, str(e))
        
        # Disable audit
        try:
            AuditSystem.disable()
            results['audit'] = (True, "Audit disabled")
        except Exception as e:
            results['audit'] = (False, str(e))
        
        return results
    
    def apply_active_policy(self) -> Tuple[bool, str]:
        """
        Apply the active security policy
        
        Returns:
            Tuple of (success, message)
        """
        # Get active policy
        policy = PolicyManager.get_active_policy()
        
        if not policy:
            return False, "No active policy"
        
        # Apply policy
        return PolicyManager.apply_policy(policy)
    
    def handle_security_event(self, event_type: str, source: str, details: Dict[str, Any]) -> None:
        """
        Handle a security event
        
        Args:
            event_type: Event type
            source: Event source
            details: Event details
        """
        # Determine severity based on event type
        severity_map = {
            'authentication_failure': 7,
            'authorization_failure': 6,
            'file_access_denied': 5,
            'file_permission_change': 4,
            'user_creation': 3,
            'user_deletion': 3,
            'user_modification': 3,
            'group_modification': 3,
            'system_startup': 2,
            'system_shutdown': 2,
            'policy_change': 4,
            'security_service_start': 2,
            'security_service_stop': 3
        }
        severity = severity_map.get(event_type, 3)
        
        # Log to audit system
        AuditSystem.add_event(
            category='security',
            event_type=event_type,
            user=details.get('user', 'system'),
            source=source,
            details=details,
            severity=severity,
            outcome=details.get('outcome', 'success')
        )
        
        # Process alert if necessary
        if event_type in ['authentication_failure', 'authorization_failure', 'file_access_denied'] or severity >= 6:
            self._process_alert(source, event_type, details, severity=severity)


# Initialize on module load
security_manager = SecurityManager()


def console_alert_handler(alert):
    """
    Print high-severity alerts to console
    
    Args:
        alert: Alert object
    """
    if alert['severity'] >= 7:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))
        print(f"HIGH SEVERITY SECURITY ALERT: {timestamp} [{alert['source']}] {alert['type']} - {alert['details']}")


# Register alert handlers
security_manager.register_alert_handler(console_alert_handler)
