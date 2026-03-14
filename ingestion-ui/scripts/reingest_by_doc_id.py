#!/usr/bin/env python3
"""
Re-trigger ingestion for rows matched by `doc_id` from ingestion-ui SQLite.

Purpose:
- Reprocess already-uploaded documents without re-uploading files from UI.
- Useful after schema changes, parser fixes, vector/graph reindex needs,
  or partial ingestion failures.

How target rows are selected:
- Reads `uploaded_files` from ingestion-ui DB configured by ingestion-api
  settings (`resolved_ingestion_ui_db_path()`).
- Computes `doc_id` as `Path(file_name).stem`.
- Selects all rows whose computed `doc_id` equals `--doc-id`.

How ingestion is called:
- Sends `POST {api_url}/run` per matched row with:
  - `file_upload_id`
  - `file_name`
  - `class_name` (override via `--class-name` or DB value)
  - `weaviate_enabled`
  - `neo4j_enabled` (effective only when backend Neo4j is enabled)

Schema compatibility:
- Works with both schemas where `uploaded_files.class_name` exists and where
  it does not. If missing, empty class is used unless `--class-name` is set.

Usage examples:
- Re-ingest a document id to both backends:
  `python ingestion-ui/scripts/reingest_by_doc_id.py --doc-id manual_001`
- Override target class:
  `python ingestion-ui/scripts/reingest_by_doc_id.py --doc-id manual_001 --class-name Machine`
- Check payloads only (no API call):
  `python ingestion-ui/scripts/reingest_by_doc_id.py --doc-id manual_001 --dry-run`
- Use a non-default API endpoint:
  `python ingestion-ui/scripts/reingest_by_doc_id.py --doc-id manual_001 --api-url http://localhost:4590`

Operational caution:
- The script performs one API call per matched row; duplicates by same doc_id
  are processed individually.
- `--dry-run` should be used first in production to verify target set.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv

from ingestion_api.config.settings import load_settings


def _doc_id_from_file_name(file_name: str) -> str:
    return Path(file_name).stem


def _find_targets(db_path: Path, doc_id: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(uploaded_files)").fetchall()
        }
        has_class_name = "class_name" in columns
        select_columns = ["id", "file_name"]
        if has_class_name:
            select_columns.append("class_name")
        select_query = f"SELECT {', '.join(select_columns)} FROM uploaded_files"
        found = conn.execute(select_query).fetchall()
    for row in found:
        file_name = str(row["file_name"] or "")
        if _doc_id_from_file_name(file_name) != doc_id:
            continue
        rows.append(
            {
                "file_upload_id": int(row["id"]),
                "file_name": file_name,
                "class_name": str(row["class_name"] or "") if has_class_name else "",
            }
        )
    return rows


def _post_run(
    *, api_url: str, payload: dict[str, object], timeout: int
) -> tuple[int, str]:
    resp = requests.post(f"{api_url.rstrip('/')}/run", json=payload, timeout=timeout)
    return resp.status_code, (resp.text or "")[:800]


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Re-ingest rows matched by doc_id")
    parser.add_argument(
        "--doc-id", required=True, help="Document id (Path(file_name).stem)"
    )
    parser.add_argument(
        "--class-name", default="", help="Override class_name if provided"
    )
    parser.add_argument(
        "--api-url", default="http://localhost:4590", help="ingestion-api base URL"
    )
    parser.add_argument("--weaviate-enabled", action="store_true", default=True)
    parser.add_argument("--neo4j-enabled", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    settings = load_settings()
    db_path = settings.resolved_ingestion_ui_db_path()
    targets = _find_targets(db_path=db_path, doc_id=args.doc_id)
    if not targets:
        print(f"[INFO] no rows found for doc_id={args.doc_id} in db={db_path}")
        return 0

    print(f"[INFO] targets={len(targets)} doc_id={args.doc_id} db={db_path}")
    for item in targets:
        payload = {
            "file_name": item["file_name"],
            "file_upload_id": item["file_upload_id"],
            # "class_name": args.class_name or item["class_name"] or settings.weaviate_default_class,
            "class_name": args.class_name or item["class_name"],
            "weaviate_enabled": bool(args.weaviate_enabled),
            "neo4j_enabled": bool(args.neo4j_enabled and settings.neo4j_enabled),
        }
        if args.dry_run:
            print(f"[DRY-RUN] {payload}")
            continue
        status, body = _post_run(
            api_url=args.api_url, payload=payload, timeout=settings.weaviate_request_timeout
        )
        print(
            f"[RUN] file_upload_id={payload['file_upload_id']} status={status} "
            f"class_name={payload['class_name']} body={body}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
