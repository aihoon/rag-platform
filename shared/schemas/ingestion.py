"""Shared ingestion request/response contracts."""

from __future__ import annotations

from typing import Optional, Dict

from pydantic import BaseModel


class IngestionRunRequest(BaseModel): ### ###
    file_name: str ### ###
    file_upload_id: int ### ###
    class_name: Optional[str] = None ### ###
    company_id: Optional[int] = 0 ### ###
    machine_cat: Optional[int] = 0 ### ###
    machine_id: Optional[int] = 0 ### ###
    weaviate_enabled: Optional[bool] = None ### ###
    neo4j_enabled: Optional[bool] = None ### ###
    user_id: Optional[str] = "" ### ###


class IngestionRunResponse(BaseModel):
    status: str
    pipeline_id: str
    class_name: str
    chunk_count: int
    neo4j: Optional[Dict[str, int]] = None


class WeaviateDeleteRequest(BaseModel): ### ###
    file_name: str ### ###
    file_upload_id: int ### ###
    class_name: Optional[str] = None ### ###


class WeaviateDeleteResponse(BaseModel): ### ###
    status: str
    class_name: str
    deleted_count: int
    deleted_ids: list[str]


class GraphDeleteRequest(BaseModel): ### ###
    file_name: str ### ###
    file_upload_id: int ### ###
    company_id: Optional[int] = 0 ### ###
    machine_cat: Optional[int] = 0 ### ###
    machine_id: Optional[int] = 0 ### ###


class GraphDeleteResponse(BaseModel): ### ###
    status: str ### ###
    deleted_docs: int ### ###
    deleted_chunks: int ### ###
    deleted_entities: int ### ###
    deleted_relations: int ### ###
