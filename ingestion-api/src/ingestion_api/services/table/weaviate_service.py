"""Table chunk storage service for Weaviate."""

from __future__ import annotations

from typing import Any, Optional

import requests

from shared.schemas.ingestion import TableRowChunk, TableSummaryChunk
from shared.schemas.chunk_type import ChunkType
from shared.utils.id_utils import deterministic_uuid_from_parts

from ...config.settings import Settings
from ..weaviate_schema_service import ensure_weaviate_class_properties


def ensure_table_fields_on_class(
    *,
    settings: Settings,
    class_name: str,
    include_machine_fields: bool,
) -> None:
    table_props = [
        {"name": "content", "dataType": ["text"]},
        {"name": "source", "dataType": ["string"]},
        {"name": "page_number", "dataType": ["int"]},
        {"name": "file_upload_id", "dataType": ["string"]},
        {"name": "chunk_type", "dataType": ["string"]},
        {"name": "doc_id", "dataType": ["string"]},
        {"name": "table_id", "dataType": ["string"]},
        {"name": "row_id", "dataType": ["string"]},
        {"name": "row_index", "dataType": ["int"]},
        {"name": "table_title", "dataType": ["text"]},
        {"name": "section_title", "dataType": ["text"]},
        {"name": "header_path", "dataType": ["text[]"]},
        {"name": "column_names", "dataType": ["text[]"]},
        {"name": "column_schema", "dataType": ["text"]},
        {"name": "units", "dataType": ["text[]"]},
        {"name": "table_row_json", "dataType": ["text"]},
        {"name": "bbox", "dataType": ["text"]},
        {"name": "parser_confidence", "dataType": ["number"]},
        {"name": "needs_review", "dataType": ["boolean"]},
        {"name": "ingest_version", "dataType": ["int"]},
        {"name": "embedding_model", "dataType": ["string"]},
        {"name": "embedding_dim", "dataType": ["int"]},
        {"name": "embedding_version", "dataType": ["int"]},
        {"name": "created_at", "dataType": ["date"]},
    ]
    if include_machine_fields:
        table_props.extend(
            [
                {"name": "machine_id", "dataType": ["string"]},
                {"name": "machine_cat", "dataType": ["int"]},
                {"name": "company_id", "dataType": ["int"]},
            ]
        )
    ensure_weaviate_class_properties(
        settings=settings, class_name=class_name, properties=table_props
    )


def _row_to_object(row: TableRowChunk) -> dict[str, Any]:
    obj = row.model_dump()
    obj.pop("extra_meta", None)
    return obj


def _summary_to_object(summary: TableSummaryChunk) -> dict[str, Any]:
    obj = summary.model_dump()
    obj.pop("extra_meta", None)
    return obj


def upsert_table_chunks(
    *,
    settings: Settings,
    logger: Any,
    class_name: str,
    include_machine_fields: bool,
    company_id: Optional[int],
    machine_id: Optional[int],
    machine_cat: Optional[int],
    file_upload_id: int,
    row_chunks: list[TableRowChunk],
    summary_chunks: list[TableSummaryChunk],
) -> dict[str, int]:
    base_url = settings.weaviate_url.rstrip("/")
    ensure_table_fields_on_class(
        settings=settings,
        class_name=class_name,
        include_machine_fields=include_machine_fields,
    )

    objects: list[dict[str, Any]] = []
    for row in row_chunks:
        objects.append(
            {
                "id": deterministic_uuid_from_parts(
                    parts=[row.doc_id, str(row.page), row.table_id, row.row_id]
                ),
                "class": class_name,
                "properties": {
                    "content": row.row_text,
                    "source": row.file_name,
                    "page_number": int(row.page),
                    "file_upload_id": str(file_upload_id),
                    "chunk_type": ChunkType.TABLE_ROW.value,
                    **_row_to_object(row),
                    **(
                        {
                            "company_id": int(company_id or 0),
                            "machine_id": str(machine_id or ""),
                            "machine_cat": int(machine_cat or 0),
                        }
                        if include_machine_fields
                        else {}
                    ),
                },
            }
        )
    for summary in summary_chunks:
        objects.append(
            {
                "id": deterministic_uuid_from_parts(
                    parts=[
                        summary.doc_id,
                        str(summary.page),
                        summary.table_id,
                        "summary",
                    ]
                ),
                "class": class_name,
                "properties": {
                    "content": summary.summary_text,
                    "source": summary.file_name,
                    "page_number": int(summary.page),
                    "file_upload_id": str(file_upload_id),
                    "chunk_type": ChunkType.TABLE_SUMMARY.value,
                    "row_id": "summary",
                    **_summary_to_object(summary),
                    **(
                        {
                            "company_id": int(company_id or 0),
                            "machine_id": str(machine_id or ""),
                            "machine_cat": int(machine_cat or 0),
                        }
                        if include_machine_fields
                        else {}
                    ),
                },
            }
        )

    if objects:
        resp = requests.post(
            f"{base_url}/v1/batch/objects",
            json={"objects": objects},
            timeout=settings.weaviate_request_timeout,
        )
        resp.raise_for_status()

    logger.info(
        "table_weaviate upsert done|class_name=%s|row_chunks=%s|summary_chunks=%s|objects=%s",
        class_name,
        len(row_chunks),
        len(summary_chunks),
        len(objects),
    )
    return {
        "row_chunks": len(row_chunks),
        "summary_chunks": len(summary_chunks),
    }
