"""Command execution for migrate CLI"""

import subprocess
from typing import List, Optional
import shutil

from .config import MigrateConfig
from .exceptions import MigrateNotFoundError


class MigrateCommand:
    """Base class for migrate CLI command execution"""

    def __init__(self, config: MigrateConfig):
        self.config = config
        self._check_migrate_command()

    def _check_migrate_command(self) -> None:
        """Check if migrate command is available"""
        if not shutil.which(self.config.command_path):
            raise MigrateNotFoundError(
                f"migrate command not found at: {self.config.command_path}. "
                "Please install golang-migrate/migrate first."
            )

    def _build_base_args(self) -> List[str]:
        """Build base command arguments"""
        return [
            self.config.command_path,
            "-database",
            self.config.database_url,
            "-path",
            str(self.config.migrations_path),
        ]

    def execute(self, args: List[str]) -> subprocess.CompletedProcess:
        """Execute migrate command"""
        return subprocess.run(
            args, capture_output=True, text=True, check=False
        )

    def parse_error(self, stderr: str) -> Optional[str]:
        """Parse error message from stderr"""
        if "dirty database" in stderr.lower():
            return "Database is in dirty state"
        if "no migration" in stderr.lower():
            return "No migrations found"
        if "already at the latest" in stderr.lower():
            return "Already at latest version"
        if "file does not exist" in stderr.lower():
            return "Migration file not found"
        if "connection refused" in stderr.lower():
            return "Database connection failed"
        return stderr.strip() if stderr else None
