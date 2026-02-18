"""FastAPI app entrypoint for ingestion-api."""

from __future__ import annotations

import os
from pathlib import Path ###
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from shared.utils.url import parse_url
from shared.observability.logger import setup_logger, get_logger

from .api.routers.health import router as health_router
from .api.routers.ingestion import router as ingestion_router
from .config.settings import load_settings

INGESTION_API_DOTENV_PATH = "../../../.env"

def create_app() -> FastAPI:
    ingestion_api_dotenv_path = os.getenv("INGESTION_API_DOTENV_PATH", INGESTION_API_DOTENV_PATH)
    dotenv_path = (Path(__file__).resolve().parent / ingestion_api_dotenv_path).resolve()
    if dotenv_path.exists():
        load_dotenv(dotenv_path=str(dotenv_path))
    else:
        load_dotenv()
    settings = load_settings()
    os.environ["LANGSMITH_PROJECT"] = os.getenv("INGESTION_LANGSMITH_PROJECT", "rag-platform-ingestion-api")

    setup_logger(log_path=settings.ingestion_api_log_path, level=settings.ingestion_api_log_level)
    _logger = get_logger(settings.ingestion_api_log_name)
    _logger.info("# Starting ingestion-api server bootstrap")

    _, _, root_path = parse_url(settings.ingestion_api_url)
    _app = FastAPI(title="ingestion-api", root_path=root_path)
    _app.state.settings = settings
    _app.state.logger = _logger
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _app.include_router(health_router)
    _app.include_router(ingestion_router)
    return _app


app = create_app()


###-----------------------------------------------------------------------------
### Argument Parsing
###-----------------------------------------------------------------------------
###
###def parse_arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
###    ap = argparse.ArgumentParser(description="Ingestion API")
###    ap.add_argument("--env_path", type=str, default=".env")
###    ap.add_argument(
###        "--env-file",
###        dest="env_file",
###        type=str,
###        default=None,
###        help="Path to .env file. If omitted, INGESTION_ENV_FILE or default .env is used.",
###    )
###    return ap.parse_args(argv)

if __name__ == "__main__":

    import uvicorn

    host, port, _ = parse_url(app.state.settings.ingestion_api_url) ###
    logger = get_logger(app.state.settings.ingestion_api_log_name) ###
    logger.info(f"# Running ingestion-api on {host}:{port}") ###
    ###uvicorn.run(runtime_app, host=host, port=port, reload=False)
    uvicorn.run("ingestion_api.main:app", host=host, port=port, reload=False) ###
