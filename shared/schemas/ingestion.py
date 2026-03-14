"""Shared ingestion request/response contracts."""

from __future__ import annotations

from typing import Any, Optional, Dict

from pydantic import BaseModel, Field


class IngestionRunRequest(BaseModel):
    file_name: str
    file_upload_id: int
    class_name: Optional[str] = None
    company_id: Optional[int] = 0
    machine_cat: Optional[int] = 0
    machine_id: Optional[int] = 0
    weaviate_enabled: Optional[bool] = None
    neo4j_enabled: Optional[bool] = None
    user_id: Optional[str] = ""


class TableIngestionStats(BaseModel):
    detected_tables: int = 0
    row_chunks: int = 0
    summary_chunks: int = 0
    needs_review_count: int = 0


class IngestionRunResponse(BaseModel):
    status: str
    pipeline_id: str
    class_name: str
    chunk_count: int
    neo4j: Optional[Dict[str, int]] = None
    table: Optional[TableIngestionStats] = None


class WeaviateDeleteRequest(BaseModel):
    file_name: str
    file_upload_id: int
    class_name: Optional[str] = None


class WeaviateDeleteResponse(BaseModel):
    status: str
    class_name: str
    deleted_count: int
    deleted_ids: list[str]


class GraphDeleteRequest(BaseModel):
    file_name: str
    file_upload_id: int
    company_id: Optional[int] = 0
    machine_cat: Optional[int] = 0
    machine_id: Optional[int] = 0


class GraphDeleteResponse(BaseModel):
    status: str
    deleted_docs: int
    deleted_chunks: int
    deleted_entities: int
    deleted_relations: int


class TableRowChunk(BaseModel):
    doc_id: str
    file_name: str
    page: int
    table_id: str
    row_id: str
    row_index: int
    table_title: str = ""
    section_title: str = ""
    header_path: list[str] = Field(default_factory=list)
    column_names: list[str] = Field(default_factory=list)
    column_schema: str = "{}"
    units: list[str] = Field(default_factory=list)
    row_text: str
    table_row_json: str
    bbox: str = "{}"
    parser_confidence: float = 0.0
    needs_review: bool = False
    ingest_version: int = 1
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_version: int = 1
    created_at: str = ""
    extra_meta: dict[str, Any] = Field(default_factory=dict)


class TableSummaryChunk(BaseModel):
    doc_id: str
    file_name: str
    page: int
    table_id: str
    table_title: str = ""
    section_title: str = ""
    column_names: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    summary_text: str
    row_count: int = 0
    bbox: str = "{}"
    parser_confidence: float = 0.0
    needs_review: bool = False
    ingest_version: int = 1
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_version: int = 1
    created_at: str = ""
    extra_meta: dict[str, Any] = Field(default_factory=dict)


class TableExtractResult(BaseModel):
    doc_id: str
    file_name: str
    class_name: str
    detected_tables: int = 0
    row_chunks: list[TableRowChunk] = Field(default_factory=list)
    summary_chunks: list[TableSummaryChunk] = Field(default_factory=list)
    needs_review_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class ImageChunk(BaseModel):
    doc_id: str
    file_name: str
    page: int
    image_id: str
    figure_number: str
    chunk_type: str
    content: str
    bbox: str = "{}"
    image_path: str = ""
    image_class: str = "semantic"
    ocr_text: str = ""
    surrounding_context: str = ""
    needs_review: bool = False
    ingest_version: int = 1
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_version: int = 1
    created_at: str = ""
