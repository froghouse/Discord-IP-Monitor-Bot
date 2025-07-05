"""
Refactored configuration tests that import from modular structure.

This file maintains backward compatibility by importing and re-exporting
all test classes from the new modular configuration test structure.
"""

# Import all test classes from the new modular structure
from .config.test_environment_loading import TestAppConfigEnvironmentVariableLoading
from .config.test_validation import TestAppConfigValidation
from .config.test_file_persistence import TestAppConfigFilePersistence
from .config.test_edge_cases import (
    TestAppConfigValidationErrorHandling,
    TestAppConfigEdgeCases,
    TestAppConfigFileHandlingEdgeCases
)
from .config.test_runtime_and_migration import (
    TestAppConfigRuntimeUpdates,
    TestAppConfigMigration
)

# Re-export all test classes for compatibility
__all__ = [
    'TestAppConfigEnvironmentVariableLoading',
    'TestAppConfigValidation', 
    'TestAppConfigFilePersistence',
    'TestAppConfigValidationErrorHandling',
    'TestAppConfigEdgeCases',
    'TestAppConfigFileHandlingEdgeCases',
    'TestAppConfigRuntimeUpdates',
    'TestAppConfigMigration'
]