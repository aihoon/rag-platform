#!/usr/bin/env python3
"""
Migrate `uploaded_files.machine_cat` to INTEGER in ingestion-ui SQLite DB.

Purpose:
- Normalize legacy schemas where `machine_cat` may be TEXT-like and ensure
  consistent INTEGER storage for downstream filtering and ingestion payloads.
- Keep migration safe by using table-swap strategy instead of in-place
  ALTER TYPE (not supported in SQLite).

What this script does:
1. Validates DB file and required source table (`uploaded_files`).
2. Creates a temporary table with target schema (`uploaded_files__mig_new`).
3. Copies rows from source table, casting `machine_cat` to INTEGER.
4. Renames current table to backup (`uploaded_files__mig_old`).
5. Renames new table to `uploaded_files`.
6. Optionally drops backup table when `--drop-old` is provided.

Compatibility notes:
- If legacy columns `weaviate_status` or `neo4j_status` are missing, default
  values are injected during copy (`NOT_INGESTED`).
- If `class_name` is null/empty, fallback to `DEFAULT_CLASS_NAME`.

Usage:
- Dry/safe migration (keeps backup):
  `python ingestion-ui/scripts/migrate_sqlite_machine_cat_int.py`
- Explicit DB path:
  `python ingestion-ui/scripts/migrate_sqlite_machine_cat_int.py --db-path ingestion-ui/data/ingestion_ui.db`
- Drop backup table after successful migration:
  `python ingestion-ui/scripts/migrate_sqlite_machine_cat_int.py --drop-old`

Operational caution:
- Run with ingestion-ui/ingestion-api stopped to avoid concurrent writes.
- If backup table already exists and `--drop-old` is not set, the script fails
  intentionally to prevent accidental data loss.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT_DIR = BASE_DIR.parent.parent
if str(REPO_ROOT_DIR) not in sys.path:
    sys.path.append(str(REPO_ROOT_DIR))
from shared.schemas.rag_class import DEFAULT_CLASS_NAME

SOURCE_TABLE = "uploaded_files"
NEW_TABLE = "uploaded_files__mig_new"
OLD_TABLE = "uploaded_files__mig_old"


def _ensure_db(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"DB not found: {path}")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def migrate(db_path: Path, drop_old: bool) -> None:
    _ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        try:
            if not _table_exists(conn, SOURCE_TABLE):
                raise RuntimeError(f"Missing required table: {SOURCE_TABLE}")

            source_columns = _columns(conn, SOURCE_TABLE)
            has_weaviate_status = "weaviate_status" in source_columns
            has_neo4j_status = "neo4j_status" in source_columns

            conn.execute(f"DROP TABLE IF EXISTS {NEW_TABLE}")
            if drop_old:
                conn.execute(f"DROP TABLE IF EXISTS {OLD_TABLE}")
            elif _table_exists(conn, OLD_TABLE):
                raise RuntimeError(
                    f"Backup table already exists: {OLD_TABLE}. "
                    "Use --drop-old or drop it manually before retrying."
                )

            conn.execute(f"""
            CREATE TABLE {NEW_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'UPLOADED',
                weaviate_status TEXT NOT NULL DEFAULT 'NOT_INGESTED',
                neo4j_status TEXT NOT NULL DEFAULT 'NOT_INGESTED',
                class_name TEXT NOT NULL DEFAULT '{DEFAULT_CLASS_NAME}',
                company_id INTEGER NOT NULL DEFAULT 0,
                machine_cat INTEGER NOT NULL DEFAULT 0,
                machine_id INTEGER NOT NULL DEFAULT 0,
                file_upload_id INTEGER,
                pipeline_id TEXT,
                ingested_at TEXT,
                last_error TEXT,
                ingestion_response TEXT
            )
            """)

            weaviate_select = "weaviate_status" if has_weaviate_status else "'NOT_INGESTED'"
            neo4j_select = "neo4j_status" if has_neo4j_status else "'NOT_INGESTED'"

            conn.execute(f"""
            INSERT INTO {NEW_TABLE} (
                id, file_name, stored_path, file_size, sha256, uploaded_at, status,
                weaviate_status, neo4j_status, class_name, company_id, machine_cat, machine_id, file_upload_id,
                pipeline_id, ingested_at, last_error, ingestion_response
            )
            SELECT
                id, file_name, stored_path, file_size, sha256, uploaded_at, status,
                {weaviate_select} AS weaviate_status,
                {neo4j_select} AS neo4j_status,
                CASE
                    WHEN class_name IS NULL OR class_name = '' THEN '{DEFAULT_CLASS_NAME}'
                    ELSE class_name
                END AS class_name,
                company_id,
                CAST(machine_cat AS INTEGER) AS machine_cat,
                machine_id,
                file_upload_id, pipeline_id, ingested_at, last_error, ingestion_response
            FROM {SOURCE_TABLE}
            """)

            conn.execute(f"ALTER TABLE {SOURCE_TABLE} RENAME TO {OLD_TABLE}")
            conn.execute(f"ALTER TABLE {NEW_TABLE} RENAME TO {SOURCE_TABLE}")

            if drop_old:
                conn.execute(f"DROP TABLE {OLD_TABLE}")

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")


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
