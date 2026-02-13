# Migration Guide: SQLite to Turso

This guide explains how to migrate your local Glimprint database to Turso.

## Prerequisites

1.  **Turso Account**: You need a Turso account and database.
2.  **Turso CLI** (Optional but recommended): For managing your database.

## Steps

### 1. Get Turso Credentials

You need the Database URL and an Authentication Token.

Using Turso CLI:
```bash
turso db show <your-db-name> --url
turso db tokens create <your-db-name>
```

### 2. Configure Environment Variables

Set the following environment variables in your terminal or `.env` file (if running locally) or in Vercel settings:

```bash
export TURSO_DATABASE_URL="libsql://your-db-name.turso.io"
export TURSO_AUTH_TOKEN="your-very-long-auth-token"
```

### 3. Run the Migration Script

From the project root directory, run:

```bash
python scripts/migrate_to_turso.py
```

This script will:
1.  Read the schema and data from `db/glimprint.db`.
2.  Connect to the Turso database specified in the environment variables.
3.  Drop existing tables in Turso (matching your local tables) to ensure a clean slate.
4.  Re-create the tables and insert all data.

### 4. Verify

You can verify the data in Turso using the CLI:

```bash
turso db shell <your-db-name> "SELECT count(*) FROM news;"
```

## Production (Vercel)

Add the `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` to your Vercel Project Settings under "Environment Variables". The application is already configured to automatically use Turso if these variables are present, and fall back to the local `db/glimprint.db` (read-only usually in serverless) if connection fails.
