"""
File: ingestion.py
Layer: API Router (FastAPI)
Purpose:
    Expose ingestion-related HTTP endpoints and translate request/response
    payloads between external API contracts and internal service calls.

Responsibilities:
    1) Validate incoming payloads using shared Pydantic schemas.
    2) Resolve application dependencies from app.state (settings, logger).
    3) Invoke domain/application services:
       - run_ingestion_pipeline: ingest PDF-derived content into Weaviate.
       - delete_chunks: remove Weaviate chunks by request filters.
    4) Return normalized response models to clients.
    5) Convert internal exceptions into HTTP status codes:
       - 404: not found resources (e.g., missing file)
       - 422: request/data validation issues
       - 500: unexpected internal errors

Endpoints:
    POST /run
        Trigger ingestion execution for a specific upload item.
    DELETE /chunks
        Delete Weaviate chunks for a specific upload scope.

Notes:
    - This module should not contain business logic.
    - All heavy operations are delegated to service layer modules.
    - Logging is performed at request boundary for start/success/failure events.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from openai import AuthenticationError, RateLimitError

from shared.observability import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings
from shared.schemas.ingestion import (
    IngestionRunRequest,
    IngestionRunResponse,
    WeaviateDeleteRequest,
    WeaviateDeleteResponse,
    GraphDeleteRequest,
    GraphDeleteResponse,
 )
from ...config.settings import load_settings
from ...services.ingestion_service import run_ingestion_pipeline
from ...services.weaviate_delete_service import delete_chunks
from ...services.neo4j_delete_service import delete_from_neo4j
from ...services.upload_status_service import get_uploaded_file_status, update_uploaded_file_status

router = APIRouter(tags=["ingestion"])


@router.post("/run", response_model=IngestionRunResponse, status_code=200)
async def execute_ingestion(
    http_request: Request,
    request: IngestionRunRequest,
    background_tasks: BackgroundTasks,
) -> IngestionRunResponse:
    settings = resolve_settings(http_request, load_settings)
    logger = resolve_logger(http_request, PrintLogger())
    logger.info(
        f"execute_ingestion start|company_id={request.company_id}|machine_cat={request.machine_cat}|"
        f"machine_id={request.machine_id}|file_upload_id={request.file_upload_id}|file_name={request.file_name}|"
        f"class_name={request.class_name}|weaviate_enabled={request.weaviate_enabled}|neo4j_enabled={request.neo4j_enabled}"
    )
    effective_weaviate = True if request.weaviate_enabled is None else bool(request.weaviate_enabled)
    effective_neo4j = settings.neo4j_enabled if request.neo4j_enabled is None else (settings.neo4j_enabled and request.neo4j_enabled)
    if not effective_weaviate and not effective_neo4j:
        raise HTTPException(status_code=422, detail="Both weaviate_enabled and neo4j_enabled are false")
    pipeline_id = f"{request.company_id}_{request.machine_id}_{request.file_upload_id}"
    if effective_weaviate:
        current_weaviate_status = get_uploaded_file_status(
            settings=settings,
            file_upload_id=request.file_upload_id,
            target="weaviate",
        )
        if current_weaviate_status in {"REQUESTED", "RUNNING"}:
            raise HTTPException(status_code=409, detail="Weaviate ingestion is already in progress for this file.")
    if effective_neo4j:
        current_neo4j_status = get_uploaded_file_status(
            settings=settings,
            file_upload_id=request.file_upload_id,
            target="neo4j",
        )
        if current_neo4j_status in {"REQUESTED", "RUNNING"}:
            raise HTTPException(status_code=409, detail="Neo4j ingestion is already in progress for this file.")
    if effective_weaviate:
        update_uploaded_file_status(
            settings=settings,
            file_upload_id=request.file_upload_id,
            target="weaviate",
            status="REQUESTED",
            pipeline_id=pipeline_id,
            error_text=None,
            response_obj=None,
        )
    if effective_neo4j:
        update_uploaded_file_status(
            settings=settings,
            file_upload_id=request.file_upload_id,
            target="neo4j",
            status="REQUESTED",
            pipeline_id=pipeline_id,
            error_text=None,
            response_obj=None,
        )
    background_tasks.add_task(
        _run_ingestion_job,
        settings,
        logger,
        request,
        pipeline_id,
        effective_weaviate,
        effective_neo4j,
    )
    try:
        return IngestionRunResponse(
            status="accepted",
            pipeline_id=pipeline_id,
            class_name=request.class_name or settings.weaviate_default_class,
            chunk_count=0,
            neo4j=None,
        )
    except FileNotFoundError as exc:
        logger.info(f"execute_ingestion fail_not_found|detail={exc}")
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        logger.info(f"execute_ingestion fail_validation|detail={exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except AuthenticationError as exc:
        logger.info(f"execute_ingestion fail_auth|detail={exc}")
        raise HTTPException(
            status_code=401,
            detail="OPENAI_API_KEY is invalid or unauthorized. Check .env key and reload server.",
        )
    except RateLimitError as exc:
        logger.info(f"execute_ingestion fail_rate_limit|detail={exc}")
        raise HTTPException(
            status_code=429,
            detail="OpenAI quota/rate limit exceeded. Check billing/quota and retry later.",
        )
    except Exception as exc:
        logger.exception(f"execute_ingestion fail_internal|detail={exc}")
        raise HTTPException(status_code=500, detail=f"ingestion failed: {exc}")


def _run_ingestion_job(
    settings,
    logger,
    request: IngestionRunRequest,
    pipeline_id: str,
    effective_weaviate: bool,
    effective_neo4j: bool,
) -> None:
    try:
        if effective_weaviate:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="weaviate",
                status="RUNNING",
                pipeline_id=pipeline_id,
                error_text=None,
                response_obj=None,
            )
        if effective_neo4j:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="neo4j",
                status="RUNNING",
                pipeline_id=pipeline_id,
                error_text=None,
                response_obj=None,
            )
        result = run_ingestion_pipeline(
            settings=settings,
            logger=logger,
            company_id=request.company_id,
            machine_cat=request.machine_cat,
            machine_id=request.machine_id,
            class_name=request.class_name,
            weaviate_enabled=request.weaviate_enabled,
            neo4j_enabled=request.neo4j_enabled,
            file_upload_id=request.file_upload_id,
            file_name=request.file_name,
        )
        if effective_weaviate:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="weaviate",
                status="INGESTED",
                pipeline_id=pipeline_id,
                error_text=None,
                response_obj=result,
            )
        if effective_neo4j:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="neo4j",
                status="INGESTED",
                pipeline_id=pipeline_id,
                error_text=None,
                response_obj=result,
            )
        logger.info(
            f"execute_ingestion background_done|pipeline_id={pipeline_id}|chunk_count={result.get('chunk_count')}"
        )
    except Exception as exc:
        if effective_weaviate:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="weaviate",
                status="FAILED",
                pipeline_id=pipeline_id,
                error_text=str(exc),
                response_obj=None,
            )
        if effective_neo4j:
            update_uploaded_file_status(
                settings=settings,
                file_upload_id=request.file_upload_id,
                target="neo4j",
                status="FAILED",
                pipeline_id=pipeline_id,
                error_text=str(exc),
                response_obj=None,
            )
        logger.exception(f"execute_ingestion background_fail|pipeline_id={pipeline_id}|detail={exc}")


@router.delete("/chunks", response_model=WeaviateDeleteResponse, status_code=200)
async def delete_weaviate_chunks(http_request: Request, request: WeaviateDeleteRequest) -> WeaviateDeleteResponse:
    settings = resolve_settings(http_request, load_settings)
    logger = resolve_logger(http_request, PrintLogger())
    logger.info(
        f"delete_weaviate_chunks start|file_upload_id={request.file_upload_id}|file_name={request.file_name}|"
        f"class_name={request.class_name}"
    )
    try:
        result = delete_chunks(
            settings=settings,
            file_upload_id=request.file_upload_id,
            file_name=request.file_name,
            class_name=request.class_name,
        )
        logger.info(
            f"delete_weaviate_chunks success|deleted_count={result.get('deleted_count')}|"
            f"class_name={result.get('class_name')}"
        )
        return WeaviateDeleteResponse(**result)
    except ValueError as exc:
        logger.info(f"delete_weaviate_chunks fail_validation|detail={exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception(f"delete_weaviate_chunks fail_internal|detail={exc}")
        raise HTTPException(status_code=500, detail=f"weaviate delete failed: {exc}")


@router.delete("/graph", response_model=GraphDeleteResponse, status_code=200)
async def delete_graph_chunks(http_request: Request, request: GraphDeleteRequest) -> GraphDeleteResponse:
    settings = resolve_settings(http_request, load_settings)
    logger = resolve_logger(http_request, PrintLogger())
    if not settings.neo4j_enabled:
        return GraphDeleteResponse(
            status="skip",
            deleted_docs=0,
            deleted_chunks=0,
            deleted_entities=0,
            deleted_relations=0,
        )
    logger.info(
        f"delete_graph_chunks start|file_upload_id={request.file_upload_id}|file_name={request.file_name}"
    )
    try:
        stats = delete_from_neo4j(
            settings=settings,
            logger=logger,
            file_upload_id=request.file_upload_id,
        )
        return GraphDeleteResponse(
            status="ok",
            deleted_docs=stats.doc_count,
            deleted_chunks=stats.chunk_count,
            deleted_entities=stats.entity_count,
            deleted_relations=stats.relation_count,
        )
    except Exception as exc:
        logger.exception(f"delete_graph_chunks fail_internal|detail={exc}")
        raise HTTPException(status_code=500, detail=f"graph delete failed: {exc}")
