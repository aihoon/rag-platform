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
import streamlit.components.v1 as components ### ###
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT_DIR = BASE_DIR.parent
if str(REPO_ROOT_DIR) not in sys.path:
    sys.path.append(str(REPO_ROOT_DIR))
from shared.schemas.ingestion import IngestionRunRequest, WeaviateDeleteRequest, GraphDeleteRequest as Neo4jDeleteRequest
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "ingestion_ui.db"
INGESTION_API_DOTENV_PATH = "../.env"

load_dotenv(dotenv_path=INGESTION_API_DOTENV_PATH, override=True)

INGESTION_API_URL = os.environ.get( "INGESTION_API_URL", "http://localhost:8000")
WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_GENERAL_CLASS = os.environ.get("WEAVIATE_GENERAL_CLASS_NAME", "General")
WEAVIATE_MACHINE_CLASS = os.environ.get("WEAVIATE_MACHINE_CLASS_NAME", "Machine")
WEAVIATE_DEFAULT_LABEL = os.environ.get("WEAVIATE_DEFAULT_LABEL", "General")
NEO4J_DEFAULT_LABEL = os.environ.get("NEO4J_DEFAULT_LABEL", "General")

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
                weaviate_status TEXT NOT NULL DEFAULT 'NOT_INGESTED',
                neo4j_status TEXT NOT NULL DEFAULT 'NOT_INGESTED',
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
                "ALTER TABLE uploaded_files ADD COLUMN machine_cat INTEGER NOT NULL DEFAULT 0"
            )
        if "machine_id" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN machine_id INTEGER NOT NULL DEFAULT 0"
            )
        if "class_name" not in existing_columns:
            conn.execute(
                "ALTER TABLE uploaded_files ADD COLUMN class_name TEXT NOT NULL DEFAULT 'Machine'"
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
        return {"ok": False, "message": "This file already exists in local DB.", "id": existing[0]["id"]}

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


def has_active_ingestion(rows: List[sqlite3.Row]) -> bool: ### ###
    active_statuses = {"REQUESTED", "RUNNING"} ### ###
    return any( ### ###
        str(row["weaviate_status"]) in active_statuses or str(row["neo4j_status"]) in active_statuses ### ###
        for row in rows ### ###
    ) ### ###


def delete_uploaded_file(*, row_id: int, stored_path: str) -> Dict[str, Any]:
    file_path = Path(stored_path)
    if file_path.exists():
        file_path.unlink()
    db_execute("DELETE FROM uploaded_files WHERE id = ?", (row_id,))
    return {"ok": True, "message": f"Deleted row #{row_id} and local file."}


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
    return {"ok": resp.ok, "status_code": resp.status_code, "endpoint": endpoint, "body": body}


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
            datetime.now(timezone.utc).isoformat()
                if status in {"REQUESTED", "INGESTED"} else None,
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
    if not class_names or class_name not in class_names:
        return {
            "classes": class_names,
            "target_class": class_name,
            "target_count": 0,
            "sampled_rows": 0,
            "top_sources": [],
        }

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

    if class_name == WEAVIATE_MACHINE_CLASS:
        field_block = "source page_number machine_id file_upload_id machine_cat company_id"
    else:
        field_block = "source page_number file_upload_id"
    get_query = "{Get{%s(limit:200){%s}}}" % (class_name, field_block)
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


def neo4j_summary(*, ingestion_api_url: str, label: Optional[str], timeout_sec: int, ) -> Dict[str, Any]:
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
    delete_remote_data_on_file_delete: bool, ### ###
) -> None:
    st.subheader("Uploaded Files")
    st.caption("Ingest uses the saved Class/Label and machine metadata shown on each row.")
    rows = list_uploaded_files()
    if not rows:
        st.info("No files uploaded yet.")
        return
    if has_active_ingestion(rows): ### ###
        st.caption("Auto-refreshing every 10 seconds while ingestion is REQUESTED or RUNNING.") ### ###
        components.html( ### ###
            "<script>setTimeout(function(){window.parent.location.reload();}, 10000);</script>", ### ###
            height=0, ### ###
        ) ### ###

    for row in rows:
        with st.container(border=True):
            cols = st.columns([3, 3, 2, 3])
            cols[0].write(f"**#{row['id']}** {row['file_name']}")
            cols[1].write(
                f"Weaviate: `{row['weaviate_status']}`\nNeo4j: `{row['neo4j_status']}`"
            )
            cols[2].write(f"Class/Label: `{row['class_name']}`")
            cols[3].write(f"Company / Machine Category / Machine: "
                          f"`{row['company_id']}/{row['machine_cat']}/{row['machine_id']}`")
            st.caption(f"Uploaded: `{row['uploaded_at']}`")

            is_machine_class = row["class_name"] == WEAVIATE_MACHINE_CLASS
            weaviate_busy = str(row["weaviate_status"]) in {"REQUESTED", "RUNNING"} ### ###
            neo4j_busy = str(row["neo4j_status"]) in {"REQUESTED", "RUNNING"} ### ###
            action_cols = st.columns([1, 1, 1, 1, 1]) ### ###
            if action_cols[0].button("Ingest to Weaviate", key=f"run_weaviate_{row['id']}", disabled=weaviate_busy): ### ###
                file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                try:
                    result = call_ingestion_api(
                        ingestion_api_url=ingestion_api_url,
                        class_name=row["class_name"],
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
                        status="REQUESTED", ### ###
                        row_id=row["id"],
                        pipeline_id=result.get("pipeline_id"),
                        error_text=None,
                        response_obj=result,
                    )
                    st.success(f"Weaviate ingest requested: {result}") ### ###
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

            if action_cols[1].button("Ingest to Neo4j", key=f"run_neo4j_{row['id']}", disabled=neo4j_busy): ### ###
                file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                try:
                    result = call_ingestion_api(
                        ingestion_api_url=ingestion_api_url,
                        class_name=row["class_name"],
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
                        status="REQUESTED", ### ###
                        pipeline_id=result.get("pipeline_id"),
                        error_text=None,
                        response_obj=result,
                    )
                    st.success(f"Neo4j ingest requested: {result}") ### ###
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

            if action_cols[2].button("Delete Weaviate Data", key=f"del_weaviate_{row['id']}"): ### ###
                try:
                    file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    weaviate_result = call_weaviate_delete_api( ### ###
                        ingestion_api_url=ingestion_api_url, ### ###
                        class_name=row["class_name"], ### ###
                        file_upload_id=int(file_upload_id), ### ###
                        file_name=str(row["file_name"]), ### ###
                        timeout_sec=timeout_sec, ### ###
                    ) ### ###
                    st.info(f"Weaviate delete result: {weaviate_result}") ### ###
                except Exception as exc:
                    st.error(f"Weaviate delete failed: {exc}") ### ###

            if action_cols[3].button("Delete Neo4j Data", key=f"del_neo4j_{row['id']}"): ### ###
                try:
                    file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"]
                    neo4j_result = call_neo4j_delete_api( ### ###
                        ingestion_api_url=ingestion_api_url, ### ###
                        file_upload_id=int(file_upload_id), ### ###
                        file_name=str(row["file_name"]), ### ###
                        timeout_sec=timeout_sec, ### ###
                    ) ### ###
                    st.info(f"Neo4j delete result: {neo4j_result}") ### ###
                except Exception as exc:
                    st.error(f"Neo4j delete failed: {exc}") ### ###

            if action_cols[4].button("Delete File", key=f"del_file_{row['id']}"): ### ###
                try: ### ###
                    file_upload_id = row["file_upload_id"] if row["file_upload_id"] else row["id"] ### ###
                    if delete_remote_data_on_file_delete: ### ###
                        weaviate_result = call_weaviate_delete_api( ### ###
                            ingestion_api_url=ingestion_api_url, ### ###
                            class_name=row["class_name"], ### ###
                            file_upload_id=int(file_upload_id), ### ###
                            file_name=str(row["file_name"]), ### ###
                            timeout_sec=timeout_sec, ### ###
                        ) ### ###
                        neo4j_result = call_neo4j_delete_api( ### ###
                            ingestion_api_url=ingestion_api_url, ### ###
                            file_upload_id=int(file_upload_id), ### ###
                            file_name=str(row["file_name"]), ### ###
                            timeout_sec=timeout_sec, ### ###
                        ) ### ###
                        st.info(f"Weaviate delete result: {weaviate_result}") ### ###
                        st.info(f"Neo4j delete result: {neo4j_result}") ### ###
                    result = delete_uploaded_file(row_id=row["id"], stored_path=row["stored_path"]) ### ###
                    st.success(result["message"]) ### ###
                    st.rerun() ### ###
                except Exception as exc: ### ###
                    st.error(f"File delete failed: {exc}") ### ###

            if row["last_error"]:
                st.caption(f"last_error={row['last_error']}")
            if row["ingestion_response"]:
                try:
                    parsed = json.loads(row["ingestion_response"])
                except (json.JSONDecodeError, TypeError, ValueError):
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("neo4j"):
                    st.caption(f"neo4j={parsed.get('neo4j')}")


def main() -> None:
    ensure_storage()
    st.set_page_config(page_title="Ingestion UI", page_icon="📥", layout="wide")
    st.title("Ingestion UI")
    st.caption("Upload PDF metadata locally and trigger ingestion-api to process Weaviate ingestion.")

    with st.sidebar:
        st.subheader("Backend")
        ingestion_api_url = st.text_input("Ingestion API URL", value=INGESTION_API_URL)
        timeout_sec = st.slider("API Timeout (sec)", min_value=5, max_value=30, value=10) ### ###
        delete_remote_data_on_file_delete = st.checkbox( ### ###
            "Delete Weaviate and Neo4j data on file delete", value=True ### ###
        ) ### ###

        st.subheader("Weaviate")
        weaviate_url = st.text_input("Weaviate URL", value=WEAVIATE_URL)

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
    st.caption("These values are stored with the file and reused later when you click 'Ingest to Weaviate'.")
    rag_class_name = st.selectbox(
        "Class / Label",
        options=[WEAVIATE_GENERAL_CLASS, WEAVIATE_MACHINE_CLASS],
        index=0,
    )
    if rag_class_name == WEAVIATE_MACHINE_CLASS:
        company_id = st.number_input("company_id", min_value=0, value=0, step=1)
        machine_cat = st.number_input("machine_cat", min_value=0, value=0, step=1)
        machine_id = st.number_input("machine_id", min_value=0, value=0, step=1)
    else:
        st.caption("Class 'General' does not use company/machine fields.")
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
        delete_remote_data_on_file_delete=delete_remote_data_on_file_delete, ### ###
    )

    st.subheader("Weaviate Summary")
    if st.button("Refresh Weaviate Summary"):
        try:
            summary = weaviate_summary(weaviate_url=weaviate_url, class_name=rag_class_name)
            st.json(summary)
        except Exception as exc:
            st.error(f"Failed to fetch Weaviate summary: {exc}")

    st.subheader("Neo4j Summary")
    if st.button("Refresh Neo4j Summary"):
        try:
            result = neo4j_summary(
                ingestion_api_url=ingestion_api_url,
                label=None,
                timeout_sec=timeout_sec,
            )
            st.json(result)
        except Exception as exc:
            st.error(f"Failed to fetch Neo4j summary: {exc}")


if __name__ == "__main__":
    main()
