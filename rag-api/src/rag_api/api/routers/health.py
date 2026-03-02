"""Health router."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings
from shared.utils.health import (
    check_weaviate_live,
    check_neo4j_live,
)

from ...config.settings import load_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    logger = resolve_logger(request, PrintLogger())
    logger.info("health_check ok")
    return JSONResponse(content={"status": "ok", "service": "rag-api"}, status_code=200)


@router.get("/health/weaviate-live")
async def weaviate_live_check(request: Request) -> JSONResponse:
    logger = resolve_logger(request, PrintLogger())
    settings = resolve_settings(request, load_settings)
    return check_weaviate_live(
        base_url=settings.weaviate_url,
        timeout_sec=settings.weaviate_request_timeout,
        logger=logger,
    )


@router.get("/health/neo4j-live")
async def neo4j_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return check_neo4j_live(
        enabled=settings.neo4j_enabled,
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
        logger=logger,
    )
