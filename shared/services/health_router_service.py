"""Shared helpers for health routers in ingestion-api and rag-api."""

from __future__ import annotations

from pathlib import Path

from starlette.responses import JSONResponse

from .neo4j_summary_service import get_neo4j_summary
from .weaviate_summary_service import get_weaviate_summary
from ..utils.health import check_sqlite_live, check_weaviate_live, check_neo4j_live


def health_ok_response(*, service_name: str, logger) -> JSONResponse:
    logger.info("health_check ok")
    return JSONResponse(
        content={"status": "ok", "service": service_name}, status_code=200
    )


def sqlite_live_response(*, db_path: Path, logger) -> JSONResponse:
    return check_sqlite_live(
        db_path=Path(db_path),
        logger=logger,
    )


def weaviate_live_response(*, base_url: str, timeout_sec: int, logger) -> JSONResponse:
    return check_weaviate_live(
        base_url=base_url,
        timeout_sec=timeout_sec,
        logger=logger,
    )


def neo4j_live_response(
    *,
    enabled: bool,
    uri: str,
    user: str,
    password: str,
    database: str,
    logger,
) -> JSONResponse:
    return check_neo4j_live(
        enabled=enabled,
        uri=uri,
        user=user,
        password=password,
        database=database,
        logger=logger,
    )


def weaviate_summary_response(
    *,
    weaviate_url: str,
    timeout_sec: int,
    default_class: str,
    logger,
    class_name: str | None = None,
) -> JSONResponse:
    try:
        stats = get_weaviate_summary(
            weaviate_url=weaviate_url,
            timeout_sec=timeout_sec,
            default_class=default_class,
            logger=logger,
            class_name=class_name,
        )
        return JSONResponse(
            content={
                "status": "ok",
                "check": "weaviate",
                "classes": stats.classes,
                "target_class": stats.class_name,
                "target_count": stats.total_count,
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


def neo4j_summary_response(
    *,
    enabled: bool,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str,
    default_label: str,
    logger,
    label: str | None = None,
) -> JSONResponse:
    if not enabled:
        return JSONResponse(
            content={
                "status": "skip",
                "check": "neo4j",
                "detail": "NEO4J_ENABLED=false",
            },
            status_code=200,
        )
    try:
        stats = get_neo4j_summary(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
            default_label=default_label,
            logger=logger,
            label=label,
        )
        return JSONResponse(
            content={
                "status": "ok",
                "check": "neo4j",
                "label": stats.label,
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
