"""Table chunk building service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from shared.schemas.ingestion import TableRowChunk, TableSummaryChunk

from .normalize_service import NormalizedTable


def _build_row_text(*, row: dict[str, str], column_names: list[str]) -> str:
    parts: list[str] = []
    for key in column_names:
        value = str(row.get(key, "")).strip()
        if not value:
            continue
        parts.append(f"{key}: {value}")
    return " | ".join(parts)


def _collapse_text(value: str, *, max_chars: int = 180) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def _build_table_summary_text(*, normalized_table: NormalizedTable) -> str:
    row_count = len(normalized_table.rows)
    col_count = len(normalized_table.column_names)
    title = _collapse_text(normalized_table.table_title, max_chars=80)
    before_ctx = _collapse_text(normalized_table.context_before, max_chars=170)
    after_ctx = _collapse_text(normalized_table.context_after, max_chars=170)
    sample_values: list[str] = []
    for row in normalized_table.rows[:2]:
        for key in normalized_table.column_names[:4]:
            val = str(row.get(key, "")).strip()
            if val:
                sample_values.append(f"{key}={val}")
    sample_text = ", ".join(sample_values[:6])

    base = f"테이블 {normalized_table.table_id}는 {row_count}개 행, {col_count}개 열로 구성되어 있습니다."
    if title:
        base += f" 제목/주제: {title}."
    if normalized_table.column_names:
        columns_text = ", ".join(normalized_table.column_names[:8])
        base += f" 주요 컬럼: {columns_text}."
    if sample_text:
        base += f" 표 내부 핵심 값 예시: {sample_text}."
    if before_ctx:
        base += f" 표 앞 문맥: {before_ctx}."
    if after_ctx:
        base += f" 표 뒤 문맥: {after_ctx}."
    return base


def build_table_chunks(
    *,
    doc_id: str,
    file_name: str,
    ingest_version: int,
    embedding_model: str,
    embedding_version: int,
    normalized_table: NormalizedTable,
) -> tuple[list[TableRowChunk], list[TableSummaryChunk]]:
    now_iso = datetime.now(timezone.utc).isoformat()

    row_chunks: list[TableRowChunk] = []
    for row_index, row in enumerate(normalized_table.rows):
        row_key = f"r{row_index}"
        row_text = _build_row_text(row=row, column_names=normalized_table.column_names)
        row_chunks.append(
            TableRowChunk(
                doc_id=doc_id,
                file_name=file_name,
                page=normalized_table.page,
                table_id=normalized_table.table_id,
                row_id=row_key,
                row_index=row_index,
                table_title=normalized_table.table_title,
                section_title=normalized_table.section_title,
                header_path=normalized_table.header_path,
                column_names=normalized_table.column_names,
                column_schema=normalized_table.column_schema,
                units=normalized_table.units,
                row_text=row_text,
                table_row_json=json.dumps(
                    row, ensure_ascii=False, separators=(",", ":")
                ),
                bbox=normalized_table.bbox,
                parser_confidence=normalized_table.parser_confidence,
                needs_review=False,
                ingest_version=ingest_version,
                embedding_model=embedding_model,
                embedding_dim=0,
                embedding_version=embedding_version,
                created_at=now_iso,
            )
        )

    summary_text = _build_table_summary_text(normalized_table=normalized_table)
    summary_chunks = [
        TableSummaryChunk(
            doc_id=doc_id,
            file_name=file_name,
            page=normalized_table.page,
            table_id=normalized_table.table_id,
            table_title=normalized_table.table_title,
            section_title=normalized_table.section_title,
            column_names=normalized_table.column_names,
            units=normalized_table.units,
            summary_text=summary_text,
            row_count=len(normalized_table.rows),
            bbox=normalized_table.bbox,
            parser_confidence=normalized_table.parser_confidence,
            needs_review=False,
            ingest_version=ingest_version,
            embedding_model=embedding_model,
            embedding_dim=0,
            embedding_version=embedding_version,
            created_at=now_iso,
        )
    ]

    return row_chunks, summary_chunks
