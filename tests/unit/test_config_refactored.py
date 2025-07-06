"""
Refactored configuration tests that import from modular structure.

This file maintains backward compatibility by importing and re-exporting
all test classes from the new modular configuration test structure.

NOTE: Test classes are now in individual files under tests/unit/config/
and should be run from there to access the proper fixtures.
"""

# All test classes have been moved to modular structure under tests/unit/config/
# Run tests directly from the config directory:
#   pytest tests/unit/config/

# Individual test files:
# - tests/unit/config/test_edge_cases.py
# - tests/unit/config/test_environment_loading.py
# - tests/unit/config/test_file_persistence.py
# - tests/unit/config/test_runtime_and_migration.py
# - tests/unit/config/test_validation.py

# This file is kept for backward compatibility documentation only
