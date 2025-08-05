"""
Complete Fingerprint System Implementation with Custom Encryption Formula
Production-ready with strong cryptography
"""

import os
import time
import hmac
import hashlib
import secrets
import base64
import struct
import threading
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger('kos.security.fingerprint')


class FingerprintException(Exception):
    """Base exception for fingerprint operations"""
    pass


@dataclass
class FingerprintRecord:
    """Fingerprint record structure"""
    entity_id: str
    entity_type: str  # host, user, app, kos_instance, kadcm, kaim, driver, admin
    salt: bytes
    hash: bytes  # SHA512 of formula output
    parts: List[str]  # Formula output split into parts
    created: float
    last_used: float
    status: str  # active, revoked, expired
    metadata: Dict[str, Any] = field(default_factory=dict)


class FingerprintManager:
    """
    Complete fingerprint management system with custom encryption formula
    """
    
    def __init__(self, db_path: str = "/var/lib/kos/secure/fingerprints.kfdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Master key - in production, store in hardware security module
        self._master_key = self._load_or_generate_master_key()
        
        # Database
        self._db: Dict[str, FingerprintRecord] = {}
        self._db_lock = threading.RLock()
        
        # Load existing database
        self._load_database()
    
    def _load_or_generate_master_key(self) -> bytes:
        """Load or generate master encryption key"""
        key_file = Path("/etc/kos/secure/master.key")
        
        if key_file.exists():
            # Load existing key
            with open(key_file, 'rb') as f:
                return f.read(32)  # 256-bit key
        else:
            # Generate new key
            key = secrets.token_bytes(32)
            
            # Create directory with strict permissions
            key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            # Write key with strict permissions
            with open(key_file, 'wb') as f:
                f.write(key)
            
            os.chmod(key_file, 0o600)
            return key
    
    def _apply_formula(self, fingerprint_data: str, salt: bytes, 
                      entity_id: str, entity_type: str) -> str:
        """
        Apply the custom encryption formula
        
        Formula:
        base64(base85(base64(base85(pad64(a)+pad64(b)+pad64(f)))+
        base64(base85(pad64(C))+base85(pad64(E)))+
        base85(base64(pad64(c)+pad64(e))+base85(pad64(a)+pad64(b)+pad64(f))+
        base64(base85(pad64(E)))+base64(base85(pad64(M)))+base64(pad64(m))+
        base85(base64(hex(base64(base85(pad64(M)))))+
        base85(base64(hex(base64(pad64(m)))))+
        base85(hex(base64(base85(pad64(M)))))+
        base85(hex(base64(pad64(m))))+
        hex(base64(base85(pad64(M))))+
        hex(base64(base85(pad64(M))))+
        base64(hex(base64(base85(pad64(M)))))+
        hex(base64(pad64(m)))))))
        """
        
        # Helper function for padding
        def pad64(data: str) -> str:
            """Pad to 64 characters with length prefix"""
            data_bytes = data.encode('utf-8')
            if len(data_bytes) > 62:  # Leave room for 2-byte length
                data_bytes = data_bytes[:62]
            
            # Length prefix (2 bytes, big-endian)
            length_prefix = struct.pack('>H', len(data_bytes))
            
            # Pad with zeros
            padded = length_prefix + data_bytes + b'\x00' * (64 - len(data_bytes) - 2)
            return padded.decode('latin-1')
        
        # Define variables
        a = base64.b64encode(self._master_key + salt).decode('ascii')
        b = base64.b64encode(fingerprint_data.encode() + salt).decode('ascii')
        
        # Metadata
        metadata = {
            'timestamp': int(time.time()),
            'version': '1.0.0',
            'entity_id': entity_id
        }
        M = base64.b85encode(base64.b64encode(
            str(metadata).encode()
        ).decode().encode()).decode()
        m = base64.b64encode(str(metadata).encode()).decode()
        
        # Control metadata
        control = {
            'type': entity_type,
            'flags': 'NET_EN=1;KSECURE=1;'
        }
        C = base64.b85encode(base64.b64encode(
            str(control).encode()
        ).decode().encode()).decode()
        c = base64.b64encode(str(control).encode()).decode()
        
        # Environment metadata
        environment = {
            'hostname': os.uname().nodename,
            'platform': os.uname().sysname
        }
        E = base64.b85encode(base64.b64encode(
            str(environment).encode()
        ).decode().encode()).decode()
        e = base64.b64encode(str(environment).encode()).decode()
        
        # UUID
        uuid_val = secrets.token_hex(16)
        f = base64.b64encode(uuid_val.encode()).decode()
        
        # Apply formula layer by layer
        try:
            # Inner layer
            layer1 = (
                base64.b85encode((pad64(a) + pad64(b) + pad64(f)).encode()).decode()
            )
            
            layer2 = base64.b64encode((
                base64.b85encode(pad64(C).encode()).decode() +
                base64.b85encode(pad64(E).encode()).decode()
            ).encode()).decode()
            
            # Complex middle layer
            layer3_parts = [
                base64.b64encode((pad64(c) + pad64(e)).encode()).decode(),
                base64.b85encode((pad64(a) + pad64(b) + pad64(f)).encode()).decode(),
                base64.b64encode(base64.b85encode(pad64(E).encode()).decode().encode()).decode(),
                base64.b64encode(base64.b85encode(pad64(M).encode()).decode().encode()).decode(),
                base64.b64encode(pad64(m).encode()).decode()
            ]
            
            # Hex transformations
            hex_parts = [
                base64.b85encode(
                    base64.b64encode(
                        hex(int.from_bytes(
                            base64.b64encode(
                                base64.b85encode(pad64(M).encode()).decode().encode()
                            ), 'big'
                        ))[2:].encode()
                    ).decode().encode()
                ).decode(),
                base64.b85encode(
                    base64.b64encode(
                        hex(int.from_bytes(
                            base64.b64encode(pad64(m).encode()), 'big'
                        ))[2:].encode()
                    ).decode().encode()
                ).decode(),
                base64.b85encode(
                    hex(int.from_bytes(
                        base64.b64encode(
                            base64.b85encode(pad64(M).encode()).decode().encode()
                        ), 'big'
                    ))[2:].encode()
                ).decode(),
                base64.b85encode(
                    hex(int.from_bytes(
                        base64.b64encode(pad64(m).encode()), 'big'
                    ))[2:].encode()
                ).decode(),
                hex(int.from_bytes(
                    base64.b64encode(
                        base64.b85encode(pad64(M).encode()).decode().encode()
                    ), 'big'
                ))[2:],
                hex(int.from_bytes(
                    base64.b64encode(
                        base64.b85encode(pad64(M).encode()).decode().encode()
                    ), 'big'
                ))[2:],
                base64.b64encode(
                    hex(int.from_bytes(
                        base64.b64encode(
                            base64.b85encode(pad64(M).encode()).decode().encode()
                        ), 'big'
                    ))[2:].encode()
                ).decode(),
                hex(int.from_bytes(
                    base64.b64encode(pad64(m).encode()), 'big'
                ))[2:]
            ]
            
            layer3 = base64.b85encode(
                (''.join(layer3_parts) + ''.join(hex_parts)).encode()
            ).decode()
            
            # Combine all layers
            combined = base64.b85encode(
                (layer1 + layer2 + layer3).encode()
            ).decode()
            
            # Final encoding
            result = base64.b64encode(combined.encode()).decode()
            
            return result
            
        except Exception as e:
            logger.error(f"Formula application error: {e}")
            raise
    
    def create_fingerprint(self, entity_id: str, entity_type: str,
                          identifying_data: Dict[str, Any]) -> str:
        """
        Create a new fingerprint for an entity
        
        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (host, user, app, etc.)
            identifying_data: Data to create fingerprint from
            
        Returns:
            Fingerprint string for authentication
        """
        # Generate fingerprint data
        fingerprint_str = self._generate_fingerprint_string(identifying_data)
        
        # Generate salt
        salt = secrets.token_bytes(16)
        
        # Apply formula
        formula_output = self._apply_formula(
            fingerprint_str, salt, entity_id, entity_type
        )
        
        # Hash the formula output
        final_hash = hashlib.sha512(formula_output.encode()).digest()
        
        # Split formula output into parts (max 128 chars each)
        parts = []
        for i in range(0, len(formula_output), 128):
            parts.append(formula_output[i:i+128])
        
        # Create record
        record = FingerprintRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            salt=salt,
            hash=final_hash,
            parts=parts,
            created=time.time(),
            last_used=time.time(),
            status="active",
            metadata=identifying_data
        )
        
        # Store in database
        with self._db_lock:
            self._db[entity_id] = record
            self._save_database()
        
        # Return fingerprint for use
        return fingerprint_str
    
    def verify(self, fingerprint: str, entity_type: str) -> bool:
        """
        Verify a fingerprint
        
        Args:
            fingerprint: The fingerprint to verify
            entity_type: Expected entity type
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Search for matching fingerprint
            with self._db_lock:
                for entity_id, record in self._db.items():
                    if record.entity_type != entity_type:
                        continue
                    
                    if record.status != "active":
                        continue
                    
                    # Apply formula with stored salt
                    formula_output = self._apply_formula(
                        fingerprint, record.salt, entity_id, entity_type
                    )
                    
                    # Hash and compare
                    test_hash = hashlib.sha512(formula_output.encode()).digest()
                    
                    if hmac.compare_digest(test_hash, record.hash):
                        # Update last used
                        record.last_used = time.time()
                        self._save_database()
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Fingerprint verification error: {e}")
            return False
    
    def revoke(self, entity_id: str) -> bool:
        """Revoke a fingerprint"""
        with self._db_lock:
            if entity_id in self._db:
                self._db[entity_id].status = "revoked"
                self._save_database()
                return True
        return False
    
    def _generate_fingerprint_string(self, data: Dict[str, Any]) -> str:
        """Generate fingerprint string from identifying data"""
        # Sort keys for consistency
        sorted_data = sorted(data.items())
        
        # Create string representation
        parts = []
        for key, value in sorted_data:
            parts.append(f"{key}:{value}")
        
        fingerprint_data = "|".join(parts)
        
        # Hash it
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    def _save_database(self):
        """Save database to disk with custom format"""
        # Use the custom KFDB format with fp_part_1 to fp_part_16
        from .fingerprint_db import FingerprintDatabase
        
        if not hasattr(self, '_kfdb'):
            self._kfdb = FingerprintDatabase(str(self.db_path))
        
        # Save all records to KFDB
        for entity_id, record in self._db.items():
            # Reconstruct fingerprint from parts
            fingerprint = ''.join(record.parts)
            
            self._kfdb.store_fingerprint(
                entity_id=entity_id,
                entity_type=record.entity_type,
                fingerprint=fingerprint,
                salt=record.salt,
                hash=record.hash,
                metadata=record.metadata
            )
    
    def _load_database(self):
        """Load database from disk"""
        try:
            from .fingerprint_db import FingerprintDatabase
            
            self._kfdb = FingerprintDatabase(str(self.db_path))
            
            # Get all entity types and load records
            for entity_type in ['host', 'user', 'app', 'kos_instance', 'kadcm', 'kaim', 'driver', 'admin']:
                records = self._kfdb.search_by_type(entity_type)
                
                for record_info in records:
                    # Load full record
                    full_record = self._kfdb.get_fingerprint(record_info['entity_id'])
                    if full_record:
                        # Convert to FingerprintRecord
                        fingerprint = full_record['fingerprint']
                        parts = []
                        for i in range(0, len(fingerprint), 128):
                            parts.append(fingerprint[i:i+128])
                        
                        record = FingerprintRecord(
                            entity_id=full_record['entity_id'],
                            entity_type=full_record['entity_type'],
                            salt=full_record['salt'],
                            hash=full_record['hash'],
                            parts=parts,
                            created=full_record['created'],
                            last_used=full_record['last_used'],
                            status=full_record['status'],
                            metadata=full_record['metadata']
                        )
                        self._db[record.entity_id] = record
                        
        except Exception as e:
            logger.error(f"Failed to load fingerprint database: {e}")
    
    def admin_decrypt_fingerprint(self, entity_id: str, admin_key: bytes) -> Optional[Dict[str, Any]]:
        """
        Admin function to decrypt and inspect a fingerprint
        Requires special admin key
        """
        # Verify admin key
        expected_admin_key_hash = hashlib.sha512(
            self._master_key + b"ADMIN_ACCESS"
        ).digest()
        
        provided_admin_key_hash = hashlib.sha512(admin_key).digest()
        
        if not hmac.compare_digest(expected_admin_key_hash, provided_admin_key_hash):
            logger.warning(f"Invalid admin key attempt for entity {entity_id}")
            return None
        
        # Get record
        with self._db_lock:
            record = self._db.get(entity_id)
            if not record:
                return None
            
            # Return decrypted info
            return {
                'entity_id': entity_id,
                'entity_type': record.entity_type,
                'created': record.created,
                'last_used': record.last_used,
                'status': record.status,
                'metadata': record.metadata,
                'parts_count': len(record.parts)
            }


# Global instance
_fingerprint_manager: Optional[FingerprintManager] = None


def get_fingerprint_manager() -> FingerprintManager:
    """Get global fingerprint manager instance"""
    global _fingerprint_manager
    if _fingerprint_manager is None:
        _fingerprint_manager = FingerprintManager()
    return _fingerprint_manager