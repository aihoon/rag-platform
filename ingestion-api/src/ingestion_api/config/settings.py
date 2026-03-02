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
    weaviate_general_class_name: str = "General"
    weaviate_machine_class_name: str = "Machine"
    weaviate_default_class: str = "General"

    openai_api_key: str = ""

    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_password"
    neo4j_database: str = "neo4j"
    neo4j_extract_triples: bool = True
    neo4j_extract_max_chars: int = 4000
    neo4j_triple_model: str = "gpt-4o-mini"
    neo4j_triple_max_tokens: int = 200
    neo4j_max_triples_per_chunk: int = 20
    neo4j_default_label: str = "General"

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
        weaviate_general_class_name=os.getenv("WEAVIATE_GENERAL_CLASS_NAME", "General"),
        weaviate_machine_class_name=os.getenv("WEAVIATE_MACHINE_CLASS_NAME", "Machine"),
        weaviate_default_class=os.getenv("WEAVIATE_DEFAULT_CLASS", "General"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),

        neo4j_enabled=os.getenv("NEO4J_ENABLED", "false").lower() == "true",
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "neo4j_password"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_extract_triples=os.getenv("NEO4J_EXTRACT_TRIPLES", "true").lower() == "true",
        neo4j_extract_max_chars=int(os.getenv("NEO4J_EXTRACT_MAX_CHARS", "4000")),
        neo4j_triple_model=os.getenv("NEO4J_TRIPLE_MODEL", "gpt-4o-mini"),
        neo4j_triple_max_tokens=int(os.getenv("NEO4J_TRIPLE_MAX_TOKENS", "200")),
        neo4j_max_triples_per_chunk=int(os.getenv("NEO4J_MAX_TRIPLES_PER_CHUNK", "20")),
        neo4j_default_label=os.getenv("NEO4J_DEFAULT_LABEL", "General"),
    )
