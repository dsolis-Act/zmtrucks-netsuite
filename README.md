# NetSuite 943 Export

This is a simple NetSuite purchase-order export pipeline built so the same structure can later be reused for sales orders.

## Files

- `config.py` - settings and environment variables
- `db.py` - SQLite schema and persistence helpers
- `logger_setup.py` - file and console logging
- `netsuite_client.py` - token refresh, SuiteQL, record GET, failure email
- `po_exporter.py` - purchase-order SuiteQL pull, header enrichment, JSON build, file write, duplicate prevention
- `seed_refresh_token.py` - one-time seed script for the refresh token
- `run_export.py` - entry point

## SQLite tables

### oauth_tokens
Stores the current refresh token, access token, expiration, and update timestamp.

### exports
Tracks which records were already processed so duplicate files are not generated.

Important fields:
- `export_type` - lets you reuse the same table for future exports like sales orders
- `record_internal_id` - NetSuite internal ID
- `status` - `suiteql_pulled`, `header_pulled`, `success`, or `failed`
- `output_file` - written file path when successful

## Setup

Set environment variables before running:

```bash
export NS_ACCOUNT_ID="9582941-sb1"
export NS_CLIENT_ID="your_client_id"
export NS_CLIENT_SECRET="your_client_secret"
export DATABASE_FILE="netsuite_943.db"
export OUTPUT_FOLDER="out"
export LOG_FOLDER="logs"
```

Optional SMTP settings for failure emails:

```bash
export SMTP_HOST="mail.yourserver.com"
export SMTP_PORT="25"
export SMTP_USERNAME=""
export SMTP_PASSWORD=""
export SMTP_USE_TLS="false"
export FAILURE_EMAIL_FROM="alerts@yourdomain.com"
export FAILURE_EMAIL_TO="you@yourdomain.com"
```

## First run

1. Put your refresh token into `seed_refresh_token.py`
2. Run:

```bash
python seed_refresh_token.py
```

3. Then run:

```bash
python run_export.py
```

## Current flow

1. Read token state from SQLite
2. Refresh token if expired
3. Run SuiteQL for purchase-order lines and reusable header fields
4. Group rows by PO internal ID
5. Skip records already marked `success`
6. Call PO REST endpoint for ship-to/header enrichment
7. Build 943 JSON payload
8. Write file
9. Track success or failure in SQLite
10. Send failure email if configured

## Future sales-order reuse

The structure is already ready for a future sales-order exporter:

- same `NetSuiteClient`
- same token lifecycle
- same `exports` table
- same logger
- same output and failure email pattern

You would mainly add another exporter file like `so_exporter.py` with:
- a sales-order SuiteQL query
- a sales-order header GET
- a sales-order JSON mapper
