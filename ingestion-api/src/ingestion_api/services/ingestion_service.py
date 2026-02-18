"""Ingestion service: read uploaded PDF from ingestion-ui DB and index to Weaviate."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
import requests
from openai import OpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai

from ..config.settings import Settings
from .vector_delete_service import delete_chunks


@dataclass
class UploadedFileRecord:
    row_id: int
    file_name: str
    stored_path: str
    company_id: int
    machine_cat: str
    machine_id: int


@dataclass
class TextChunk:
    chunk_id: str
    page_number: int
    start_char: int
    end_char: int
    text: str


def _load_uploaded_file_record(settings: Settings, file_upload_id: int) -> UploadedFileRecord:
    db_path = settings.resolved_ingestion_ui_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"ingestion-ui DB not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {r[1] for r in conn.execute("PRAGMA table_info(uploaded_files)").fetchall()}
        required_columns = {"company_id", "machine_cat", "machine_id"}
        missing_columns = required_columns - columns
        if missing_columns:
            raise ValueError(
                "SQLite schema mismatch: missing required columns "
                f"{sorted(missing_columns)}. Reset DB file and restart: {db_path}"
            )
        query = (
            "SELECT id, file_name, stored_path, company_id, machine_cat, machine_id "
            "FROM uploaded_files WHERE id = ?"
        )
        row = conn.execute(query, (file_upload_id,)).fetchone()

    if row is None:
        raise ValueError(f"file_upload_id not found in ingestion-ui DB: {file_upload_id}")

    return UploadedFileRecord(
        row_id=int(row["id"]),
        file_name=str(row["file_name"]),
        stored_path=str(row["stored_path"]),
        company_id=int(row["company_id"]),
        machine_cat=str(row["machine_cat"]),
        machine_id=int(row["machine_id"]),
    )


def _extract_pages(pdf_path: Path, logger: Any) -> list[dict]:
    pages: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"pdf_extract start|path={pdf_path}|total_pages={total_pages}")
        for idx, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"page": idx, "text": text})
            if idx == 1 or idx == total_pages or idx % 10 == 0:
                logger.info(f"pdf_extract progress|page={idx}/{total_pages}|has_text={bool(text)}")
    logger.info(f"pdf_extract done|path={pdf_path}|pages_with_text={len(pages)}")
    return pages


def _make_chunk_id(doc_id: str, page_number: int, start: int, end: int, text: str) -> str:
    digest = hashlib.sha1(f"{doc_id}:{page_number}:{start}:{end}:{text[:64]}".encode("utf-8")).hexdigest()[:12]
    return f"{doc_id}_p{page_number}_{start}_{end}_{digest}"


def _simple_char_chunk(text: str, chunk_size: int, overlap: int) -> list[tuple[int, int, str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    if not text:
        return []

    chunks: list[tuple[int, int, str]] = []
    text_len = len(text)
    start = 0
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append((start, end, chunk_text))
        if end == text_len:
            break
        start = end - overlap
    return chunks


def _build_chunks_from_pages(doc_id: str, pages: list[dict], chunk_size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        page_number = int(page["page"])
        page_text = str(page["text"])
        for start, end, chunk_text in _simple_char_chunk(page_text, chunk_size, overlap):
            chunks.append(
                TextChunk(
                    chunk_id=_make_chunk_id(doc_id, page_number, start, end, chunk_text),
                    page_number=page_number,
                    start_char=start,
                    end_char=end,
                    text=chunk_text,
                )
            )
    return chunks


def _ensure_weaviate_class(settings: Settings, class_name: str) -> None:
    """
    Ensure the target Weaviate class exists before object upsert.

    This function checks the current schema and creates the class when missing,
    so ingestion can write vectors without schema-not-found failures.
    """
    base_url = settings.weaviate_url.rstrip("/")
    schema_resp = requests.get(f"{base_url}/v1/schema", timeout=settings.request_timeout)
    schema_resp.raise_for_status()
    classes = schema_resp.json().get("classes", [])
    existing = {c.get("class") for c in classes}
    if class_name in existing:
        return

    schema_body = {
        "class": class_name,
        "vectorizer": "none",
        "properties": [
            {"name": "content", "dataType": ["text"]},
            {"name": "source", "dataType": ["string"]},
            {"name": "page_number", "dataType": ["int"]},
            {"name": "machine_id", "dataType": ["string"]},
            {"name": "file_upload_id", "dataType": ["string"]},
            {"name": "machine_cat", "dataType": ["string"]},
        ],
    }
    create_resp = requests.post(f"{base_url}/v1/schema", json=schema_body, timeout=settings.request_timeout)
    create_resp.raise_for_status()


def _embed_chunks(client: OpenAI, model: str, chunks: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    batch_size = 64
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vectors.extend([item.embedding for item in resp.data])
    return vectors

@traceable(name="run_ingestion_pipeline", run_type="chain")
def run_ingestion_pipeline(
    *,
    settings: Settings,
    logger: Any,
    company_id: int,
    machine_cat: str,
    machine_id: int,
    file_upload_id: int,
    file_name: str,
) -> dict:
    record = _load_uploaded_file_record(settings, file_upload_id)
    pdf_path = Path(record.stored_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"uploaded file not found: {pdf_path}")

    if record.company_id != company_id:
        raise ValueError(f"company_id mismatch: request={company_id}, stored={record.company_id}")
    if record.machine_id != machine_id:
        raise ValueError(f"machine_id mismatch: request={machine_id}, stored={record.machine_id}")
    if record.machine_cat != machine_cat:
        raise ValueError(f"machine_cat mismatch: request={machine_cat}, stored={record.machine_cat}")

    pages = _extract_pages(pdf_path, logger)
    if not pages:
        raise ValueError("no extractable text found in PDF")

    class_name = f"{settings.class_prefix}{company_id}"
    _ensure_weaviate_class(settings, class_name)
    pre_delete_result = delete_chunks(
        settings=settings,
        company_id=company_id,
        machine_cat=machine_cat,
        machine_id=machine_id,
        file_upload_id=file_upload_id,
        file_name=file_name,
        class_name=class_name,
    )
    logger.info(
        f"weaviate pre_delete done|class_name={class_name}|"
        f"deleted_count={pre_delete_result.get('deleted_count', 0)}"
    )

    doc_id = Path(file_name).stem
    chunks = _build_chunks_from_pages(doc_id, pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("no chunks generated from PDF text")
    logger.info(
        f"chunking done|doc_id={doc_id}|chunk_size={settings.chunk_size}|overlap={settings.chunk_overlap}|"
        f"chunk_count={len(chunks)}"
    )

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for embedding")
    # openai_client = OpenAI(api_key=settings.openai_api_key)
    openai_client = wrap_openai(OpenAI(api_key=settings.openai_api_key))
    vectors = _embed_chunks(openai_client, settings.embedding_model, [chunk.text for chunk in chunks])

    logger.info(f"embedding done|model={settings.embedding_model}|vector_count={len(vectors)}")

    objects = []
    for chunk, vector in zip(chunks, vectors):
        objects.append({
            "class": class_name,
            "vector": vector,
                "properties": {
                    "content": chunk.text,
                    "source": file_name,
                    "page_number": int(chunk.page_number),
                    "machine_id": str(machine_id),
                    "file_upload_id": str(file_upload_id),
                    "machine_cat": machine_cat,
                },
        })

    batch_resp = requests.post(
        f"{settings.weaviate_url.rstrip('/')}/v1/batch/objects",
        json={"objects": objects},
        timeout=settings.request_timeout,
    )
    batch_resp.raise_for_status()
    logger.info(f"weaviate upsert done|class_name={class_name}|object_count={len(objects)}")

    return {
        "status": "ok",
        "pipeline_id": f"{company_id}_{machine_id}_{file_upload_id}",
        "class_name": class_name,
        "chunk_count": len(objects),
    }
