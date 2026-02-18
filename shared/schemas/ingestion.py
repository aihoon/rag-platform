"""Shared ingestion request/response contracts."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IngestionRunRequest(BaseModel):
    file_name: str
    file_upload_id: int
    company_id: int
    machine_cat: str
    machine_id: int
    user_id: Optional[str] = ""


class IngestionRunResponse(BaseModel):
    status: str
    pipeline_id: str
    class_name: str
    chunk_count: int


class VectorDeleteRequest(BaseModel):
    file_name: str
    file_upload_id: int
    company_id: int
    machine_cat: str
    machine_id: int
    class_name: Optional[str] = None


class VectorDeleteResponse(BaseModel):
    status: str
    class_name: str
    deleted_count: int
    deleted_ids: list[str]
