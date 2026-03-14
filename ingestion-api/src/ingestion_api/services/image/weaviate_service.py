"""Image chunk storage service for Weaviate."""

from __future__ import annotations

from typing import Any, Optional

import requests

from shared.schemas.ingestion import ImageChunk
from shared.schemas.chunk_type import ChunkType
from shared.utils.id_utils import deterministic_uuid_from_parts

from ...config.settings import Settings
from ..weaviate_schema_service import ensure_weaviate_class_properties


def ensure_image_fields_on_class(
    *, settings: Settings, class_name: str, include_machine_fields: bool
) -> None:
    image_props = [
        {"name": "content", "dataType": ["text"]},
        {"name": "source", "dataType": ["string"]},
        {"name": "page_number", "dataType": ["int"]},
        {"name": "file_upload_id", "dataType": ["string"]},
        {"name": "chunk_type", "dataType": ["string"]},
        {"name": "doc_id", "dataType": ["string"]},
        {"name": "image_id", "dataType": ["string"]},
        {"name": "figure_number", "dataType": ["string"]},
        {"name": "image_bbox", "dataType": ["text"]},
        {"name": "image_path", "dataType": ["string"]},
        {"name": "image_class", "dataType": ["string"]},
        {"name": "ocr_text", "dataType": ["text"]},
        {"name": "surrounding_context", "dataType": ["text"]},
        {"name": "needs_review", "dataType": ["boolean"]},
        {"name": "ingest_version", "dataType": ["int"]},
        {"name": "embedding_model", "dataType": ["string"]},
        {"name": "embedding_dim", "dataType": ["int"]},
        {"name": "embedding_version", "dataType": ["int"]},
        {"name": "created_at", "dataType": ["date"]},
    ]
    if include_machine_fields:
        image_props.extend(
            [
                {"name": "machine_id", "dataType": ["string"]},
                {"name": "machine_cat", "dataType": ["int"]},
                {"name": "company_id", "dataType": ["int"]},
            ]
        )
    ensure_weaviate_class_properties(
        settings=settings, class_name=class_name, properties=image_props
    )


def upsert_image_chunks(
    *,
    settings: Settings,
    logger: Any,
    class_name: str,
    include_machine_fields: bool,
    company_id: Optional[int],
    machine_id: Optional[int],
    machine_cat: Optional[int],
    file_upload_id: int,
    image_chunks: list[ImageChunk],
) -> dict[str, int]:
    base_url = settings.weaviate_url.rstrip("/")
    ensure_image_fields_on_class(
        settings=settings,
        class_name=class_name,
        include_machine_fields=include_machine_fields,
    )

    objects: list[dict[str, Any]] = []
    chunk_type_counts: dict[str, int] = {
        ChunkType.IMAGE_SUMMARY.value: 0,
        ChunkType.IMAGE_OCR.value: 0,
        ChunkType.IMAGE_CONTEXT.value: 0,
    }
    for chunk in image_chunks:
        chunk_type_counts[chunk.chunk_type] = (
            int(chunk_type_counts.get(chunk.chunk_type, 0)) + 1
        )
        objects.append(
            {
                "id": deterministic_uuid_from_parts(
                    parts=[
                        chunk.doc_id,
                        str(chunk.page),
                        chunk.image_id,
                        chunk.chunk_type,
                    ]
                ),
                "class": class_name,
                "properties": {
                    "content": chunk.content,
                    "source": chunk.file_name,
                    "page_number": int(chunk.page),
                    "file_upload_id": str(file_upload_id),
                    "chunk_type": chunk.chunk_type,
                    "doc_id": chunk.doc_id,
                    "image_id": chunk.image_id,
                    "figure_number": chunk.figure_number,
                    "image_bbox": chunk.bbox,
                    "image_path": chunk.image_path,
                    "image_class": chunk.image_class,
                    "ocr_text": chunk.ocr_text,
                    "surrounding_context": chunk.surrounding_context,
                    "needs_review": bool(chunk.needs_review),
                    "ingest_version": int(chunk.ingest_version),
                    "embedding_model": chunk.embedding_model,
                    "embedding_dim": int(chunk.embedding_dim),
                    "embedding_version": int(chunk.embedding_version),
                    "created_at": chunk.created_at,
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
    logger.info(
        "image weaviate objects prepared|class_name=%s|chunks=%s|objects=%s",
        class_name,
        len(image_chunks),
        len(objects),
    )

    if objects:
        resp = requests.post(
            f"{base_url}/v1/batch/objects",
            json={"objects": objects},
            timeout=settings.weaviate_request_timeout,
        )
        resp.raise_for_status()

    logger.info(
        "image_weaviate upsert done|class_name=%s|objects=%s|summary=%s|ocr=%s|context=%s",
        class_name,
        len(objects),
        chunk_type_counts.get(ChunkType.IMAGE_SUMMARY.value, 0),
        chunk_type_counts.get(ChunkType.IMAGE_OCR.value, 0),
        chunk_type_counts.get(ChunkType.IMAGE_CONTEXT.value, 0),
    )
    return {
        "image_summary": int(chunk_type_counts.get(ChunkType.IMAGE_SUMMARY.value, 0)),
        "image_ocr": int(chunk_type_counts.get(ChunkType.IMAGE_OCR.value, 0)),
        "image_context": int(chunk_type_counts.get(ChunkType.IMAGE_CONTEXT.value, 0)),
        "total": len(objects),
    }
