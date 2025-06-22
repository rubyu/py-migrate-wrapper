"""Main MigrateWrapper implementation"""

import re
from typing import Optional, List

from .config import MigrateConfig
from .command import MigrateCommand
from .scanner import MigrationScanner
from .models import (
    Migration,
    MigrationResult,
    DatabaseInfo,
    ValidationResult,
    MissingDownFile,
)
from .exceptions import MigrateError, MigrateDirtyError


class MigrateWrapper:
    """Main wrapper class for migrate tool"""

    def __init__(self, config: MigrateConfig):
        self.config = config
        self.config.validate()
        self.command = MigrateCommand(config)
        self.scanner = MigrationScanner(config.migrations_path)

    def create(
        self, name: str, sequential: bool = True, extension: str = "sql"
    ) -> Migration:
        """Create new migration files"""
        args = self.command._build_base_args()
        args.extend(["create", "-ext", extension])

        if sequential:
            args.extend(["-seq", name])
        else:
            args.append(name)

        result = self.command.execute(args)

        if result.returncode != 0:
            raise MigrateError(f"Failed to create migration: {result.stderr}")

        # Parse created files from output and rescan
        migrations_before = set(m.version for m in self.scanner.scan())
        migrations_after = self.scanner.scan()

        # Find the newly created migration
        for migration in migrations_after:
            if migration.version not in migrations_before:
                return migration

        # If sequential, return the latest migration
        if migrations_after:
            return migrations_after[-1]

        raise MigrateError("Could not find created migration")

    def up(self, steps: Optional[int] = None) -> MigrationResult:
        """Apply migrations forward"""
        args = self.command._build_base_args()
        args.append("up")

        if steps is not None:
            args.append(str(steps))

        result = self.command.execute(args)

        if result.returncode == 0:
            return MigrationResult(
                success=True,
                version=self.version(),
                message="Migrations applied successfully",
            )
        else:
            error_msg = self.command.parse_error(result.stderr)
            is_dirty = "dirty" in result.stderr.lower()

            if is_dirty:
                raise MigrateDirtyError(error_msg or "Database is in dirty state")

            return MigrationResult(
                success=False,
                version=self.version(),
                message=error_msg or "Migration failed",
                dirty=is_dirty,
            )

    def down(self, steps: Optional[int] = None) -> MigrationResult:
        """Rollback migrations"""
        args = self.command._build_base_args()
        args.append("down")

        if steps is not None:
            args.append(str(steps))
        else:
            # down without args means rollback all
            args.append("-all")

        result = self.command.execute(args)

        if result.returncode == 0:
            return MigrationResult(
                success=True,
                version=self.version(),
                message="Migrations rolled back successfully",
            )
        else:
            error_msg = self.command.parse_error(result.stderr)
            is_dirty = "dirty" in result.stderr.lower()

            if is_dirty:
                raise MigrateDirtyError(error_msg or "Database is in dirty state")

            return MigrationResult(
                success=False,
                version=self.version(),
                message=error_msg or "Rollback failed",
                dirty=is_dirty,
            )

    def goto(self, version: int) -> MigrationResult:
        """Migrate to specific version"""
        args = self.command._build_base_args()
        args.extend(["goto", str(version)])

        result = self.command.execute(args)

        if result.returncode == 0:
            return MigrationResult(
                success=True,
                version=version if version > 0 else None,
                message=f"Migrated to version {version}",
            )
        else:
            error_msg = self.command.parse_error(result.stderr)
            is_dirty = "dirty" in result.stderr.lower()

            if is_dirty:
                raise MigrateDirtyError(error_msg or "Database is in dirty state")

            return MigrationResult(
                success=False,
                version=self.version(),
                message=error_msg or "Goto failed",
                dirty=is_dirty,
            )

    def force(self, version: int) -> MigrationResult:
        """Force set version without running migrations"""
        args = self.command._build_base_args()
        args.extend(["force", str(version)])

        result = self.command.execute(args)

        if result.returncode == 0:
            return MigrationResult(
                success=True,
                version=version if version > 0 else None,
                message=f"Forced version to {version}",
                dirty=False,
            )
        else:
            return MigrationResult(
                success=False,
                version=self.version(),
                message=(self.command.parse_error(result.stderr) or "Force failed"),
            )

    def drop(self, force: bool = False) -> MigrationResult:
        """Drop entire database"""
        args = self.command._build_base_args()
        args.append("drop")

        if force:
            args.append("-f")

        result = self.command.execute(args)

        if result.returncode == 0:
            return MigrationResult(
                success=True,
                version=None,
                message="Database dropped successfully",
            )
        else:
            return MigrationResult(
                success=False,
                version=self.version(),
                message=(self.command.parse_error(result.stderr) or "Drop failed"),
            )

    def version(self) -> Optional[int]:
        """Get current version"""
        args = self.command._build_base_args()
        args.append("version")

        result = self.command.execute(args)

        if result.returncode == 0:
            # Check stdout first, then stderr if stdout is empty
            # golang-migrate version command outputs to stderr
            output = (result.stdout or "").strip()
            if not output and result.stderr:
                output = result.stderr.strip()
            
            if output:
                # Parse version from output
                # Expected formats:
                # - "1" (just version number)
                # - "version: 1"
                # - "1 (dirty)"
                # - "version: 1 (dirty)"
                match = re.search(r"\b(\d+)\b", output)
                if match:
                    return int(match.group(1))

        return None

    def status(self) -> DatabaseInfo:
        """Get current database migration status"""
        args = self.command._build_base_args()
        args.append("version")

        result = self.command.execute(args)

        version = None
        dirty = False

        if result.returncode == 0:
            # Check stdout first, then stderr if stdout is empty
            # golang-migrate version command outputs to stderr
            output = (result.stdout or "").strip()
            if not output and result.stderr:
                output = result.stderr.strip()
            
            if output:
                # Extract version
                match = re.search(r"\b(\d+)\b", output)
                if match:
                    version = int(match.group(1))

                # Check if dirty
                dirty = "dirty" in output.lower()

        return DatabaseInfo(version=version, dirty=dirty)

    def list_migrations(self) -> List[Migration]:
        """List all available migrations"""
        return self.scanner.scan()

    def validate_migrations(self) -> ValidationResult:
        """Validate migration files and sequence"""
        migrations = self.list_migrations()
        gaps = self.scanner.find_gaps(migrations)
        missing_down = [m for m in migrations if not m.has_down_file()]

        missing_down_files = [
            MissingDownFile(version=m.version, name=m.name) for m in missing_down
        ]

        return ValidationResult(
            valid=len(gaps) == 0 and len(missing_down) == 0,
            total_migrations=len(migrations),
            gaps=gaps,
            missing_down_files=missing_down_files,
        )
