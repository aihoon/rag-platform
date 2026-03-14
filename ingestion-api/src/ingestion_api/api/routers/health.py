"""Health router."""

from __future__ import annotations

from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse
from shared.observability.logger import PrintLogger
from shared.services.health_router_service import (
    health_ok_response,
    sqlite_live_response,
    weaviate_live_response,
    neo4j_live_response,
    weaviate_summary_response,
    neo4j_summary_response,
)
from shared.utils.request import resolve_logger, resolve_settings

from ...config.settings import load_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    logger = resolve_logger(request, PrintLogger())
    return health_ok_response(service_name="ingestion-api", logger=logger)


@router.get("/health/sqlite-live")
async def sqlite_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return sqlite_live_response(
        db_path=settings.resolved_ingestion_ui_db_path(),
        logger=logger,
    )


@router.get("/health/weaviate-live")
async def weaviate_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return weaviate_live_response(
        base_url=settings.weaviate_url,
        timeout_sec=settings.weaviate_request_timeout,
        logger=logger,
    )


@router.get("/health/neo4j-live")
async def neo4j_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return neo4j_live_response(
        enabled=settings.neo4j_enabled,
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
        logger=logger,
    )


@router.get("/health/neo4j-summary")
async def neo4j_summary(
    request: Request,
    label: str | None = Query(default=None),
) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return neo4j_summary_response(
        enabled=settings.neo4j_enabled,
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        neo4j_database=settings.neo4j_database,
        default_label=settings.neo4j_default_label,
        logger=logger,
        label=label,
    )


@router.get("/health/weaviate-summary")
async def weaviate_summary(
    request: Request,
    class_name: str | None = Query(default=None),
) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return weaviate_summary_response(
        weaviate_url=settings.weaviate_url,
        timeout_sec=settings.weaviate_request_timeout,
        default_class=settings.weaviate_default_class,
        logger=logger,
        class_name=class_name,
    )
