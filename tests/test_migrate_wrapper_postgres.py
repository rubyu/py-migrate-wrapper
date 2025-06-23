"""
Tests for MigrateWrapper using PostgreSQL database via Docker
"""

import os
import psycopg
import unittest
import uuid
import time

from tests.test_base import MigrateWrapperTestBase, MigrateWrapperTestMixin


class TestMigrateWrapperPostgreSQL(MigrateWrapperTestBase, MigrateWrapperTestMixin):
    """Test suite for MigrateWrapper with PostgreSQL via Docker"""

    def setup_database(self) -> str:
        """Setup PostgreSQL database and return connection URL"""
        # Use environment variables for connection details, with sensible defaults
        db_host = os.environ.get("POSTGRES_HOST", "localhost")
        db_port = os.environ.get("POSTGRES_PORT", "5433")
        db_user = os.environ.get("POSTGRES_USER", "migrate_user")
        db_password = os.environ.get("POSTGRES_PASSWORD", "migrate_pass")
        db_name = os.environ.get("POSTGRES_DB", "migrate_test")

        # Create a unique schema for this test to avoid conflicts in parallel execution
        # Use combination of timestamp and UUID to ensure uniqueness
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
        test_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        self.schema_name = f"test_{worker_id}_{test_id}"

        # Connect to the main database first
        main_connection_url = (
            f"postgres://{db_user}:{db_password}@"
            f"{db_host}:{db_port}/{db_name}?sslmode=disable"
        )

        # Test connection and create schema
        try:
            conn = psycopg.connect(main_connection_url)
            conn.autocommit = True
            cursor = conn.cursor()

            # Create schema for this test
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema_name}"')
            conn.close()
        except Exception as e:
            self.fail(
                f"Cannot connect to PostgreSQL at {db_host}:{db_port}. "
                f"Please ensure PostgreSQL is running (try: docker compose up -d). "
                f"Error: {e}"
            )

        # Return connection URL with schema as migration table option
        # This ensures golang-migrate will create tables in our test schema
        connection_url = (
            f"postgres://{db_user}:{db_password}@"
            f"{db_host}:{db_port}/{db_name}"
            f"?sslmode=disable"
            f'&x-migrations-table="{self.schema_name}"."schema_migrations"'
            f"&x-migrations-table-quoted=1"
        )

        return connection_url

    def cleanup_database(self):
        """Cleanup PostgreSQL database"""
        # For Docker PostgreSQL, we drop the test schema
        try:
            # Parse connection URL to remove schema parameter
            base_url = self.db_url.split("?")[0]
            conn = psycopg.connect(f"{base_url}?sslmode=disable")
            conn.autocommit = True
            cursor = conn.cursor()

            # Drop the test schema
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE')

            conn.close()
        except Exception:
            # Ignore cleanup errors - schema might already be dropped
            pass

    def create_schema_migrations_table(self):
        """Create schema_migrations table manually for testing"""
        try:
            # Parse connection URL to connect without schema parameter
            base_url = self.db_url.split("?")[0]
            conn = psycopg.connect(f"{base_url}?sslmode=disable")
            conn.autocommit = False

            cursor = conn.cursor()
            # Set search path to the test schema
            cursor.execute(f"SET search_path TO {self.schema_name}")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version BIGINT PRIMARY KEY,
                    dirty BOOLEAN NOT NULL DEFAULT FALSE
                )
            """
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Re-raise the exception to make test failures visible
            raise RuntimeError(f"Database operation failed: {e}") from e

    def set_db_version(self, version: int, dirty: bool = False):
        """Set database version manually for testing"""
        try:
            self.create_schema_migrations_table()
            # Parse connection URL to connect without schema parameter
            base_url = self.db_url.split("?")[0]
            conn = psycopg.connect(f"{base_url}?sslmode=disable")
            conn.autocommit = False

            cursor = conn.cursor()
            # Set search path to the test schema
            cursor.execute(f"SET search_path TO {self.schema_name}")
            cursor.execute("DELETE FROM schema_migrations")
            cursor.execute(
                "INSERT INTO schema_migrations (version, dirty) VALUES (%s, %s)",
                (version, dirty),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Re-raise the exception to make test failures visible
            raise RuntimeError(f"Database operation failed: {e}") from e


class TestPostgreSQLSpecificFeatures(unittest.TestCase):
    """Test PostgreSQL-specific functionality"""

    def setUp(self):
        """Set up test environment"""
        # Use environment variables for connection details
        db_host = os.environ.get("POSTGRES_HOST", "localhost")
        db_port = os.environ.get("POSTGRES_PORT", "5433")
        db_user = os.environ.get("POSTGRES_USER", "migrate_user")
        db_password = os.environ.get("POSTGRES_PASSWORD", "migrate_pass")
        db_name = os.environ.get("POSTGRES_DB", "migrate_test")

        # Create unique schema for this test
        worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
        test_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        self.schema_name = f"test_{worker_id}_{test_id}"

        self.connection_url = (
            f"postgres://{db_user}:{db_password}@"
            f"{db_host}:{db_port}/{db_name}?sslmode=disable"
        )

        # Create schema
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema_name}"')
            cursor.execute(f"SET search_path TO {self.schema_name}")
            conn.close()
        except Exception as e:
            self.fail(f"Failed to create test schema: {e}")

    def tearDown(self):
        """Clean up test schema"""
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE')
            conn.close()
        except Exception:
            pass

    def test_postgres_connection_string_parsing(self):
        """Test PostgreSQL connection string format"""
        self.assertIn("postgres://", self.connection_url)
        self.assertIn("@", self.connection_url)

    def test_postgres_schema_migrations_table(self):
        """Test schema_migrations table creation"""
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"SET search_path TO {self.schema_name}")

            # Create table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_schema_migrations (
                    version BIGINT PRIMARY KEY,
                    dirty BOOLEAN NOT NULL DEFAULT FALSE
                )
            """
            )

            # Verify table exists
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s
                AND table_name = 'test_schema_migrations'
                ORDER BY column_name
            """,
                (self.schema_name,),
            )
            columns = cursor.fetchall()

            # Clean up
            cursor.execute("DROP TABLE IF EXISTS test_schema_migrations")
            conn.close()

            # Verify column structure
            self.assertEqual(len(columns), 2)
            column_names = [col[0] for col in columns]
            self.assertIn("version", column_names)
            self.assertIn("dirty", column_names)

        except Exception as e:
            self.fail(f"PostgreSQL schema test failed: {e}")

    def test_postgres_transactions_in_migrations(self):
        """Test PostgreSQL transaction handling"""
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = False
            cursor = conn.cursor()
            cursor.execute(f"SET search_path TO {self.schema_name}")

            cursor.execute("CREATE TABLE test_transaction (id SERIAL PRIMARY KEY)")
            cursor.execute("INSERT INTO test_transaction DEFAULT VALUES")

            # Test rollback
            conn.rollback()

            # Verify rollback worked
            conn.autocommit = True
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'test_transaction'
                )
            """,
                (self.schema_name,),
            )
            exists = cursor.fetchone()[0]
            self.assertFalse(exists, "Table should not exist after rollback")

            conn.close()

        except Exception as e:
            self.fail(f"PostgreSQL transaction test failed: {e}")

    def test_postgres_serial_columns(self):
        """Test PostgreSQL SERIAL column support"""
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"SET search_path TO {self.schema_name}")

            cursor.execute(
                """
                CREATE TABLE test_serial (
                    id SERIAL PRIMARY KEY,
                    name TEXT
                )
            """
            )
            cursor.execute("INSERT INTO test_serial (name) VALUES ('test')")
            cursor.execute("SELECT id FROM test_serial WHERE name = 'test'")
            result = cursor.fetchone()

            # Clean up
            cursor.execute("DROP TABLE test_serial")
            conn.close()

            self.assertEqual(result[0], 1)

        except Exception as e:
            self.fail(f"PostgreSQL SERIAL test failed: {e}")

    def test_postgres_json_columns(self):
        """Test PostgreSQL JSON column support"""
        try:
            conn = psycopg.connect(self.connection_url)
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"SET search_path TO {self.schema_name}")

            cursor.execute(
                """
                CREATE TABLE test_json (
                    id SERIAL PRIMARY KEY,
                    data JSONB
                )
            """
            )
            cursor.execute(
                "INSERT INTO test_json (data) VALUES (%s)", ['{"key": "value"}']
            )
            cursor.execute("SELECT data->>'key' FROM test_json")
            result = cursor.fetchone()

            # Clean up
            cursor.execute("DROP TABLE test_json")
            conn.close()

            self.assertEqual(result[0], "value")

        except Exception as e:
            self.fail(f"PostgreSQL JSON test failed: {e}")


if __name__ == "__main__":
    unittest.main()
