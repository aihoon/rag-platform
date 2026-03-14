"""Weaviate vector ingestion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

import requests
from openai import OpenAI
from langsmith.wrappers import wrap_openai
from shared.schemas.chunk_type import ChunkType

from ..config.settings import Settings
from .weaviate_delete_service import delete_chunks
from .weaviate_schema_service import ensure_weaviate_class_properties

if TYPE_CHECKING:
    from .ingestion_service import TextChunk


@dataclass
class WeaviateIngestionStats:
    object_count: int


def _ensure_weaviate_class(
    settings: Settings, class_name: str, include_machine_fields: bool
) -> None:
    """Ensure the target Weaviate class exists before object upsert."""
    base_properties = [
        {"name": "content", "dataType": ["text"]},
        {"name": "source", "dataType": ["string"]},
        {"name": "page_number", "dataType": ["int"]},
        {"name": "file_upload_id", "dataType": ["string"]},
        {"name": "chunk_type", "dataType": ["string"]},
    ]
    machine_properties = [
        {"name": "machine_id", "dataType": ["string"]},
        {"name": "machine_cat", "dataType": ["int"]},
        {"name": "company_id", "dataType": ["int"]},
    ]
    properties = list(base_properties)
    if include_machine_fields:
        properties.extend(machine_properties)
    ensure_weaviate_class_properties(
        settings=settings, class_name=class_name, properties=properties
    )


def _embed_chunks(client: OpenAI, model: str, chunks: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    batch_size = 64
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vectors.extend([item.embedding for item in resp.data])
    return vectors


def ingest_to_weaviate(
    *,
    settings: Settings,
    logger: Any,
    class_name: str,
    include_machine_fields: bool,
    company_id: Optional[int],
    machine_cat: Optional[int],
    machine_id: Optional[int],
    file_upload_id: int,
    file_name: str,
    chunks: list["TextChunk"],
) -> WeaviateIngestionStats:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for embedding")
    _ensure_weaviate_class(settings, class_name, include_machine_fields)
    pre_delete_result = delete_chunks(
        settings=settings,
        file_upload_id=file_upload_id,
        file_name=file_name,
        class_name=class_name,
    )
    logger.info(
        f"weaviate pre_delete done|class_name={class_name}|"
        f"deleted_count={pre_delete_result.get('deleted_count', 0)}"
    )
    openai_client = wrap_openai(OpenAI(api_key=settings.openai_api_key))
    vectors = _embed_chunks(
        openai_client, settings.embedding_model, [chunk.text for chunk in chunks]
    )
    logger.info(
        f"embedding done|model={settings.embedding_model}|vector_count={len(vectors)}"
    )
    objects = []
    for chunk, vector in zip(chunks, vectors):
        objects.append(
            {
                "class": class_name,
                "vector": vector,
                "properties": {
                    "content": chunk.text,
                    "source": file_name,
                    "page_number": int(chunk.page_number),
                    "file_upload_id": str(file_upload_id),
                    "chunk_type": ChunkType.PARAGRAPH.value,
                    **(
                        {
                            "machine_id": str(machine_id),
                            "machine_cat": int(machine_cat or 0),
                            "company_id": int(company_id or 0),
                        }
                        if include_machine_fields
                        else {}
                    ),
                },
            }
        )
    batch_resp = requests.post(
        f"{settings.weaviate_url.rstrip('/')}/v1/batch/objects",
        json={"objects": objects},
        timeout=settings.weaviate_request_timeout,
    )
    batch_resp.raise_for_status()
    logger.info(
        f"weaviate upsert done|class_name={class_name}|object_count={len(objects)}"
    )
    return WeaviateIngestionStats(object_count=len(objects))
