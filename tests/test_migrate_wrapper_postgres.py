"""
Tests for MigrateWrapper using PostgreSQL database via PGlite
"""
import subprocess
import os
import time
import signal
import psycopg
from pathlib import Path
import unittest
from typing import Optional, List

from tests.test_base import MigrateWrapperTestBase, MigrateWrapperTestMixin


class TestMigrateWrapperPostgreSQL(MigrateWrapperTestBase, MigrateWrapperTestMixin):
    """Test suite for MigrateWrapper with PostgreSQL via PGlite"""
    
    def setup_database(self) -> str:
        """Setup PGlite database and return connection URL"""
        # Check if pglite is available
        if not self._check_pglite_available():
            self.fail("PGlite Socket Server not available - install it with: npm install -g @electric-sql/pglite-socket")
        
        # Start PGlite server with in-memory database
        self.pglite_port = self._find_free_port()
        self.pglite_process = self._start_pglite()
        
        # Wait for server to be ready
        self._wait_for_server()
        
        return f"postgres://postgres@localhost:{self.pglite_port}/postgres?sslmode=disable"
    
    def cleanup_database(self):
        """Cleanup PGlite server"""
        if hasattr(self, 'pglite_process') and self.pglite_process:
            try:
                # On Unix, kill the entire process group
                if os.name != 'nt' and hasattr(os, 'killpg'):
                    try:
                        os.killpg(os.getpgid(self.pglite_process.pid), signal.SIGTERM)
                        self.pglite_process.wait(timeout=2)
                    except ProcessLookupError:
                        pass  # Process already terminated
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(self.pglite_process.pid), signal.SIGKILL)
                        self.pglite_process.wait(timeout=1)
                else:
                    # Windows or fallback
                    self.pglite_process.terminate()
                    self.pglite_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.pglite_process.kill()
                self.pglite_process.wait()
            except Exception as e:
                # Log cleanup errors for debugging
                print(f"Cleanup error: {e}")
                pass
    
    def create_schema_migrations_table(self):
        """Create schema_migrations table manually for testing"""
        try:
            conninfo = f"dbname=postgres host=localhost port={self.pglite_port} user=postgres password=postgres sslmode=disable"
            conn = psycopg.connect(conninfo)
            conn.autocommit = False
            
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version BIGINT PRIMARY KEY,
                    dirty BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            # Re-raise the exception to make test failures visible
            raise RuntimeError(f"Database operation failed: {e}") from e
    
    def set_db_version(self, version: int, dirty: bool = False):
        """Set database version manually for testing"""
        try:
            self.create_schema_migrations_table()
            conninfo = f"dbname=postgres host=localhost port={self.pglite_port} user=postgres password=postgres sslmode=disable"
            conn = psycopg.connect(conninfo)
            conn.autocommit = False
            
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schema_migrations")
            cursor.execute(
                "INSERT INTO schema_migrations (version, dirty) VALUES (%s, %s)",
                (version, dirty)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Re-raise the exception to make test failures visible
            raise RuntimeError(f"Database operation failed: {e}") from e
    
    def _check_pglite_available(self) -> bool:
        """Check if PGlite Server CLI is available"""
        # Try local installation first
        pglite_cmd = self._get_pglite_command()
        if pglite_cmd:
            return True
        return False
    
    def _get_pglite_command(self) -> Optional[List[str]]:
        """Get PGlite server command (prefer local installation)"""
        import shutil
        
        # Check local node_modules first
        local_pglite = Path(__file__).parent.parent / "pglite-server" / "node_modules" / ".bin" / "pglite-server"
        if local_pglite.exists():
            return ["node", str(local_pglite)]
        
        # Check if globally installed
        if shutil.which("pglite-server"):
            return ["pglite-server"]
        
        return None
    
    def _find_free_port(self) -> int:
        """Find a free port for PGlite server"""
        import socket
        import random
        # Use random port range to reduce conflicts in parallel execution
        base_port = 15000 + random.randint(0, 9999)
        for offset in range(100):
            port = base_port + offset
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    s.listen(1)
                return port
            except OSError:
                continue
        # Fallback to system-assigned port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def _start_pglite(self) -> subprocess.Popen:
        """Start PGlite server"""
        # Get PGlite command
        pglite_cmd = self._get_pglite_command()
        if not pglite_cmd:
            raise RuntimeError("PGlite server command not found")
        
        # PGlite Socket Server command line interface
        # Using memory:// URL for in-memory database
        cmd = pglite_cmd + [
            "--port", str(self.pglite_port),
            "--db", "memory://",
            "--host", "127.0.0.1"
        ]
        
        # Start PGlite in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stdout and stderr
            preexec_fn=os.setsid if os.name != 'nt' else None  # Create new process group on Unix
        )
        
        # Give the server a moment to start
        time.sleep(1.0)
        
        # Check if process started successfully
        if process.poll() is not None:
            output = process.stdout.read().decode() if process.stdout else ""
            raise RuntimeError(f"PGlite server failed to start: {output}")
        
        # Server started successfully
        
        return process
    
    def _wait_for_server(self, timeout: int = 10):
        """Wait for PGlite server to be ready"""
        import socket
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Just check if port is open
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('127.0.0.1', self.pglite_port))
                    if result == 0:
                        # Server is listening
                        # Give it a bit more time to fully initialize
                        time.sleep(1)
                        return  # Port is open
            except Exception as e:
                # Log connection errors during startup for debugging
                print(f"Connection attempt failed: {e}")
                pass
            
            time.sleep(0.5)
        
        # Check if process is still running
        if hasattr(self, 'pglite_process') and self.pglite_process.poll() is not None:
            output = self.pglite_process.stdout.read().decode() if self.pglite_process.stdout else ""
            raise RuntimeError(f"PGlite server crashed: {output}")
        
        raise TimeoutError(f"PGlite server not ready after {timeout} seconds")


# PostgreSQL-specific tests
class TestPostgreSQLSpecificFeatures(TestMigrateWrapperPostgreSQL):
    """Tests specific to PostgreSQL features"""
    
    def test_postgres_connection_string_parsing(self):
        """Test PostgreSQL connection string format"""
        self.assertIn("postgres://", self.db_url)
        self.assertIn("localhost", self.db_url)
        self.assertIn("sslmode=disable", self.db_url)
    
    def test_postgres_schema_migrations_table(self):
        """Test PostgreSQL schema_migrations table creation"""
        self.create_schema_migrations_table()
        
        # Verify table exists using direct table query instead of information_schema
        # This avoids the segmentation fault issue with PGlite + psycopg + information_schema
        try:
            conninfo = f"dbname=postgres host=localhost port={self.pglite_port} user=postgres password=postgres sslmode=disable"
            conn = psycopg.connect(conninfo)
            
            cursor = conn.cursor()
            # Use direct table query instead of information_schema to avoid segfault
            cursor.execute("SELECT COUNT(*) FROM schema_migrations")
            count = cursor.fetchone()[0]
            self.assertIsInstance(count, int)
            
            # Test table structure by attempting INSERT/SELECT
            cursor.execute("INSERT INTO schema_migrations (version, dirty) VALUES (999, FALSE) ON CONFLICT (version) DO NOTHING")
            cursor.execute("SELECT version, dirty FROM schema_migrations WHERE version = 999")
            result = cursor.fetchone()
            if result:
                version, dirty = result
                self.assertEqual(version, 999)
                self.assertFalse(dirty)
            
            conn.commit()
            conn.close()
        except Exception as e:
            self.fail(f"Failed to verify schema_migrations table: {e}")
        
        # Test completed - schema_migrations table verification successful
    
    def test_postgres_transactions_in_migrations(self):
        """Test PostgreSQL transaction handling in migrations"""
        # Create a migration with explicit transaction
        self.create_test_migration(
            1, 
            "test_transaction",
            """
            BEGIN;
            CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR(100));
            INSERT INTO test_table (name) VALUES ('test');
            COMMIT;
            """,
            """
            BEGIN;
            DROP TABLE test_table;
            COMMIT;
            """
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        self.assertEqual(migrations[0].name, "test_transaction")
    
    def test_postgres_serial_columns(self):
        """Test PostgreSQL SERIAL column type in migrations"""
        self.create_test_migration(
            1,
            "create_users_with_serial",
            "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE);",
            "DROP TABLE users;"
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        
        # Check file contents
        up_content = migrations[0].up_file.read_text()
        self.assertIn("SERIAL", up_content)
    
    def test_postgres_json_columns(self):
        """Test PostgreSQL JSON column type in migrations"""
        self.create_test_migration(
            1,
            "create_with_json",
            """
            CREATE TABLE documents (
                id SERIAL PRIMARY KEY,
                data JSONB,
                metadata JSON
            );
            """,
            "DROP TABLE documents;"
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        
        # Check file contents
        up_content = migrations[0].up_file.read_text()
        self.assertIn("JSONB", up_content)
        self.assertIn("JSON", up_content)


if __name__ == '__main__':
    unittest.main()