"""
Registry Index for KOS Container Registry

This module implements an optimized indexing system for the KOS container registry,
providing fast image searching and retrieval.
"""

import os
import json
import time
import bisect
import hashlib
import logging
import threading
import mmap
from typing import Dict, List, Set, Optional, Any, Union, Tuple, Callable

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
REGISTRY_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/registry')
REGISTRY_INDEX_PATH = os.path.join(REGISTRY_ROOT, 'index')

# Ensure directories exist
os.makedirs(REGISTRY_INDEX_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class SearchResult:
    """Result of a registry search."""
    
    def __init__(self, name: str, tag: str, digest: str, created: float,
                 size: int, labels: Optional[Dict[str, str]] = None):
        """
        Initialize a search result.
        
        Args:
            name: Image name
            tag: Image tag
            digest: Image digest
            created: Creation timestamp
            size: Image size in bytes
            labels: Image labels
        """
        self.name = name
        self.tag = tag
        self.digest = digest
        self.created = created
        self.size = size
        self.labels = labels or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the search result to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "tag": self.tag,
            "digest": self.digest,
            "created": self.created,
            "size": self.size,
            "labels": self.labels
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchResult':
        """
        Create a search result from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            SearchResult object
        """
        return cls(
            name=data.get("name", ""),
            tag=data.get("tag", ""),
            digest=data.get("digest", ""),
            created=data.get("created", 0),
            size=data.get("size", 0),
            labels=data.get("labels", {})
        )


class IndexEntry:
    """Entry in the registry index."""
    
    def __init__(self, name: str, tag: str, digest: str,
                 created: float, size: int, 
                 labels: Optional[Dict[str, str]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize an index entry.
        
        Args:
            name: Image name
            tag: Image tag
            digest: Image digest
            created: Creation timestamp
            size: Image size in bytes
            labels: Image labels
            metadata: Additional metadata
        """
        self.name = name
        self.tag = tag
        self.digest = digest
        self.created = created
        self.size = size
        self.labels = labels or {}
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the index entry to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "tag": self.tag,
            "digest": self.digest,
            "created": self.created,
            "size": self.size,
            "labels": self.labels,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndexEntry':
        """
        Create an index entry from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            IndexEntry object
        """
        return cls(
            name=data.get("name", ""),
            tag=data.get("tag", ""),
            digest=data.get("digest", ""),
            created=data.get("created", 0),
            size=data.get("size", 0),
            labels=data.get("labels", {}),
            metadata=data.get("metadata", {})
        )
    
    def matches(self, query: str) -> bool:
        """
        Check if this entry matches a search query.
        
        Args:
            query: Search query
            
        Returns:
            True if the entry matches the query
        """
        query = query.lower()
        
        # Check name
        if query in self.name.lower():
            return True
        
        # Check tag
        if query in self.tag.lower():
            return True
        
        # Check digest (short form)
        short_digest = self.digest.split(':')[-1][:12]
        if query in short_digest.lower():
            return True
        
        # Check labels
        for key, value in self.labels.items():
            if query in key.lower() or query in str(value).lower():
                return True
        
        return False


class BTreeNode:
    """B-tree node for the registry index."""
    
    def __init__(self, is_leaf: bool = True, keys: Optional[List[str]] = None,
                 children: Optional[List['BTreeNode']] = None,
                 entries: Optional[Dict[str, List[IndexEntry]]] = None):
        """
        Initialize a B-tree node.
        
        Args:
            is_leaf: Whether this is a leaf node
            keys: Node keys
            children: Child nodes
            entries: Index entries
        """
        self.is_leaf = is_leaf
        self.keys = keys or []
        self.children = children or []
        self.entries = entries or {}
    
    def search(self, key: str) -> Optional[List[IndexEntry]]:
        """
        Search for entries with the given key.
        
        Args:
            key: Key to search for
            
        Returns:
            List of entries or None if not found
        """
        # Find the appropriate child node
        i = bisect.bisect_left(self.keys, key)
        
        if i < len(self.keys) and self.keys[i] == key:
            # Found the key in this node
            if self.is_leaf:
                return self.entries.get(key, [])
            else:
                # For non-leaf nodes, search the child node
                return self.children[i].search(key)
        
        if self.is_leaf:
            # Key not found in leaf node
            return None
        
        # Search the appropriate child node
        if i == len(self.keys):
            return self.children[i].search(key)
        
        return self.children[i].search(key)
    
    def insert(self, key: str, entry: IndexEntry, t: int) -> Optional[Tuple[str, 'BTreeNode']]:
        """
        Insert an entry into the B-tree.
        
        Args:
            key: Key to insert
            entry: Entry to insert
            t: Minimum degree of the B-tree
            
        Returns:
            Tuple of (median key, new node) if split occurred, or None
        """
        if self.is_leaf:
            # Insert into leaf node
            i = bisect.bisect_left(self.keys, key)
            
            if i < len(self.keys) and self.keys[i] == key:
                # Key already exists, append to entries
                self.entries[key].append(entry)
            else:
                # Insert new key and entry
                self.keys.insert(i, key)
                self.entries[key] = [entry]
            
            # Check if node needs to be split
            if len(self.keys) >= 2 * t - 1:
                return self._split(t)
            
            return None
        
        # Find the appropriate child node
        i = bisect.bisect_left(self.keys, key)
        if i < len(self.keys) and self.keys[i] == key:
            # Key already exists, insert into child node
            result = self.children[i].insert(key, entry, t)
        else:
            # Insert into child node
            if i == len(self.keys):
                result = self.children[i].insert(key, entry, t)
            else:
                result = self.children[i].insert(key, entry, t)
        
        # Handle child split
        if result:
            median_key, new_node = result
            
            # Insert median key and new node
            i = bisect.bisect_left(self.keys, median_key)
            self.keys.insert(i, median_key)
            self.children.insert(i + 1, new_node)
            
            # Check if node needs to be split
            if len(self.keys) >= 2 * t - 1:
                return self._split(t)
        
        return None
    
    def _split(self, t: int) -> Tuple[str, 'BTreeNode']:
        """
        Split this node.
        
        Args:
            t: Minimum degree of the B-tree
            
        Returns:
            Tuple of (median key, new node)
        """
        # Create new node
        new_node = BTreeNode(is_leaf=self.is_leaf)
        
        # Get median key
        median_idx = t - 1
        median_key = self.keys[median_idx]
        
        # Move keys and entries to new node
        new_node.keys = self.keys[median_idx + 1:]
        self.keys = self.keys[:median_idx]
        
        if self.is_leaf:
            # Move entries
            for key in new_node.keys:
                new_node.entries[key] = self.entries.pop(key)
        else:
            # Move children
            new_node.children = self.children[median_idx + 1:]
            self.children = self.children[:median_idx + 1]
        
        return median_key, new_node


class BTree:
    """B-tree for the registry index."""
    
    def __init__(self, t: int = 3):
        """
        Initialize a B-tree.
        
        Args:
            t: Minimum degree of the B-tree (must be >= 2)
        """
        self.root = BTreeNode(is_leaf=True)
        self.t = max(2, t)
    
    def search(self, key: str) -> Optional[List[IndexEntry]]:
        """
        Search for entries with the given key.
        
        Args:
            key: Key to search for
            
        Returns:
            List of entries or None if not found
        """
        return self.root.search(key)
    
    def insert(self, key: str, entry: IndexEntry):
        """
        Insert an entry into the B-tree.
        
        Args:
            key: Key to insert
            entry: Entry to insert
        """
        result = self.root.insert(key, entry, self.t)
        
        if result:
            # Root was split, create new root
            median_key, new_node = result
            
            new_root = BTreeNode(is_leaf=False)
            new_root.keys = [median_key]
            new_root.children = [self.root, new_node]
            
            self.root = new_root


class RegistryIndex:
    """
    Optimized index for the KOS container registry.
    
    This class provides fast image searching and retrieval using a B-tree
    index and memory-mapped files for efficient I/O.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RegistryIndex, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the registry index."""
        if self._initialized:
            return
        
        self._initialized = True
        self._name_index = BTree()  # Index by image name
        self._tag_index = BTree()   # Index by tag
        self._digest_index = BTree()  # Index by digest
        self._label_index = BTree()  # Index by label
        
        self._entries = {}  # name:tag -> IndexEntry
        self._cache = {}    # name:tag -> SearchResult
        self._cache_lock = threading.Lock()
        self._cache_size = 1000
        self._dirty = False
        
        # Load the index
        self._load_index()
    
    def _load_index(self):
        """Load the index from disk."""
        index_file = os.path.join(REGISTRY_INDEX_PATH, 'registry_index.json')
        if not os.path.exists(index_file):
            logger.info("Registry index file not found, creating new index")
            return
        
        try:
            with open(index_file, 'r') as f:
                data = json.load(f)
            
            # Load entries
            entries = data.get("entries", [])
            for entry_data in entries:
                entry = IndexEntry.from_dict(entry_data)
                self._add_entry_to_indices(entry)
            
            logger.info(f"Loaded {len(entries)} entries from registry index")
        except Exception as e:
            logger.error(f"Failed to load registry index: {e}")
    
    def _save_index(self):
        """Save the index to disk."""
        if not self._dirty:
            return
        
        index_file = os.path.join(REGISTRY_INDEX_PATH, 'registry_index.json')
        
        try:
            # Collect all entries
            entries = []
            for entry_list in self._entries.values():
                entries.extend([entry.to_dict() for entry in entry_list])
            
            # Save to disk
            data = {"entries": entries}
            
            # Create temporary file
            temp_file = f"{index_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f)
            
            # Atomically replace the index file
            os.replace(temp_file, index_file)
            
            self._dirty = False
            logger.info(f"Saved {len(entries)} entries to registry index")
        except Exception as e:
            logger.error(f"Failed to save registry index: {e}")
    
    def _add_entry_to_indices(self, entry: IndexEntry):
        """
        Add an entry to all indices.
        
        Args:
            entry: Entry to add
        """
        # Add to name index
        self._name_index.insert(entry.name, entry)
        
        # Add to tag index
        self._tag_index.insert(entry.tag, entry)
        
        # Add to digest index
        self._digest_index.insert(entry.digest, entry)
        
        # Add to label index
        for key, value in entry.labels.items():
            label_key = f"{key}:{value}"
            self._label_index.insert(label_key, entry)
        
        # Add to entries dictionary
        key = f"{entry.name}:{entry.tag}"
        if key in self._entries:
            self._entries[key].append(entry)
        else:
            self._entries[key] = [entry]
        
        self._dirty = True
    
    def add_entry(self, name: str, tag: str, digest: str,
                 created: float, size: int,
                 labels: Optional[Dict[str, str]] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an entry to the registry index.
        
        Args:
            name: Image name
            tag: Image tag
            digest: Image digest
            created: Creation timestamp
            size: Image size in bytes
            labels: Image labels
            metadata: Additional metadata
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Create entry
                entry = IndexEntry(
                    name=name,
                    tag=tag,
                    digest=digest,
                    created=created,
                    size=size,
                    labels=labels,
                    metadata=metadata
                )
                
                # Add to indices
                self._add_entry_to_indices(entry)
                
                # Clear cache for this entry
                key = f"{name}:{tag}"
                with self._cache_lock:
                    if key in self._cache:
                        del self._cache[key]
                
                # Schedule index save
                threading.Thread(target=self._save_index).start()
                
                return True
        except Exception as e:
            logger.error(f"Failed to add entry to registry index: {e}")
            return False
    
    def remove_entry(self, name: str, tag: str) -> bool:
        """
        Remove an entry from the registry index.
        
        Args:
            name: Image name
            tag: Image tag
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                key = f"{name}:{tag}"
                
                if key not in self._entries:
                    logger.warning(f"Entry not found for removal: {key}")
                    return False
                
                # Remove from entries dictionary
                entries = self._entries.pop(key)
                
                # Rebuild indices (simple approach - for more complex scenarios,
                # we would implement proper B-tree deletion)
                self._name_index = BTree(self.t)
                self._tag_index = BTree(self.t)
                self._digest_index = BTree(self.t)
                self._label_index = BTree(self.t)
                
                for k, v in self._entries.items():
                    for entry in v:
                        self._add_entry_to_indices(entry)
                
                # Clear cache for this entry
                with self._cache_lock:
                    if key in self._cache:
                        del self._cache[key]
                
                self._dirty = True
                
                # Schedule index save
                threading.Thread(target=self._save_index).start()
                
                return True
        except Exception as e:
            logger.error(f"Failed to remove entry from registry index: {e}")
            return False
    
    def get_entry(self, name: str, tag: str) -> Optional[IndexEntry]:
        """
        Get an entry from the registry index.
        
        Args:
            name: Image name
            tag: Image tag
            
        Returns:
            IndexEntry or None if not found
        """
        key = f"{name}:{tag}"
        
        # Check cache first
        with self._cache_lock:
            if key in self._cache:
                cached = self._cache[key]
                entry = IndexEntry(
                    name=cached.name,
                    tag=cached.tag,
                    digest=cached.digest,
                    created=cached.created,
                    size=cached.size,
                    labels=cached.labels
                )
                return entry
        
        # Look up in entries dictionary
        entries = self._entries.get(key)
        if not entries:
            return None
        
        # Use the most recent entry
        entry = max(entries, key=lambda e: e.created)
        
        # Update cache
        with self._cache_lock:
            self._cache[key] = SearchResult(
                name=entry.name,
                tag=entry.tag,
                digest=entry.digest,
                created=entry.created,
                size=entry.size,
                labels=entry.labels
            )
            
            # Trim cache if needed
            if len(self._cache) > self._cache_size:
                # Remove oldest entries
                oldest = sorted(self._cache.items(), key=lambda x: x[1].created)
                for k, _ in oldest[:len(self._cache) - self._cache_size]:
                    del self._cache[k]
        
        return entry
    
    def search(self, query: str, limit: int = 100) -> List[SearchResult]:
        """
        Search the registry index.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        results = []
        seen = set()
        
        try:
            # Check if the query matches a specific pattern
            if ':' in query:
                # Could be name:tag or label:value
                if query.count(':') == 1:
                    name, tag = query.split(':', 1)
                    
                    # Check if it's a name:tag query
                    key = f"{name}:{tag}"
                    if key in self._entries:
                        entries = self._entries[key]
                        for entry in entries:
                            result_key = f"{entry.name}:{entry.tag}"
                            if result_key not in seen:
                                seen.add(result_key)
                                results.append(SearchResult(
                                    name=entry.name,
                                    tag=entry.tag,
                                    digest=entry.digest,
                                    created=entry.created,
                                    size=entry.size,
                                    labels=entry.labels
                                ))
                        
                        return results[:limit]
                    
                    # Check if it's a label query
                    label_entries = self._label_index.search(query)
                    if label_entries:
                        for entry in label_entries:
                            result_key = f"{entry.name}:{entry.tag}"
                            if result_key not in seen:
                                seen.add(result_key)
                                results.append(SearchResult(
                                    name=entry.name,
                                    tag=entry.tag,
                                    digest=entry.digest,
                                    created=entry.created,
                                    size=entry.size,
                                    labels=entry.labels
                                ))
                        
                        return results[:limit]
            
            # Try as image name
            name_entries = self._name_index.search(query)
            if name_entries:
                for entry in name_entries:
                    result_key = f"{entry.name}:{entry.tag}"
                    if result_key not in seen:
                        seen.add(result_key)
                        results.append(SearchResult(
                            name=entry.name,
                            tag=entry.tag,
                            digest=entry.digest,
                            created=entry.created,
                            size=entry.size,
                            labels=entry.labels
                        ))
            
            # Try as tag
            tag_entries = self._tag_index.search(query)
            if tag_entries:
                for entry in tag_entries:
                    result_key = f"{entry.name}:{entry.tag}"
                    if result_key not in seen:
                        seen.add(result_key)
                        results.append(SearchResult(
                            name=entry.name,
                            tag=entry.tag,
                            digest=entry.digest,
                            created=entry.created,
                            size=entry.size,
                            labels=entry.labels
                        ))
            
            # Try as digest
            digest_entries = self._digest_index.search(query)
            if digest_entries:
                for entry in digest_entries:
                    result_key = f"{entry.name}:{entry.tag}"
                    if result_key not in seen:
                        seen.add(result_key)
                        results.append(SearchResult(
                            name=entry.name,
                            tag=entry.tag,
                            digest=entry.digest,
                            created=entry.created,
                            size=entry.size,
                            labels=entry.labels
                        ))
            
            # If still no results, do a full text search
            if not results:
                for entries in self._entries.values():
                    for entry in entries:
                        if entry.matches(query):
                            result_key = f"{entry.name}:{entry.tag}"
                            if result_key not in seen:
                                seen.add(result_key)
                                results.append(SearchResult(
                                    name=entry.name,
                                    tag=entry.tag,
                                    digest=entry.digest,
                                    created=entry.created,
                                    size=entry.size,
                                    labels=entry.labels
                                ))
                            
                            if len(results) >= limit:
                                break
            
            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching registry index: {e}")
            return []
    
    def rebuild_index(self) -> bool:
        """
        Rebuild the registry index from scratch.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Clear indices
                self._name_index = BTree(self.t)
                self._tag_index = BTree(self.t)
                self._digest_index = BTree(self.t)
                self._label_index = BTree(self.t)
                
                # Rebuild from entries
                for entries in self._entries.values():
                    for entry in entries:
                        self._add_entry_to_indices(entry)
                
                # Clear cache
                with self._cache_lock:
                    self._cache.clear()
                
                self._dirty = True
                
                # Schedule index save
                threading.Thread(target=self._save_index).start()
                
                return True
        except Exception as e:
            logger.error(f"Failed to rebuild registry index: {e}")
            return False
    
    @property
    def t(self) -> int:
        """Get the minimum degree of the B-tree."""
        return 3  # Default minimum degree
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the registry index.
        
        Returns:
            Dict with statistics
        """
        entry_count = sum(len(entries) for entries in self._entries.values())
        
        return {
            "entry_count": entry_count,
            "name_count": len(set(entry.name for entries in self._entries.values() for entry in entries)),
            "tag_count": len(set(entry.tag for entries in self._entries.values() for entry in entries)),
            "digest_count": len(set(entry.digest for entries in self._entries.values() for entry in entries)),
            "cache_size": len(self._cache),
            "dirty": self._dirty
        }
