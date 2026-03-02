"""Shared health check helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import requests
from neo4j import GraphDatabase
from starlette.responses import JSONResponse


def _health_response(
    *,
    status: str,
    check: str,
    detail: str | None = None,
    extra: dict | None = None,
) -> JSONResponse:
    payload = {"status": status, "check": check}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    status_code = 200 if status in ("ok", "skip") else 503
    return JSONResponse(content=payload, status_code=status_code)


def check_sqlite_live(
    *,
    db_path: Path,
    logger,
) -> JSONResponse:
    if not Path(db_path).exists():
        logger.info(f"sqlite_live_check fail: db file not found ({db_path})")
        return _health_response(
            status="fail",
            check="sqlite",
            detail=f"db file not found: {db_path}",
        )
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        logger.info(f"sqlite_live_check ok: {db_path}")
        return _health_response(
            status="ok",
            check="sqlite",
            extra={"db_path": str(db_path)},
        )
    except Exception as exc:
        logger.info(f"sqlite_live_check fail: {exc}")
        return _health_response(
            status="fail",
            check="sqlite",
            detail=str(exc),
        )


def check_weaviate_live(
    *,
    base_url: str,
    timeout_sec: int,
    logger,
) -> JSONResponse:
    base = base_url.rstrip("/")
    try:
        ready_resp = requests.get(f"{base}/v1/.well-known/ready", timeout=timeout_sec)
        if ready_resp.ok:
            logger.info(f"weaviate_live_check ok: {base}")
            return _health_response(
                status="ok",
                check="weaviate",
                extra={"url": base},
            )
        meta_resp = requests.get(f"{base}/v1/meta", timeout=timeout_sec)
        meta_resp.raise_for_status()
        logger.info(f"weaviate_live_check ok (meta): {base}")
        return _health_response(
            status="ok",
            check="weaviate",
            extra={"url": base},
        )
    except Exception as exc:
        logger.info(f"weaviate_live_check fail: {exc}")
        return _health_response(
            status="fail",
            check="weaviate",
            detail=str(exc),
            extra={"url": base},
        )


def check_neo4j_live(
    *,
    enabled: bool,
    uri: str,
    user: str,
    password: str,
    database: str,
    logger,
) -> JSONResponse:
    if not enabled:
        return _health_response(
            status="skip",
            check="neo4j",
            detail="NEO4J_ENABLED=false",
        )
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database) as session:
            session.run("RETURN 1").single()
        driver.close()
        logger.info(f"neo4j_live_check ok: {uri}")
        return _health_response(
            status="ok",
            check="neo4j",
            extra={"uri": uri},
        )
    except Exception as exc:
        logger.info(f"neo4j_live_check fail: {exc}")
        return _health_response(
            status="fail",
            check="neo4j",
            detail=str(exc),
            extra={"uri": uri},
        )
