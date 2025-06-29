# Migrate Wrapper

[![CI](https://github.com/rubyu/py-migrate-wrapper/workflows/CI/badge.svg)](https://github.com/rubyu/py-migrate-wrapper/actions/workflows/ci.yml)
[![Release](https://github.com/rubyu/py-migrate-wrapper/workflows/Release/badge.svg)](https://github.com/rubyu/py-migrate-wrapper/actions/workflows/release.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Python wrapper for golang-migrate/migrate CLI tool.

## Installation

```bash
# Clone the repository
git clone https://github.com/rubyu/py-migrate-wrapper.git
cd py-migrate-wrapper

# Install with rye
rye sync

# Or download from GitHub releases
# Download wheel from: https://github.com/rubyu/py-migrate-wrapper/releases
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
# Install dependencies and setup PostgreSQL with Docker
make setup
```

This will:
- Install Python dependencies with rye
- Download and install the migrate CLI tool
- Start PostgreSQL using Docker Compose

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

# Run only PostgreSQL tests (requires Docker)
make test-postgres

# Run PostgreSQL tests in parallel
make test-postgres-parallel
```

### PostgreSQL Tests with Docker

PostgreSQL tests use Docker Compose to run a real PostgreSQL instance:

```bash
# Start PostgreSQL manually (optional - done automatically in tests)
docker compose up -d postgres

# Or use the make target
make setup-postgres
```

The tests will automatically start PostgreSQL if it's not running and wait for it to be ready.

**Note**: PostgreSQL tests require Docker to be installed and running.

### Test Structure

- `tests/test_base.py` - Common test base classes and mixins
- `tests/test_migrate_wrapper_sqlite.py` - SQLite-specific tests
- `tests/test_migrate_wrapper_postgres.py` - PostgreSQL-specific tests

Each database-specific test file includes:
- All common migration operations (via `MigrateWrapperTestMixin`)
- Database-specific feature tests
- Connection and schema tests
