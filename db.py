import sqlite3
from datetime import datetime, UTC

from config import DATABASE_FILE


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT,
            refresh_token TEXT NOT NULL,
            token_type TEXT,
            expires_in INTEGER,
            expires_at TEXT,
            updated_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            record_internal_id TEXT NOT NULL,
            record_number TEXT,
            status TEXT NOT NULL,
            suiteql_pulled_at TEXT,
            header_pulled_at TEXT,
            file_generated_at TEXT,
            output_file TEXT,
            error_message TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(export_type, record_internal_id)
        )
        """
    )

    connection.commit()
    connection.close()


def get_current_token_record():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            access_token,
            refresh_token,
            token_type,
            expires_in,
            expires_at,
            updated_at
        FROM oauth_tokens
        ORDER BY id DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()
    connection.close()
    return row


def update_token_record(token_id, access_token, refresh_token, token_type, expires_in, expires_at):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE oauth_tokens
        SET
            access_token = ?,
            refresh_token = ?,
            token_type = ?,
            expires_in = ?,
            expires_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            access_token,
            refresh_token,
            token_type,
            expires_in,
            expires_at,
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            token_id,
        ),
    )

    connection.commit()
    connection.close()


def get_export_record(export_type, record_internal_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM exports
        WHERE export_type = ?
          AND record_internal_id = ?
        LIMIT 1
        """,
        (export_type, str(record_internal_id)),
    )

    row = cursor.fetchone()
    connection.close()
    return row


def upsert_export_record(
    export_type,
    record_internal_id,
    record_number,
    status,
    suiteql_pulled_at=None,
    header_pulled_at=None,
    file_generated_at=None,
    output_file=None,
    error_message=None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO exports (
            export_type,
            record_internal_id,
            record_number,
            status,
            suiteql_pulled_at,
            header_pulled_at,
            file_generated_at,
            output_file,
            error_message,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(export_type, record_internal_id)
        DO UPDATE SET
            record_number = excluded.record_number,
            status = excluded.status,
            suiteql_pulled_at = COALESCE(excluded.suiteql_pulled_at, exports.suiteql_pulled_at),
            header_pulled_at = COALESCE(excluded.header_pulled_at, exports.header_pulled_at),
            file_generated_at = COALESCE(excluded.file_generated_at, exports.file_generated_at),
            output_file = COALESCE(excluded.output_file, exports.output_file),
            error_message = excluded.error_message,
            updated_at = excluded.updated_at
        """,
        (
            export_type,
            str(record_internal_id),
            record_number,
            status,
            suiteql_pulled_at,
            header_pulled_at,
            file_generated_at,
            output_file,
            error_message,
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    connection.commit()
    connection.close()

if __name__ == "__main__":
    initialize_database()