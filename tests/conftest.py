"""
Pytest configuration for migrate-wrapper tests
"""
import pytest


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "requires_pglite: marks test as requiring PGlite for PostgreSQL testing"
    )


def pytest_collection_modifyitems(config, items):
    """Add markers to test items based on their module"""
    for item in items:
        # Add requires_pglite marker to all PostgreSQL tests
        if "test_migrate_wrapper_postgres" in str(item.fspath):
            item.add_marker(pytest.mark.requires_pglite)