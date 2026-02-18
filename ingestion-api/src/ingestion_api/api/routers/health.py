"""Health router.""" ###

from __future__ import annotations ###

import sqlite3 ###
from pathlib import Path ###
from typing import Any ###

import requests ###
from fastapi import APIRouter, Request ###
from starlette.responses import JSONResponse ###
from shared.observability.logger import PrintLogger ###

from ...config.settings import load_settings ###

router = APIRouter(tags=["health"]) ###


def _resolve_settings(request: Request) -> Any: ###
    return getattr(request.app.state, "settings", load_settings()) ###


def _resolve_logger(request: Request) -> Any: ###
    ###return getattr(request.app.state, "logger", None)
    return getattr(request.app.state, "logger", PrintLogger()) ###


@router.get("/health") ###
async def health_check(request: Request) -> JSONResponse: ###
    logger = _resolve_logger(request) ###
    ###if logger:
    ###    logger.info("health_check ok")
    logger.info("health_check ok") ###
    return JSONResponse(content={"status": "ok", "service": "ingestion-api"}, status_code=200) ###


@router.get("/health/sqlite-live") ###
async def sqlite_live_check(request: Request) -> JSONResponse: ###
    settings = _resolve_settings(request) ###
    logger = _resolve_logger(request) ###
    db_path = settings.resolved_ingestion_ui_db_path() ###
    if not Path(db_path).exists(): ###
        logger.info(f"sqlite_live_check fail: db file not found ({db_path})") ###
        return JSONResponse( ###
            content={"status": "fail", "check": "sqlite", "detail": f"db file not found: {db_path}"}, ###
            status_code=503, ###
        ) ###
    try: ###
        with sqlite3.connect(db_path) as conn: ###
            conn.execute("SELECT 1").fetchone() ###
        logger.info(f"sqlite_live_check ok: {db_path}") ###
        return JSONResponse( ###
            content={"status": "ok", "check": "sqlite", "db_path": str(db_path)}, ###
            status_code=200, ###
        ) ###
    except Exception as exc: ###
        logger.info(f"sqlite_live_check fail: {exc}") ###
        return JSONResponse( ###
            content={"status": "fail", "check": "sqlite", "detail": str(exc)}, ###
            status_code=503, ###
        ) ###


@router.get("/health/weaviate-live") ###
async def weaviate_live_check(request: Request) -> JSONResponse: ###
    settings = _resolve_settings(request) ###
    logger = _resolve_logger(request) ###
    base = settings.weaviate_url.rstrip("/") ###
    try: ###
        ready_resp = requests.get(f"{base}/v1/.well-known/ready", timeout=settings.request_timeout) ###
        if ready_resp.ok: ###
            logger.info(f"weaviate_live_check ok: {base}") ###
            return JSONResponse( ###
                content={"status": "ok", "check": "weaviate", "url": base}, ###
                status_code=200, ###
            ) ###
        meta_resp = requests.get(f"{base}/v1/meta", timeout=settings.request_timeout) ###
        meta_resp.raise_for_status() ###
        logger.info(f"weaviate_live_check ok (meta): {base}") ###
        return JSONResponse( ###
            content={"status": "ok", "check": "weaviate", "url": base}, ###
            status_code=200, ###
        ) ###
    except Exception as exc: ###
        logger.info(f"weaviate_live_check fail: {exc}") ###
        return JSONResponse( ###
            content={"status": "fail", "check": "weaviate", "detail": str(exc), "url": base}, ###
            status_code=503, ###
        ) ###
