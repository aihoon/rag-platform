"""Ingestion service: read uploaded PDF from ingestion-ui DB and index to Weaviate."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pdfplumber
from langsmith import traceable

from ..config.settings import Settings
from .neo4j_ingest_service import ingest_to_neo4j
from .weaviate_ingest_service import ingest_to_weaviate


@dataclass
class UploadedFileRecord:
    row_id: int
    file_name: str
    stored_path: str
    company_id: int
    machine_cat: int
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
        machine_cat=int(row["machine_cat"]),
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


@traceable(name="run_ingestion_pipeline", run_type="chain")
def run_ingestion_pipeline(
    *,
    settings: Settings,
    logger: Any,
    class_name: Optional[str],
    company_id: Optional[int],
    machine_cat: Optional[int],
    machine_id: Optional[int],
    weaviate_enabled: Optional[bool],
    neo4j_enabled: Optional[bool],
    file_upload_id: int,
    file_name: str,
) -> dict:
    record = _load_uploaded_file_record(settings, file_upload_id)
    pdf_path = Path(record.stored_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"uploaded file not found: {pdf_path}")

    if company_id is not None and record.company_id != company_id:
        raise ValueError(f"company_id mismatch: request={company_id}, stored={record.company_id}")
    if machine_id is not None and record.machine_id != machine_id:
        raise ValueError(f"machine_id mismatch: request={machine_id}, stored={record.machine_id}")
    if machine_cat is not None and record.machine_cat != machine_cat:
        raise ValueError(f"machine_cat mismatch: request={machine_cat}, stored={record.machine_cat}")

    pages = _extract_pages(pdf_path, logger)
    if not pages:
        raise ValueError("no extractable text found in PDF")

    effective_weaviate = True if weaviate_enabled is None else bool(weaviate_enabled)
    effective_neo4j = settings.neo4j_enabled if neo4j_enabled is None else (settings.neo4j_enabled and neo4j_enabled)
    if not effective_weaviate and not effective_neo4j:
        raise ValueError("Both weaviate_enabled and neo4j_enabled are false")

    if class_name is None:
        class_name = settings.weaviate_default_class
    include_machine_fields = class_name == settings.weaviate_machine_class_name

    doc_id = Path(file_name).stem
    chunks = _build_chunks_from_pages(doc_id, pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("no chunks generated from PDF text")
    logger.info(
        f"chunking done|doc_id={doc_id}|chunk_size={settings.chunk_size}|overlap={settings.chunk_overlap}|"
        f"chunk_count={len(chunks)}"
    )

    weaviate_stats = None
    if effective_weaviate:
        weaviate_stats = ingest_to_weaviate(
            settings=settings,
            logger=logger,
            class_name=class_name,
            include_machine_fields=include_machine_fields,
            company_id=company_id,
            machine_cat=machine_cat,
            machine_id=machine_id,
            file_upload_id=file_upload_id,
            file_name=file_name,
            chunks=chunks,
        )

    neo4j_stats = None
    if effective_neo4j:
        doc_props = {
            "id": doc_id,
            "file_name": file_name,
            "company_id": company_id,
            "machine_id": machine_id,
            "machine_cat": machine_cat,
            "file_upload_id": file_upload_id,
            "class_name": class_name,
        }
        neo4j_stats = ingest_to_neo4j(
            settings=settings,
            logger=logger,
            doc_id=doc_id,
            doc_props=doc_props,
            chunks=chunks,
        )

    result = {
        "status": "ok",
        "pipeline_id": f"{company_id}_{machine_id}_{file_upload_id}",
        "class_name": class_name or "",
        "chunk_count": weaviate_stats.object_count if weaviate_stats else 0,
        "weaviate_enabled": effective_weaviate,
        "neo4j_enabled": effective_neo4j,
    }
    if neo4j_stats:
        result["neo4j"] = {
            "chunk_count": neo4j_stats.chunk_count,
            "entity_count": neo4j_stats.entity_count,
            "relation_count": neo4j_stats.relation_count,
        }
    return result
