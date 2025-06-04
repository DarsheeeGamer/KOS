"""
KOS Advanced Index System
=========================

Comprehensive indexing and search system for applications and repositories.
Features:
- Multi-dimensional indexing (name, category, tags, description, etc.)
- Advanced search with ranking and relevance scoring
- Real-time index updates
- Performance optimization with caching
- Metadata enrichment and analysis
- Cross-repository search and deduplication
"""

import os
import json
import time
import sqlite3
import hashlib
import threading
import logging
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
import re
import urllib.parse
from pathlib import Path

logger = logging.getLogger('KOS.index_system')

class IndexType(Enum):
    """Types of indices"""
    APPLICATION = "application"
    PACKAGE = "package"
    REPOSITORY = "repository"
    FILE = "file"
    COMMAND = "command"

class SearchOperator(Enum):
    """Search operators"""
    AND = "and"
    OR = "or"
    NOT = "not"
    PHRASE = "phrase"
    WILDCARD = "wildcard"
    REGEX = "regex"

@dataclass
class IndexEntry:
    """Base index entry"""
    id: str
    name: str
    type: IndexType
    title: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    indexed_at: datetime = field(default_factory=datetime.now)
    
    # Search relevance fields
    popularity_score: float = 0.0
    quality_score: float = 0.0
    download_count: int = 0
    rating: float = 0.0
    last_updated: Optional[datetime] = None
    
    # Repository information
    repository: str = ""
    repository_url: str = ""
    
    # File system information
    file_path: str = ""
    file_size: int = 0
    checksum: str = ""

@dataclass
class ApplicationIndexEntry(IndexEntry):
    """Application-specific index entry"""
    version: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    
    # Application-specific metadata
    entry_point: str = ""
    executable_path: str = ""
    dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    platform_support: List[str] = field(default_factory=list)
    
    # Runtime information
    installation_size: int = 0
    memory_usage: int = 0
    cpu_usage: float = 0.0
    
    # Security information
    signed: bool = False
    signature_valid: bool = False
    security_scan_date: Optional[datetime] = None
    vulnerabilities: List[str] = field(default_factory=list)

@dataclass
class RepositoryIndexEntry(IndexEntry):
    """Repository-specific index entry"""
    url: str = ""
    repo_type: str = ""  # git, http, local, etc.
    maintainer: str = ""
    
    # Repository statistics
    package_count: int = 0
    total_downloads: int = 0
    avg_rating: float = 0.0
    
    # Repository health
    last_sync: Optional[datetime] = None
    sync_status: str = "unknown"  # success, failed, in_progress
    error_count: int = 0
    uptime_percentage: float = 0.0

@dataclass
class SearchQuery:
    """Advanced search query structure"""
    text: str = ""
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    type_filter: Optional[IndexType] = None
    repository_filter: Optional[str] = None
    
    # Advanced filters
    min_rating: float = 0.0
    max_age_days: Optional[int] = None
    platform_filter: List[str] = field(default_factory=list)
    license_filter: List[str] = field(default_factory=list)
    
    # Search operators
    operator: SearchOperator = SearchOperator.AND
    fuzzy: bool = False
    exact_match: bool = False
    
    # Result options
    limit: int = 50
    offset: int = 0
    sort_by: str = "relevance"  # relevance, name, date, rating, downloads
    sort_order: str = "desc"  # asc, desc

@dataclass
class SearchResult:
    """Search result with relevance scoring"""
    entry: IndexEntry
    relevance_score: float
    match_reasons: List[str] = field(default_factory=list)
    highlighted_text: str = ""

class InvertedIndex:
    """Inverted index for fast text search"""
    
    def __init__(self):
        self.index: Dict[str, Set[str]] = defaultdict(set)
        self.document_frequencies: Dict[str, int] = defaultdict(int)
        self.total_documents = 0
        self.lock = threading.RLock()
    
    def add_document(self, doc_id: str, text: str):
        """Add document to inverted index"""
        with self.lock:
            words = self._tokenize(text)
            unique_words = set(words)
            
            for word in unique_words:
                self.index[word].add(doc_id)
                self.document_frequencies[word] += 1
            
            self.total_documents += 1
    
    def remove_document(self, doc_id: str, text: str):
        """Remove document from inverted index"""
        with self.lock:
            words = self._tokenize(text)
            unique_words = set(words)
            
            for word in unique_words:
                if doc_id in self.index[word]:
                    self.index[word].remove(doc_id)
                    self.document_frequencies[word] -= 1
                    
                    if not self.index[word]:
                        del self.index[word]
                        del self.document_frequencies[word]
            
            self.total_documents = max(0, self.total_documents - 1)
    
    def search(self, query: str) -> Set[str]:
        """Search for documents matching query"""
        with self.lock:
            words = self._tokenize(query)
            if not words:
                return set()
            
            # Start with documents containing first word
            result_docs = self.index.get(words[0], set()).copy()
            
            # Intersect with documents containing other words
            for word in words[1:]:
                result_docs &= self.index.get(word, set())
            
            return result_docs
    
    def search_or(self, query: str) -> Set[str]:
        """Search for documents matching any word in query"""
        with self.lock:
            words = self._tokenize(query)
            result_docs = set()
            
            for word in words:
                result_docs |= self.index.get(word, set())
            
            return result_docs
    
    def get_tf_idf_score(self, doc_id: str, query: str) -> float:
        """Calculate TF-IDF score for document and query"""
        import math
        
        words = self._tokenize(query)
        score = 0.0
        
        for word in words:
            if doc_id in self.index.get(word, set()):
                # Term frequency (simplified - assume 1 occurrence)
                tf = 1.0
                
                # Inverse document frequency
                df = self.document_frequencies.get(word, 0)
                if df > 0:
                    idf = math.log(self.total_documents / df)
                    score += tf * idf
        
        return score
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into searchable words"""
        # Convert to lowercase and split on non-alphanumeric characters
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        words = text.split()
        
        # Filter out very short words and common stop words
        stop_words = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 
                     'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 
                     'that', 'the', 'to', 'was', 'will', 'with'}
        
        return [word for word in words if len(word) > 2 and word not in stop_words]

class AdvancedIndexSystem:
    """Advanced indexing system for KOS"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.expanduser("~/.kos/index.db")
        self.cache_dir = os.path.expanduser("~/.kos/index_cache")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # In-memory indices
        self.inverted_index = InvertedIndex()
        self.entries: Dict[str, IndexEntry] = {}
        self.categories: Dict[str, Set[str]] = defaultdict(set)
        self.tags: Dict[str, Set[str]] = defaultdict(set)
        self.repositories: Dict[str, Set[str]] = defaultdict(set)
        
        # Performance tracking
        self.search_stats = {
            'total_searches': 0,
            'avg_search_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Threading
        self.lock = threading.RLock()
        self.background_tasks = []
        
        # Initialize database and load existing data
        self._init_database()
        self._load_from_database()
        
        logger.info("Advanced index system initialized")
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create main index table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_entries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT,
                description TEXT,
                category TEXT,
                tags TEXT,
                keywords TEXT,
                metadata TEXT,
                created_at TEXT,
                updated_at TEXT,
                indexed_at TEXT,
                popularity_score REAL DEFAULT 0.0,
                quality_score REAL DEFAULT 0.0,
                download_count INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                last_updated TEXT,
                repository TEXT,
                repository_url TEXT,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                checksum TEXT
            )
        ''')
        
        # Create search optimization indices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON index_entries(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON index_entries(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON index_entries(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repository ON index_entries(repository)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON index_entries(rating)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_updated ON index_entries(updated_at)')
        
        # Create full-text search table
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
                id,
                name,
                title,
                description,
                category,
                tags,
                keywords
            )
        ''')
        
        # Create search statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_stats (
                query_hash TEXT PRIMARY KEY,
                query_text TEXT,
                result_count INTEGER,
                search_time REAL,
                timestamp TEXT,
                user_agent TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_from_database(self):
        """Load existing entries from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM index_entries')
        rows = cursor.fetchall()
        
        for row in rows:
            entry = self._row_to_entry(row)
            self._add_to_memory_indices(entry)
        
        conn.close()
        logger.info(f"Loaded {len(self.entries)} entries from database")
    
    def add_entry(self, entry: IndexEntry) -> bool:
        """Add entry to index"""
        try:
            with self.lock:
                # Update timestamps
                entry.indexed_at = datetime.now()
                if entry.id in self.entries:
                    entry.updated_at = datetime.now()
                else:
                    entry.created_at = datetime.now()
                    entry.updated_at = datetime.now()
                
                # Add to memory indices
                self._add_to_memory_indices(entry)
                
                # Add to database
                self._save_to_database(entry)
                
                logger.debug(f"Added entry to index: {entry.name} ({entry.id})")
                return True
                
        except Exception as e:
            logger.error(f"Error adding entry to index: {e}")
            return False
    
    def remove_entry(self, entry_id: str) -> bool:
        """Remove entry from index"""
        try:
            with self.lock:
                if entry_id not in self.entries:
                    return False
                
                entry = self.entries[entry_id]
                
                # Remove from memory indices
                self._remove_from_memory_indices(entry)
                
                # Remove from database
                self._remove_from_database(entry_id)
                
                logger.debug(f"Removed entry from index: {entry.name} ({entry_id})")
                return True
                
        except Exception as e:
            logger.error(f"Error removing entry from index: {e}")
            return False
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform advanced search"""
        start_time = time.time()
        
        try:
            with self.lock:
                # Generate cache key
                cache_key = self._generate_cache_key(query)
                
                # Check cache first
                cached_result = self._get_from_cache(cache_key)
                if cached_result:
                    self.search_stats['cache_hits'] += 1
                    return cached_result
                
                self.search_stats['cache_misses'] += 1
                
                # Perform search
                results = self._perform_search(query)
                
                # Cache results
                self._save_to_cache(cache_key, results)
                
                # Update statistics
                search_time = time.time() - start_time
                self._update_search_stats(query, len(results), search_time)
                
                logger.debug(f"Search completed: {len(results)} results in {search_time:.3f}s")
                return results
                
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            return []
    
    def _perform_search(self, query: SearchQuery) -> List[SearchResult]:
        """Internal search implementation"""
        candidate_ids = set()
        
        # Text search
        if query.text:
            if query.operator == SearchOperator.OR:
                text_candidates = self.inverted_index.search_or(query.text)
            else:
                text_candidates = self.inverted_index.search(query.text)
            
            if not candidate_ids:
                candidate_ids = text_candidates
            else:
                candidate_ids &= text_candidates
        
        # If no text query, start with all entries
        if not query.text:
            candidate_ids = set(self.entries.keys())
        
        # Apply filters
        candidate_ids = self._apply_filters(candidate_ids, query)
        
        # Calculate relevance scores
        results = []
        for entry_id in candidate_ids:
            entry = self.entries[entry_id]
            score = self._calculate_relevance_score(entry, query)
            
            if score > 0:  # Only include entries with positive relevance
                result = SearchResult(
                    entry=entry,
                    relevance_score=score,
                    match_reasons=self._get_match_reasons(entry, query),
                    highlighted_text=self._highlight_matches(entry, query)
                )
                results.append(result)
        
        # Sort results
        results = self._sort_results(results, query)
        
        # Apply pagination
        start_idx = query.offset
        end_idx = start_idx + query.limit
        return results[start_idx:end_idx]
    
    def _apply_filters(self, candidate_ids: Set[str], query: SearchQuery) -> Set[str]:
        """Apply search filters"""
        filtered_ids = candidate_ids.copy()
        
        # Category filter
        if query.category:
            category_ids = self.categories.get(query.category, set())
            filtered_ids &= category_ids
        
        # Type filter
        if query.type_filter:
            type_ids = {id for id, entry in self.entries.items() 
                       if entry.type == query.type_filter}
            filtered_ids &= type_ids
        
        # Repository filter
        if query.repository_filter:
            repo_ids = self.repositories.get(query.repository_filter, set())
            filtered_ids &= repo_ids
        
        # Tags filter
        if query.tags:
            for tag in query.tags:
                tag_ids = self.tags.get(tag, set())
                filtered_ids &= tag_ids
        
        # Rating filter
        if query.min_rating > 0:
            rating_ids = {id for id, entry in self.entries.items() 
                         if entry.rating >= query.min_rating}
            filtered_ids &= rating_ids
        
        # Age filter
        if query.max_age_days:
            cutoff_date = datetime.now() - timedelta(days=query.max_age_days)
            age_ids = {id for id, entry in self.entries.items() 
                      if entry.last_updated and entry.last_updated >= cutoff_date}
            filtered_ids &= age_ids
        
        return filtered_ids
    
    def _calculate_relevance_score(self, entry: IndexEntry, query: SearchQuery) -> float:
        """Calculate relevance score for entry"""
        score = 0.0
        
        # Base TF-IDF score for text search
        if query.text:
            searchable_text = f"{entry.name} {entry.title} {entry.description}"
            tf_idf_score = self.inverted_index.get_tf_idf_score(entry.id, query.text)
            score += tf_idf_score * 10  # Weight text relevance highly
        
        # Exact name match bonus
        if query.text and query.text.lower() in entry.name.lower():
            score += 50
        
        # Title match bonus
        if query.text and query.text.lower() in entry.title.lower():
            score += 30
        
        # Category match bonus
        if query.category and entry.category == query.category:
            score += 20
        
        # Tag match bonus
        matching_tags = set(query.tags) & set(entry.tags)
        score += len(matching_tags) * 15
        
        # Quality indicators
        score += entry.popularity_score * 5
        score += entry.quality_score * 5
        score += min(entry.rating * 10, 50)  # Cap rating bonus at 50
        
        # Download count (logarithmic scaling)
        if entry.download_count > 0:
            import math
            score += math.log10(entry.download_count + 1) * 5
        
        # Freshness bonus (prefer recently updated)
        if entry.last_updated:
            days_old = (datetime.now() - entry.last_updated).days
            freshness_score = max(0, 30 - days_old * 0.5)  # Decay over time
            score += freshness_score
        
        return score
    
    def _get_match_reasons(self, entry: IndexEntry, query: SearchQuery) -> List[str]:
        """Get reasons why entry matched the query"""
        reasons = []
        
        if query.text:
            if query.text.lower() in entry.name.lower():
                reasons.append("Name match")
            if query.text.lower() in entry.title.lower():
                reasons.append("Title match")
            if query.text.lower() in entry.description.lower():
                reasons.append("Description match")
        
        if query.category and entry.category == query.category:
            reasons.append(f"Category: {entry.category}")
        
        matching_tags = set(query.tags) & set(entry.tags)
        if matching_tags:
            reasons.append(f"Tags: {', '.join(matching_tags)}")
        
        if entry.rating >= 4.0:
            reasons.append("High rating")
        
        if entry.download_count > 1000:
            reasons.append("Popular")
        
        return reasons
    
    def _highlight_matches(self, entry: IndexEntry, query: SearchQuery) -> str:
        """Highlight matching text in entry description"""
        if not query.text:
            return entry.description[:200] + "..." if len(entry.description) > 200 else entry.description
        
        text = entry.description
        words = query.text.split()
        
        for word in words:
            # Simple highlighting (in a real implementation, use proper HTML/markup)
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            text = pattern.sub(f"**{word}**", text)
        
        # Truncate if too long
        if len(text) > 200:
            text = text[:200] + "..."
        
        return text
    
    def _sort_results(self, results: List[SearchResult], query: SearchQuery) -> List[SearchResult]:
        """Sort search results"""
        if query.sort_by == "relevance":
            results.sort(key=lambda r: r.relevance_score, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "name":
            results.sort(key=lambda r: r.entry.name, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "date":
            results.sort(key=lambda r: r.entry.updated_at or datetime.min, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "rating":
            results.sort(key=lambda r: r.entry.rating, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "downloads":
            results.sort(key=lambda r: r.entry.download_count, reverse=(query.sort_order == "desc"))
        
        return results
    
    def _add_to_memory_indices(self, entry: IndexEntry):
        """Add entry to in-memory indices"""
        # Main entry storage
        self.entries[entry.id] = entry
        
        # Inverted index for text search
        searchable_text = f"{entry.name} {entry.title} {entry.description} {' '.join(entry.tags)} {' '.join(entry.keywords)}"
        self.inverted_index.add_document(entry.id, searchable_text)
        
        # Category index
        if entry.category:
            self.categories[entry.category].add(entry.id)
        
        # Tags index
        for tag in entry.tags:
            self.tags[tag].add(entry.id)
        
        # Repository index
        if entry.repository:
            self.repositories[entry.repository].add(entry.id)
    
    def _remove_from_memory_indices(self, entry: IndexEntry):
        """Remove entry from in-memory indices"""
        entry_id = entry.id
        
        # Remove from main storage
        if entry_id in self.entries:
            del self.entries[entry_id]
        
        # Remove from inverted index
        searchable_text = f"{entry.name} {entry.title} {entry.description} {' '.join(entry.tags)} {' '.join(entry.keywords)}"
        self.inverted_index.remove_document(entry_id, searchable_text)
        
        # Remove from category index
        if entry.category and entry_id in self.categories[entry.category]:
            self.categories[entry.category].remove(entry_id)
            if not self.categories[entry.category]:
                del self.categories[entry.category]
        
        # Remove from tags index
        for tag in entry.tags:
            if entry_id in self.tags[tag]:
                self.tags[tag].remove(entry_id)
                if not self.tags[tag]:
                    del self.tags[tag]
        
        # Remove from repository index
        if entry.repository and entry_id in self.repositories[entry.repository]:
            self.repositories[entry.repository].remove(entry_id)
            if not self.repositories[entry.repository]:
                del self.repositories[entry.repository]
    
    def _save_to_database(self, entry: IndexEntry):
        """Save entry to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert entry to database row
        row_data = (
            entry.id, entry.name, entry.type.value, entry.title, entry.description,
            entry.category, json.dumps(entry.tags), json.dumps(entry.keywords),
            json.dumps(entry.metadata), entry.created_at.isoformat(),
            entry.updated_at.isoformat(), entry.indexed_at.isoformat(),
            entry.popularity_score, entry.quality_score, entry.download_count,
            entry.rating, entry.last_updated.isoformat() if entry.last_updated else None,
            entry.repository, entry.repository_url, entry.file_path,
            entry.file_size, entry.checksum
        )
        
        # Insert or update
        cursor.execute('''
            INSERT OR REPLACE INTO index_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', row_data)
        
        # Update FTS index
        fts_data = (
            entry.id, entry.name, entry.title, entry.description,
            entry.category, ' '.join(entry.tags), ' '.join(entry.keywords)
        )
        cursor.execute('INSERT OR REPLACE INTO fts_index VALUES (?, ?, ?, ?, ?, ?, ?)', fts_data)
        
        conn.commit()
        conn.close()
    
    def _remove_from_database(self, entry_id: str):
        """Remove entry from SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM index_entries WHERE id = ?', (entry_id,))
        cursor.execute('DELETE FROM fts_index WHERE id = ?', (entry_id,))
        
        conn.commit()
        conn.close()
    
    def _row_to_entry(self, row) -> IndexEntry:
        """Convert database row to IndexEntry"""
        return IndexEntry(
            id=row[0],
            name=row[1],
            type=IndexType(row[2]),
            title=row[3] or "",
            description=row[4] or "",
            category=row[5] or "",
            tags=json.loads(row[6]) if row[6] else [],
            keywords=json.loads(row[7]) if row[7] else [],
            metadata=json.loads(row[8]) if row[8] else {},
            created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(),
            updated_at=datetime.fromisoformat(row[10]) if row[10] else datetime.now(),
            indexed_at=datetime.fromisoformat(row[11]) if row[11] else datetime.now(),
            popularity_score=row[12] or 0.0,
            quality_score=row[13] or 0.0,
            download_count=row[14] or 0,
            rating=row[15] or 0.0,
            last_updated=datetime.fromisoformat(row[16]) if row[16] else None,
            repository=row[17] or "",
            repository_url=row[18] or "",
            file_path=row[19] or "",
            file_size=row[20] or 0,
            checksum=row[21] or ""
        )
    
    def _generate_cache_key(self, query: SearchQuery) -> str:
        """Generate cache key for search query"""
        query_dict = asdict(query)
        query_json = json.dumps(query_dict, sort_keys=True, default=str)
        return hashlib.md5(query_json.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[SearchResult]]:
        """Get search results from cache"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            try:
                # Check if cache is still valid (1 hour TTL)
                if time.time() - os.path.getmtime(cache_file) < 3600:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        return self._deserialize_search_results(data)
            except:
                pass
        
        return None
    
    def _save_to_cache(self, cache_key: str, results: List[SearchResult]):
        """Save search results to cache"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        try:
            serialized_results = self._serialize_search_results(results)
            with open(cache_file, 'w') as f:
                json.dump(serialized_results, f, default=str)
        except Exception as e:
            logger.debug(f"Failed to cache search results: {e}")
    
    def _serialize_search_results(self, results: List[SearchResult]) -> List[Dict]:
        """Serialize search results for caching"""
        return [
            {
                'entry': asdict(result.entry),
                'relevance_score': result.relevance_score,
                'match_reasons': result.match_reasons,
                'highlighted_text': result.highlighted_text
            }
            for result in results
        ]
    
    def _deserialize_search_results(self, data: List[Dict]) -> List[SearchResult]:
        """Deserialize search results from cache"""
        results = []
        for item in data:
            entry_data = item['entry']
            entry = IndexEntry(
                id=entry_data['id'],
                name=entry_data['name'],
                type=IndexType(entry_data['type']),
                title=entry_data['title'],
                description=entry_data['description'],
                category=entry_data['category'],
                tags=entry_data['tags'],
                keywords=entry_data['keywords'],
                metadata=entry_data['metadata'],
                created_at=datetime.fromisoformat(entry_data['created_at']),
                updated_at=datetime.fromisoformat(entry_data['updated_at']),
                indexed_at=datetime.fromisoformat(entry_data['indexed_at']),
                popularity_score=entry_data['popularity_score'],
                quality_score=entry_data['quality_score'],
                download_count=entry_data['download_count'],
                rating=entry_data['rating'],
                last_updated=datetime.fromisoformat(entry_data['last_updated']) if entry_data['last_updated'] else None,
                repository=entry_data['repository'],
                repository_url=entry_data['repository_url'],
                file_path=entry_data['file_path'],
                file_size=entry_data['file_size'],
                checksum=entry_data['checksum']
            )
            
            result = SearchResult(
                entry=entry,
                relevance_score=item['relevance_score'],
                match_reasons=item['match_reasons'],
                highlighted_text=item['highlighted_text']
            )
            results.append(result)
        
        return results
    
    def _update_search_stats(self, query: SearchQuery, result_count: int, search_time: float):
        """Update search statistics"""
        self.search_stats['total_searches'] += 1
        
        # Update average search time
        prev_avg = self.search_stats['avg_search_time']
        total_searches = self.search_stats['total_searches']
        self.search_stats['avg_search_time'] = (prev_avg * (total_searches - 1) + search_time) / total_searches
        
        # Store in database for analytics
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query_hash = hashlib.md5(query.text.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO search_stats VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                query_hash, query.text, result_count, search_time,
                datetime.now().isoformat(), "KOS-Index-System"
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Failed to update search stats: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get index system statistics"""
        with self.lock:
            return {
                'total_entries': len(self.entries),
                'entries_by_type': {
                    type_val.value: sum(1 for entry in self.entries.values() if entry.type == type_val)
                    for type_val in IndexType
                },
                'categories': len(self.categories),
                'tags': len(self.tags),
                'repositories': len(self.repositories),
                'search_stats': self.search_stats.copy(),
                'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                'cache_size': sum(
                    os.path.getsize(os.path.join(self.cache_dir, f))
                    for f in os.listdir(self.cache_dir)
                    if os.path.isfile(os.path.join(self.cache_dir, f))
                ) if os.path.exists(self.cache_dir) else 0
            }
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            # Clear old cache files (older than 24 hours)
            if os.path.exists(self.cache_dir):
                cutoff_time = time.time() - 24 * 3600
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
            
            logger.info("Index system cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Global index system instance
_index_system: Optional[AdvancedIndexSystem] = None

def get_index_system() -> AdvancedIndexSystem:
    """Get or create the global index system instance"""
    global _index_system
    if _index_system is None:
        _index_system = AdvancedIndexSystem()
    return _index_system

# Alias for backward compatibility
IndexSystem = AdvancedIndexSystem

__all__ = [
    'AdvancedIndexSystem', 'IndexSystem', 'IndexEntry', 'ApplicationIndexEntry', 'RepositoryIndexEntry',
    'SearchQuery', 'SearchResult', 'InvertedIndex', 'IndexType', 'SearchOperator',
    'get_index_system'
] 