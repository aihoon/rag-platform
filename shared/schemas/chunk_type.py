"""Shared chunk type definitions for ingestion/retrieval pipelines."""

from __future__ import annotations

from enum import Enum


class ChunkType(str, Enum):
    PARAGRAPH = "paragraph"
    TABLE_ROW = "table_row"
    TABLE_SUMMARY = "table_summary"
    IMAGE_SUMMARY = "image_summary"
    IMAGE_OCR = "image_ocr"
    IMAGE_CONTEXT = "image_context"

    @classmethod
    def table_prefix(cls) -> str:
        return "table"

    @classmethod
    def image_prefix(cls) -> str:
        return "image"


def is_table_chunk_type(chunk_type: str | None) -> bool:
    return (chunk_type or "").strip().startswith(ChunkType.table_prefix())


def is_image_chunk_type(chunk_type: str | None) -> bool:
    return (chunk_type or "").strip().startswith(ChunkType.image_prefix())
