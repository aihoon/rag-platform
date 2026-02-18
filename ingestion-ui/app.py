"""
Streamlit ingestion UI for local upload tracking and ingestion API triggering.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT_DIR = BASE_DIR.parent
if str(REPO_ROOT_DIR) not in sys.path:
    sys.path.append(str(REPO_ROOT_DIR))
from shared.schemas.ingestion import IngestionRunRequest, VectorDeleteRequest
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "ingestion_ui.db"
INGESTION_API_DOTENV_PATH = "../.env"

load_dotenv(dotenv_path=INGESTION_API_DOTENV_PATH, override=True)

DEFAULT_INGESTION_API_URL = os.environ.get( "INGESTION_API_URL", "http://localhost:8000")
DEFAULT_WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://localhost:8080")
DEFAULT_RAG_CLASS = os.environ.get("RAG_CLASS_NAME", "RagDocumentChunk")
DEFAULT_COMPANY_ID = int(os.environ.get("INGESTION_DEFAULT_COMPANY_ID", "1"))
DEFAULT_MACHINE_CAT = os.environ.get("INGESTION_DEFAULT_MACHINE_CAT", "general")
DEFAULT_MACHINE_ID = int(os.environ.get("INGESTION_DEFAULT_MACHINE_ID", "1"))
TupleParams = tuple[Any, ...]


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'UPLOADED',
                company_id INTEGER NOT NULL DEFAULT 1,
                machine_cat TEXT NOT NULL DEFAULT 'general',
                machine_id INTEGER NOT NULL DEFAULT 1,
                file_upload_id INTEGER,
                pipeline_id TEXT,
                ingested_at TEXT,
                last_error TEXT,
                ingestion_response TEXT
            )
            """
        )
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(uploaded_files)").fetchall()
        }
        if "company_id" not in existing_columns:
            raise ValueError(
                "SQLite schema mismatch: missing required 'company_id'. "
                f"Reset DB file and restart: {DB_PATH}"
            )
        if "machine_cat" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN machine_cat TEXT NOT NULL DEFAULT 'general'"
            )
        if "machine_id" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN machine_id INTEGER NOT NULL DEFAULT 1"
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
    company_id: int,
    machine_cat: str,
    machine_id: int,
) -> Dict[str, Any]:
    sha = file_sha256(file_bytes)
    existing = db_fetchall("SELECT * FROM uploaded_files WHERE sha256 = ?", (sha,))
    if existing:
        return {"ok": False, "message": "This file already exists in local DB.", "id": existing[0]["id"]}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = file_name.replace("/", "_").replace("\\", "_")
    stored_name = f"{timestamp}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(file_bytes)

    db_execute( ###
        """
        INSERT INTO uploaded_files (
            file_name, stored_path, file_size, sha256, uploaded_at, status, company_id, machine_cat, machine_id
        ) VALUES (?, ?, ?, ?, ?, 'UPLOADED', ?, ?, ?)
        """,
        ( ###
            file_name, ###
            str(stored_path), ###
            len(file_bytes), ###
            sha, ###
            datetime.now(timezone.utc).isoformat(), ###
            company_id, ###
            machine_cat, ###
            machine_id, ###
        ), ###
    ) ###
    return {"ok": True, "message": "File saved to local DB and disk."}


def list_uploaded_files() -> List[sqlite3.Row]:
    return db_fetchall("SELECT * FROM uploaded_files ORDER BY id DESC")


def delete_uploaded_file(*, row_id: int, stored_path: str) -> Dict[str, Any]:
    file_path = Path(stored_path)
    if file_path.exists():
        file_path.unlink()
    db_execute("DELETE FROM uploaded_files WHERE id = ?", (row_id,))
    return {"ok": True, "message": f"Deleted row #{row_id} and local file."}


def call_vector_delete_api(
    *,
    ingestion_api_url: str,
    company_id: int,
    machine_cat: str,
    machine_id: int,
    file_upload_id: int,
    file_name: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/chunks"
    payload = VectorDeleteRequest(
        company_id=company_id,
        machine_cat=machine_cat,
        machine_id=machine_id,
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
    company_id: int,
    machine_cat: str,
    machine_id: int,
    file_upload_id: int,
    file_name: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    endpoint = f"{ingestion_api_url.rstrip('/')}/run"
    payload = IngestionRunRequest(
        company_id=company_id,
        machine_cat=machine_cat,
        machine_id=machine_id,
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
    return {"ok": resp.ok, "status_code": resp.status_code, "endpoint": endpoint, "body": body}


def update_ingestion_result(
    *,
    row_id: int,
    status: str,
    pipeline_id: Optional[str],
    error_text: Optional[str],
    response_obj: Optional[Dict[str, Any]],
) -> None:
    db_execute(
        """
        UPDATE uploaded_files
        SET status = ?,
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
            datetime.now(timezone.utc).isoformat() if status == "INGEST_REQUESTED" else None,
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

    count_query = f'{{Aggregate{{{class_name}{{meta{{count}}}}}}}}'
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

    ###get_query = (
    ###    "{Get{%s(limit:200){source page companyId machineId fileUploadId}}}" % class_name
    ###)
    get_query = ( ###
        "{Get{%s(limit:200){source page_number machine_id file_upload_id machine_cat}}}" % class_name ###
    ) ###
    get_resp = requests.post(
        f"{weaviate_url.rstrip('/')}/v1/graphql",
        json={"query": get_query},
        timeout=20,
    )
    get_resp.raise_for_status()
    rows = get_resp.json().get("data", {}).get("Get", {}).get(class_name, [])

    source_counter = Counter([r.get("source", "unknown") for r in rows])
    return {
        "classes": class_names,
        "target_class": class_name,
        "target_count": count,
        "sampled_rows": len(rows),
        "top_sources": source_counter.most_common(10),
    }


def render_uploaded_files(
    *,
    ingestion_api_url: str,
    timeout_sec: int,
    delete_vector_on_remove: bool,
) -> None:
    st.subheader("Uploaded Files")
    rows = list_uploaded_files()
    if not rows:
        st.info("No files uploaded yet.")
        return

    for row in rows:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 3])
            cols[0].write(f"**#{row['id']}** {row['file_name']}")
            cols[1].write(f"Status: `{row['status']}`")
            cols[2].write(f"Company / Machine Category / Machine: "
                          f"`{row['company_id']}/{row['machine_cat']}/{row['machine_id']}`")
            cols[3].write(f"Uploaded: `{row['uploaded_at']}`")

            action_cols = st.columns([1, 1, 1, 3])
            if action_cols[0].button("Run Ingestion", key=f"run_{row['id']}"):
                file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                try:
                    result = call_ingestion_api(
                        ingestion_api_url=ingestion_api_url,
                        company_id=row["company_id"],
                        machine_cat=row["machine_cat"],
                        machine_id=row["machine_id"],
                        file_upload_id=int(file_upload_id),
                        file_name=row["file_name"],
                        timeout_sec=timeout_sec,
                    )
                    update_ingestion_result(
                        row_id=row["id"],
                        status="INGEST_REQUESTED",
                        pipeline_id=result.get("pipeline_id"),
                        error_text=None,
                        response_obj=result,
                    )
                    st.success(f"Pipeline requested: {result}")
                    st.rerun()
                except Exception as exc:
                    update_ingestion_result(
                        row_id=row["id"],
                        status="FAILED",
                        pipeline_id=None,
                        error_text=str(exc),
                        response_obj=None,
                    )
                    st.error(f"Ingestion API call failed: {exc}")

            if action_cols[1].button("Mark Ingested", key=f"done_{row['id']}"):
                update_ingestion_result(
                    row_id=row["id"],
                    status="INGESTED",
                    pipeline_id=row["pipeline_id"],
                    error_text=None,
                    response_obj=None,
                )
                st.rerun()

            if action_cols[2].button("Delete", key=f"del_{row['id']}"):
                try:
                    file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    if delete_vector_on_remove:
                        vector_result = call_vector_delete_api(
                            ingestion_api_url=ingestion_api_url,
                            company_id=int(row["company_id"]),
                            machine_cat=str(row["machine_cat"]),
                            machine_id=int(row["machine_id"]),
                            file_upload_id=int(file_upload_id),
                            file_name=str(row["file_name"]),
                            timeout_sec=timeout_sec,
                        )
                        st.info(f"Vector delete result: {vector_result}")
                    result = delete_uploaded_file(row_id=row["id"], stored_path=row["stored_path"])
                    st.success(result["message"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")

            if row["pipeline_id"] or row["last_error"]:
                st.caption(f"pipeline_id={row['pipeline_id']} error={row['last_error']}")


def main() -> None:
    ensure_storage()
    st.set_page_config(page_title="Ingestion UI", page_icon="📥", layout="wide")
    st.title("Ingestion UI")
    st.caption("Upload PDF metadata locally and trigger ingestion-api to process vector ingestion.")

    with st.sidebar:
        st.subheader("Backend")
        ingestion_api_url = st.text_input("Ingestion API URL", value=DEFAULT_INGESTION_API_URL)
        timeout_sec = st.slider("API Timeout (sec)", min_value=5, max_value=180, value=30)
        delete_vector_on_remove = st.checkbox("Delete vector data on file delete", value=True)

        st.subheader("Vector DB")
        weaviate_url = st.text_input("Weaviate URL", value=DEFAULT_WEAVIATE_URL)
        rag_class_name = st.text_input("RAG Class Name", value=DEFAULT_RAG_CLASS)

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

    st.subheader("Upload PDF")
    company_id = st.number_input("company_id", min_value=1, value=DEFAULT_COMPANY_ID, step=1)
    machine_cat = st.text_input("machine_cat", value=DEFAULT_MACHINE_CAT)
    machine_id = st.number_input("machine_id", min_value=1, value=DEFAULT_MACHINE_ID, step=1)
    uploaded = st.file_uploader("Select PDF", type=["pdf"])

    if uploaded is not None:
        st.write(f"Selected: `{uploaded.name}` ({uploaded.size} bytes)")
        if st.button("Save to Local DB", type="primary"):
            result = persist_uploaded_file(
                file_name=uploaded.name,
                file_bytes=uploaded.getvalue(),
                company_id=int(company_id),
                machine_cat=machine_cat.strip() or DEFAULT_MACHINE_CAT,
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
        delete_vector_on_remove=delete_vector_on_remove,
    )

    st.subheader("Weaviate Summary")
    if st.button("Refresh Weaviate Summary"):
        try:
            summary = weaviate_summary(weaviate_url=weaviate_url, class_name=rag_class_name)
            st.json(summary)
        except Exception as exc:
            st.error(f"Failed to fetch Weaviate summary: {exc}")


if __name__ == "__main__":
    main()
