"""
KOS User Quota Management System

This module provides disk and resource quota management for KOS users,
similar to the Unix quota system.
"""

import os
import sys
import time
import json
import logging
import threading
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager, GroupManager
from kos.security.auth import get_current_uid, get_current_gid

# Set up logging
logger = logging.getLogger('KOS.security.quotas')

# Quota locks
_quota_lock = threading.RLock()

# Default quota values
DEFAULT_BLOCK_SOFT_LIMIT = 1024 * 1024  # 1GB (in KB)
DEFAULT_BLOCK_HARD_LIMIT = 1024 * 1024 * 2  # 2GB (in KB)
DEFAULT_INODE_SOFT_LIMIT = 1000000  # 1 million inodes
DEFAULT_INODE_HARD_LIMIT = 2000000  # 2 million inodes

# Grace periods
DEFAULT_BLOCK_GRACE = 7 * 86400  # 7 days in seconds
DEFAULT_INODE_GRACE = 7 * 86400  # 7 days in seconds


class QuotaLimits:
    """Class representing quota limits for a user or group"""
    
    def __init__(self, blocks_soft: int = DEFAULT_BLOCK_SOFT_LIMIT,
                 blocks_hard: int = DEFAULT_BLOCK_HARD_LIMIT,
                 inodes_soft: int = DEFAULT_INODE_SOFT_LIMIT,
                 inodes_hard: int = DEFAULT_INODE_HARD_LIMIT,
                 blocks_grace: int = DEFAULT_BLOCK_GRACE,
                 inodes_grace: int = DEFAULT_INODE_GRACE):
        """
        Initialize quota limits
        
        Args:
            blocks_soft: Soft limit for disk blocks (KB)
            blocks_hard: Hard limit for disk blocks (KB)
            inodes_soft: Soft limit for inodes
            inodes_hard: Hard limit for inodes
            blocks_grace: Grace period for blocks (seconds)
            inodes_grace: Grace period for inodes (seconds)
        """
        self.blocks_soft = blocks_soft
        self.blocks_hard = blocks_hard
        self.inodes_soft = inodes_soft
        self.inodes_hard = inodes_hard
        self.blocks_grace = blocks_grace
        self.inodes_grace = inodes_grace
        
        # Grace time expiration (set when soft limit is exceeded)
        self.blocks_grace_expires = None
        self.inodes_grace_expires = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "blocks_soft": self.blocks_soft,
            "blocks_hard": self.blocks_hard,
            "inodes_soft": self.inodes_soft,
            "inodes_hard": self.inodes_hard,
            "blocks_grace": self.blocks_grace,
            "inodes_grace": self.inodes_grace,
            "blocks_grace_expires": self.blocks_grace_expires,
            "inodes_grace_expires": self.inodes_grace_expires
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotaLimits':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            QuotaLimits instance
        """
        limits = cls(
            blocks_soft=data.get("blocks_soft", DEFAULT_BLOCK_SOFT_LIMIT),
            blocks_hard=data.get("blocks_hard", DEFAULT_BLOCK_HARD_LIMIT),
            inodes_soft=data.get("inodes_soft", DEFAULT_INODE_SOFT_LIMIT),
            inodes_hard=data.get("inodes_hard", DEFAULT_INODE_HARD_LIMIT),
            blocks_grace=data.get("blocks_grace", DEFAULT_BLOCK_GRACE),
            inodes_grace=data.get("inodes_grace", DEFAULT_INODE_GRACE)
        )
        limits.blocks_grace_expires = data.get("blocks_grace_expires")
        limits.inodes_grace_expires = data.get("inodes_grace_expires")
        return limits


class QuotaUsage:
    """Class representing quota usage for a user or group"""
    
    def __init__(self, blocks: int = 0, inodes: int = 0):
        """
        Initialize quota usage
        
        Args:
            blocks: Used disk blocks (KB)
            inodes: Used inodes
        """
        self.blocks = blocks
        self.inodes = inodes
        self.last_updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "blocks": self.blocks,
            "inodes": self.inodes,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotaUsage':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            QuotaUsage instance
        """
        usage = cls(
            blocks=data.get("blocks", 0),
            inodes=data.get("inodes", 0)
        )
        usage.last_updated = data.get("last_updated", time.time())
        return usage


class QuotaManager:
    """Manager for quota operations"""
    
    # Quota dictionaries (maps user/group ID to quota info)
    _user_quotas: Dict[int, QuotaLimits] = {}
    _group_quotas: Dict[int, QuotaLimits] = {}
    _user_usage: Dict[int, QuotaUsage] = {}
    _group_usage: Dict[int, QuotaUsage] = {}
    
    @classmethod
    def set_user_quota(cls, uid: int, limits: QuotaLimits) -> Tuple[bool, str]:
        """
        Set quota limits for a user
        
        Args:
            uid: User ID
            limits: Quota limits
        
        Returns:
            (success, message)
        """
        with _quota_lock:
            # Verify user exists
            user = UserManager.get_user_by_uid(uid)
            if not user:
                return False, f"No such user ID: {uid}"
            
            cls._user_quotas[uid] = limits
            return True, f"Quota set for user {user.username}"
    
    @classmethod
    def set_group_quota(cls, gid: int, limits: QuotaLimits) -> Tuple[bool, str]:
        """
        Set quota limits for a group
        
        Args:
            gid: Group ID
            limits: Quota limits
        
        Returns:
            (success, message)
        """
        with _quota_lock:
            # Verify group exists
            group = GroupManager.get_group_by_gid(gid)
            if not group:
                return False, f"No such group ID: {gid}"
            
            cls._group_quotas[gid] = limits
            return True, f"Quota set for group {group.name}"
    
    @classmethod
    def get_user_quota(cls, uid: int) -> Optional[QuotaLimits]:
        """
        Get quota limits for a user
        
        Args:
            uid: User ID
        
        Returns:
            Quota limits or None
        """
        with _quota_lock:
            return cls._user_quotas.get(uid)
    
    @classmethod
    def get_group_quota(cls, gid: int) -> Optional[QuotaLimits]:
        """
        Get quota limits for a group
        
        Args:
            gid: Group ID
        
        Returns:
            Quota limits or None
        """
        with _quota_lock:
            return cls._group_quotas.get(gid)
    
    @classmethod
    def get_user_usage(cls, uid: int) -> QuotaUsage:
        """
        Get quota usage for a user
        
        Args:
            uid: User ID
        
        Returns:
            Quota usage
        """
        with _quota_lock:
            if uid not in cls._user_usage:
                cls._user_usage[uid] = QuotaUsage()
            return cls._user_usage[uid]
    
    @classmethod
    def get_group_usage(cls, gid: int) -> QuotaUsage:
        """
        Get quota usage for a group
        
        Args:
            gid: Group ID
        
        Returns:
            Quota usage
        """
        with _quota_lock:
            if gid not in cls._group_usage:
                cls._group_usage[gid] = QuotaUsage()
            return cls._group_usage[gid]
    
    @classmethod
    def update_usage(cls, uid: int, gid: int, blocks_delta: int, inodes_delta: int) -> Tuple[bool, str]:
        """
        Update usage for a user and group
        
        Args:
            uid: User ID
            gid: Group ID
            blocks_delta: Change in blocks used
            inodes_delta: Change in inodes used
        
        Returns:
            (success, message)
        """
        with _quota_lock:
            # Update user usage
            user_usage = cls.get_user_usage(uid)
            user_usage.blocks += blocks_delta
            user_usage.inodes += inodes_delta
            user_usage.last_updated = time.time()
            
            # Update group usage
            group_usage = cls.get_group_usage(gid)
            group_usage.blocks += blocks_delta
            group_usage.inodes += inodes_delta
            group_usage.last_updated = time.time()
            
            # Check if user is exceeding soft limits
            user_limits = cls.get_user_quota(uid)
            if user_limits:
                # Check blocks
                if user_usage.blocks > user_limits.blocks_soft and user_limits.blocks_grace_expires is None:
                    # Set grace period expiration
                    user_limits.blocks_grace_expires = time.time() + user_limits.blocks_grace
                
                # Check inodes
                if user_usage.inodes > user_limits.inodes_soft and user_limits.inodes_grace_expires is None:
                    # Set grace period expiration
                    user_limits.inodes_grace_expires = time.time() + user_limits.inodes_grace
            
            # Check if group is exceeding soft limits
            group_limits = cls.get_group_quota(gid)
            if group_limits:
                # Check blocks
                if group_usage.blocks > group_limits.blocks_soft and group_limits.blocks_grace_expires is None:
                    # Set grace period expiration
                    group_limits.blocks_grace_expires = time.time() + group_limits.blocks_grace
                
                # Check inodes
                if group_usage.inodes > group_limits.inodes_soft and group_limits.inodes_grace_expires is None:
                    # Set grace period expiration
                    group_limits.inodes_grace_expires = time.time() + group_limits.inodes_grace
            
            return True, "Usage updated"
    
    @classmethod
    def check_quota(cls, uid: int, gid: int, blocks_needed: int, inodes_needed: int) -> Tuple[bool, str]:
        """
        Check if operation would exceed quota
        
        Args:
            uid: User ID
            gid: Group ID
            blocks_needed: Additional blocks needed
            inodes_needed: Additional inodes needed
        
        Returns:
            (allowed, message)
        """
        with _quota_lock:
            # Get user quota info
            user_limits = cls.get_user_quota(uid)
            user_usage = cls.get_user_usage(uid)
            
            if user_limits:
                # Check hard limits (always enforced)
                if user_usage.blocks + blocks_needed > user_limits.blocks_hard:
                    return False, "Disk quota exceeded"
                
                if user_usage.inodes + inodes_needed > user_limits.inodes_hard:
                    return False, "File quota exceeded"
                
                # Check soft limits with grace period
                now = time.time()
                
                # Check blocks soft limit
                if user_usage.blocks > user_limits.blocks_soft:
                    if user_limits.blocks_grace_expires and now > user_limits.blocks_grace_expires:
                        return False, "Disk quota exceeded (grace period expired)"
                
                # Check inodes soft limit
                if user_usage.inodes > user_limits.inodes_soft:
                    if user_limits.inodes_grace_expires and now > user_limits.inodes_grace_expires:
                        return False, "File quota exceeded (grace period expired)"
            
            # Get group quota info
            group_limits = cls.get_group_quota(gid)
            group_usage = cls.get_group_usage(gid)
            
            if group_limits:
                # Check hard limits (always enforced)
                if group_usage.blocks + blocks_needed > group_limits.blocks_hard:
                    return False, "Group disk quota exceeded"
                
                if group_usage.inodes + inodes_needed > group_limits.inodes_hard:
                    return False, "Group file quota exceeded"
                
                # Check soft limits with grace period
                now = time.time()
                
                # Check blocks soft limit
                if group_usage.blocks > group_limits.blocks_soft:
                    if group_limits.blocks_grace_expires and now > group_limits.blocks_grace_expires:
                        return False, "Group disk quota exceeded (grace period expired)"
                
                # Check inodes soft limit
                if group_usage.inodes > group_limits.inodes_soft:
                    if group_limits.inodes_grace_expires and now > group_limits.inodes_grace_expires:
                        return False, "Group file quota exceeded (grace period expired)"
            
            return True, "Quota check passed"
    
    @classmethod
    def list_user_quotas(cls) -> List[Tuple[int, QuotaLimits, QuotaUsage]]:
        """
        List all user quotas
        
        Returns:
            List of (uid, limits, usage) tuples
        """
        with _quota_lock:
            result = []
            for uid, limits in cls._user_quotas.items():
                usage = cls.get_user_usage(uid)
                result.append((uid, limits, usage))
            return result
    
    @classmethod
    def list_group_quotas(cls) -> List[Tuple[int, QuotaLimits, QuotaUsage]]:
        """
        List all group quotas
        
        Returns:
            List of (gid, limits, usage) tuples
        """
        with _quota_lock:
            result = []
            for gid, limits in cls._group_quotas.items():
                usage = cls.get_group_usage(gid)
                result.append((gid, limits, usage))
            return result
    
    @classmethod
    def scan_directory(cls, path: str, uid: int = None, gid: int = None) -> Tuple[bool, str, Dict[int, int], Dict[int, int]]:
        """
        Scan directory to calculate usage by user/group
        
        Args:
            path: Directory path
            uid: Filter by user ID
            gid: Filter by group ID
        
        Returns:
            (success, message, user_usage, group_usage)
        """
        try:
            user_blocks = {}  # uid -> blocks
            group_blocks = {}  # gid -> blocks
            user_inodes = {}  # uid -> inodes
            group_inodes = {}  # gid -> inodes
            
            for root, dirs, files in os.walk(path):
                for name in dirs + files:
                    file_path = os.path.join(root, name)
                    try:
                        stat_info = os.stat(file_path)
                        file_uid = stat_info.st_uid
                        file_gid = stat_info.st_gid
                        
                        # Skip if not matching filters
                        if uid is not None and file_uid != uid:
                            continue
                        if gid is not None and file_gid != gid:
                            continue
                        
                        # Calculate size in KB (rounded up)
                        size_kb = (stat_info.st_size + 1023) // 1024
                        
                        # Update user usage
                        if file_uid not in user_blocks:
                            user_blocks[file_uid] = 0
                            user_inodes[file_uid] = 0
                        user_blocks[file_uid] += size_kb
                        user_inodes[file_uid] += 1
                        
                        # Update group usage
                        if file_gid not in group_blocks:
                            group_blocks[file_gid] = 0
                            group_inodes[file_gid] = 0
                        group_blocks[file_gid] += size_kb
                        group_inodes[file_gid] += 1
                    except (FileNotFoundError, PermissionError):
                        continue
            
            # Update stored usage
            for u_id, blocks in user_blocks.items():
                with _quota_lock:
                    usage = cls.get_user_usage(u_id)
                    usage.blocks = blocks
                    usage.inodes = user_inodes[u_id]
                    usage.last_updated = time.time()
            
            for g_id, blocks in group_blocks.items():
                with _quota_lock:
                    usage = cls.get_group_usage(g_id)
                    usage.blocks = blocks
                    usage.inodes = group_inodes[g_id]
                    usage.last_updated = time.time()
            
            return True, "Scan completed", user_blocks, group_blocks
        
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
            return False, str(e), {}, {}
    
    @classmethod
    def save_quotas(cls, quotas_file: str) -> Tuple[bool, str]:
        """
        Save quotas to file
        
        Args:
            quotas_file: File path
        
        Returns:
            (success, message)
        """
        with _quota_lock:
            try:
                data = {
                    "user_quotas": {str(uid): limits.to_dict() for uid, limits in cls._user_quotas.items()},
                    "group_quotas": {str(gid): limits.to_dict() for gid, limits in cls._group_quotas.items()},
                    "user_usage": {str(uid): usage.to_dict() for uid, usage in cls._user_usage.items()},
                    "group_usage": {str(gid): usage.to_dict() for gid, usage in cls._group_usage.items()}
                }
                
                with open(quotas_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, "Quotas saved"
            except Exception as e:
                return False, str(e)
    
    @classmethod
    def load_quotas(cls, quotas_file: str) -> Tuple[bool, str]:
        """
        Load quotas from file
        
        Args:
            quotas_file: File path
        
        Returns:
            (success, message)
        """
        with _quota_lock:
            try:
                if not os.path.exists(quotas_file):
                    return False, "Quotas file not found"
                
                with open(quotas_file, 'r') as f:
                    data = json.load(f)
                
                # Load user quotas
                cls._user_quotas = {}
                for uid_str, limits_data in data.get("user_quotas", {}).items():
                    uid = int(uid_str)
                    cls._user_quotas[uid] = QuotaLimits.from_dict(limits_data)
                
                # Load group quotas
                cls._group_quotas = {}
                for gid_str, limits_data in data.get("group_quotas", {}).items():
                    gid = int(gid_str)
                    cls._group_quotas[gid] = QuotaLimits.from_dict(limits_data)
                
                # Load user usage
                cls._user_usage = {}
                for uid_str, usage_data in data.get("user_usage", {}).items():
                    uid = int(uid_str)
                    cls._user_usage[uid] = QuotaUsage.from_dict(usage_data)
                
                # Load group usage
                cls._group_usage = {}
                for gid_str, usage_data in data.get("group_usage", {}).items():
                    gid = int(gid_str)
                    cls._group_usage[gid] = QuotaUsage.from_dict(usage_data)
                
                return True, "Quotas loaded"
            except Exception as e:
                return False, str(e)


def initialize():
    """Initialize quota management system"""
    logger.info("Initializing quota management system")
    
    # Create quota directory
    quota_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(quota_dir, exist_ok=True)
    
    # Load quotas if they exist
    quotas_file = os.path.join(quota_dir, 'quotas.json')
    if os.path.exists(quotas_file):
        QuotaManager.load_quotas(quotas_file)
    else:
        # Save empty quotas
        QuotaManager.save_quotas(quotas_file)
    
    logger.info("Quota management system initialized")


# Initialize system
initialize()
