.PHONY: help setup install test test-sqlite test-postgres test-parallel lint format clean setup-migrate setup-postgres

help:
	@echo "Available commands:"
	@echo "  make setup         - Setup development environment including PostgreSQL and migrate"
	@echo "  make install       - Install Python dependencies"
	@echo "  make setup-migrate - Download and install migrate CLI tool"
	@echo "  make setup-postgres - Start PostgreSQL with Docker Compose"
	@echo "  make test          - Run all tests"
	@echo "  make test-parallel - Run all tests in parallel"
	@echo "  make test-sqlite   - Run SQLite tests only"
	@echo "  make test-postgres - Run PostgreSQL tests only"
	@echo "  make lint          - Run linter"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Clean up generated files"

setup: install setup-migrate setup-postgres
	@echo "Development environment setup complete!"

setup-postgres:
	@echo "Setting up PostgreSQL with Docker..."
	@docker compose up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@timeout 30 sh -c 'until docker compose exec postgres pg_isready -U migrate_user -d migrate_test; do sleep 1; done'
	@echo "PostgreSQL setup complete!"

install:
	@echo "Installing Python dependencies..."
	@rye sync

setup-migrate:
	@echo "Setting up migrate CLI tool..."
	@MIGRATE_VERSION="v4.18.3"; \
	MIGRATE_OS="linux"; \
	MIGRATE_ARCH="amd64"; \
	INSTALL_DIR="./bin"; \
	mkdir -p "$${INSTALL_DIR}"; \
	if [ ! -f "$${INSTALL_DIR}/migrate" ]; then \
		echo "Downloading migrate $${MIGRATE_VERSION} for $${MIGRATE_OS}-$${MIGRATE_ARCH}..."; \
		curl -L "https://github.com/golang-migrate/migrate/releases/download/$${MIGRATE_VERSION}/migrate.$${MIGRATE_OS}-$${MIGRATE_ARCH}.tar.gz" | \
			tar -xz -C "$${INSTALL_DIR}" migrate; \
		chmod +x "$${INSTALL_DIR}/migrate"; \
		echo "migrate installed successfully to $${INSTALL_DIR}/migrate"; \
	else \
		echo "migrate already exists in $${INSTALL_DIR}/migrate"; \
	fi

test:
	@echo "Running all tests in parallel..."
	@rye test

test-sequential:
	@echo "Running all tests sequentially..."
	@rye run pytest tests/ -v --tb=short

test-parallel:
	@echo "Running all tests in parallel..."
	@rye run pytest tests/ -n auto -v

test-sqlite:
	@echo "Running SQLite tests..."
	@rye run pytest tests/test_migrate_wrapper_sqlite.py -v

test-sqlite-parallel:
	@echo "Running SQLite tests in parallel..."
	@rye run pytest tests/test_migrate_wrapper_sqlite.py -n auto -v

test-postgres:
	@echo "Running PostgreSQL tests..."
	@docker compose up -d postgres
	@timeout 30 sh -c 'until docker compose exec postgres pg_isready -U migrate_user -d migrate_test; do sleep 1; done'
	@POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_USER=migrate_user POSTGRES_PASSWORD=migrate_pass POSTGRES_DB=migrate_test rye run pytest tests/test_migrate_wrapper_postgres.py -v

test-postgres-parallel:
	@echo "Running PostgreSQL tests in parallel..."
	@docker compose up -d postgres
	@timeout 30 sh -c 'until docker compose exec postgres pg_isready -U migrate_user -d migrate_test; do sleep 1; done'
	@POSTGRES_HOST=localhost POSTGRES_PORT=5433 POSTGRES_USER=migrate_user POSTGRES_PASSWORD=migrate_pass POSTGRES_DB=migrate_test rye run pytest tests/test_migrate_wrapper_postgres.py -n auto -v

lint:
	@echo "Running linter..."
	@rye run flake8 src tests

format:
	@echo "Formatting code..."
	@rye run black src tests

clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".coverage" -delete
	@rm -f bin/migrate
	@docker compose down -v
	@echo "Stopped Docker services and removed volumes"

check-all: format lint test ## Run formatting, linting, and tests
	@echo "All checks completed successfully!"

pre-commit: check-all ## Run all pre-commit checks (format, lint, test)
	@echo "Pre-commit checks completed!"
