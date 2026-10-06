# ZMTRUCKS NetSuite Integration

Python integration for exporting ZMTRUCKS purchase orders and sales orders from NetSuite into JSON payloads for ACT Fulfillment's warehouse workflows.

The application retrieves transaction data using SuiteQL and NetSuite record API calls, builds transaction-specific payloads, and tracks export results in SQLite to avoid re-exporting records already marked successful.

## Supported exports

| NetSuite transaction | Export | Module | Output filename |
| --- | --- | --- | --- |
| Purchase order | 943 JSON | [`po_exporter.py`](po_exporter.py) | `AR_943_<po_number>_<timestamp>.json` |
| Sales order | 940 JSON | [`so_exporter.py`](so_exporter.py) | `PO_940_<so_number>_<timestamp>.json` |

These outputs are JSON payloads for the corresponding warehouse integration workflows, not raw X12 documents. Files are written to the configured `OUTPUT_FOLDER` with UTC timestamps in their filenames.

## Architecture

Purchase-order and sales-order processing use separate exporter classes with a shared NetSuite client, persistence layer, and logging infrastructure. Both classes accept a NetSuite client and logger and expose a `run()` method.

| File | Responsibility |
| --- | --- |
| [`po_exporter.py`](po_exporter.py) | `PurchaseOrder943Exporter`: purchase-order queries, grouping, 943 mapping, and file generation. |
| [`so_exporter.py`](so_exporter.py) | `SalesOrderExporter`: sales-order queries, grouping, 940 mapping, and file generation. |
| [`netsuite_client.py`](netsuite_client.py) | Shared token refresh, SuiteQL execution, record retrieval, and failure-email handling. |
| [`db.py`](db.py) | SQLite schema and persistence helpers for OAuth tokens and export tracking. |
| [`logger_setup.py`](logger_setup.py) | File and console logging. |
| [`seed_refresh_token.py`](seed_refresh_token.py) | Initial refresh-token seeding utility. |
| [`run_export.py`](run_export.py) | Application entry point. |

## Processing flow

1. Query eligible transaction lines using SuiteQL.
2. Group lines by NetSuite internal ID and skip records already marked `success` for that export type.
3. Retrieve the transaction header through the shared NetSuite client.
4. Build the 943 or 940 payload and write a JSON file.
5. Record the result in SQLite. Per-order failures are logged and passed to the client's failure-email handler.

### Purchase orders — 943

The purchase-order query selects `PurchOrd` transactions where `custbodyzm_actlocation_field = 1` and the line has an item. The payload includes shipment and purchase-order references, facility addresses, item identifiers, and quantities.

The current mapping uses the container number for the order-level `PurchaseOrderNumber` and fixed facility address values.

### Sales orders — 940

The sales-order query selects `SalesOrd` transactions for the same ACT-location field value. It excludes lines without an item, item `-7`, and zero quantities. Payload construction also excludes an item matching the order header's shipping method.

The payload includes order references, transaction and shipping dates, ship-to details, carrier and service information, and line-level VIN references. Order quantities are converted to absolute values.

## Persistence and export tracking

SQLite stores local state in two tables:

| Table | Purpose |
| --- | --- |
| `oauth_tokens` | Refresh token, access token, expiration, and token-update information. |
| `exports` | Processing status, transaction identifiers, timestamps, output paths, and error details. |

Export records are looked up by export type and NetSuite internal ID. The exporters use `purchase_order_943` and `sales_order_940` as their export types.

Normal processing advances through `suiteql_pulled`, `header_pulled`, and `success`. Per-order exceptions are recorded as `failed`. Records marked `success` are skipped on subsequent runs.

A successful export means the JSON file was written and the export record was updated. It does not confirm downstream delivery, warehouse import, or acknowledgment.

## Configuration and execution

Execution requires a Python environment with the application's dependencies, NetSuite OAuth access, and writable local paths for the database, output files, and logs.

Environment-specific settings are maintained in a local `config.py`, which is excluded from version control. Configuration covers NetSuite account and client credentials, the SQLite database path, output and log folders, and optional SMTP settings for failure notifications.

The local OAuth token store must be initialized before authenticated processing. `seed_refresh_token.py` is the token-initialization utility; credentials and token values must not be saved in tracked source files.

With dependencies, local configuration, and database/token state prepared, run the application entry point:

```bash
python run_export.py
```

## Security

Keep credentials, OAuth tokens, and operational customer data out of version control. Local configuration, virtual environments, databases, logs, backups, and generated exports are excluded through [`.gitignore`](.gitignore). Any committed configuration examples or test fixtures must contain only placeholders or sanitized data.

## Development and releases

Development follows a trunk-based workflow on `main`, with incremental commits rather than long-lived development or release branches. Annotated version tags identify selected release commits and remain fixed once published.

The same commits and release tags should be published to Gitea and GitHub. Both hosts represent the same project, not separate development versions.
