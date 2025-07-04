"""Database cleanup utilities for testing.

This module provides comprehensive database cleanup utilities for:
- Automatic test database cleanup
- Transaction rollback testing
- Data isolation between tests
- Performance benchmarking cleanup
- Test data seeding and teardown
"""

import os
import sqlite3
import tempfile
import shutil
import logging
from typing import Optional, List, Dict, Any, Callable, Union
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from unittest.mock import Mock


@dataclass
class DatabaseBackup:
    """Represents a database backup for test restoration."""
    
    backup_path: str
    original_path: str
    timestamp: datetime
    test_name: str
    
    def restore(self) -> bool:
        """Restore the database from backup."""
        try:
            shutil.copy2(self.backup_path, self.original_path)
            return True
        except Exception as e:
            logging.error(f"Failed to restore database backup: {e}")
            return False
    
    def cleanup(self) -> bool:
        """Remove the backup file."""
        try:
            if os.path.exists(self.backup_path):
                os.unlink(self.backup_path)
            return True
        except Exception as e:
            logging.error(f"Failed to cleanup database backup: {e}")
            return False


class DatabaseTestManager:
    """Manages database setup and cleanup for tests."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.temp_db_path: Optional[str] = None
        self.backup: Optional[DatabaseBackup] = None
        self.logger = logging.getLogger(__name__)
        self.connections: List[sqlite3.Connection] = []
        self.temp_files: List[str] = []
    
    def create_temp_database(self, test_name: str = "test") -> str:
        """Create a temporary database for testing."""
        
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.db', prefix=f'test_{test_name}_')
        os.close(temp_fd)
        
        self.temp_db_path = temp_path
        self.temp_files.append(temp_path)
        
        # Initialize database schema
        self._initialize_test_schema(temp_path)
        
        self.logger.info(f"Created temporary database: {temp_path}")
        return temp_path
    
    def _initialize_test_schema(self, db_path: str) -> None:
        """Initialize the test database with required schema."""
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Create current_ip table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS current_ip (
                    id INTEGER PRIMARY KEY,
                    ip TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create ip_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ip_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ip_history_timestamp 
                ON ip_history(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ip_history_created_at 
                ON ip_history(created_at)
            """)
            
            # Create test-specific tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_metadata (
                    id INTEGER PRIMARY KEY,
                    test_name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data TEXT
                )
            """)
            
            conn.commit()
            
        finally:
            conn.close()
    
    def backup_database(self, test_name: str) -> Optional[DatabaseBackup]:
        """Create a backup of the current database."""
        
        if not self.db_path or not os.path.exists(self.db_path):
            self.logger.warning("No database to backup")
            return None
        
        # Create backup file
        backup_fd, backup_path = tempfile.mkstemp(
            suffix='.db', 
            prefix=f'backup_{test_name}_'
        )
        os.close(backup_fd)
        
        try:
            shutil.copy2(self.db_path, backup_path)
            
            self.backup = DatabaseBackup(
                backup_path=backup_path,
                original_path=self.db_path,
                timestamp=datetime.now(),
                test_name=test_name
            )
            
            self.temp_files.append(backup_path)
            self.logger.info(f"Created database backup: {backup_path}")
            return self.backup
            
        except Exception as e:
            self.logger.error(f"Failed to create database backup: {e}")
            if os.path.exists(backup_path):
                os.unlink(backup_path)
            return None
    
    def restore_database(self) -> bool:
        """Restore database from backup."""
        
        if not self.backup:
            self.logger.warning("No backup to restore")
            return False
        
        return self.backup.restore()
    
    def clear_database(self, db_path: Optional[str] = None) -> bool:
        """Clear all data from database tables."""
        
        target_path = db_path or self.temp_db_path or self.db_path
        
        if not target_path:
            self.logger.error("No database path specified")
            return False
        
        try:
            conn = sqlite3.connect(target_path)
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Clear all tables
            for table in tables:
                if table != 'sqlite_sequence':  # Skip SQLite internal table
                    cursor.execute(f"DELETE FROM {table}")
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleared all data from database: {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear database: {e}")
            return False
    
    def seed_test_data(
        self, 
        db_path: Optional[str] = None,
        current_ip: Optional[str] = None,
        ip_history: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Seed database with test data."""
        
        target_path = db_path or self.temp_db_path or self.db_path
        
        if not target_path:
            self.logger.error("No database path specified")
            return False
        
        try:
            conn = sqlite3.connect(target_path)
            cursor = conn.cursor()
            
            # Insert current IP if provided
            if current_ip:
                cursor.execute(
                    "INSERT OR REPLACE INTO current_ip (id, ip, timestamp) VALUES (1, ?, ?)",
                    (current_ip, datetime.now().isoformat())
                )
            
            # Insert IP history if provided
            if ip_history:
                for record in ip_history:
                    cursor.execute(
                        "INSERT INTO ip_history (ip, timestamp) VALUES (?, ?)",
                        (record['ip'], record['timestamp'])
                    )
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Seeded test data in database: {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to seed test data: {e}")
            return False
    
    @contextmanager
    def transaction_rollback_test(self, db_path: Optional[str] = None):
        """Context manager for testing transaction rollback."""
        
        target_path = db_path or self.temp_db_path or self.db_path
        
        if not target_path:
            raise ValueError("No database path specified")
        
        conn = sqlite3.connect(target_path)
        self.connections.append(conn)
        
        try:
            # Begin transaction
            conn.execute("BEGIN")
            
            yield conn
            
        except Exception as e:
            # Rollback on exception
            conn.rollback()
            self.logger.info(f"Transaction rolled back due to: {e}")
            raise
        
        finally:
            # Always rollback for testing
            conn.rollback()
            conn.close()
            
            if conn in self.connections:
                self.connections.remove(conn)
    
    def cleanup_all(self) -> None:
        """Clean up all resources created during testing."""
        
        # Close all connections
        for conn in self.connections:
            try:
                conn.close()
            except Exception as e:
                self.logger.warning(f"Error closing connection: {e}")
        
        self.connections.clear()
        
        # Clean up backup
        if self.backup:
            self.backup.cleanup()
            self.backup = None
        
        # Remove all temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    self.logger.debug(f"Removed temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
        
        self.temp_files.clear()
        
        # Reset paths
        self.temp_db_path = None
        self.db_path = None
        
        self.logger.info("Database cleanup completed")


class DatabasePerformanceCleanup:
    """Specialized cleanup for performance testing."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.initial_record_counts: Dict[str, int] = {}
    
    def record_initial_state(self) -> None:
        """Record initial database state for cleanup comparison."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Count records in each table
            for table in tables:
                if table != 'sqlite_sequence':
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    self.initial_record_counts[table] = count
            
            self.logger.info(f"Recorded initial state: {self.initial_record_counts}")
            
        finally:
            conn.close()
    
    def cleanup_performance_test_data(self) -> Dict[str, int]:
        """Clean up data created during performance tests."""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cleaned_counts = {}
        
        try:
            for table, initial_count in self.initial_record_counts.items():
                # Get current count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                current_count = cursor.fetchone()[0]
                
                # Calculate records to remove
                excess_records = current_count - initial_count
                
                if excess_records > 0:
                    # Remove excess records (keeping the oldest ones)
                    if table == 'ip_history':
                        cursor.execute(f"""
                            DELETE FROM {table} 
                            WHERE id IN (
                                SELECT id FROM {table} 
                                ORDER BY created_at DESC 
                                LIMIT {excess_records}
                            )
                        """)
                    else:
                        cursor.execute(f"""
                            DELETE FROM {table} 
                            WHERE id IN (
                                SELECT id FROM {table} 
                                ORDER BY id DESC 
                                LIMIT {excess_records}
                            )
                        """)
                    
                    cleaned_counts[table] = excess_records
                    
                else:
                    cleaned_counts[table] = 0
            
            conn.commit()
            
            self.logger.info(f"Performance test cleanup completed: {cleaned_counts}")
            return cleaned_counts
            
        finally:
            conn.close()
    
    def vacuum_database(self) -> bool:
        """Vacuum database to reclaim space after cleanup."""
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()
            
            self.logger.info("Database vacuum completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to vacuum database: {e}")
            return False


class DatabaseFixtureManager:
    """Manages database fixtures for consistent testing."""
    
    def __init__(self):
        self.fixtures: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_fixture(self, name: str, fixture_func: Callable) -> None:
        """Register a database fixture."""
        self.fixtures[name] = fixture_func
        self.logger.debug(f"Registered fixture: {name}")
    
    def apply_fixture(self, name: str, db_path: str, **kwargs) -> bool:
        """Apply a registered fixture to database."""
        
        if name not in self.fixtures:
            self.logger.error(f"Unknown fixture: {name}")
            return False
        
        try:
            fixture_func = self.fixtures[name]
            fixture_func(db_path, **kwargs)
            
            self.logger.info(f"Applied fixture '{name}' to database: {db_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply fixture '{name}': {e}")
            return False
    
    def list_fixtures(self) -> List[str]:
        """List all registered fixtures."""
        return list(self.fixtures.keys())


# Default fixture functions
def empty_database_fixture(db_path: str, **kwargs) -> None:
    """Fixture that creates an empty database."""
    manager = DatabaseTestManager(db_path)
    manager.clear_database()


def single_ip_fixture(db_path: str, ip: str = "192.168.1.1", **kwargs) -> None:
    """Fixture that creates a database with a single IP."""
    manager = DatabaseTestManager(db_path)
    manager.clear_database()
    manager.seed_test_data(current_ip=ip)


def ip_history_fixture(db_path: str, history_count: int = 10, **kwargs) -> None:
    """Fixture that creates a database with IP history."""
    from .test_data_generators import IPHistoryGenerator
    
    manager = DatabaseTestManager(db_path)
    manager.clear_database()
    
    history = IPHistoryGenerator.generate_ip_history(history_count)
    history_data = [record.to_dict() for record in history]
    
    manager.seed_test_data(
        current_ip=history[-1].ip,
        ip_history=history_data
    )


def large_dataset_fixture(db_path: str, record_count: int = 1000, **kwargs) -> None:
    """Fixture that creates a large dataset for performance testing."""
    from .test_data_generators import DatabaseRecordGenerator
    
    manager = DatabaseTestManager(db_path)
    manager.clear_database()
    
    bulk_data = DatabaseRecordGenerator.generate_bulk_test_data(
        current_ip_count=1,
        history_count=record_count
    )
    
    # Insert current IP
    current_ip_data = bulk_data["current_ip"][0]
    manager.seed_test_data(current_ip=current_ip_data[0])
    
    # Insert history in batches
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.executemany(
            "INSERT INTO ip_history (ip, timestamp) VALUES (?, ?)",
            bulk_data["ip_history"]
        )
        conn.commit()
        
    finally:
        conn.close()


# Initialize default fixture manager
default_fixture_manager = DatabaseFixtureManager()
default_fixture_manager.register_fixture("empty", empty_database_fixture)
default_fixture_manager.register_fixture("single_ip", single_ip_fixture)
default_fixture_manager.register_fixture("ip_history", ip_history_fixture)
default_fixture_manager.register_fixture("large_dataset", large_dataset_fixture)


# Convenience functions
def create_test_database(test_name: str = "test") -> str:
    """Create a temporary test database."""
    manager = DatabaseTestManager()
    return manager.create_temp_database(test_name)


def cleanup_test_database(db_path: str) -> None:
    """Clean up a test database."""
    manager = DatabaseTestManager(db_path)
    manager.cleanup_all()


@contextmanager
def isolated_database_test(test_name: str = "test", fixture: Optional[str] = None):
    """Context manager for isolated database testing."""
    
    manager = DatabaseTestManager()
    db_path = manager.create_temp_database(test_name)
    
    try:
        # Apply fixture if specified
        if fixture:
            default_fixture_manager.apply_fixture(fixture, db_path)
        
        yield db_path
        
    finally:
        manager.cleanup_all()


@contextmanager
def performance_test_database(
    test_name: str = "performance_test",
    initial_records: int = 100
):
    """Context manager for performance testing with automatic cleanup."""
    
    manager = DatabaseTestManager()
    db_path = manager.create_temp_database(test_name)
    
    # Apply large dataset fixture
    default_fixture_manager.apply_fixture(
        "large_dataset", 
        db_path, 
        record_count=initial_records
    )
    
    # Create performance cleanup manager
    perf_cleanup = DatabasePerformanceCleanup(db_path)
    perf_cleanup.record_initial_state()
    
    try:
        yield db_path
        
    finally:
        # Clean up performance test data
        perf_cleanup.cleanup_performance_test_data()
        perf_cleanup.vacuum_database()
        
        # Clean up test database
        manager.cleanup_all()


# Async versions for async testing
async def async_create_test_database(test_name: str = "test") -> str:
    """Async version of create_test_database."""
    return await asyncio.get_event_loop().run_in_executor(
        None, create_test_database, test_name
    )


async def async_cleanup_test_database(db_path: str) -> None:
    """Async version of cleanup_test_database."""
    await asyncio.get_event_loop().run_in_executor(
        None, cleanup_test_database, db_path
    )


class AsyncDatabaseTestManager:
    """Async version of DatabaseTestManager."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.sync_manager = DatabaseTestManager(db_path)
        self.loop = asyncio.get_event_loop()
    
    async def create_temp_database(self, test_name: str = "test") -> str:
        """Async create temporary database."""
        return await self.loop.run_in_executor(
            None, self.sync_manager.create_temp_database, test_name
        )
    
    async def clear_database(self, db_path: Optional[str] = None) -> bool:
        """Async clear database."""
        return await self.loop.run_in_executor(
            None, self.sync_manager.clear_database, db_path
        )
    
    async def seed_test_data(
        self, 
        db_path: Optional[str] = None,
        current_ip: Optional[str] = None,
        ip_history: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Async seed test data."""
        return await self.loop.run_in_executor(
            None, self.sync_manager.seed_test_data, db_path, current_ip, ip_history
        )
    
    async def cleanup_all(self) -> None:
        """Async cleanup all resources."""
        await self.loop.run_in_executor(None, self.sync_manager.cleanup_all)