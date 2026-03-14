"""
Streamlit ingestion UI for local upload tracking and ingestion API triggering.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT_DIR = BASE_DIR.parent
if str(REPO_ROOT_DIR) not in sys.path:
    sys.path.append(str(REPO_ROOT_DIR))
from shared.schemas.rag_class import (
    CLASS_OPTIONS,
    DEFAULT_CLASS_NAME,
    DEFAULT_NEO4J_LABEL,
    RagClassName,
    class_display_name,
)
from shared.schemas.chunk_type import (
    ChunkType,
    is_image_chunk_type,
    is_table_chunk_type,
)
from shared.schemas.ingestion import (
    IngestionRunRequest,
    WeaviateDeleteRequest,
    GraphDeleteRequest as Neo4jDeleteRequest,
)

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "ingestion_ui.db"
# INGESTION_API_DOTENV_PATH = "../.env"
INGESTION_API_DOTENV_PATH = (REPO_ROOT_DIR / ".env").resolve()

load_dotenv(dotenv_path=str(INGESTION_API_DOTENV_PATH), override=True)

INGESTION_API_URL = os.environ.get("INGESTION_API_URL", "http://localhost:8000")
WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://localhost:8080")
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "neo4j_password")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
WEAVIATE_DEFAULT_LABEL = os.environ.get("WEAVIATE_DEFAULT_LABEL", DEFAULT_CLASS_NAME)
NEO4J_DEFAULT_LABEL = os.environ.get("NEO4J_DEFAULT_LABEL", DEFAULT_NEO4J_LABEL)
WEAVIATE_GENERAL_CLASS = RagClassName.GENERAL.value
WEAVIATE_MACHINE_CLASS = RagClassName.MACHINE.value

TupleParams = tuple[Any, ...]


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS uploaded_files (
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
        existing_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(uploaded_files)").fetchall()
        }
        if "company_id" not in existing_columns:
            raise ValueError(
                "SQLite schema mismatch: missing required 'company_id'. "
                f"Reset DB file and restart: {DB_PATH}"
            )
        if "machine_cat" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN machine_cat INTEGER NOT NULL DEFAULT 0"
            )
        if "machine_id" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN machine_id INTEGER NOT NULL DEFAULT 0"
            )
        if "class_name" not in existing_columns:
            conn.execute(
                f"ALTER TABLE uploaded_files ADD COLUMN class_name TEXT NOT NULL DEFAULT '{DEFAULT_CLASS_NAME}'"
            )
        if "weaviate_status" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN weaviate_status TEXT NOT NULL DEFAULT 'NOT_INGESTED'"
            )
        if "neo4j_status" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN neo4j_status TEXT NOT NULL DEFAULT 'NOT_INGESTED'"
            )
        conn.execute(
            "UPDATE uploaded_files SET weaviate_status = 'INGESTED' "
            "WHERE weaviate_status IN ('WEAVIATE_INGESTED', 'weaviate_ingested')"
        )
        conn.execute(
            "UPDATE uploaded_files SET neo4j_status = 'INGESTED' "
            "WHERE neo4j_status IN ('NEO4J_INGESTED', 'neo4j_ingested', 'GRAPH_INGESTED')"
        )


def db_execute(query: str, params: TupleParams = ()) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(query, params)


def db_fetchall(query: str, params: TupleParams = ()) -> List[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return rows


def file_sha256(file_bytes: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(file_bytes)
    return digest.hexdigest()


def persist_uploaded_file(
    *,
    file_name: str,
    file_bytes: bytes,
    class_name: str,
    company_id: int,
    machine_cat: int,
    machine_id: int,
) -> Dict[str, Any]:
    sha = file_sha256(file_bytes)
    existing = db_fetchall("SELECT * FROM uploaded_files WHERE sha256 = ?", (sha,))
    if existing:
        return {
            "ok": False,
            "message": "This file already exists in local DB.",
            "id": existing[0]["id"],
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    stored_name = f"{timestamp}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(file_bytes)

    db_execute(
        """
        INSERT INTO uploaded_files (
            file_name, stored_path, file_size, sha256, uploaded_at, status, class_name, company_id, machine_cat, machine_id
        ) VALUES (?, ?, ?, ?, ?, 'UPLOADED', ?, ?, ?, ?)
        """,
        (
            file_name,
            str(stored_path),
            len(file_bytes),
            sha,
            datetime.now(timezone.utc).isoformat(),
            class_name,
            company_id,
            machine_cat,
            machine_id,
        ),
    )
    return {"ok": True, "message": "File saved to local DB and disk."}


def list_uploaded_files() -> List[sqlite3.Row]:
    return db_fetchall("SELECT * FROM uploaded_files ORDER BY id DESC")


def has_active_ingestion(rows: List[sqlite3.Row]) -> bool:
    active_statuses = {"REQUESTED", "RUNNING"}
    return any(
        str(row["weaviate_status"]) in active_statuses
        or str(row["neo4j_status"]) in active_statuses
        for row in rows
    )


def delete_uploaded_file(*, row_id: int, stored_path: str) -> Dict[str, Any]:
    file_path = Path(stored_path)
    if file_path.exists():
        file_path.unlink()
    db_execute("DELETE FROM uploaded_files WHERE id = ?", (row_id,))
    return {"ok": True, "message": f"Deleted row #{row_id} and local file."}


def update_uploaded_file_class_name(*, row_id: int, class_name: str) -> None:
    db_execute(
        "UPDATE uploaded_files SET class_name = ? WHERE id = ?", (class_name, row_id)
    )


def sync_weaviate_statuses(*, weaviate_url: str, timeout_sec: int) -> dict[str, int]:
    rows = list_uploaded_files()
    updated = 0
    unchanged = 0
    skipped = 0
    errors = 0
    class_presence: dict[str, dict[str, set[str]]] = {}

    def fetch_presence_for_class(_class_name: str) -> dict[str, set[str]]:
        collected_sources: set[str] = set()
        collected_file_ids: set[str] = set()
        offset = 0
        page_size = 500
        while True:
            query = "{Get{%s(limit:%s,offset:%s){source file_upload_id}}}" % (
                _class_name,
                page_size,
                offset,
            )
            resp = requests.post(
                f"{weaviate_url.rstrip('/')}/v1/graphql",
                json={"query": query},
                timeout=timeout_sec,
            )
            resp.raise_for_status()
            payload = resp.json()
            if "errors" in payload:
                raise RuntimeError(str(payload["errors"]))
            _rows = payload.get("data", {}).get("Get", {}).get(_class_name, [])
            if not _rows:
                break
            for item in _rows:
                source = str((item or {}).get("source", "") or "").strip()
                if source:
                    collected_sources.add(source)
                file_upload_id = str(
                    (item or {}).get("file_upload_id", "") or ""
                ).strip()
                if file_upload_id:
                    collected_file_ids.add(_file_upload_id)
            if len(_rows) < page_size:
                break
            offset += page_size
        return {"sources": collected_sources, "file_upload_ids": collected_file_ids}

    for row in rows:
        current = str(row["weaviate_status"] or "")
        if current in {"REQUESTED", "RUNNING"}:
            skipped += 1
            continue
        class_name = str(row["class_name"] or WEAVIATE_GENERAL_CLASS)
        file_name = str(row["file_name"] or "").strip()
        _file_upload_id = str(row["file_upload_id"] or row["id"] or "").strip()
        if not file_name:
            skipped += 1
            continue
        if class_name not in class_presence:
            try:
                class_presence[class_name] = fetch_presence_for_class(class_name)
            except (requests.RequestException, RuntimeError, ValueError):
                errors += 1
                class_presence[class_name] = {
                    "sources": set(),
                    "file_upload_ids": set(),
                }
        present = class_presence[class_name]
        has_any_remote_ids = bool(present["file_upload_ids"])
        exists_by_id = _file_upload_id in present["file_upload_ids"]
        exists_by_name = (not has_any_remote_ids) and (file_name in present["sources"])
        target_status = (
            "INGESTED" if (exists_by_id or exists_by_name) else "NOT_INGESTED"
        )
        if target_status == current:
            unchanged += 1
            continue
        db_execute(
            "UPDATE uploaded_files SET weaviate_status = ? WHERE id = ?",
            (target_status, int(row["id"])),
        )
        updated += 1
    return {
        "updated": updated,
        "unchanged": unchanged,
        "skipped": skipped,
        "errors": errors,
    }


def sync_neo4j_statuses() -> dict[str, int]:
    rows = list_uploaded_files()
    updated = 0
    unchanged = 0
    skipped = 0
    errors = 0
    label_presence: dict[str, dict[str, set[str]]] = {}

    def normalize_label(raw: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "", raw or "")
        return cleaned or NEO4J_DEFAULT_LABEL

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            for row in rows:
                current = str(row["neo4j_status"] or "")
                if current in {"REQUESTED", "RUNNING"}:
                    skipped += 1
                    continue
                file_name = str(row["file_name"] or "").strip()
                if not file_name:
                    skipped += 1
                    continue
                label = normalize_label(str(row["class_name"] or NEO4J_DEFAULT_LABEL))
                if label not in label_presence:
                    query = f"MATCH (d:Document:{label}) RETURN d.file_name AS file_name, d.file_upload_id AS file_upload_id"
                    records = session.run(query)
                    file_set: set[str] = set()
                    file_id_set: set[str] = set()
                    for rec in records:
                        name = str(rec.get("file_name") or "").strip()
                        if name:
                            file_set.add(name)
                        file_id = str(rec.get("file_upload_id") or "").strip()
                        if file_id:
                            file_id_set.add(file_id)
                    label_presence[label] = {
                        "file_names": file_set,
                        "file_upload_ids": file_id_set,
                    }
                file_upload_id = str(row["file_upload_id"] or row["id"] or "").strip()
                has_any_remote_ids = bool(label_presence[label]["file_upload_ids"])
                by_id = file_upload_id in label_presence[label]["file_upload_ids"]
                by_name = (not has_any_remote_ids) and (
                    file_name in label_presence[label]["file_names"]
                )
                target_status = "INGESTED" if (by_id or by_name) else "NOT_INGESTED"
                if target_status == current:
                    unchanged += 1
                    continue
                db_execute(
                    "UPDATE uploaded_files SET neo4j_status = ? WHERE id = ?",
                    (target_status, int(row["id"])),
                )
                updated += 1
    except (Neo4jError, sqlite3.Error, ValueError, TypeError):
        errors += 1
    finally:
        driver.close()

    return {
        "updated": updated,
        "unchanged": unchanged,
        "skipped": skipped,
        "errors": errors,
    }


def call_weaviate_delete_api(
    *,
    ingestion_api_url: str,
    class_name: Optional[str],
    file_upload_id: int,
    file_name: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/chunks"
    payload = WeaviateDeleteRequest(
        class_name=class_name,
        file_upload_id=file_upload_id,
        file_name=file_name,
    ).model_dump()
    resp = requests.delete(endpoint, json=payload, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")
    return body


def call_neo4j_delete_api(
    *,
    ingestion_api_url: str,
    file_upload_id: int,
    file_name: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/graph"
    payload = Neo4jDeleteRequest(
        file_upload_id=file_upload_id,
        file_name=file_name,
    ).model_dump()
    resp = requests.delete(endpoint, json=payload, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")
    return body


def call_ingestion_api(
    *,
    ingestion_api_url: str,
    class_name: Optional[str],
    company_id: Optional[int],
    machine_cat: Optional[int],
    machine_id: Optional[int],
    weaviate_enabled: Optional[bool],
    neo4j_enabled: Optional[bool],
    file_upload_id: int,
    file_name: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/run"
    payload = IngestionRunRequest(
        class_name=class_name,
        company_id=company_id,
        machine_cat=machine_cat,
        machine_id=machine_id,
        weaviate_enabled=weaviate_enabled,
        neo4j_enabled=neo4j_enabled,
        file_upload_id=file_upload_id,
        file_name=file_name,
    ).model_dump()
    resp = requests.post(endpoint, json=payload, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}

    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")

    return body


def call_backend_health_check(
    *,
    ingestion_api_url: str,
    path: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}{path}"
    resp = requests.get(endpoint, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    return {
        "ok": resp.ok,
        "status_code": resp.status_code,
        "endpoint": endpoint,
        "body": body,
    }


def update_ingestion_result(
    *,
    row_id: int,
    target: str,
    status: str,
    pipeline_id: Optional[str],
    error_text: Optional[str],
    response_obj: Optional[Dict[str, Any]],
) -> None:
    status_column = "weaviate_status" if target == "weaviate" else "neo4j_status"
    db_execute(
        f"""
        UPDATE uploaded_files
        SET {status_column} = ?,
            pipeline_id = ?,
            last_error = ?,
            ingested_at = ?,
            ingestion_response = ?
        WHERE id = ?
        """,
        (
            status,
            pipeline_id,
            error_text,
            (
                datetime.now(timezone.utc).isoformat()
                if status in {"REQUESTED", "INGESTED"}
                else None
            ),
            json.dumps(response_obj, ensure_ascii=False) if response_obj else None,
            row_id,
        ),
    )


def weaviate_summary(weaviate_url: str, class_name: str) -> Dict[str, Any]:
    schema_url = f"{weaviate_url.rstrip('/')}/v1/schema"
    schema_resp = requests.get(schema_url, timeout=20)
    schema_resp.raise_for_status()
    classes = schema_resp.json().get("classes", [])
    class_names = [c.get("class") for c in classes if c.get("class")]
    class_schema = next(
        (c for c in classes if (c or {}).get("class") == class_name), {}
    )
    class_properties = {
        str((p or {}).get("name") or "").strip()
        for p in (class_schema or {}).get("properties", [])
    }
    get_fields = ["source"]
    if "chunk_type" in class_properties:
        get_fields.append("chunk_type")
    if "table_id" in class_properties:
        get_fields.append("table_id")
    if "image_id" in class_properties:
        get_fields.append("image_id")
    if not class_names or class_name not in class_names:
        return {
            "classes": class_names,
            "target_class": class_name,
            "target_count": 0,
            "sampled_rows": 0,
            "document_count": 0,
            "documents": [],
            "paragraph_chunks": 0,
            "table_chunks": 0,
            "image_chunks": 0,
            "table_row_chunks": 0,
            "table_summary_chunks": 0,
            "image_summary_chunks": 0,
            "image_context_chunks": 0,
            "image_ocr_chunks": 0,
            "table_count": 0,
            "image_count": 0,
        }

    count_query = f"{{Aggregate{{{class_name}{{meta{{count}}}}}}}}"
    count_resp = requests.post(
        f"{weaviate_url.rstrip('/')}/v1/graphql",
        json={"query": count_query},
        timeout=20,
    )
    count_resp.raise_for_status()
    count_data = count_resp.json()
    count = (
        count_data.get("data", {})
        .get("Aggregate", {})
        .get(class_name, [{}])[0]
        .get("meta", {})
        .get("count", 0)
    )

    page_size = 500
    offset = 0
    paragraph_chunks = 0
    table_chunks = 0
    image_chunks = 0
    table_row_chunks = 0
    table_summary_chunks = 0
    image_summary_chunks = 0
    image_context_chunks = 0
    image_ocr_chunks = 0
    global_table_ids: set[str] = set()
    global_image_ids: set[str] = set()
    per_doc: dict[str, dict[str, Any]] = {}
    while True:
        get_query = "{Get{%s(limit:%s,offset:%s){%s}}}" % (
            class_name,
            page_size,
            offset,
            " ".join(get_fields),
        )
        get_resp = requests.post(
            f"{weaviate_url.rstrip('/')}/v1/graphql",
            json={"query": get_query},
            timeout=20,
        )
        get_resp.raise_for_status()
        get_payload = get_resp.json()
        if "errors" in get_payload:
            return {
                "classes": class_names,
                "target_class": class_name,
                "target_count": count,
                "sampled_rows": 0,
                "document_count": 0,
                "paragraph_chunks": 0,
                "table_chunks": 0,
                "image_chunks": 0,
                "table_row_chunks": 0,
                "table_summary_chunks": 0,
                "image_summary_chunks": 0,
                "image_context_chunks": 0,
                "image_ocr_chunks": 0,
                "table_count": 0,
                "image_count": 0,
                "documents": [],
                "query_errors": get_payload.get("errors"),
                "used_fields": get_fields,
            }
        rows = get_payload.get("data", {}).get("Get", {}).get(class_name, [])
        if not rows:
            break
        for row in rows:
            source = str(row.get("source", "unknown") or "unknown")
            chunk_type = str(row.get("chunk_type", "") or "").strip()
            table_id = str(row.get("table_id", "") or "").strip()
            image_id = str(row.get("image_id", "") or "").strip()
            if source not in per_doc:
                per_doc[source] = {
                    "file_name": source,
                    "paragraph_chunks": 0,
                    "table_chunks": 0,
                    "image_chunks": 0,
                    "table_row_chunks": 0,
                    "table_summary_chunks": 0,
                    "image_summary_chunks": 0,
                    "image_context_chunks": 0,
                    "image_ocr_chunks": 0,
                    "table_ids": set(),
                    "image_ids": set(),
                }
            doc_entry = per_doc[source]
            if is_table_chunk_type(chunk_type):
                table_chunks += 1
                doc_entry["table_chunks"] += 1
                if chunk_type == ChunkType.TABLE_ROW.value:
                    table_row_chunks += 1
                    doc_entry["table_row_chunks"] += 1
                elif chunk_type == ChunkType.TABLE_SUMMARY.value:
                    table_summary_chunks += 1
                    doc_entry["table_summary_chunks"] += 1
                if table_id:
                    global_table_ids.add(table_id)
                    doc_entry["table_ids"].add(table_id)
            elif is_image_chunk_type(chunk_type):
                image_chunks += 1
                doc_entry["image_chunks"] += 1
                if chunk_type == ChunkType.IMAGE_SUMMARY.value:
                    image_summary_chunks += 1
                    doc_entry["image_summary_chunks"] += 1
                elif chunk_type == ChunkType.IMAGE_CONTEXT.value:
                    image_context_chunks += 1
                    doc_entry["image_context_chunks"] += 1
                elif chunk_type == ChunkType.IMAGE_OCR.value:
                    image_ocr_chunks += 1
                    doc_entry["image_ocr_chunks"] += 1
                if image_id:
                    global_image_ids.add(image_id)
                    doc_entry["image_ids"].add(image_id)
            else:
                paragraph_chunks += 1
                doc_entry["paragraph_chunks"] += 1
        if len(rows) < page_size:
            break
        offset += page_size

    documents = []
    for source, entry in per_doc.items():
        table_ids = entry.pop("table_ids", set())
        image_ids = entry.pop("image_ids", set())
        entry["table_count"] = len(table_ids)
        entry["image_count"] = len(image_ids)
        entry["chunk_count"] = int(
            entry["paragraph_chunks"] + entry["table_chunks"] + entry["image_chunks"]
        )
        documents.append(entry)
    documents = sorted(
        documents, key=lambda item: int(item.get("chunk_count", 0)), reverse=True
    )
    return {
        "classes": class_names,
        "target_class": class_name,
        "target_count": count,
        "sampled_rows": int(paragraph_chunks + table_chunks + image_chunks),
        "document_count": len(documents),
        "paragraph_chunks": paragraph_chunks,
        "table_chunks": table_chunks,
        "image_chunks": image_chunks,
        "table_row_chunks": table_row_chunks,
        "table_summary_chunks": table_summary_chunks,
        "image_summary_chunks": image_summary_chunks,
        "image_context_chunks": image_context_chunks,
        "image_ocr_chunks": image_ocr_chunks,
        "table_count": len(global_table_ids),
        "image_count": len(global_image_ids),
        "documents": documents,
    }


def neo4j_summary(
    *,
    ingestion_api_url: str,
    label: Optional[str],
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/health/neo4j-summary"
    params = {"label": label} if label else None
    resp = requests.get(endpoint, params=params, timeout=timeout_sec)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")
    return body


def render_uploaded_files(
    *,
    ingestion_api_url: str,
    timeout_sec: int,
    delete_remote_data_on_file_delete: bool,
) -> None:
    st.subheader("Uploaded Files")
    st.caption(
        "Ingest uses the saved Class/Label and machine metadata shown on each row."
    )
    small = lambda text: f"<span style='font-size:0.85rem'>{text}</span>"
    rows = list_uploaded_files()
    if not rows:
        st.info("No files uploaded yet.")
        return
    if has_active_ingestion(rows):
        st.caption(
            "Auto-refreshing every 10 seconds while ingestion is REQUESTED or RUNNING."
        )
        components.html(
            "<script>setTimeout(function(){window.parent.location.reload();}, 10000);</script>",
            height=0,
        )

    header_cols = st.columns([3.0, 1.4, 1.4, 1.6, 2.5, 1.6, 1.4, 1.6, 1.4, 1.0])
    header_cols[0].markdown(small("<b>파일이름</b>"), unsafe_allow_html=True)
    header_cols[1].markdown(small("<b>W-Status</b>"), unsafe_allow_html=True)
    header_cols[2].markdown(small("<b>N-Status</b>"), unsafe_allow_html=True)
    header_cols[3].markdown(small("<b>Class/Label</b>"), unsafe_allow_html=True)
    header_cols[4].markdown(small("<b>C / M.C / M</b>"), unsafe_allow_html=True)
    header_cols[5].markdown(small("<b>Weaviate</b>"), unsafe_allow_html=True)
    header_cols[6].markdown(small("<b>Neo4j</b>"), unsafe_allow_html=True)
    header_cols[7].markdown(small("<b>Weaviate</b>"), unsafe_allow_html=True)
    header_cols[8].markdown(small("<b>Neo4j</b>"), unsafe_allow_html=True)
    header_cols[9].markdown(small("<b>File</b>"), unsafe_allow_html=True)

    for row in rows:
        with st.container(border=True):
            raw_class_name = str(row["class_name"] or WEAVIATE_GENERAL_CLASS)
            is_machine_class = raw_class_name == WEAVIATE_MACHINE_CLASS
            raw_weaviate_status = str(row["weaviate_status"] or "")
            raw_neo4j_status = str(row["neo4j_status"] or "")
            display_weaviate_status = (
                "N.A."
                if raw_weaviate_status in {"NOT_INGESTED", "NOT-INGESTED"}
                else raw_weaviate_status
            )
            display_neo4j_status = (
                "N.A."
                if raw_neo4j_status in {"NOT_INGESTED", "NOT-INGESTED"}
                else raw_neo4j_status
            )
            weaviate_busy = raw_weaviate_status in {"REQUESTED", "RUNNING", "INGESTED"}
            neo4j_busy = raw_neo4j_status in {"REQUESTED", "RUNNING", "INGESTED"}
            row_cols = st.columns([3.0, 1.4, 1.4, 1.6, 2.5, 1.6, 1.4, 1.6, 1.4, 1.0])
            row_cols[0].markdown(
                small(f"#{row['id']} {row['file_name']}"), unsafe_allow_html=True
            )
            row_cols[1].markdown(small(display_weaviate_status), unsafe_allow_html=True)
            row_cols[2].markdown(small(display_neo4j_status), unsafe_allow_html=True)
            row_cols[3].markdown(
                small(class_display_name(raw_class_name)), unsafe_allow_html=True
            )
            row_cols[4].markdown(
                small(
                    f"{row['company_id']} / {row['machine_cat']} / {row['machine_id']}"
                ),
                unsafe_allow_html=True,
            )

            if row_cols[5].button(
                "Ingest", key=f"run_weaviate_{row['id']}", disabled=weaviate_busy
            ):
                file_upload_id = (
                    row["file_upload_id"] if row["file_upload_id"] else row["id"]
                )
                try:
                    result = call_ingestion_api(
                        ingestion_api_url=ingestion_api_url,
                        class_name=raw_class_name,
                        company_id=row["company_id"] if is_machine_class else None,
                        machine_cat=row["machine_cat"] if is_machine_class else None,
                        machine_id=row["machine_id"] if is_machine_class else None,
                        weaviate_enabled=True,
                        neo4j_enabled=False,
                        file_upload_id=int(file_upload_id),
                        file_name=row["file_name"],
                        timeout_sec=timeout_sec,
                    )
                    update_ingestion_result(
                        target="weaviate",
                        status="REQUESTED",
                        row_id=row["id"],
                        pipeline_id=result.get("pipeline_id"),
                        error_text=None,
                        response_obj=result,
                    )
                    st.success(f"Weaviate ingest requested: {result}")
                    if result.get("neo4j"):
                        st.info(f"Neo4j ingest: {result.get('neo4j')}")
                    st.rerun()
                except Exception as exc:
                    update_ingestion_result(
                        target="weaviate",
                        row_id=row["id"],
                        status="FAILED",
                        pipeline_id=None,
                        error_text=str(exc),
                        response_obj=None,
                    )
                    st.error(f"Weaviate ingestion failed: {exc}")

            if row_cols[6].button(
                "Ingest", key=f"run_neo4j_{row['id']}", disabled=neo4j_busy
            ):
                file_upload_id = (
                    row["file_upload_id"] if row["file_upload_id"] else row["id"]
                )
                try:
                    result = call_ingestion_api(
                        ingestion_api_url=ingestion_api_url,
                        class_name=raw_class_name,
                        company_id=row["company_id"] if is_machine_class else None,
                        machine_cat=row["machine_cat"] if is_machine_class else None,
                        machine_id=row["machine_id"] if is_machine_class else None,
                        weaviate_enabled=False,
                        neo4j_enabled=True,
                        file_upload_id=int(file_upload_id),
                        file_name=row["file_name"],
                        timeout_sec=timeout_sec,
                    )
                    update_ingestion_result(
                        target="neo4j",
                        row_id=row["id"],
                        status="REQUESTED",
                        pipeline_id=result.get("pipeline_id"),
                        error_text=None,
                        response_obj=result,
                    )
                    st.success(f"Neo4j ingest requested: {result}")
                    if result.get("neo4j"):
                        st.info(f"Neo4j ingest: {result.get('neo4j')}")
                    st.rerun()
                except Exception as exc:
                    update_ingestion_result(
                        target="neo4j",
                        row_id=row["id"],
                        status="FAILED",
                        pipeline_id=None,
                        error_text=str(exc),
                        response_obj=None,
                    )
                    st.error(f"Neo4j ingestion failed: {exc}")

            if row_cols[7].button("Delete", key=f"del_weaviate_{row['id']}"):
                try:
                    file_upload_id = (
                        row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    )
                    weaviate_result = call_weaviate_delete_api(
                        ingestion_api_url=ingestion_api_url,
                        class_name=None,
                        file_upload_id=int(file_upload_id),
                        file_name=str(row["file_name"]),
                        timeout_sec=timeout_sec,
                    )
                    update_ingestion_result(
                        target="weaviate",
                        row_id=row["id"],
                        status="NOT_INGESTED",
                        pipeline_id=None,
                        error_text=None,
                        response_obj=weaviate_result,
                    )
                    st.info(f"Weaviate delete result: {weaviate_result}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Weaviate delete failed: {exc}")

            if row_cols[8].button("Delete", key=f"del_neo4j_{row['id']}"):
                try:
                    file_upload_id = (
                        row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    )
                    neo4j_result = call_neo4j_delete_api(
                        ingestion_api_url=ingestion_api_url,
                        file_upload_id=int(file_upload_id),
                        file_name=str(row["file_name"]),
                        timeout_sec=timeout_sec,
                    )
                    update_ingestion_result(
                        target="neo4j",
                        row_id=row["id"],
                        status="NOT_INGESTED",
                        pipeline_id=None,
                        error_text=None,
                        response_obj=neo4j_result,
                    )
                    st.info(f"Neo4j delete result: {neo4j_result}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Neo4j delete failed: {exc}")

            if row_cols[9].button("Delete", key=f"del_file_{row['id']}"):
                try:
                    file_upload_id = (
                        row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    )
                    if delete_remote_data_on_file_delete:
                        weaviate_result = call_weaviate_delete_api(
                            ingestion_api_url=ingestion_api_url,
                            class_name=None,
                            file_upload_id=int(file_upload_id),
                            file_name=str(row["file_name"]),
                            timeout_sec=timeout_sec,
                        )
                        neo4j_result = call_neo4j_delete_api(
                            ingestion_api_url=ingestion_api_url,
                            file_upload_id=int(file_upload_id),
                            file_name=str(row["file_name"]),
                            timeout_sec=timeout_sec,
                        )
                        st.info(f"Weaviate delete result: {weaviate_result}")
                        st.info(f"Neo4j delete result: {neo4j_result}")
                    result = delete_uploaded_file(
                        row_id=row["id"], stored_path=row["stored_path"]
                    )
                    st.success(result["message"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"File delete failed: {exc}")

            if row["last_error"]:
                st.caption(f"last_error={row['last_error']}")
            if row["ingestion_response"]:
                try:
                    parsed = json.loads(row["ingestion_response"])
                except (json.JSONDecodeError, TypeError, ValueError):
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("neo4j"):
                    st.caption(f"neo4j={parsed.get('neo4j')}")

    if st.button(
        "Sync Weaviate Status (from Weaviate data)", key="sync_weaviate_statuses_button"
    ):
        try:
            result = sync_weaviate_statuses(
                weaviate_url=WEAVIATE_URL, timeout_sec=timeout_sec
            )
            st.success(f"Sync done: {result}")
            st.rerun()
        except Exception as exc:
            st.error(f"Sync failed: {exc}")

    if st.button(
        "Sync Neo4j Status (from Neo4j data)", key="sync_neo4j_statuses_button"
    ):
        try:
            result = sync_neo4j_statuses()
            st.success(f"Sync done: {result}")
            st.rerun()
        except Exception as exc:
            st.error(f"Sync failed: {exc}")


def main() -> None:
    ensure_storage()
    st.set_page_config(page_title="Ingestion UI", page_icon="📥", layout="wide")
    st.title("Ingestion UI")
    st.caption(
        "Upload PDF metadata locally and trigger ingestion-api to process Weaviate ingestion."
    )

    with st.sidebar:
        st.subheader("Backend")
        ingestion_api_url = INGESTION_API_URL
        st.caption(f"Ingestion API URL (.env): `{ingestion_api_url}`")
        timeout_sec = st.slider(
            "API Timeout (sec)", min_value=5, max_value=30, value=10
        )
        delete_remote_data_on_file_delete = st.checkbox(
            "Delete Weaviate and Neo4j data on file delete", value=True
        )

        st.subheader("Weaviate")

        st.caption(f"Weaviate URL (.env): `{WEAVIATE_URL}`")
        st.caption(f"Loaded dotenv path: `{INGESTION_API_DOTENV_PATH}`")

        st.subheader("Live Checks")
        if st.button("API Health Check"):
            result = call_backend_health_check(
                ingestion_api_url=ingestion_api_url,
                path="/health",
                timeout_sec=timeout_sec,
            )
            if result["ok"]:
                st.success(result)
            else:
                st.error(result)
        if st.button("SQLite DB Live Check"):
            result = call_backend_health_check(
                ingestion_api_url=ingestion_api_url,
                path="/health/sqlite-live",
                timeout_sec=timeout_sec,
            )
            if result["ok"]:
                st.success(result)
            else:
                st.error(result)
        if st.button("Weaviate Live Check"):
            result = call_backend_health_check(
                ingestion_api_url=ingestion_api_url,
                path="/health/weaviate-live",
                timeout_sec=timeout_sec,
            )
            if result["ok"]:
                st.success(result)
            else:
                st.error(result)
        if st.button("Neo4j Live Check"):
            result = call_backend_health_check(
                ingestion_api_url=ingestion_api_url,
                path="/health/neo4j-live",
                timeout_sec=timeout_sec,
            )
            if result["ok"]:
                st.success(result)
            else:
                st.error(result)

    st.subheader("Upload PDF")
    st.caption("Weaviate Ingestion Parameters")
    st.caption(
        "These values are stored with the file and reused later when you click 'Ingest to Weaviate'."
    )
    rag_class_name = st.selectbox(
        "Class / Label",
        options=CLASS_OPTIONS,
        index=0,
        format_func=class_display_name,
    )
    if rag_class_name == WEAVIATE_MACHINE_CLASS:
        company_id = st.number_input("company_id", min_value=0, value=0, step=1)
        machine_cat = st.number_input("machine_cat", min_value=0, value=0, step=1)
        machine_id = st.number_input("machine_id", min_value=0, value=0, step=1)
    else:
        st.caption(
            f"Class '{WEAVIATE_GENERAL_CLASS}' does not use company/machine fields."
        )
        company_id = 0
        machine_cat = 0
        machine_id = 0
    uploaded = st.file_uploader("Select PDF", type=["pdf"])

    if uploaded is not None:
        st.write(f"Selected: `{uploaded.name}` ({uploaded.size} bytes)")
        if st.button("Save to Local DB", type="primary"):
            result = persist_uploaded_file(
                file_name=uploaded.name,
                file_bytes=uploaded.getvalue(),
                class_name=rag_class_name,
                company_id=int(company_id),
                machine_cat=int(machine_cat),
                machine_id=int(machine_id),
            )
            if result["ok"]:
                st.success(result["message"])
                st.rerun()
            else:
                st.warning(result["message"])

    render_uploaded_files(
        ingestion_api_url=ingestion_api_url,
        timeout_sec=timeout_sec,
        delete_remote_data_on_file_delete=delete_remote_data_on_file_delete,
    )

    st.subheader("Weaviate Summary")
    if st.button("Refresh Weaviate Summary"):
        try:
            summary = weaviate_summary(
                weaviate_url=WEAVIATE_URL, class_name=rag_class_name
            )
            st.json(summary)
            documents = summary.get("documents", [])
            if documents:
                st.caption(
                    "Per-document chunk breakdown (paragraph/table/image + detailed table/image chunk types)"
                )
                st.dataframe(
                    [
                        {
                            "file_name": item.get("file_name", ""),
                            "chunk_count": item.get("chunk_count", 0),
                            "paragraph_chunks": item.get("paragraph_chunks", 0),
                            "table_chunks": item.get("table_chunks", 0),
                            "table_row_chunks": item.get("table_row_chunks", 0),
                            "table_summary_chunks": item.get("table_summary_chunks", 0),
                            "image_chunks": item.get("image_chunks", 0),
                            "image_summary_chunks": item.get("image_summary_chunks", 0),
                            "image_context_chunks": item.get("image_context_chunks", 0),
                            "image_ocr_chunks": item.get("image_ocr_chunks", 0),
                            "table_count": item.get("table_count", 0),
                            "image_count": item.get("image_count", 0),
                        }
                        for item in documents
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as exc:
            st.error(f"Failed to fetch Weaviate summary: {exc}")

    st.subheader("Neo4j Summary")
    if st.button("Refresh Neo4j Summary"):
        try:
            st.caption(
                f"Summary target label: `{class_display_name(rag_class_name)}` ({rag_class_name})"
            )
            result = neo4j_summary(
                ingestion_api_url=ingestion_api_url,
                label=rag_class_name,
                timeout_sec=timeout_sec,
            )
            st.json(result)
        except Exception as exc:
            st.error(f"Failed to fetch Neo4j summary: {exc}")


if __name__ == "__main__":
    main()
