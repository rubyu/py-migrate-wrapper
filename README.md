# Migrate Wrapper

Python wrapper for golang-migrate/migrate CLI tool.

## Installation

```bash
pip install migrate-wrapper
```

### Prerequisites

This library requires the `migrate` CLI tool to be installed:

```bash
# Install golang-migrate
# macOS
brew install golang-migrate

# Linux
curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/

# Or use Go
go install -tags 'postgres mysql sqlite3' github.com/golang-migrate/migrate/v4/cmd/migrate@latest
```

### Dependencies

This library has **no runtime dependencies**. It's a pure Python wrapper around the `migrate` CLI tool.

Development dependencies (for testing only):
- psycopg (PostgreSQL adapter)
- pytest and related testing tools

## Usage

```python
from migrate_wrapper import MigrateWrapper, MigrateConfig

# SQLite example
config = MigrateConfig(
    database_url="sqlite://test.db",
    migrations_path="./migrations"
)

# PostgreSQL example
config = MigrateConfig(
    database_url="postgres://user:pass@localhost/dbname",
    migrations_path="./migrations"
)

migrate = MigrateWrapper(config)

# Apply migrations
result = migrate.up()

# Check status
status = migrate.status()
print(f"Version: {status.version}, Clean: {status.is_clean}")

# Create new migration
migration = migrate.create("add_users_table")

# Go to specific version
result = migrate.goto(version=3)

# Validate migrations
validation = migrate.validate_migrations()
if not validation.valid:
    print(f"Found {len(validation.gaps)} gaps and {len(validation.missing_down_files)} missing down files")
    if validation.has_gaps:
        print(f"Missing versions: {validation.gaps}")
    if validation.has_missing_down_files:
        for missing in validation.missing_down_files:
            print(f"Missing down file: {missing.version}_{missing.name}.down.sql")
```

## Supported Databases

All databases supported by [golang-migrate/migrate](https://github.com/golang-migrate/migrate#cli-usage):
- PostgreSQL
- MySQL / MariaDB
- SQLite
- MongoDB
- CockroachDB
- Cassandra / ScyllaDB
- ClickHouse
- Firebird
- MS SQL Server
- Neo4j
- Redis
- And more...

## API Reference

### MigrateConfig

```python
config = MigrateConfig(
    database_url="postgres://user:pass@localhost/dbname",  # Required
    migrations_path="./migrations",                        # Required
    table_name="schema_migrations",                       # Optional (default)
    command_path="migrate"                                # Optional (default)
)
```

### MigrateWrapper Methods

- `create(name: str, sequential: bool = True, extension: str = "sql") -> Migration`
- `up(steps: Optional[int] = None) -> MigrationResult`
- `down(steps: Optional[int] = None) -> MigrationResult`
- `goto(version: int) -> MigrationResult`
- `force(version: int) -> MigrationResult`
- `drop(force: bool = False) -> MigrationResult`
- `version() -> int`
- `status() -> DatabaseInfo`
- `list_migrations() -> List[Migration]`
- `validate_migrations() -> ValidationResult`

## Development

This project uses rye for dependency management.

### Setup Development Environment

```bash
# Install dependencies and setup PGlite
make setup
```

### Running Tests

```bash
# Run all tests in parallel (default)
make test

# Run all tests sequentially
make test-sequential

# Run only SQLite tests
make test-sqlite

# Run SQLite tests in parallel
make test-sqlite-parallel

# Run only PostgreSQL tests (requires PGlite)
make test-postgres

# Run PostgreSQL tests in parallel
make test-postgres-parallel
```

### PostgreSQL Tests with PGlite

PostgreSQL tests use [PGlite Socket Server](https://pglite.dev/docs/pglite-socket#cli-usage) which is installed locally in the project:

```bash
# Setup is done automatically with:
make setup
```

The tests will automatically use the local PGlite installation from `pglite-server/node_modules`.

**Note**: PostgreSQL tests will fail if PGlite Socket Server is not installed. This is intentional to ensure consistent test environments.

### Test Structure

- `tests/test_base.py` - Common test base classes and mixins
- `tests/test_migrate_wrapper_sqlite.py` - SQLite-specific tests
- `tests/test_migrate_wrapper_postgres.py` - PostgreSQL-specific tests

Each database-specific test file includes:
- All common migration operations (via `MigrateWrapperTestMixin`)
- Database-specific feature tests
- Connection and schema tests
