"""
KOS Custom Fingerprint Database Format Implementation
Implements the KFDB format with fp_part_1 to fp_part_16 fields
"""

import os
import time
import hmac
import hashlib
import struct
import sqlite3
import zlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import threading

logger = logging.getLogger('kos.security.fingerprint_db')


class FingerprintDatabase:
    """
    Custom fingerprint database with fp_part_1 to fp_part_16 format
    Each part can store up to 128 characters
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS fingerprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id TEXT UNIQUE NOT NULL,
        entity_type TEXT NOT NULL,
        fp_part_1 TEXT,
        fp_part_2 TEXT,
        fp_part_3 TEXT,
        fp_part_4 TEXT,
        fp_part_5 TEXT,
        fp_part_6 TEXT,
        fp_part_7 TEXT,
        fp_part_8 TEXT,
        fp_part_9 TEXT,
        fp_part_10 TEXT,
        fp_part_11 TEXT,
        fp_part_12 TEXT,
        fp_part_13 TEXT,
        fp_part_14 TEXT,
        fp_part_15 TEXT,
        fp_part_16 TEXT,
        crc32 INTEGER NOT NULL,
        salt BLOB NOT NULL,
        hash BLOB NOT NULL,
        created REAL NOT NULL,
        last_used REAL NOT NULL,
        status TEXT NOT NULL,
        metadata TEXT,
        CHECK (length(fp_part_1) <= 128),
        CHECK (length(fp_part_2) <= 128),
        CHECK (length(fp_part_3) <= 128),
        CHECK (length(fp_part_4) <= 128),
        CHECK (length(fp_part_5) <= 128),
        CHECK (length(fp_part_6) <= 128),
        CHECK (length(fp_part_7) <= 128),
        CHECK (length(fp_part_8) <= 128),
        CHECK (length(fp_part_9) <= 128),
        CHECK (length(fp_part_10) <= 128),
        CHECK (length(fp_part_11) <= 128),
        CHECK (length(fp_part_12) <= 128),
        CHECK (length(fp_part_13) <= 128),
        CHECK (length(fp_part_14) <= 128),
        CHECK (length(fp_part_15) <= 128),
        CHECK (length(fp_part_16) <= 128)
    );
    
    CREATE INDEX IF NOT EXISTS idx_entity_id ON fingerprints(entity_id);
    CREATE INDEX IF NOT EXISTS idx_entity_type ON fingerprints(entity_type);
    CREATE INDEX IF NOT EXISTS idx_status ON fingerprints(status);
    """
    
    def __init__(self, db_path: str = "/var/lib/kos/secure/fingerprints.kfdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Thread-local storage for connections
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Initialize database
        self._init_database()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.execute("PRAGMA journal_mode = WAL")
        return self._local.connection
        
    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        conn.executescript(self.SCHEMA)
        conn.commit()
        
        # Set secure permissions
        os.chmod(self.db_path, 0o600)
        
    def _split_fingerprint_parts(self, fingerprint: str) -> List[str]:
        """Split fingerprint into parts (max 128 chars each)"""
        parts = []
        for i in range(0, len(fingerprint), 128):
            parts.append(fingerprint[i:i+128])
        
        # Pad to 16 parts
        while len(parts) < 16:
            parts.append("")
            
        return parts[:16]  # Ensure max 16 parts
        
    def _calculate_crc32(self, data: str) -> int:
        """Calculate CRC32 checksum"""
        return zlib.crc32(data.encode()) & 0xffffffff
        
    def store_fingerprint(self, entity_id: str, entity_type: str,
                         fingerprint: str, salt: bytes, hash: bytes,
                         metadata: Dict[str, Any] = None) -> bool:
        """Store fingerprint in database"""
        try:
            with self._lock:
                conn = self._get_connection()
                
                # Split fingerprint into parts
                parts = self._split_fingerprint_parts(fingerprint)
                
                # Calculate CRC32 of complete fingerprint
                crc32 = self._calculate_crc32(fingerprint)
                
                # Prepare metadata
                import json
                metadata_str = json.dumps(metadata) if metadata else "{}"
                
                # Insert or update
                conn.execute("""
                    INSERT OR REPLACE INTO fingerprints (
                        entity_id, entity_type,
                        fp_part_1, fp_part_2, fp_part_3, fp_part_4,
                        fp_part_5, fp_part_6, fp_part_7, fp_part_8,
                        fp_part_9, fp_part_10, fp_part_11, fp_part_12,
                        fp_part_13, fp_part_14, fp_part_15, fp_part_16,
                        crc32, salt, hash, created, last_used, status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entity_id, entity_type,
                    *parts,
                    crc32, salt, hash,
                    time.time(), time.time(), "active", metadata_str
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to store fingerprint: {e}")
            return False
            
    def get_fingerprint(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve fingerprint from database"""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute("""
                    SELECT * FROM fingerprints WHERE entity_id = ?
                """, (entity_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                    
                # Reconstruct fingerprint from parts
                parts = []
                for i in range(1, 17):
                    part = row[f'fp_part_{i}']
                    if part:
                        parts.append(part)
                        
                fingerprint = ''.join(parts)
                
                # Verify CRC32
                calculated_crc = self._calculate_crc32(fingerprint)
                if calculated_crc != row['crc32']:
                    logger.error(f"CRC32 mismatch for entity {entity_id}")
                    return None
                    
                # Update last_used
                conn.execute("""
                    UPDATE fingerprints SET last_used = ? WHERE entity_id = ?
                """, (time.time(), entity_id))
                conn.commit()
                
                import json
                return {
                    'entity_id': row['entity_id'],
                    'entity_type': row['entity_type'],
                    'fingerprint': fingerprint,
                    'salt': row['salt'],
                    'hash': row['hash'],
                    'created': row['created'],
                    'last_used': row['last_used'],
                    'status': row['status'],
                    'metadata': json.loads(row['metadata'] or '{}')
                }
                
        except Exception as e:
            logger.error(f"Failed to retrieve fingerprint: {e}")
            return None
            
    def search_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Search fingerprints by entity type"""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute("""
                    SELECT entity_id, entity_type, created, last_used, status
                    FROM fingerprints WHERE entity_type = ? AND status = 'active'
                """, (entity_type,))
                
                results = []
                for row in cursor:
                    results.append({
                        'entity_id': row['entity_id'],
                        'entity_type': row['entity_type'],
                        'created': row['created'],
                        'last_used': row['last_used'],
                        'status': row['status']
                    })
                    
                return results
                
        except Exception as e:
            logger.error(f"Failed to search fingerprints: {e}")
            return []
            
    def revoke_fingerprint(self, entity_id: str) -> bool:
        """Revoke a fingerprint"""
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute("""
                    UPDATE fingerprints SET status = 'revoked' WHERE entity_id = ?
                """, (entity_id,))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke fingerprint: {e}")
            return False
            
    def cleanup_expired(self, max_age_days: int = 365) -> int:
        """Clean up expired fingerprints"""
        try:
            with self._lock:
                conn = self._get_connection()
                cutoff_time = time.time() - (max_age_days * 86400)
                
                cursor = conn.execute("""
                    DELETE FROM fingerprints 
                    WHERE last_used < ? OR status = 'expired'
                """, (cutoff_time,))
                
                conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"Failed to cleanup fingerprints: {e}")
            return 0
            
    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics"""
        try:
            with self._lock:
                conn = self._get_connection()
                
                stats = {}
                cursor = conn.execute("""
                    SELECT entity_type, status, COUNT(*) as count
                    FROM fingerprints
                    GROUP BY entity_type, status
                """)
                
                for row in cursor:
                    key = f"{row['entity_type']}_{row['status']}"
                    stats[key] = row['count']
                    
                # Total count
                cursor = conn.execute("SELECT COUNT(*) FROM fingerprints")
                stats['total'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
            
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')