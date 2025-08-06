"""
Database support for KOS (SQLite-based)
"""

import sqlite3
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class DataType(Enum):
    """SQL data types"""
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BLOB = "BLOB"
    NULL = "NULL"

@dataclass
class Column:
    """Database column definition"""
    name: str
    data_type: DataType
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False
    default: Any = None
    auto_increment: bool = False
    
    def to_sql(self) -> str:
        """Convert to SQL definition"""
        sql = f"{self.name} {self.data_type.value}"
        
        if self.primary_key:
            sql += " PRIMARY KEY"
            if self.auto_increment:
                sql += " AUTOINCREMENT"
        
        if self.not_null:
            sql += " NOT NULL"
        
        if self.unique:
            sql += " UNIQUE"
        
        if self.default is not None:
            if self.data_type == DataType.TEXT:
                sql += f" DEFAULT '{self.default}'"
            else:
                sql += f" DEFAULT {self.default}"
        
        return sql

class Database:
    """SQLite database wrapper for VFS"""
    
    def __init__(self, vfs=None, db_path: str = ":memory:"):
        self.vfs = vfs
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self.in_transaction = False
        
        if db_path != ":memory:" and vfs:
            # Store database in VFS
            self.db_file = f"/var/db/{db_path}"
            self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        if not self.vfs:
            return
        
        if not self.vfs.exists("/var/db"):
            try:
                self.vfs.mkdir("/var/db")
            except:
                pass
    
    def connect(self) -> bool:
        """Connect to database"""
        try:
            if self.db_path == ":memory:":
                self.connection = sqlite3.connect(":memory:")
            else:
                # In real implementation, would use VFS-backed storage
                # For now, use in-memory with persistence simulation
                self.connection = sqlite3.connect(":memory:")
                
                # Load from VFS if exists
                if self.vfs and self.vfs.exists(self.db_file):
                    self._load_from_vfs()
            
            self.cursor = self.connection.cursor()
            return True
        except Exception as e:
            print(f"Database connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from database"""
        if self.connection:
            # Save to VFS before closing
            if self.db_path != ":memory:" and self.vfs:
                self._save_to_vfs()
            
            self.connection.close()
            self.connection = None
            self.cursor = None
    
    def _save_to_vfs(self):
        """Save database to VFS"""
        if not self.vfs or not self.connection:
            return
        
        try:
            # Dump database to SQL
            sql_dump = '\n'.join(self.connection.iterdump())
            
            # Save to VFS
            with self.vfs.open(self.db_file, 'w') as f:
                f.write(sql_dump.encode())
        except:
            pass
    
    def _load_from_vfs(self):
        """Load database from VFS"""
        if not self.vfs or not self.connection:
            return
        
        try:
            # Read SQL dump from VFS
            with self.vfs.open(self.db_file, 'r') as f:
                sql_dump = f.read().decode()
            
            # Execute SQL dump
            self.connection.executescript(sql_dump)
        except:
            pass
    
    def create_table(self, table_name: str, columns: List[Column]) -> bool:
        """Create table"""
        if not self.cursor:
            return False
        
        try:
            # Generate CREATE TABLE statement
            column_defs = [col.to_sql() for col in columns]
            sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
            
            self.cursor.execute(sql)
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Create table error: {e}")
            return False
    
    def drop_table(self, table_name: str) -> bool:
        """Drop table"""
        if not self.cursor:
            return False
        
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.connection.commit()
            return True
        except:
            return False
    
    def insert(self, table_name: str, data: Dict[str, Any]) -> Optional[int]:
        """Insert data into table"""
        if not self.cursor:
            return None
        
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())
            
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            self.cursor.execute(sql, values)
            
            if not self.in_transaction:
                self.connection.commit()
            
            return self.cursor.lastrowid
        except Exception as e:
            print(f"Insert error: {e}")
            return None
    
    def select(self, table_name: str, columns: List[str] = None,
              where: str = None, params: Tuple = None,
              order_by: str = None, limit: int = None) -> List[Dict]:
        """Select data from table"""
        if not self.cursor:
            return []
        
        try:
            # Build SELECT statement
            col_str = ', '.join(columns) if columns else '*'
            sql = f"SELECT {col_str} FROM {table_name}"
            
            if where:
                sql += f" WHERE {where}"
            
            if order_by:
                sql += f" ORDER BY {order_by}"
            
            if limit:
                sql += f" LIMIT {limit}"
            
            # Execute query
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
            
            # Fetch results
            rows = self.cursor.fetchall()
            
            # Get column names
            column_names = [desc[0] for desc in self.cursor.description]
            
            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(column_names, row)))
            
            return results
        except Exception as e:
            print(f"Select error: {e}")
            return []
    
    def update(self, table_name: str, data: Dict[str, Any],
              where: str, params: Tuple = None) -> int:
        """Update data in table"""
        if not self.cursor:
            return 0
        
        try:
            # Build UPDATE statement
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {where}"
            
            # Combine values
            values = list(data.values())
            if params:
                values.extend(params)
            
            self.cursor.execute(sql, values)
            
            if not self.in_transaction:
                self.connection.commit()
            
            return self.cursor.rowcount
        except Exception as e:
            print(f"Update error: {e}")
            return 0
    
    def delete(self, table_name: str, where: str, params: Tuple = None) -> int:
        """Delete data from table"""
        if not self.cursor:
            return 0
        
        try:
            sql = f"DELETE FROM {table_name} WHERE {where}"
            
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
            
            if not self.in_transaction:
                self.connection.commit()
            
            return self.cursor.rowcount
        except Exception as e:
            print(f"Delete error: {e}")
            return 0
    
    def execute(self, sql: str, params: Tuple = None) -> bool:
        """Execute raw SQL"""
        if not self.cursor:
            return False
        
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
            
            if not self.in_transaction:
                self.connection.commit()
            
            return True
        except Exception as e:
            print(f"Execute error: {e}")
            return False
    
    def begin_transaction(self):
        """Begin transaction"""
        if self.connection:
            self.in_transaction = True
    
    def commit(self):
        """Commit transaction"""
        if self.connection:
            self.connection.commit()
            self.in_transaction = False
    
    def rollback(self):
        """Rollback transaction"""
        if self.connection:
            self.connection.rollback()
            self.in_transaction = False
    
    def get_tables(self) -> List[str]:
        """Get list of tables"""
        if not self.cursor:
            return []
        
        try:
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            return [row[0] for row in self.cursor.fetchall()]
        except:
            return []
    
    def get_table_info(self, table_name: str) -> List[Dict]:
        """Get table schema information"""
        if not self.cursor:
            return []
        
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            
            columns = []
            for row in self.cursor.fetchall():
                columns.append({
                    'cid': row[0],
                    'name': row[1],
                    'type': row[2],
                    'not_null': bool(row[3]),
                    'default': row[4],
                    'primary_key': bool(row[5])
                })
            
            return columns
        except:
            return []
    
    def create_index(self, index_name: str, table_name: str,
                    columns: List[str], unique: bool = False) -> bool:
        """Create index"""
        if not self.cursor:
            return False
        
        try:
            unique_str = "UNIQUE " if unique else ""
            col_str = ', '.join(columns)
            sql = f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} "
            sql += f"ON {table_name} ({col_str})"
            
            self.cursor.execute(sql)
            self.connection.commit()
            return True
        except:
            return False
    
    def drop_index(self, index_name: str) -> bool:
        """Drop index"""
        if not self.cursor:
            return False
        
        try:
            self.cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
            self.connection.commit()
            return True
        except:
            return False

class QueryBuilder:
    """SQL query builder"""
    
    def __init__(self):
        self.query_type = None
        self.table = None
        self.columns = []
        self.values = []
        self.where_conditions = []
        self.join_clauses = []
        self.order_by_clause = None
        self.group_by_clause = None
        self.having_clause = None
        self.limit_value = None
        self.offset_value = None
    
    def select(self, *columns) -> 'QueryBuilder':
        """Start SELECT query"""
        self.query_type = "SELECT"
        self.columns = list(columns) if columns else ['*']
        return self
    
    def insert_into(self, table: str) -> 'QueryBuilder':
        """Start INSERT query"""
        self.query_type = "INSERT"
        self.table = table
        return self
    
    def update(self, table: str) -> 'QueryBuilder':
        """Start UPDATE query"""
        self.query_type = "UPDATE"
        self.table = table
        return self
    
    def delete_from(self, table: str) -> 'QueryBuilder':
        """Start DELETE query"""
        self.query_type = "DELETE"
        self.table = table
        return self
    
    def from_table(self, table: str) -> 'QueryBuilder':
        """Set FROM table"""
        self.table = table
        return self
    
    def where(self, condition: str) -> 'QueryBuilder':
        """Add WHERE condition"""
        self.where_conditions.append(condition)
        return self
    
    def join(self, table: str, on: str, join_type: str = "INNER") -> 'QueryBuilder':
        """Add JOIN clause"""
        self.join_clauses.append(f"{join_type} JOIN {table} ON {on}")
        return self
    
    def order_by(self, column: str, direction: str = "ASC") -> 'QueryBuilder':
        """Add ORDER BY clause"""
        self.order_by_clause = f"{column} {direction}"
        return self
    
    def group_by(self, *columns) -> 'QueryBuilder':
        """Add GROUP BY clause"""
        self.group_by_clause = ', '.join(columns)
        return self
    
    def having(self, condition: str) -> 'QueryBuilder':
        """Add HAVING clause"""
        self.having_clause = condition
        return self
    
    def limit(self, value: int) -> 'QueryBuilder':
        """Add LIMIT clause"""
        self.limit_value = value
        return self
    
    def offset(self, value: int) -> 'QueryBuilder':
        """Add OFFSET clause"""
        self.offset_value = value
        return self
    
    def build(self) -> str:
        """Build SQL query"""
        if self.query_type == "SELECT":
            sql = f"SELECT {', '.join(self.columns)}"
            sql += f" FROM {self.table}"
            
            for join in self.join_clauses:
                sql += f" {join}"
            
            if self.where_conditions:
                sql += f" WHERE {' AND '.join(self.where_conditions)}"
            
            if self.group_by_clause:
                sql += f" GROUP BY {self.group_by_clause}"
            
            if self.having_clause:
                sql += f" HAVING {self.having_clause}"
            
            if self.order_by_clause:
                sql += f" ORDER BY {self.order_by_clause}"
            
            if self.limit_value:
                sql += f" LIMIT {self.limit_value}"
            
            if self.offset_value:
                sql += f" OFFSET {self.offset_value}"
            
            return sql
        
        elif self.query_type == "DELETE":
            sql = f"DELETE FROM {self.table}"
            
            if self.where_conditions:
                sql += f" WHERE {' AND '.join(self.where_conditions)}"
            
            return sql
        
        return ""

class ORM:
    """Simple Object-Relational Mapping"""
    
    def __init__(self, database: Database):
        self.database = database
        self.models: Dict[str, type] = {}
    
    def register_model(self, model_class: type):
        """Register model class"""
        table_name = model_class.__name__.lower() + 's'
        self.models[table_name] = model_class
        
        # Create table from model
        columns = []
        for attr_name, attr_type in model_class.__annotations__.items():
            if attr_type == int:
                data_type = DataType.INTEGER
            elif attr_type == float:
                data_type = DataType.REAL
            elif attr_type == str:
                data_type = DataType.TEXT
            else:
                data_type = DataType.BLOB
            
            column = Column(
                name=attr_name,
                data_type=data_type,
                primary_key=(attr_name == 'id'),
                auto_increment=(attr_name == 'id')
            )
            columns.append(column)
        
        self.database.create_table(table_name, columns)
    
    def save(self, obj) -> bool:
        """Save object to database"""
        table_name = obj.__class__.__name__.lower() + 's'
        
        data = {}
        for attr in obj.__class__.__annotations__:
            if hasattr(obj, attr):
                data[attr] = getattr(obj, attr)
        
        if 'id' in data and data['id']:
            # Update existing
            obj_id = data.pop('id')
            rows = self.database.update(table_name, data, "id = ?", (obj_id,))
            return rows > 0
        else:
            # Insert new
            new_id = self.database.insert(table_name, data)
            if new_id:
                obj.id = new_id
                return True
            return False
    
    def find(self, model_class: type, **kwargs) -> List:
        """Find objects by criteria"""
        table_name = model_class.__name__.lower() + 's'
        
        where_conditions = []
        params = []
        
        for key, value in kwargs.items():
            where_conditions.append(f"{key} = ?")
            params.append(value)
        
        where_clause = ' AND '.join(where_conditions) if where_conditions else None
        
        results = self.database.select(
            table_name,
            where=where_clause,
            params=tuple(params) if params else None
        )
        
        # Convert to objects
        objects = []
        for row in results:
            obj = model_class()
            for key, value in row.items():
                setattr(obj, key, value)
            objects.append(obj)
        
        return objects