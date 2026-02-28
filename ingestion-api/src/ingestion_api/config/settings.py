"""Application settings for ingestion-api."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    ingestion_api_url: str = "http://0.0.0.0:8000"

    ingestion_api_log_path: str = "./logs/ingestion-api.log"
    ingestion_api_log_level: str = "INFO"
    ingestion_api_log_name: str = "ingestion-api"

    ingestion_ui_db_path: str = ""

    weaviate_url: str = "http://localhost:8080"
    weaviate_log_path: str = "./logs/weaviate-db.log"

    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    request_timeout: int = 30
    class_prefix: str = "C"

    openai_api_key: str = ""

    def resolved_ingestion_ui_db_path(self) -> Path:
        if self.ingestion_ui_db_path:
            return Path(self.ingestion_ui_db_path).expanduser().resolve()
        return (Path(__file__).resolve().parents[4] / "ingestion-ui" / "data" / "ingestion_ui.db").resolve()


def load_settings() -> Settings:
    return Settings(
        ingestion_api_url=os.getenv("INGESTION_API_URL", "http://0.0.0.0:8000"),
        ingestion_api_log_path=os.getenv("INGESTION_API_LOG_PATH", "./logs/ingestion-api.log"),
        ingestion_api_log_level=os.getenv("INGESTION_API_LOG_LEVEL", "INFO"),
        ingestion_api_log_name=os.getenv("INGESTION_API_LOG_NAME", "ingestion-api"),
        ingestion_ui_db_path=os.getenv("INGESTION_UI_DB_PATH", ""),
        weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        weaviate_log_path=os.getenv("WEAVIATE_LOG_PATH", "./logs/weaviate-db.log"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        chunk_size=int(os.getenv("EMBEDDING_CHUNK_SIZE", "1200")),
        chunk_overlap=int(os.getenv("EMBEDDING_CHUNK_OVERLAP", "200")),
        request_timeout=int(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SEC", "30")),
        class_prefix=os.getenv("WEAVIATE_CLASS_PREFIX", "C"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
