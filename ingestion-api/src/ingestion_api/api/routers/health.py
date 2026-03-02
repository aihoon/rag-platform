"""Health router."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse
from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings
from shared.utils.health import (
    check_sqlite_live,
    check_weaviate_live,
    check_neo4j_live,
)
from ...services.neo4j_summary_service import get_neo4j_summary
from ...services.weaviate_summary_service import get_weaviate_summary

from ...config.settings import load_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    logger = resolve_logger(request, PrintLogger())
    logger.info("health_check ok")
    return JSONResponse(content={"status": "ok", "service": "ingestion-api"}, status_code=200)


@router.get("/health/sqlite-live")
async def sqlite_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    db_path = settings.resolved_ingestion_ui_db_path()
    return check_sqlite_live(
        db_path=Path(db_path),
        logger=logger,
    )


@router.get("/health/weaviate-live")
async def weaviate_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    return check_weaviate_live(
        base_url=settings.weaviate_url,
        timeout_sec=settings.request_timeout,
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


@router.get("/health/neo4j-summary")
async def neo4j_summary(
    request: Request,
    label: str | None = Query(default=None),
) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    if not settings.neo4j_enabled:
        return JSONResponse(
            content={"status": "skip", "check": "neo4j", "detail": "NEO4J_ENABLED=false"},
            status_code=200,
        )
    try:
        stats = get_neo4j_summary(settings=settings, logger=logger, label=label)
        return JSONResponse(
            content={
                "status": "ok",
                "check": "neo4j",
                "label": label or settings.neo4j_default_label,
                "docs": stats.doc_count,
                "chunks": stats.chunk_count,
                "entities": stats.entity_count,
                "relations": stats.relation_count,
            },
            status_code=200,
        )
    except Exception as exc:
        logger.info(f"neo4j_summary fail: {exc}")
        return JSONResponse(
            content={"status": "fail", "check": "neo4j", "detail": str(exc)},
            status_code=503,
        )


@router.get("/health/weaviate-summary")
async def weaviate_summary(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    class_name = settings.weaviate_default_class
    try:
        stats = get_weaviate_summary(
            settings=settings,
            logger=logger,
            class_name=class_name,
        )
        return JSONResponse(
            content={
                "status": "ok",
                "check": "weaviate",
                "class_name": stats.class_name,
                "total": stats.total_count,
                "sampled_rows": stats.sampled_rows,
                "top_sources": stats.top_sources,
            },
            status_code=200,
        )
    except Exception as exc:
        logger.info(f"weaviate_summary fail: {exc}")
        return JSONResponse(
            content={"status": "fail", "check": "weaviate", "detail": str(exc)},
            status_code=503,
        )
