"""Configuration for migrate-wrapper"""

from pathlib import Path
from typing import Union


class MigrateConfig:
    """Configuration for migrate command"""

    def __init__(
        self,
        database_url: str,
        migrations_path: Union[str, Path],
        table_name: str = "schema_migrations",
        command_path: str = "migrate",
    ):
        self.database_url = database_url
        self.migrations_path = Path(migrations_path)
        self.table_name = table_name
        self.command_path = command_path

    def validate(self) -> None:
        """Validate configuration"""
        if not self.database_url:
            raise ValueError("Database URL is required")
        if not self.migrations_path.exists():
            raise ValueError(f"Migrations path does not exist: {self.migrations_path}")
