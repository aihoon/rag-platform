"""Application settings for rag-api."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    rag_api_url: str = "http://0.0.0.0:8010"
    rag_api_root_path: str = ""
    rag_api_log_path: str = "./logs/rag-api.log"
    rag_api_log_level: str = "INFO"
    rag_api_log_name: str = "rag-api"

    embedding_model: str = "text-embedding-3-small"
    embedding_request_timeout: int = 30

    rag_max_context_chars: int = 4000
    rag_history_turns: int = 6
    rag_min_score_distance: float = -1.0
    rag_system_prompt: str = ""

    crag_min_relevant_docs: int = 1
    crag_min_relevance_ratio: float = 0.4
    crag_max_retries: int = 1
    crag_fallback_top_k: int = 8
    crag_grader_max_chars: int = 1200

    weaviate_url: str = "http://localhost:8080"
    weaviate_log_path: str = "./logs/weaviate-db.log"
    weaviate_class_prefix: str = "C"
    weaviate_request_timeout: int = 30
    weaviate_retrieval_top_k: int = 4

    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    chat_model_request_timeout: int = 30
    chat_model_temperature: float = 0.2
    chat_model_max_tokens: int = 800


def load_settings() -> Settings:
    return Settings(
        rag_api_url=os.getenv("RAG_API_URL", "http://0.0.0.0:8000"),
        rag_api_root_path=os.getenv("RAG_API_ROOT_PATH", ""),
        rag_api_log_path=os.getenv("RAG_API_LOG_PATH", "./logs/rag-api.log"),
        rag_api_log_level=os.getenv("RAG_API_LOG_LEVEL", "INFO"),
        rag_api_log_name=os.getenv("RAG_API_LOG_NAME", "rag-api"),

        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_request_timeout=int(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SEC", "30")),

        rag_max_context_chars=int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000")),
        rag_history_turns=int(os.getenv("RAG_MAX_HISTORY_TURNS", "6")),
        rag_min_score_distance=float(os.getenv("RAG_MIN_SCORE_DISTANCE", "-1")),
        rag_system_prompt=os.getenv("RAG_SYSTEM_PROMPT", ""),

        crag_min_relevant_docs=int(os.getenv("CRAG_MIN_RELEVANT_DOCS", "1")),
        crag_min_relevance_ratio=float(os.getenv("CRAG_MIN_RELEVANCE_RATIO", "0.4")),
        crag_max_retries=int(os.getenv("CRAG_MAX_RETRIES", "2")),
        crag_fallback_top_k=int(os.getenv("CRAG_FALLBACK_TOP_K", "8")),
        crag_grader_max_chars=int(os.getenv("CRAG_GRADER_MAX_CHARS", "1200")),

        weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        weaviate_log_path=os.getenv("WEAVIATE_LOG_PATH", "./logs/weaviate-db.log"),
        weaviate_class_prefix=os.getenv("WEAVIATE_CLASS_PREFIX", "C"),
        weaviate_request_timeout=int(os.getenv("WEAVIATE_REQUEST_TIMEOUT_SEC", "30")),
        weaviate_retrieval_top_k=int(os.getenv("WEAVIATE_RETRIEVAL_TOP_K", "4")),

        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        chat_model_request_timeout=int(os.getenv("CHAT_MODEL_REQUEST_TIMEOUT_SEC", "30")),
        chat_model_temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.2")),
        chat_model_max_tokens=int(os.getenv("CHAT_MODEL_MAX_TOKENS", "800")),
    )
