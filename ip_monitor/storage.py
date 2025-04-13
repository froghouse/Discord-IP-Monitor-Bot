"""
File storage operations for the IP Monitor Bot.
"""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            # Clean up the temporary file if it exists
            if "temp_path" in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as remove_error:
                    logger.warning(
                        f"Failed to remove temporary file {temp_path}: {remove_error}"
                    )
            return False

    def load_ip_history(self) -> List[Dict[str, Any]]:
        """
        Load the IP address history from file.

        Returns:
            List of dictionaries containing IP addresses and timestamps
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    logger.warning("Invalid format in IP history file")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading IP history: {e}")
        return []

    def save_ip_history(self, history: List[Dict[str, Any]]) -> bool:
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

    def load_last_ip(self) -> Optional[str]:
        """
        Load the last known IP from file.

        Returns:
            IP address string or None if unsuccessful
        """
        if os.path.exists(self.ip_file):
            try:
                with open(self.ip_file, "r") as f:
                    data = json.load(f)
                    ip = data.get("ip")
                    if ip and self.is_valid_ip(ip):
                        return ip
                    logger.warning("Invalid or missing IP in last_ip.json")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading last IP: {e}")
        return None

    def load_last_ip_timestamp(self) -> Optional[str]:
        """
        Load the timestamp of the last known IP from file.

        Returns:
            Timestamp string or None if unsuccessful
        """
        if os.path.exists(self.ip_file):
            try:
                with open(self.ip_file, "r") as f:
                    data = json.load(f)
                    timestamp = data.get("timestamp")
                    if timestamp:
                        return timestamp
                    logger.warning("Invalid or missing timestamp in last_ip.json")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading last IP timestamp: {e}")
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
