"""Helpers for updating ingestion-ui uploaded_files status from ingestion-api."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from ..config.settings import Settings


def _ensure_status_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(uploaded_files)").fetchall()
    }
    if "weaviate_status" not in existing_columns:
        conn.execute(
            "ALTER TABLE uploaded_files ADD COLUMN weaviate_status TEXT NOT NULL DEFAULT 'NOT_INGESTED'"
        )
    if "neo4j_status" not in existing_columns:
        conn.execute(
            "ALTER TABLE uploaded_files ADD COLUMN neo4j_status TEXT NOT NULL DEFAULT 'NOT_INGESTED'"
        )


def update_uploaded_file_status(
    *,
    settings: Settings,
    file_upload_id: int,
    target: str,
    status: str,
    pipeline_id: Optional[str] = None,
    error_text: Optional[str] = None,
    response_obj: Optional[dict[str, Any]] = None,
) -> None:
    db_path = settings.resolved_ingestion_ui_db_path()
    status_column = "weaviate_status" if target == "weaviate" else "neo4j_status"
    ingested_at = (
        datetime.now(timezone.utc).isoformat()
        if status in {"REQUESTED", "RUNNING", "INGESTED"}
        else None
    )
    with sqlite3.connect(db_path) as conn:
        _ensure_status_columns(conn)
        conn.execute(
            f"""
            UPDATE uploaded_files
            SET {status_column} = ?,
                pipeline_id = COALESCE(?, pipeline_id),
                last_error = ?,
                ingested_at = ?,
                ingestion_response = COALESCE(?, ingestion_response)
            WHERE id = ?
            """,
            (
                status,
                pipeline_id,
                error_text,
                ingested_at,
                json.dumps(response_obj, ensure_ascii=False) if response_obj else None,
                file_upload_id,
            ),
        )


def get_uploaded_file_status(
    *,
    settings: Settings,
    file_upload_id: int,
    target: str,
) -> str:
    db_path = settings.resolved_ingestion_ui_db_path()
    status_column = "weaviate_status" if target == "weaviate" else "neo4j_status"
    with sqlite3.connect(db_path) as conn:
        _ensure_status_columns(conn)
        row = conn.execute(
            f"SELECT {status_column} FROM uploaded_files WHERE id = ?",
            (file_upload_id,),
        ).fetchone()
    if not row:
        return "NOT_INGESTED"
    return str(row[0] or "NOT_INGESTED")
