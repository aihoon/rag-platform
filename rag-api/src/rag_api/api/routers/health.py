"""Health router."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings

from ...config.settings import load_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    logger = resolve_logger(request, PrintLogger())
    logger.info("health_check ok")
    return JSONResponse(content={"status": "ok", "service": "rag-api"}, status_code=200)


@router.get("/health/weaviate-live")
async def weaviate_live_check(request: Request) -> JSONResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    base = settings.weaviate_url.rstrip("/") ###
    try:
        ###ready_resp = requests.get(f"{base}/v1/.well-known/ready", timeout=settings.request_timeout)
        ready_resp = requests.get(f"{base}/v1/.well-known/ready", timeout=settings.weaviate_request_timeout) ###
        if ready_resp.ok:
            logger.info(f"weaviate_live_check ok: {base}")
            return JSONResponse(
                content={"status": "ok", "check": "weaviate", "url": base},
                status_code=200,
            )
        ###meta_resp = requests.get(f"{base}/v1/meta", timeout=settings.request_timeout)
        meta_resp = requests.get(f"{base}/v1/meta", timeout=settings.weaviate_request_timeout) ###
        meta_resp.raise_for_status()
        logger.info(f"weaviate_live_check ok (meta): {base}")
        return JSONResponse(
            content={"status": "ok", "check": "weaviate", "url": base},
            status_code=200,
        )
    except Exception as exc:
        logger.info(f"weaviate_live_check fail: {exc}")
        return JSONResponse(
            content={"status": "fail", "check": "weaviate", "detail": str(exc), "url": base},
            status_code=503,
        )
