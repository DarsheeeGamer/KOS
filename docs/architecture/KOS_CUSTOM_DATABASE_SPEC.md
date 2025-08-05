# KOS Custom Database Specification

## Overview
KOS uses a custom binary database format optimized for security, performance, and KOS-specific requirements.

## Database File Structure

### KFDB (KOS Fingerprint Database) Format

```
[Header Block - 512 bytes]
+---------------------------+
| Magic: "KFDB\x00\x01"     | 6 bytes  - File identifier + version
| Creation Time             | 8 bytes  - Unix timestamp
| Last Modified             | 8 bytes  - Unix timestamp
| Index Offset              | 8 bytes  - Offset to index block
| Data Offset               | 8 bytes  - Offset to data block
| Record Count              | 4 bytes  - Total records
| Checksum Algorithm        | 2 bytes  - 0x01=CRC32, 0x02=SHA256
| Encryption Flag           | 1 byte   - 0x00=none, 0x01=AES256
| Reserved                  | 469 bytes - Future use
+---------------------------+

[Index Block - Variable size]
+---------------------------+
| Index Entry 1             | 64 bytes per entry
| Index Entry 2             |
| ...                       |
| Index Entry N             |
+---------------------------+

[Data Block - Variable size]
+---------------------------+
| Data Record 1             | Variable size
| Data Record 2             |
| ...                       |
| Data Record N             |
+---------------------------+

[Checksum Block - 32 bytes]
+---------------------------+
| File Checksum             | 32 bytes - SHA256 of entire file
+---------------------------+
```

### Index Entry Structure (64 bytes)
```
+---------------------------+
| Entity ID                 | 16 bytes - UUID
| Record Offset             | 8 bytes  - Offset in data block
| Record Size               | 4 bytes  - Size of record
| Record Type               | 2 bytes  - Type identifier
| Flags                     | 2 bytes  - Status flags
| Creation Time             | 8 bytes  - Unix timestamp
| Hash                      | 24 bytes - Quick lookup hash
+---------------------------+
```

### Fingerprint Data Record Structure
```
+---------------------------+
| Record Header (32 bytes)  |
|   - Length: 4 bytes       |
|   - Type: 2 bytes         |
|   - Version: 2 bytes      |
|   - Checksum: 24 bytes    |
+---------------------------+
| Fingerprint Data          |
|   - Entity UUID: 16 bytes |
|   - Type: 1 byte          | (host/user/app/etc)
|   - Salt: 16 bytes        |
|   - Hash: 64 bytes        | (SHA512 of formula output)
|   - Parts Count: 2 bytes  |
|   - Part 1: var length    |
|   - Part 2: var length    |
|   - ...                   |
|   - Part N: var length    |
+---------------------------+
| Metadata                  |
|   - Created: 8 bytes      |
|   - Last Used: 8 bytes    |
|   - Status: 1 byte        |
|   - Reserved: 16 bytes    |
+---------------------------+
```

### KSDB (KOS Shadow Database) Format

```
[Header Block - 256 bytes]
+---------------------------+
| Magic: "KSDB\x00\x01"     | 6 bytes
| Record Count              | 4 bytes
| Index Offset              | 8 bytes
| Reserved                  | 238 bytes
+---------------------------+

[Shadow Record - Fixed 256 bytes each]
+---------------------------+
| Username                  | 32 bytes - Null padded
| Password Hash             | 128 bytes - Formula + SHA512
| Salt                      | 16 bytes
| Last Change               | 8 bytes - Days since epoch
| Min Days                  | 2 bytes
| Max Days                  | 2 bytes
| Warn Days                 | 2 bytes
| Inactive Days             | 2 bytes
| Expire Date               | 8 bytes
| Flags                     | 4 bytes
| Reserved                  | 58 bytes
+---------------------------+
```

### KPDB (KOS Policy Database) Format

```
[Header Block - 1024 bytes]
+---------------------------+
| Magic: "KPDB\x00\x01"     | 6 bytes
| Policy Version            | 4 bytes
| Role Count                | 4 bytes
| Group Count               | 4 bytes
| Flag Definition Count     | 4 bytes
| Index Offset              | 8 bytes
| Reserved                  | 994 bytes
+---------------------------+

[Role Record - Variable size]
+---------------------------+
| Role Name                 | 32 bytes
| Role ID                   | 4 bytes
| Flag Count                | 2 bytes
| Flags[]                   | 2 bytes each
| Parent Role ID            | 4 bytes
| Commands Count            | 4 bytes
| Commands[]                | Variable
| Paths Count               | 4 bytes
| Paths[]                   | Variable
+---------------------------+
```

## Database Operations

### Read Operation
```c
typedef struct {
    uint8_t magic[6];
    uint64_t creation_time;
    uint64_t last_modified;
    uint64_t index_offset;
    uint64_t data_offset;
    uint32_t record_count;
    uint16_t checksum_algo;
    uint8_t encryption_flag;
    uint8_t reserved[469];
} kfdb_header_t;

// Read record by UUID
kfdb_record_t* kfdb_read(const char* db_path, uuid_t entity_id) {
    // 1. Open file and read header
    // 2. Verify magic and checksum
    // 3. Binary search index for UUID
    // 4. Read data record at offset
    // 5. Verify record checksum
    // 6. Return decoded record
}
```

### Write Operation
```c
// Write with atomic transaction
int kfdb_write(const char* db_path, kfdb_record_t* record) {
    // 1. Create temporary file
    // 2. Copy existing records
    // 3. Insert/update new record
    // 4. Update index
    // 5. Calculate new checksums
    // 6. Atomic rename
}
```

### Security Features

1. **Integrity Checks**
   - Header checksum
   - Per-record checksums
   - Full file checksum

2. **Access Control**
   - File permissions: 0600 (user DBs) or 0000 (system DBs)
   - Mandatory file locking during operations
   - Audit trail for all modifications

3. **Performance Optimizations**
   - Binary search on sorted index
   - Memory-mapped I/O for large databases
   - Write-ahead logging for transactions

4. **Backup & Recovery**
   - Automatic backup before modifications
   - Transaction log for recovery
   - Versioned backups with rotation

## Implementation Example

```python
class KOSDatabase:
    MAGIC_KFDB = b'KFDB\x00\x01'
    HEADER_SIZE = 512
    INDEX_ENTRY_SIZE = 64
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.header = None
        self.index = []
        
    def create(self):
        """Create new database file"""
        header = {
            'magic': self.MAGIC_KFDB,
            'creation_time': int(time.time()),
            'last_modified': int(time.time()),
            'index_offset': self.HEADER_SIZE,
            'data_offset': self.HEADER_SIZE,  # Updated as records added
            'record_count': 0,
            'checksum_algo': 0x02,  # SHA256
            'encryption_flag': 0x00
        }
        
        with open(self.db_path, 'wb') as f:
            # Write header
            f.write(self._pack_header(header))
            # Write empty checksum block
            f.seek(-32, 2)
            f.write(b'\x00' * 32)
            
    def add_fingerprint(self, entity_id, fingerprint_data, salt, formula_output):
        """Add fingerprint record"""
        # Apply hash to formula output
        final_hash = hashlib.sha512(formula_output.encode()).digest()
        
        record = {
            'entity_id': entity_id,
            'type': 'user',
            'salt': salt,
            'hash': final_hash,
            'parts': self._split_formula_output(formula_output),
            'created': int(time.time()),
            'status': 0x01  # Active
        }
        
        self._write_record(record)
```

## File Locations

- Fingerprint DB: `/var/lib/kos/secure/fingerprints.kfdb`
- Shadow DB: `/etc/kos/shadow.ksdb`  
- Policy DB: `/etc/kos/policy.kpdb`
- History DBs: `/var/lib/kos/history/{uid}.khdb`
- Session DB: `/var/run/kos/sessions.ktdb` (temporary)

## Database Tools

- `kdb-inspect` - View database contents (requires KROOT)
- `kdb-verify` - Verify database integrity
- `kdb-backup` - Backup database
- `kdb-recover` - Recover from corruption