"""
Tests for MigrateWrapper using SQLite database
"""
import sqlite3
from pathlib import Path

from tests.test_base import MigrateWrapperTestBase, MigrateWrapperTestMixin


class TestMigrateWrapperSQLite(MigrateWrapperTestBase, MigrateWrapperTestMixin):
    """Test suite for MigrateWrapper with SQLite"""
    
    def setup_database(self) -> str:
        """Setup SQLite database and return connection URL"""
        # Use file-based database with unique name for parallel testing
        # SQLite's in-memory mode has issues with migrate tool
        import uuid
        db_name = f"test_{uuid.uuid4().hex[:8]}.db"
        self.db_path = Path(self.temp_dir) / db_name
        # Use temp file which is fast enough for testing
        return f"sqlite://{self.db_path}"
    
    def cleanup_database(self):
        """Cleanup SQLite database"""
        # File will be cleaned up with temp directory
        pass
    
    def create_schema_migrations_table(self):
        """Create schema_migrations table manually for testing"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                dirty INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    
    def set_db_version(self, version: int, dirty: bool = False):
        """Set database version manually for testing"""
        self.create_schema_migrations_table()
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schema_migrations")
        cursor.execute(
            "INSERT INTO schema_migrations (version, dirty) VALUES (?, ?)",
            (version, 1 if dirty else 0)
        )
        conn.commit()
        conn.close()


# SQLite-specific tests
class TestSQLiteSpecificFeatures(TestMigrateWrapperSQLite):
    """Tests specific to SQLite features"""
    
    def test_sqlite_connection_string_format(self):
        """Test SQLite connection string format"""
        self.assertTrue(self.db_url.startswith("sqlite://"))
        self.assertIn(str(self.db_path), self.db_url)
    
    def test_sqlite_schema_migrations_table(self):
        """Test SQLite schema_migrations table creation"""
        self.create_schema_migrations_table()
        
        # Verify table exists
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_migrations'
        """)
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "schema_migrations")
    
    def test_sqlite_integer_primary_key(self):
        """Test SQLite INTEGER PRIMARY KEY in migrations"""
        self.create_test_migration(
            1,
            "create_users",
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
            "DROP TABLE users;"
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        
        # Check file contents
        up_content = migrations[0].up_file.read_text()
        self.assertIn("INTEGER PRIMARY KEY", up_content)
    
    def test_sqlite_without_rowid(self):
        """Test SQLite WITHOUT ROWID table option"""
        self.create_test_migration(
            1,
            "create_optimized_table",
            """
            CREATE TABLE cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                expires_at INTEGER
            ) WITHOUT ROWID;
            """,
            "DROP TABLE cache;"
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        
        # Check file contents
        up_content = migrations[0].up_file.read_text()
        self.assertIn("WITHOUT ROWID", up_content)
    
    def test_sqlite_pragma_statements(self):
        """Test SQLite PRAGMA statements in migrations"""
        self.create_test_migration(
            1,
            "enable_foreign_keys",
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY, 
                user_id INTEGER REFERENCES users(id)
            );
            """,
            """
            DROP TABLE posts;
            DROP TABLE users;
            """
        )
        
        migrations = self.wrapper.list_migrations()
        self.assertEqual(len(migrations), 1)
        
        # Check file contents
        up_content = migrations[0].up_file.read_text()
        self.assertIn("PRAGMA foreign_keys", up_content)
        self.assertIn("REFERENCES", up_content)


if __name__ == '__main__':
    import unittest
    unittest.main()