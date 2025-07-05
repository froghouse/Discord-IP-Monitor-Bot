"""
Storage operations for the IP Monitor Bot using SQLite for data integrity.
"""

from datetime import datetime
import json
import logging
import os
import shutil
import sqlite3
import tempfile
from typing import Any

from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class SQLiteIPStorage:
    """
    Handles storage and retrieval of IP address data using SQLite database.
    """

    def __init__(self, db_file: str, history_size: int) -> None:
        """
        Initialize the SQLite storage handler.

        Args:
            db_file: Path to SQLite database file
            history_size: Maximum number of IP records to store in history
        """
        self.db_file = db_file
        self.history_size = history_size
        self._init_database()

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        # SQLiteIPStorage uses context managers for all operations,
        # so there are no persistent connections to close.
        return False

    def close(self):
        """Close any resources and clean up connections."""
        # SQLiteIPStorage uses context managers for all operations,
        # so there are no persistent connections to close.
        # This method is provided for API compatibility.
        pass

    def _init_database(self) -> None:
        """Initialize the SQLite database with required tables."""
        # Create directory if it doesn't exist
        directory = os.path.dirname(self.db_file)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                return

        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

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

                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ip_history_timestamp 
                    ON ip_history(timestamp)
                """)

                conn.commit()
                service_health.record_success("storage", "init_database")
                logger.info("SQLite database initialized successfully")

        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            service_health.record_failure(
                "storage", f"Database init error: {e}", "init_database"
            )

    def load_ip_history(self) -> list[dict[str, Any]]:
        """
        Load the IP address history from database.

        Returns:
            List of dictionaries containing IP addresses and timestamps
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT ip, timestamp FROM ip_history 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """,
                    (self.history_size,),
                )

                rows = cursor.fetchall()
                history = [{"ip": row[0], "timestamp": row[1]} for row in rows]

                service_health.record_success("storage", "read_file")
                return list(reversed(history))  # Return chronological order

        except sqlite3.Error as e:
            logger.error(f"Error loading IP history: {e}")
            service_health.record_failure(
                "storage", f"Error loading IP history: {e}", "read_file"
            )
            return []

    def save_ip_history(self, history: list[dict[str, Any]]) -> bool:
        """
        Save the IP address history to database.
        Note: This method is kept for compatibility but SQLite handles history automatically.

        Args:
            history: List of dictionaries containing IP addresses and timestamps

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

                # Clear existing history
                cursor.execute("DELETE FROM ip_history")

                # Insert new history records
                for record in history[-self.history_size :]:
                    cursor.execute(
                        """
                        INSERT INTO ip_history (ip, timestamp) 
                        VALUES (?, ?)
                    """,
                        (record["ip"], record["timestamp"]),
                    )

                conn.commit()
                service_health.record_success("storage", "write_file")
                return True

        except (sqlite3.Error, KeyError) as e:
            logger.error(f"Error saving IP history: {e}")
            service_health.record_failure(
                "storage", f"Error saving IP history: {e}", "write_file"
            )
            return False

    def load_last_ip(self) -> str | None:
        """
        Load the last known IP from database.

        Returns:
            IP address string or None if unsuccessful
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ip FROM current_ip 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if row and self.is_valid_ip(row[0]):
                    service_health.record_success("storage", "read_file")
                    return row[0]

                if row:
                    logger.warning("Invalid IP in database")
                    service_health.record_failure(
                        "storage", "Invalid IP in database", "read_file"
                    )

        except sqlite3.Error as e:
            logger.error(f"Error loading last IP: {e}")
            service_health.record_failure(
                "storage", f"Error loading last IP: {e}", "read_file"
            )

        return None

    def save_current_ip(self, ip: str) -> bool:
        """
        Save the current IP to database and update history if changed.

        Args:
            ip: The IP address to save

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_valid_ip(ip):
            logger.error(f"Invalid IP address: {ip}")
            return False

        timestamp = datetime.now().isoformat()
        success = True

        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

                # Get the last IP to check if it changed
                last_ip = self.load_last_ip()

                # Update current IP (replace the single record)
                cursor.execute("DELETE FROM current_ip")
                cursor.execute(
                    """
                    INSERT INTO current_ip (ip, timestamp) 
                    VALUES (?, ?)
                """,
                    (ip, timestamp),
                )

                # Add to history only if IP has changed
                if last_ip != ip:
                    cursor.execute(
                        """
                        INSERT INTO ip_history (ip, timestamp) 
                        VALUES (?, ?)
                    """,
                        (ip, timestamp),
                    )

                    # Maintain history size limit
                    cursor.execute(
                        """
                        DELETE FROM ip_history 
                        WHERE id NOT IN (
                            SELECT id FROM ip_history 
                            ORDER BY created_at DESC 
                            LIMIT ?
                        )
                    """,
                        (self.history_size,),
                    )

                conn.commit()
                service_health.record_success("storage", "write_file")

        except sqlite3.Error as e:
            logger.error(f"Error saving current IP: {e}")
            service_health.record_failure(
                "storage", f"Error saving current IP: {e}", "write_file"
            )
            success = False

        return success

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """
        Validate if the given string is a valid IPv4 or IPv6 address.

        Args:
            ip: The IP address to validate

        Returns:
            bool: True if the IP is valid, False otherwise
        """
        import ipaddress

        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def migrate_from_json(self, ip_file: str, history_file: str) -> bool:
        """
        Migrate existing JSON data to SQLite database.

        Args:
            ip_file: Path to current IP JSON file
            history_file: Path to history JSON file

        Returns:
            bool: True if migration successful, False otherwise
        """
        try:
            # Load existing JSON data
            current_ip_data = None
            if os.path.exists(ip_file):
                with open(ip_file) as f:
                    current_ip_data = json.load(f)

            history_data = []
            if os.path.exists(history_file):
                with open(history_file) as f:
                    history_data = json.load(f)

            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

                # Migrate current IP
                if current_ip_data and "ip" in current_ip_data:
                    cursor.execute("DELETE FROM current_ip")
                    cursor.execute(
                        """
                        INSERT INTO current_ip (ip, timestamp) 
                        VALUES (?, ?)
                    """,
                        (
                            current_ip_data["ip"],
                            current_ip_data.get(
                                "timestamp", datetime.now().isoformat()
                            ),
                        ),
                    )

                # Migrate history
                if history_data:
                    cursor.execute("DELETE FROM ip_history")
                    for record in history_data[-self.history_size :]:
                        if "ip" in record and "timestamp" in record:
                            cursor.execute(
                                """
                                INSERT INTO ip_history (ip, timestamp) 
                                VALUES (?, ?)
                            """,
                                (record["ip"], record["timestamp"]),
                            )

                conn.commit()
                logger.info("Successfully migrated JSON data to SQLite")
                return True

        except (OSError, json.JSONDecodeError, sqlite3.Error) as e:
            logger.error(f"Error migrating JSON data: {e}")
            return False


class IPStorage:
    """
    Handles storage and retrieval of IP address data.
    """

    def __init__(self, ip_file: str, history_file: str, history_size: int) -> None:
        """
        Initialize the storage handler.

        Args:
            ip_file: Path to file storing the current IP
            history_file: Path to file storing IP history
            history_size: Maximum number of IP records to store
        """
        self.ip_file = ip_file
        self.history_file = history_file
        self.history_size = history_size

    def atomic_write_json(self, file_path: str, data: Any) -> bool:
        """
        Write data to a JSON file atomically using a temporary file.

        Args:
            file_path: Path to the target file
            data: Data to write (must be JSON serializable)

        Returns:
            bool: True if successful, False otherwise
        """
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                return False

        # Create a temporary file in the same directory
        try:
            fd, temp_path = tempfile.mkstemp(dir=directory or os.getcwd())

            # Close the file descriptor returned by mkstemp
            os.close(fd)

            # Write the data to the temporary file
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
                # Ensure data is written to disk
                f.flush()
                os.fsync(f.fileno())

            # Rename the temporary file to the target file (atomic operation)
            shutil.move(temp_path, file_path)

            service_health.record_success("storage", "write_file")
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            service_health.record_failure(
                "storage", f"Write error to {file_path}: {e}", "write_file"
            )
            # Clean up the temporary file if it exists
            if "temp_path" in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as remove_error:
                    logger.warning(
                        f"Failed to remove temporary file {temp_path}: {remove_error}"
                    )
            return False

    def load_ip_history(self) -> list[dict[str, Any]]:
        """
        Load the IP address history from file.

        Returns:
            List of dictionaries containing IP addresses and timestamps
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        service_health.record_success("storage", "read_file")
                        return data
                    logger.warning("Invalid format in IP history file")
                    service_health.record_failure(
                        "storage", "Invalid format in IP history file", "read_file"
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error loading IP history: {e}")
                service_health.record_failure(
                    "storage", f"Error loading IP history: {e}", "read_file"
                )
        return []

    def save_ip_history(self, history: list[dict[str, Any]]) -> bool:
        """
        Save the IP address history to file.

        Args:
            history: List of dictionaries containing IP addresses and timestamps

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Limit the history size
            if len(history) > self.history_size:
                history = history[-self.history_size :]

            return self.atomic_write_json(self.history_file, history)
        except Exception as e:
            logger.error(f"Error saving IP history: {e}")
            return False

    def load_last_ip(self) -> str | None:
        """
        Load the last known IP from file.

        Returns:
            IP address string or None if unsuccessful
        """
        if os.path.exists(self.ip_file):
            try:
                with open(self.ip_file) as f:
                    data = json.load(f)
                    ip = data.get("ip")
                    if ip and self.is_valid_ip(ip):
                        service_health.record_success("storage", "read_file")
                        return ip
                    logger.warning("Invalid or missing IP in last_ip.json")
                    service_health.record_failure(
                        "storage", "Invalid or missing IP in last_ip.json", "read_file"
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error loading last IP: {e}")
                service_health.record_failure(
                    "storage", f"Error loading last IP: {e}", "read_file"
                )
        return None

    def save_current_ip(self, ip: str) -> bool:
        """
        Save the current IP to file and update history.

        Args:
            ip: The IP address to save

        Returns:
            bool: True if successful, False otherwise
        """
        timestamp = datetime.now().isoformat()
        success = True

        # Save to last_ip.json
        if not self.atomic_write_json(self.ip_file, {"ip": ip, "timestamp": timestamp}):
            success = False

        # Update IP history only if the IP has changed
        try:
            last_ip = self.load_last_ip()
            if last_ip != ip:  # Only add to history if IP has changed
                history = self.load_ip_history()
                history.append({"ip": ip, "timestamp": timestamp})
                if not self.save_ip_history(history):
                    success = False
        except Exception as e:
            logger.error(f"Error updating IP history: {e}")
            success = False

        return success

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """
        Validate if the given string is a valid IPv4 or IPv6 address.

        Args:
            ip: The IP address to validate

        Returns:
            bool: True if the IP is valid, False otherwise
        """
        import ipaddress

        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
