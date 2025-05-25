"""
KOS File Integrity Monitoring (FIM) System

This module provides file integrity monitoring capabilities,
allowing detection of unauthorized changes to critical system files.
"""

import os
import sys
import time
import logging
import json
import threading
import hashlib
import base64
import re
from typing import Dict, List, Any, Optional, Union, Tuple, Set

# Set up logging
logger = logging.getLogger('KOS.security.fim')

# Lock for FIM operations
_fim_lock = threading.RLock()

# FIM database
_fim_database = {}

# FIM configuration
_fim_config = {
    'monitoring_enabled': False,
    'alert_on_changes': True,
    'check_interval': 3600,  # Default: check every hour
    'hash_algorithm': 'sha256',
    'ignore_patterns': [r'.*\.log$', r'.*\.tmp$', r'.*\.swp$']
}

# FIM background thread
_fim_thread = None
_fim_thread_stop = False


class FileRecord:
    """Class representing a file integrity record"""
    
    def __init__(self, path: str, hash_value: str, size: int, mode: int, 
                 mtime: float, owner: str, group: str, last_checked: float):
        """
        Initialize file record
        
        Args:
            path: File path
            hash_value: File hash
            size: File size in bytes
            mode: File permission mode
            mtime: File modification time
            owner: File owner
            group: File group
            last_checked: Last check time
        """
        self.path = path
        self.hash_value = hash_value
        self.size = size
        self.mode = mode
        self.mtime = mtime
        self.owner = owner
        self.group = group
        self.last_checked = last_checked
        self.alerts = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'path': self.path,
            'hash_value': self.hash_value,
            'size': self.size,
            'mode': self.mode,
            'mtime': self.mtime,
            'owner': self.owner,
            'group': self.group,
            'last_checked': self.last_checked,
            'alerts': self.alerts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileRecord':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            FileRecord instance
        """
        record = cls(
            path=data.get('path', ''),
            hash_value=data.get('hash_value', ''),
            size=data.get('size', 0),
            mode=data.get('mode', 0),
            mtime=data.get('mtime', 0.0),
            owner=data.get('owner', ''),
            group=data.get('group', ''),
            last_checked=data.get('last_checked', 0.0)
        )
        
        record.alerts = data.get('alerts', [])
        
        return record


class Alert:
    """Class representing a file integrity alert"""
    
    def __init__(self, path: str, timestamp: float, alert_type: str, 
                 old_value: Optional[str], new_value: Optional[str], details: str):
        """
        Initialize alert
        
        Args:
            path: File path
            timestamp: Alert timestamp
            alert_type: Alert type
            old_value: Old value
            new_value: New value
            details: Alert details
        """
        self.path = path
        self.timestamp = timestamp
        self.alert_type = alert_type
        self.old_value = old_value
        self.new_value = new_value
        self.details = details
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'path': self.path,
            'timestamp': self.timestamp,
            'alert_type': self.alert_type,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'details': self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            Alert instance
        """
        return cls(
            path=data.get('path', ''),
            timestamp=data.get('timestamp', 0.0),
            alert_type=data.get('alert_type', ''),
            old_value=data.get('old_value'),
            new_value=data.get('new_value'),
            details=data.get('details', '')
        )


class FIMManager:
    """Manager for file integrity monitoring operations"""
    
    @classmethod
    def calculate_file_hash(cls, file_path: str, algorithm: str = 'sha256') -> Optional[str]:
        """
        Calculate file hash
        
        Args:
            file_path: File path
            algorithm: Hash algorithm
        
        Returns:
            File hash or None if error
        """
        try:
            hash_obj = None
            
            if algorithm == 'md5':
                hash_obj = hashlib.md5()
            elif algorithm == 'sha1':
                hash_obj = hashlib.sha1()
            elif algorithm == 'sha256':
                hash_obj = hashlib.sha256()
            elif algorithm == 'sha512':
                hash_obj = hashlib.sha512()
            else:
                hash_obj = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    @classmethod
    def add_file(cls, file_path: str) -> Tuple[bool, str]:
        """
        Add a file to FIM database
        
        Args:
            file_path: File path
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            # Check if file exists
            if not os.path.isfile(file_path):
                return False, f"File {file_path} not found"
            
            # Check if file is already monitored
            if file_path in _fim_database:
                return False, f"File {file_path} is already monitored"
            
            # Check if file matches ignore patterns
            for pattern in _fim_config['ignore_patterns']:
                if re.match(pattern, file_path):
                    return False, f"File {file_path} matches ignore pattern: {pattern}"
            
            try:
                # Get file info
                stat_info = os.stat(file_path)
                
                # Calculate file hash
                hash_value = cls.calculate_file_hash(file_path, _fim_config['hash_algorithm'])
                if hash_value is None:
                    return False, f"Error calculating hash for {file_path}"
                
                # Get owner and group
                try:
                    # In a full implementation, this would use pwd and grp modules
                    # For now, just use IDs
                    owner = str(stat_info.st_uid)
                    group = str(stat_info.st_gid)
                except:
                    owner = str(stat_info.st_uid)
                    group = str(stat_info.st_gid)
                
                # Create file record
                record = FileRecord(
                    path=file_path,
                    hash_value=hash_value,
                    size=stat_info.st_size,
                    mode=stat_info.st_mode,
                    mtime=stat_info.st_mtime,
                    owner=owner,
                    group=group,
                    last_checked=time.time()
                )
                
                # Add to database
                _fim_database[file_path] = record
                
                logger.info(f"Added file {file_path} to FIM database")
                
                return True, f"File {file_path} added to FIM database"
            except Exception as e:
                logger.error(f"Error adding file {file_path} to FIM database: {e}")
                return False, str(e)
    
    @classmethod
    def add_directory(cls, dir_path: str, recursive: bool = True) -> Tuple[bool, List[str]]:
        """
        Add a directory to FIM database
        
        Args:
            dir_path: Directory path
            recursive: Add files recursively
        
        Returns:
            (success, list of added files)
        """
        with _fim_lock:
            # Check if directory exists
            if not os.path.isdir(dir_path):
                return False, [f"Directory {dir_path} not found"]
            
            added_files = []
            failed_files = []
            
            try:
                # Get files to add
                if recursive:
                    for root, dirs, files in os.walk(dir_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            success, message = cls.add_file(file_path)
                            if success:
                                added_files.append(file_path)
                            else:
                                failed_files.append(f"{file_path}: {message}")
                else:
                    for item in os.listdir(dir_path):
                        item_path = os.path.join(dir_path, item)
                        if os.path.isfile(item_path):
                            success, message = cls.add_file(item_path)
                            if success:
                                added_files.append(item_path)
                            else:
                                failed_files.append(f"{item_path}: {message}")
                
                if not added_files and failed_files:
                    return False, failed_files
                
                return True, added_files
            except Exception as e:
                logger.error(f"Error adding directory {dir_path} to FIM database: {e}")
                return False, [str(e)]
    
    @classmethod
    def remove_file(cls, file_path: str) -> Tuple[bool, str]:
        """
        Remove a file from FIM database
        
        Args:
            file_path: File path
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            # Check if file is monitored
            if file_path not in _fim_database:
                return False, f"File {file_path} is not monitored"
            
            # Remove from database
            del _fim_database[file_path]
            
            logger.info(f"Removed file {file_path} from FIM database")
            
            return True, f"File {file_path} removed from FIM database"
    
    @classmethod
    def remove_directory(cls, dir_path: str) -> Tuple[bool, List[str]]:
        """
        Remove a directory from FIM database
        
        Args:
            dir_path: Directory path
        
        Returns:
            (success, list of removed files)
        """
        with _fim_lock:
            removed_files = []
            
            # Find files to remove
            for file_path in list(_fim_database.keys()):
                if file_path.startswith(dir_path):
                    del _fim_database[file_path]
                    removed_files.append(file_path)
            
            if not removed_files:
                return False, [f"No monitored files found in {dir_path}"]
            
            logger.info(f"Removed {len(removed_files)} files from FIM database")
            
            return True, removed_files
    
    @classmethod
    def check_file(cls, file_path: str) -> Tuple[bool, Optional[List[Dict[str, Any]]]]:
        """
        Check file integrity
        
        Args:
            file_path: File path
        
        Returns:
            (integrity_intact, alerts)
        """
        with _fim_lock:
            # Check if file is monitored
            if file_path not in _fim_database:
                return False, None
            
            record = _fim_database[file_path]
            alerts = []
            
            try:
                # Check if file exists
                if not os.path.isfile(file_path):
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='missing',
                        old_value=None,
                        new_value=None,
                        details='File is missing'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} is missing")
                    
                    return False, alerts
                
                # Get file info
                stat_info = os.stat(file_path)
                
                # Check file size
                if stat_info.st_size != record.size:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='size',
                        old_value=str(record.size),
                        new_value=str(stat_info.st_size),
                        details='File size changed'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} size changed from {record.size} to {stat_info.st_size}")
                
                # Check file permissions
                if stat_info.st_mode != record.mode:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='permissions',
                        old_value=str(record.mode),
                        new_value=str(stat_info.st_mode),
                        details='File permissions changed'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} permissions changed")
                
                # Check file ownership
                current_owner = str(stat_info.st_uid)
                current_group = str(stat_info.st_gid)
                
                if current_owner != record.owner:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='owner',
                        old_value=record.owner,
                        new_value=current_owner,
                        details='File owner changed'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} owner changed from {record.owner} to {current_owner}")
                
                if current_group != record.group:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='group',
                        old_value=record.group,
                        new_value=current_group,
                        details='File group changed'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} group changed from {record.group} to {current_group}")
                
                # Calculate file hash
                new_hash = cls.calculate_file_hash(file_path, _fim_config['hash_algorithm'])
                if new_hash is None:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='hash_error',
                        old_value=record.hash_value,
                        new_value=None,
                        details='Error calculating file hash'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: Error calculating hash for {file_path}")
                    
                    return False, alerts
                
                # Check file hash
                if new_hash != record.hash_value:
                    alert = Alert(
                        path=file_path,
                        timestamp=time.time(),
                        alert_type='content',
                        old_value=record.hash_value,
                        new_value=new_hash,
                        details='File content changed'
                    )
                    alerts.append(alert.to_dict())
                    
                    if _fim_config['alert_on_changes']:
                        logger.warning(f"FIM Alert: File {file_path} content changed")
                
                # Update record
                record.hash_value = new_hash
                record.size = stat_info.st_size
                record.mode = stat_info.st_mode
                record.mtime = stat_info.st_mtime
                record.owner = current_owner
                record.group = current_group
                record.last_checked = time.time()
                
                if alerts:
                    record.alerts.extend([alert for alert in alerts])
                    return False, alerts
                
                return True, None
            except Exception as e:
                logger.error(f"Error checking file {file_path}: {e}")
                
                alert = Alert(
                    path=file_path,
                    timestamp=time.time(),
                    alert_type='error',
                    old_value=None,
                    new_value=None,
                    details=str(e)
                )
                alerts.append(alert.to_dict())
                
                return False, alerts
    
    @classmethod
    def check_all_files(cls) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check integrity of all monitored files
        
        Returns:
            Dictionary of file paths and alerts
        """
        with _fim_lock:
            results = {}
            
            for file_path in list(_fim_database.keys()):
                integrity_intact, alerts = cls.check_file(file_path)
                
                if not integrity_intact and alerts:
                    results[file_path] = alerts
            
            return results
    
    @classmethod
    def get_file_record(cls, file_path: str) -> Optional[FileRecord]:
        """
        Get file record
        
        Args:
            file_path: File path
        
        Returns:
            FileRecord or None if not found
        """
        with _fim_lock:
            return _fim_database.get(file_path)
    
    @classmethod
    def list_monitored_files(cls) -> List[str]:
        """
        List monitored files
        
        Returns:
            List of file paths
        """
        with _fim_lock:
            return list(_fim_database.keys())
    
    @classmethod
    def save_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Save FIM database to file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            try:
                data = {
                    'config': _fim_config,
                    'database': {}
                }
                
                for file_path, record in _fim_database.items():
                    data['database'][file_path] = record.to_dict()
                
                with open(db_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"FIM database saved to {db_file}"
            except Exception as e:
                logger.error(f"Error saving FIM database: {e}")
                return False, str(e)
    
    @classmethod
    def load_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Load FIM database from file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            try:
                if not os.path.exists(db_file):
                    return False, f"Database file {db_file} not found"
                
                with open(db_file, 'r') as f:
                    data = json.load(f)
                
                if 'config' in data:
                    _fim_config.update(data['config'])
                
                _fim_database.clear()
                
                if 'database' in data:
                    for file_path, record_data in data['database'].items():
                        _fim_database[file_path] = FileRecord.from_dict(record_data)
                
                return True, "FIM database loaded"
            except Exception as e:
                logger.error(f"Error loading FIM database: {e}")
                return False, str(e)
    
    @classmethod
    def start_monitoring(cls) -> Tuple[bool, str]:
        """
        Start automatic monitoring
        
        Returns:
            (success, message)
        """
        global _fim_thread, _fim_thread_stop
        
        with _fim_lock:
            # Check if monitoring is already enabled
            if _fim_config['monitoring_enabled']:
                return True, "Monitoring is already enabled"
            
            # Enable monitoring
            _fim_config['monitoring_enabled'] = True
            _fim_thread_stop = False
            
            # Start monitoring thread
            if _fim_thread is None or not _fim_thread.is_alive():
                _fim_thread = threading.Thread(target=cls._monitoring_thread)
                _fim_thread.daemon = True
                _fim_thread.start()
            
            logger.info("FIM monitoring started")
            
            return True, "FIM monitoring started"
    
    @classmethod
    def stop_monitoring(cls) -> Tuple[bool, str]:
        """
        Stop automatic monitoring
        
        Returns:
            (success, message)
        """
        global _fim_thread, _fim_thread_stop
        
        with _fim_lock:
            # Check if monitoring is already disabled
            if not _fim_config['monitoring_enabled']:
                return True, "Monitoring is already disabled"
            
            # Disable monitoring
            _fim_config['monitoring_enabled'] = False
            _fim_thread_stop = True
            
            logger.info("FIM monitoring stopped")
            
            return True, "FIM monitoring stopped"
    
    @classmethod
    def set_check_interval(cls, interval: int) -> Tuple[bool, str]:
        """
        Set check interval
        
        Args:
            interval: Check interval in seconds
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            if interval < 1:
                return False, "Check interval must be at least 1 second"
            
            _fim_config['check_interval'] = interval
            
            logger.info(f"FIM check interval set to {interval} seconds")
            
            return True, f"Check interval set to {interval} seconds"
    
    @classmethod
    def set_hash_algorithm(cls, algorithm: str) -> Tuple[bool, str]:
        """
        Set hash algorithm
        
        Args:
            algorithm: Hash algorithm
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            valid_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
            
            if algorithm not in valid_algorithms:
                return False, f"Invalid algorithm: {algorithm}. Valid algorithms: {', '.join(valid_algorithms)}"
            
            _fim_config['hash_algorithm'] = algorithm
            
            logger.info(f"FIM hash algorithm set to {algorithm}")
            
            return True, f"Hash algorithm set to {algorithm}"
    
    @classmethod
    def add_ignore_pattern(cls, pattern: str) -> Tuple[bool, str]:
        """
        Add ignore pattern
        
        Args:
            pattern: Ignore pattern
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            try:
                # Test pattern
                re.compile(pattern)
            except re.error:
                return False, f"Invalid regular expression: {pattern}"
            
            if pattern in _fim_config['ignore_patterns']:
                return False, f"Pattern {pattern} is already in ignore list"
            
            _fim_config['ignore_patterns'].append(pattern)
            
            logger.info(f"Added ignore pattern: {pattern}")
            
            return True, f"Ignore pattern added: {pattern}"
    
    @classmethod
    def remove_ignore_pattern(cls, pattern: str) -> Tuple[bool, str]:
        """
        Remove ignore pattern
        
        Args:
            pattern: Ignore pattern
        
        Returns:
            (success, message)
        """
        with _fim_lock:
            if pattern not in _fim_config['ignore_patterns']:
                return False, f"Pattern {pattern} is not in ignore list"
            
            _fim_config['ignore_patterns'].remove(pattern)
            
            logger.info(f"Removed ignore pattern: {pattern}")
            
            return True, f"Ignore pattern removed: {pattern}"
    
    @classmethod
    def list_ignore_patterns(cls) -> List[str]:
        """
        List ignore patterns
        
        Returns:
            List of ignore patterns
        """
        with _fim_lock:
            return _fim_config['ignore_patterns'].copy()
    
    @classmethod
    def _monitoring_thread(cls) -> None:
        """Monitoring thread function"""
        logger.info("FIM monitoring thread started")
        
        while not _fim_thread_stop:
            try:
                if _fim_config['monitoring_enabled']:
                    logger.debug("Checking file integrity")
                    cls.check_all_files()
            except Exception as e:
                logger.error(f"Error in FIM monitoring thread: {e}")
            
            # Sleep for check interval
            for _ in range(_fim_config['check_interval']):
                if _fim_thread_stop:
                    break
                time.sleep(1)
        
        logger.info("FIM monitoring thread stopped")


def initialize():
    """Initialize FIM system"""
    logger.info("Initializing FIM system")
    
    # Create FIM directory
    fim_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(fim_dir, exist_ok=True)
    
    # Load database if it exists
    db_file = os.path.join(fim_dir, 'fim.json')
    if os.path.exists(db_file):
        FIMManager.load_database(db_file)
    
    logger.info("FIM system initialized")


# Initialize on module load
initialize()
