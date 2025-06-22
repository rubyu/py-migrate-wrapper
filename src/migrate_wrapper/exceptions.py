"""Exceptions for migrate-wrapper"""


class MigrateError(Exception):
    """Base exception for migrate-wrapper"""

    pass


class MigrateDirtyError(MigrateError):
    """Exception raised when database is in dirty state"""

    pass


class MigrateNotFoundError(MigrateError):
    """Exception raised when migrate command is not found"""

    pass


class MigrationNotFoundError(MigrateError):
    """Exception raised when migration file is not found"""

    pass


class MigrateConnectionError(MigrateError):
    """Exception raised when database connection fails"""

    pass
