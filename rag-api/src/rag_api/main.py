"""FastAPI app entrypoint for rag-api."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from shared.utils.url import parse_url
from shared.observability.logger import setup_logger, get_logger

from .api.routers.health import router as health_router
from .api.routers.chat import router as chat_router
from .config.settings import load_settings

RAG_API_DOTENV_PATH = "../../../.env"


def create_app() -> FastAPI:
    rag_api_dotenv_path = os.getenv("RAG_API_DOTENV_PATH", RAG_API_DOTENV_PATH)
    dotenv_path = (Path(__file__).resolve().parent / rag_api_dotenv_path).resolve()
    if dotenv_path.exists():
        load_dotenv(dotenv_path=str(dotenv_path))
    else:
        load_dotenv()

    settings = load_settings()
    os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_RAG_PROJECT", "rag-platform-rag-api")

    setup_logger(log_path=settings.rag_api_log_path, level=settings.rag_api_log_level)
    _logger = get_logger(settings.rag_api_log_name)
    _logger.info("# Starting rag-api server bootstrap")

    _, _, parsed_root_path = parse_url(settings.rag_api_url)
    root_path = settings.rag_api_root_path or parsed_root_path
    _app = FastAPI(title="rag-api", root_path=root_path)
    _app.state.settings = settings
    _app.state.logger = _logger
    _app.state.chat_store = {} # 서버 메모리에서 대화 히스토리를 임시로 저장하기 위한 캐시.

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _app.include_router(health_router)
    _app.include_router(chat_router)
    return _app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host, port, _ = parse_url(app.state.settings.rag_api_url)
    logger = get_logger(app.state.settings.rag_api_log_name)
    logger.info(f"# Running rag-api on {host}:{port}")
    uvicorn.run("rag_api.main:app", host=host, port=port, reload=False)
