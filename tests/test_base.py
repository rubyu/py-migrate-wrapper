"""
Common test base classes for MigrateWrapper tests
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from abc import ABC, abstractmethod

from migrate_wrapper import (
    MigrateWrapper,
    MigrateConfig,
    Migration,
    MigrateError,
    MigrateDirtyError,
)


class MigrateWrapperTestBase(unittest.TestCase, ABC):
    """Base test class for MigrateWrapper with database-specific setup"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test
        self.temp_dir = tempfile.mkdtemp()
        self.migrations_dir = Path(self.temp_dir) / "migrations"
        self.migrations_dir.mkdir()

        # Add .bin directory to PATH
        project_root = Path(__file__).parent.parent
        bin_path = project_root / "bin"
        self.original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_path}:{self.original_path}"

        # Database-specific setup
        self.db_url = self.setup_database()

        # Create config (migrate will be found in PATH)
        self.config = MigrateConfig(
            database_url=self.db_url, migrations_path=self.migrations_dir
        )

        # Create wrapper instance
        self.wrapper = MigrateWrapper(self.config)

    def tearDown(self):
        """Clean up test environment"""
        self.cleanup_database()
        shutil.rmtree(self.temp_dir)
        # Restore original PATH
        os.environ["PATH"] = self.original_path

    @abstractmethod
    def setup_database(self) -> str:
        """Setup database and return connection URL"""
        pass

    @abstractmethod
    def cleanup_database(self):
        """Cleanup database resources"""
        pass

    @abstractmethod
    def create_schema_migrations_table(self):
        """Create schema_migrations table manually for testing"""
        pass

    @abstractmethod
    def set_db_version(self, version: int, dirty: bool = False):
        """Set database version manually for testing"""
        pass

    def create_test_migration(
        self, version: int, name: str, up_sql: str, down_sql: str
    ):
        """Helper to create migration files"""
        up_file = self.migrations_dir / f"{version:06d}_{name}.up.sql"
        down_file = self.migrations_dir / f"{version:06d}_{name}.down.sql"

        up_file.write_text(up_sql)
        down_file.write_text(down_sql)

        return Migration(
            version=version, name=name, up_file=up_file, down_file=down_file
        )


class TestMigrateConfig(unittest.TestCase):
    """Test MigrateConfig class"""

    def test_config_validation_success(self):
        """Test valid configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MigrateConfig(
                database_url="sqlite://test.db", migrations_path=temp_dir
            )
            config.validate()  # Should not raise

    def test_config_validation_missing_url(self):
        """Test validation with missing database URL"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MigrateConfig(database_url="", migrations_path=temp_dir)
            with self.assertRaises(ValueError) as ctx:
                config.validate()
            self.assertIn("Database URL is required", str(ctx.exception))

    def test_config_validation_missing_path(self):
        """Test validation with non-existent migrations path"""
        config = MigrateConfig(
            database_url="sqlite://test.db", migrations_path="/non/existent/path"
        )
        with self.assertRaises(ValueError) as ctx:
            config.validate()
        self.assertIn("Migrations path does not exist", str(ctx.exception))


class MigrateWrapperTestMixin:
    """Mixin containing common test methods for MigrateWrapper"""

    # Create command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_create_sequential(self, mock_run):
        """Test creating sequential migration"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Create mock files that would be created by migrate
        self.create_test_migration(1, "test_migration", "", "")

        result = self.wrapper.create("test_migration", sequential=True)

        # Verify command was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("create", args)
        self.assertIn("-seq", args)
        self.assertIn("test_migration", args)
        self.assertIsInstance(result, Migration)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_create_timestamp(self, mock_run):
        """Test creating timestamp-based migration"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Create a fake migration file for the test
        self.create_test_migration(1, "test_migration", "", "")

        result = self.wrapper.create("test_migration", sequential=False)

        args = mock_run.call_args[0][0]
        self.assertIn("create", args)
        self.assertNotIn("-seq", args)
        self.assertIsInstance(result, Migration)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_create_with_different_extension(self, mock_run):
        """Test creating migration with different extension"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Create a fake migration file for the test
        self.create_test_migration(1, "test_migration", "", "")

        result = self.wrapper.create("test_migration", extension="go")

        args = mock_run.call_args[0][0]
        self.assertIn("-ext", args)
        self.assertIn("go", args)
        self.assertIsInstance(result, Migration)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_create_failure(self, mock_run):
        """Test handling creation failure"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Failed to create migration"
        )

        with self.assertRaises(MigrateError) as ctx:
            self.wrapper.create("test_migration")
        self.assertIn("Failed to create migration", str(ctx.exception))

    # Up command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_up_all_success(self, mock_run):
        """Test applying all migrations successfully"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = self.wrapper.up()

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Migrations applied successfully")
        self.assertFalse(result.dirty)

        # Check the first call (up command)
        up_args = mock_run.call_args_list[0][0][0]
        self.assertIn("up", up_args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_up_with_steps(self, mock_run):
        """Test applying specific number of migrations"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        self.wrapper.up(steps=2)

        # Check the first call (up command)
        up_args = mock_run.call_args_list[0][0][0]
        self.assertIn("up", up_args)
        self.assertIn("2", up_args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_up_dirty_state(self, mock_run):
        """Test up command when database is dirty"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: Dirty database version"
        )

        with self.assertRaises(MigrateDirtyError):
            self.wrapper.up()

    @patch("migrate_wrapper.command.subprocess.run")
    def test_up_already_latest(self, mock_run):
        """Test up when already at latest version"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="no change: already at the latest version"
        )

        result = self.wrapper.up()

        self.assertFalse(result.success)
        self.assertEqual(result.message, "Already at latest version")

    @patch("migrate_wrapper.command.subprocess.run")
    def test_up_sql_error(self, mock_run):
        """Test up with SQL execution error"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="migration failed: syntax error"
        )

        result = self.wrapper.up()

        self.assertFalse(result.success)
        self.assertIn("syntax error", result.message)

    # Down command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_down_single_success(self, mock_run):
        """Test rolling back single migration"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = self.wrapper.down(steps=1)

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Migrations rolled back successfully")

        # Check the first call (down command)
        down_args = mock_run.call_args_list[0][0][0]
        self.assertIn("down", down_args)
        self.assertIn("1", down_args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_down_all(self, mock_run):
        """Test rolling back all migrations"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        self.wrapper.down()

        # Check the first call (down command)
        down_args = mock_run.call_args_list[0][0][0]
        self.assertIn("down", down_args)
        self.assertIn("-all", down_args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_down_from_dirty_state(self, mock_run):
        """Test down from dirty state"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: Dirty database"
        )

        with self.assertRaises(MigrateDirtyError):
            self.wrapper.down()

    @patch("migrate_wrapper.command.subprocess.run")
    def test_down_no_migrations(self, mock_run):
        """Test down when no migrations to rollback"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="no migration to rollback"
        )

        result = self.wrapper.down()

        self.assertFalse(result.success)
        self.assertIn("No migrations found", result.message)

    # Goto command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_goto_specific_version(self, mock_run):
        """Test going to specific version"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = self.wrapper.goto(version=3)

        self.assertTrue(result.success)
        self.assertEqual(result.version, 3)
        self.assertEqual(result.message, "Migrated to version 3")

        args = mock_run.call_args[0][0]
        self.assertIn("goto", args)
        self.assertIn("3", args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_goto_zero(self, mock_run):
        """Test going to initial state (version 0)"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        self.wrapper.goto(version=0)

        args = mock_run.call_args[0][0]
        self.assertIn("goto", args)
        self.assertIn("0", args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_goto_non_existent(self, mock_run):
        """Test going to non-existent version"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="migration not found"
        )

        result = self.wrapper.goto(version=999)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_goto_from_dirty_state(self, mock_run):
        """Test goto from dirty state"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: Dirty database"
        )

        with self.assertRaises(MigrateDirtyError):
            self.wrapper.goto(version=3)

    # Force command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_force_version(self, mock_run):
        """Test forcing version"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = self.wrapper.force(version=5)

        self.assertTrue(result.success)
        self.assertEqual(result.version, 5)
        self.assertFalse(result.dirty)

        args = mock_run.call_args[0][0]
        self.assertIn("force", args)
        self.assertIn("5", args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_force_to_clean_dirty_state(self, mock_run):
        """Test using force to clean dirty state"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Simulate dirty state
        self.set_db_version(3, dirty=True)

        result = self.wrapper.force(version=3)

        self.assertTrue(result.success)
        self.assertFalse(result.dirty)
        self.assertEqual(result.message, "Forced version to 3")

    @patch("migrate_wrapper.command.subprocess.run")
    def test_force_failure(self, mock_run):
        """Test force command failure"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="force failed"
        )

        result = self.wrapper.force(version=5)

        self.assertFalse(result.success)
        self.assertEqual(result.message, "force failed")

    # Drop command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_drop_with_force(self, mock_run):
        """Test dropping database with force flag"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = self.wrapper.drop(force=True)

        self.assertTrue(result.success)
        self.assertIsNone(result.version)
        self.assertEqual(result.message, "Database dropped successfully")

        args = mock_run.call_args[0][0]
        self.assertIn("drop", args)
        self.assertIn("-f", args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_drop_without_force(self, mock_run):
        """Test dropping database without force flag"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="confirmation required"
        )

        result = self.wrapper.drop(force=False)

        self.assertFalse(result.success)

        # Check the first call (drop command)
        drop_args = mock_run.call_args_list[0][0][0]
        self.assertIn("drop", drop_args)
        self.assertNotIn("-f", drop_args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_drop_from_dirty_state(self, mock_run):
        """Test dropping database from dirty state"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Set dirty state
        self.set_db_version(3, dirty=True)

        result = self.wrapper.drop(force=True)

        self.assertTrue(result.success)

    # Version command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_with_migrations(self, mock_run):
        """Test getting version with migrations applied"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version: 3\n", stderr=""
        )

        version = self.wrapper.version()

        self.assertEqual(version, 3)

        args = mock_run.call_args[0][0]
        self.assertIn("version", args)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_no_migrations(self, mock_run):
        """Test getting version with no migrations"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="no migration\n", stderr=""
        )

        version = self.wrapper.version()

        self.assertIsNone(version)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_dirty_state(self, mock_run):
        """Test getting version in dirty state"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version: 3 (dirty)\n", stderr=""
        )

        version = self.wrapper.version()

        self.assertEqual(version, 3)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_command_failure(self, mock_run):
        """Test version command failure"""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="database connection failed"
        )

        version = self.wrapper.version()

        self.assertIsNone(version)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_handles_stderr_output(self, mock_run):
        """Test version() correctly parses version from stderr (Issue: version stderr bug)"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",  # Empty stdout
            stderr="1\n"  # Version in stderr
        )

        version = self.wrapper.version()
        
        self.assertEqual(version, 1)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_prefers_stdout_over_stderr(self, mock_run):
        """Test version() prefers stdout when both stdout and stderr have content"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2\n",  # Version in stdout
            stderr="1\n"   # Different version in stderr
        )

        version = self.wrapper.version()
        
        self.assertEqual(version, 2)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_handles_dirty_state_in_stderr(self, mock_run):
        """Test version() correctly handles dirty state marker when version is in stderr"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="3 (dirty)\n"
        )

        version = self.wrapper.version()
        
        self.assertEqual(version, 3)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_version_handles_various_stderr_formats(self, mock_run):
        """Test version() handles various output formats when in stderr"""
        test_cases = [
            ("5\n", 5),
            ("version: 7\n", 7),
            ("42\n", 42),
            ("version: 99 (dirty)\n", 99),
        ]

        for stderr_output, expected_version in test_cases:
            with self.subTest(stderr_output=stderr_output):
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="",
                    stderr=stderr_output
                )

                version = self.wrapper.version()
                
                self.assertEqual(version, expected_version)

    # Status command tests
    @patch("migrate_wrapper.command.subprocess.run")
    def test_status_clean(self, mock_run):
        """Test getting clean status"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version: 3\n", stderr=""
        )

        status = self.wrapper.status()

        self.assertEqual(status.version, 3)
        self.assertFalse(status.dirty)
        self.assertTrue(status.is_clean)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_status_dirty(self, mock_run):
        """Test getting dirty status"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="version: 3 (dirty)\n", stderr=""
        )

        status = self.wrapper.status()

        self.assertEqual(status.version, 3)
        self.assertTrue(status.dirty)
        self.assertFalse(status.is_clean)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_status_no_version(self, mock_run):
        """Test status with no version"""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="no migration\n", stderr=""
        )

        status = self.wrapper.status()

        self.assertIsNone(status.version)
        self.assertFalse(status.dirty)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_status_handles_stderr_output(self, mock_run):
        """Test status() method also correctly handles stderr output"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="5 (dirty)\n"
        )

        status = self.wrapper.status()
        
        self.assertEqual(status.version, 5)
        self.assertTrue(status.dirty)
        self.assertFalse(status.is_clean)

    # Validation tests
    def test_validate_empty(self):
        """Test validation with no migrations"""
        validation = self.wrapper.validate_migrations()

        self.assertTrue(validation.valid)
        self.assertEqual(validation.total_migrations, 0)
        self.assertEqual(validation.gaps, [])
        self.assertEqual(validation.missing_down_files, [])

    def test_validate_with_gaps(self):
        """Test validation with gaps in sequence"""
        self.create_test_migration(1, "first", "CREATE TABLE a;", "DROP TABLE a;")
        self.create_test_migration(3, "third", "CREATE TABLE c;", "DROP TABLE c;")

        validation = self.wrapper.validate_migrations()

        self.assertFalse(validation.valid)
        self.assertEqual(validation.gaps, [2])

    def test_validate_missing_down_files(self):
        """Test validation with missing down files"""
        # Create migration with only up file
        up_file = self.migrations_dir / "000001_test.up.sql"
        up_file.write_text("CREATE TABLE test;")

        validation = self.wrapper.validate_migrations()

        self.assertFalse(validation.valid)
        self.assertEqual(len(validation.missing_down_files), 1)

    def test_validate_all_good(self):
        """Test validation with valid migrations"""
        self.create_test_migration(1, "first", "CREATE TABLE a;", "DROP TABLE a;")
        self.create_test_migration(2, "second", "CREATE TABLE b;", "DROP TABLE b;")
        self.create_test_migration(3, "third", "CREATE TABLE c;", "DROP TABLE c;")

        validation = self.wrapper.validate_migrations()

        self.assertTrue(validation.valid)
        self.assertEqual(validation.total_migrations, 3)
        self.assertEqual(validation.gaps, [])
        self.assertEqual(validation.missing_down_files, [])

    # Migration class tests
    def test_migration_properties(self):
        """Test Migration class properties"""
        with tempfile.TemporaryDirectory() as temp_dir:
            up_file = Path(temp_dir) / "000001_test.up.sql"
            down_file = Path(temp_dir) / "000001_test.down.sql"
            up_file.write_text("CREATE TABLE test;")
            down_file.write_text("DROP TABLE test;")

            migration = Migration(
                version=1, name="test", up_file=up_file, down_file=down_file
            )

            self.assertEqual(migration.filename_prefix, "000001_test")
            self.assertTrue(migration.has_up_file())
            self.assertTrue(migration.has_down_file())

    def test_migration_missing_files(self):
        """Test migration with missing files"""
        migration = Migration(
            version=1,
            name="test",
            up_file=Path("/non/existent/file.up.sql"),
            down_file=None,
        )

        self.assertFalse(migration.has_up_file())
        self.assertFalse(migration.has_down_file())

    def test_migration_timestamp_prefix(self):
        """Test migration with timestamp"""
        migration = Migration(
            version=1,
            name="test",
            up_file=Path("test.up.sql"),
            down_file=Path("test.down.sql"),
            timestamp=20231225120000,
        )

        self.assertEqual(migration.filename_prefix, "20231225120000_test")

    # Integration scenarios
    @patch("migrate_wrapper.command.subprocess.run")
    def test_full_migration_lifecycle(self, mock_run):
        """Test complete migration lifecycle"""
        # Create migrations
        self.create_test_migration(
            1,
            "create_users",
            "CREATE TABLE users (id INTEGER PRIMARY KEY);",
            "DROP TABLE users;",
        )
        self.create_test_migration(
            2,
            "add_email",
            "ALTER TABLE users ADD COLUMN email TEXT;",
            "ALTER TABLE users DROP COLUMN email;",
        )

        # Mock successful operations
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Apply migrations
        result = self.wrapper.up()
        self.assertTrue(result.success)

        # Rollback one
        result = self.wrapper.down(steps=1)
        self.assertTrue(result.success)

        # Go to specific version
        result = self.wrapper.goto(version=2)
        self.assertTrue(result.success)

        # Drop database
        result = self.wrapper.drop(force=True)
        self.assertTrue(result.success)

    @patch("migrate_wrapper.command.subprocess.run")
    def test_dirty_state_recovery(self, mock_run):
        """Test recovering from dirty state"""
        # Simulate dirty state
        mock_run.side_effect = [
            # First up fails and leaves dirty
            MagicMock(returncode=1, stdout="", stderr="migration failed"),
            # up() calls version() after failure
            MagicMock(returncode=0, stdout="version: 2\n", stderr=""),
            # status() call shows dirty
            MagicMock(returncode=0, stdout="version: 2 (dirty)\n", stderr=""),
            # Force to fix
            MagicMock(returncode=0, stdout="", stderr=""),
            # Verify clean
            MagicMock(returncode=0, stdout="version: 2\n", stderr=""),
        ]

        # Try to migrate (fails with non-dirty error for this test)
        result = self.wrapper.up()
        self.assertFalse(result.success)

        # Check status
        status = self.wrapper.status()
        self.assertTrue(status.dirty)

        # Fix with force
        result = self.wrapper.force(version=status.version)
        self.assertTrue(result.success)

        # Verify clean
        status = self.wrapper.status()
        self.assertFalse(status.dirty)
