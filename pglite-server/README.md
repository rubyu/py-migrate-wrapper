# PGlite Test Server

This directory contains the PGlite server setup for testing the migrate-wrapper with PostgreSQL.

## Installation

```bash
npm install
```

## Usage

To start PGlite server for tests:

```bash
# Default (memory database on port 5432)
npm start

# Test mode (memory database on port 5433)
npm run start:test

# Custom options
npx pglite-server --port 5434 --db file://./test.db
```

## Global Installation (Optional)

If you want to install PGlite globally:

```bash
npm run install:global
```

Then you can run `pglite-server` from anywhere.