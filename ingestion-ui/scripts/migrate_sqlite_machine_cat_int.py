#!/usr/bin/env python3
"""
SQLite migration: change uploaded_files.machine_cat to INTEGER.
Creates a new table, copies data with CAST, swaps tables.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _ensure_db(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"DB not found: {path}")


def migrate(db_path: Path, drop_old: bool) -> None:
    _ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'UPLOADED',
                class_name TEXT NOT NULL DEFAULT 'Machine',
                company_id INTEGER NOT NULL DEFAULT 0,
                machine_cat INTEGER NOT NULL DEFAULT 0,
                machine_id INTEGER NOT NULL DEFAULT 0,
                file_upload_id INTEGER,
                pipeline_id TEXT,
                ingested_at TEXT,
                last_error TEXT,
                ingestion_response TEXT
            )
            """
        )

        conn.execute(
            """
            INSERT INTO uploaded_files_new (
                id, file_name, stored_path, file_size, sha256, uploaded_at, status,
                class_name, company_id, machine_cat, machine_id, file_upload_id,
                pipeline_id, ingested_at, last_error, ingestion_response
            )
            SELECT
                id, file_name, stored_path, file_size, sha256, uploaded_at, status,
                COALESCE(class_name, 'Machine') AS class_name,
                COALESCE(company_id, 0) AS company_id,
                CAST(COALESCE(machine_cat, 0) AS INTEGER) AS machine_cat,
                COALESCE(machine_id, 0) AS machine_id,
                file_upload_id, pipeline_id, ingested_at, last_error, ingestion_response
            FROM uploaded_files
            """
        )

        conn.execute("ALTER TABLE uploaded_files RENAME TO uploaded_files_old")
        conn.execute("ALTER TABLE uploaded_files_new RENAME TO uploaded_files")

        if drop_old:
            conn.execute("DROP TABLE uploaded_files_old")

        conn.execute("COMMIT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db-path",
        default="ingestion-ui/data/ingestion_ui.db",
        help="Path to ingestion-ui SQLite DB",
    )
    parser.add_argument(
        "--drop-old",
        action="store_true",
        help="Drop uploaded_files_old after migration",
    )
    args = parser.parse_args()
    migrate(Path(args.db_path).expanduser(), args.drop_old)
    print("Migration complete.")


if __name__ == "__main__":
    main()
