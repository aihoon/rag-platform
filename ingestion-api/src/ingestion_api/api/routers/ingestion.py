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
       - run_ingestion_pipeline: ingest PDF-derived content into vector DB.
       - delete_chunks: remove vector chunks by request filters.
    4) Return normalized response models to clients.
    5) Convert internal exceptions into HTTP status codes:
       - 404: not found resources (e.g., missing file)
       - 422: request/data validation issues
       - 500: unexpected internal errors

Endpoints:
    POST /run
        Trigger ingestion execution for a specific upload item.
    DELETE /chunks
        Delete vector chunks for a specific upload scope.

Notes:
    - This module should not contain business logic.
    - All heavy operations are delegated to service layer modules.
    - Logging is performed at request boundary for start/success/failure events.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from openai import AuthenticationError, RateLimitError

from shared.observability import PrintLogger
from shared.schemas.ingestion import (
    IngestionRunRequest,
    IngestionRunResponse,
    VectorDeleteRequest,
    VectorDeleteResponse
 )
from ...config.settings import load_settings
from ...services.ingestion_service import run_ingestion_pipeline
from ...services.vector_delete_service import delete_chunks

router = APIRouter(tags=["ingestion"])


def _resolve_settings(request: Request) -> Any:
    return getattr(request.app.state, "settings", load_settings())


def _resolve_logger(request: Request) -> Any:
    return getattr(request.app.state, "logger", PrintLogger())


@router.post("/run", response_model=IngestionRunResponse, status_code=200)
async def execute_ingestion(http_request: Request, request: IngestionRunRequest) -> IngestionRunResponse:
    settings = _resolve_settings(http_request)
    logger = _resolve_logger(http_request)
    logger.info(
        f"execute_ingestion start|company_id={request.company_id}|machine_cat={request.machine_cat}|"
        f"machine_id={request.machine_id}|file_upload_id={request.file_upload_id}|file_name={request.file_name}"
    )
    try:
        result = run_ingestion_pipeline(
            settings=settings,
            logger=logger,
            company_id=request.company_id,
            machine_cat=request.machine_cat,
            machine_id=request.machine_id,
            file_upload_id=request.file_upload_id,
            file_name=request.file_name,
        )
        logger.info(
            f"execute_ingestion success|pipeline_id={result.get('pipeline_id')}|"
            f"chunk_count={result.get('chunk_count')}"
        )
        return IngestionRunResponse(**result)
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


@router.delete("/chunks", response_model=VectorDeleteResponse, status_code=200)
async def delete_vector_chunks(http_request: Request, request: VectorDeleteRequest) -> VectorDeleteResponse:
    settings = _resolve_settings(http_request)
    logger = _resolve_logger(http_request)
    logger.info(
        f"delete_vector_chunks start|company_id={request.company_id}|machine_cat={request.machine_cat}|"
        f"machine_id={request.machine_id}|file_upload_id={request.file_upload_id}|file_name={request.file_name}"
    )
    try:
        result = delete_chunks(
            settings=settings,
            company_id=request.company_id,
            machine_cat=request.machine_cat,
            machine_id=request.machine_id,
            file_upload_id=request.file_upload_id,
            file_name=request.file_name,
            class_name=request.class_name,
        )
        logger.info(
            f"delete_vector_chunks success|deleted_count={result.get('deleted_count')}|"
            f"class_name={result.get('class_name')}"
        )
        return VectorDeleteResponse(**result)
    except ValueError as exc:
        logger.info(f"delete_vector_chunks fail_validation|detail={exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception(f"delete_vector_chunks fail_internal|detail={exc}")
        raise HTTPException(status_code=500, detail=f"vector delete failed: {exc}")
