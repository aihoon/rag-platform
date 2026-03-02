"""Application settings for rag-api."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    rag_api_url: str = "http://0.0.0.0:8010"

    rag_api_root_path: str = ""
    rag_api_log_path: str = "./logs/rag-api.log"
    rag_api_log_level: str = "INFO"
    rag_api_log_name: str = "rag-api"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_request_timeout: int = 30
    chat_model: str = "gpt-4o-mini"
    chat_model_request_timeout: int = 30
    chat_model_temperature: float = 0.2
    chat_model_max_tokens: int = 800

    weaviate_url: str = "http://localhost:8080"
    weaviate_log_path: str = "./logs/weaviate-db.log"
    weaviate_general_class_name: str = "General"
    weaviate_machine_class_name: str = "Machine"
    weaviate_default_class: str = "General"
    weaviate_request_timeout: int = 30
    weaviate_retrieval_top_k: int = 4

    neo4j_enabled: bool = True
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_password"
    neo4j_database: str = "neo4j"
    neo4j_default_label: str = "General"

    tavily_api_key: str = ""
    tavily_search_depth: str = "basic"
    tavily_max_results: int = 5
    tavily_include_answer: bool = True
    tavily_include_raw_content: bool = False
    tavily_request_timeout: int = 30
    tavily_max_retries: int = 2
    tavily_retry_backoff_sec: float = 1.0
    tavily_result_max_chars: int = 800
    tavily_external_log_path: str = "./logs/tavily_external_sources.csv"
    tavily_summary_max_tokens: int = 160
    tavily_summary_temperature: float = 0.0

    rag_max_context_chars: int = 4000
    rag_history_turns: int = 6
    rag_min_score_distance: float = -1.0
    standard_rag_system_prompt_path: str = ""

    crag_min_relevant_docs: int = 1
    crag_min_relevance_ratio: float = 0.4
    crag_max_retries: int = 1
    crag_fallback_top_k: int = 8
    crag_grader_max_chars: int = 1200

    selfrag_retrieval_top_k: int = 4
    selfrag_max_retries: int = 1
    selfrag_grader_max_chars: int = 1200
    selfrag_router_temperature: float = 0.0
    selfrag_router_max_tokens: int = 32

    fusion_query_count: int = 4
    fusion_query_top_k: int = 4
    fusion_final_top_k: int = 6
    fusion_rrf_k: int = 60
    fusion_query_temperature: float = 0.2
    fusion_query_max_tokens: int = 120

    hyde_retrieval_top_k: int = 4
    hyde_hypothesis_temperature: float = 0.2
    hyde_hypothesis_max_tokens: int = 200

    graph_retrieval_top_k: int = 6
    graph_extract_max_chars: int = 4000
    graph_extract_max_tokens: int = 300
    graph_max_triples: int = 60
    graph_use_second_retrieval: bool = True
    graph_second_retrieval_top_k: int = 4

    adaptive_router_temperature: float = 0.0
    adaptive_router_max_tokens: int = 32
    adaptive_router_log_path: str = "./logs/adaptive_router.csv"

    agentic_candidates: str = "standard,corrective,self_rag,fusion,hyde,graph"
    agentic_max_candidates: int = 3
    agentic_judge_temperature: float = 0.0
    agentic_judge_max_tokens: int = 32

    def resolved_standard_rag_system_prompt_path(self) -> Path | None:
        if not self.standard_rag_system_prompt_path:
            return None
        return (Path(__file__).resolve().parents[4] /
                self.standard_rag_system_prompt_path
                ).resolve()


def load_settings() -> Settings:
    return Settings(
        rag_api_url=os.getenv("RAG_API_URL", "http://0.0.0.0:8000"),

        rag_api_root_path=os.getenv("RAG_API_ROOT_PATH", ""),
        rag_api_log_path=os.getenv("RAG_API_LOG_PATH", "./logs/rag-api.log"),
        rag_api_log_level=os.getenv("RAG_API_LOG_LEVEL", "INFO"),
        rag_api_log_name=os.getenv("RAG_API_LOG_NAME", "rag-api"),

        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_request_timeout=int(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SEC", "30")),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        chat_model_request_timeout=int(os.getenv("CHAT_MODEL_REQUEST_TIMEOUT_SEC", "30")),
        chat_model_temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.2")),
        chat_model_max_tokens=int(os.getenv("CHAT_MODEL_MAX_TOKENS", "800")),

        weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        weaviate_log_path=os.getenv("WEAVIATE_LOG_PATH", "./logs/weaviate-db.log"),
        weaviate_general_class_name=os.getenv("WEAVIATE_GENERAL_CLASS_NAME", "General"),
        weaviate_machine_class_name=os.getenv("WEAVIATE_MACHINE_CLASS_NAME", "Machine"),
        weaviate_default_class=os.getenv("WEAVIATE_DEFAULT_CLASS", "General"),
        weaviate_request_timeout=int(os.getenv("WEAVIATE_REQUEST_TIMEOUT_SEC", "30")),
        weaviate_retrieval_top_k=int(os.getenv("WEAVIATE_RETRIEVAL_TOP_K", "4")),

        neo4j_enabled=os.getenv("NEO4J_ENABLED", "false").lower() == "true",
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "neo4j_password"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_default_label=os.getenv("NEO4J_DEFAULT_LABEL", "General"),

        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        tavily_search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        tavily_max_results=int(os.getenv("TAVILY_MAX_RESULTS", "5")),
        tavily_include_answer=os.getenv("TAVILY_INCLUDE_ANSWER", "true").lower() == "true",
        tavily_include_raw_content=os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "false").lower() == "true",
        tavily_request_timeout=int(os.getenv("TAVILY_REQUEST_TIMEOUT_SEC", "30")),
        tavily_max_retries=int(os.getenv("TAVILY_MAX_RETRIES", "2")),
        tavily_retry_backoff_sec=float(os.getenv("TAVILY_RETRY_BACKOFF_SEC", "1.0")),
        tavily_result_max_chars=int(os.getenv("TAVILY_RESULT_MAX_CHARS", "800")),
        tavily_external_log_path=os.getenv("TAVILY_EXTERNAL_LOG_PATH", "./logs/tavily_external_sources.csv"),
        tavily_summary_max_tokens=int(os.getenv("TAVILY_SUMMARY_MAX_TOKENS", "160")),
        tavily_summary_temperature=float(os.getenv("TAVILY_SUMMARY_TEMPERATURE", "0.0")),

        rag_max_context_chars=int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000")),
        rag_history_turns=int(os.getenv("RAG_MAX_HISTORY_TURNS", "6")),
        rag_min_score_distance=float(os.getenv("RAG_MIN_SCORE_DISTANCE", "-1")),
        standard_rag_system_prompt_path=os.getenv("STANDARD_RAG_SYSTEM_PROMPT_PATH", ""),

        crag_min_relevant_docs=int(os.getenv("CRAG_MIN_RELEVANT_DOCS", "1")),
        crag_min_relevance_ratio=float(os.getenv("CRAG_MIN_RELEVANCE_RATIO", "0.4")),
        crag_max_retries=int(os.getenv("CRAG_MAX_RETRIES", "2")),
        crag_fallback_top_k=int(os.getenv("CRAG_FALLBACK_TOP_K", "8")),
        crag_grader_max_chars=int(os.getenv("CRAG_GRADER_MAX_CHARS", "1200")),

        selfrag_retrieval_top_k=int(os.getenv("SELFRAG_RETRIEVAL_TOP_K", "4")),
        selfrag_max_retries=int(os.getenv("SELFRAG_MAX_RETRIES", "1")),
        selfrag_grader_max_chars=int(os.getenv("SELFRAG_GRADER_MAX_CHARS", "1200")),
        selfrag_router_temperature=float(os.getenv("SELFRAG_ROUTER_TEMPERATURE", "0.0")),
        selfrag_router_max_tokens=int(os.getenv("SELFRAG_ROUTER_MAX_TOKENS", "32")),

        fusion_query_count=int(os.getenv("FUSION_QUERY_COUNT", "4")),
        fusion_query_top_k=int(os.getenv("FUSION_QUERY_TOP_K", "4")),
        fusion_final_top_k=int(os.getenv("FUSION_FINAL_TOP_K", "6")),
        fusion_rrf_k=int(os.getenv("FUSION_RRF_K", "60")),
        fusion_query_temperature=float(os.getenv("FUSION_QUERY_TEMPERATURE", "0.2")),
        fusion_query_max_tokens=int(os.getenv("FUSION_QUERY_MAX_TOKENS", "120")),

        hyde_retrieval_top_k=int(os.getenv("HYDE_RETRIEVAL_TOP_K", "4")),
        hyde_hypothesis_temperature=float(os.getenv("HYDE_HYPOTHESIS_TEMPERATURE", "0.2")),
        hyde_hypothesis_max_tokens=int(os.getenv("HYDE_HYPOTHESIS_MAX_TOKENS", "200")),

        graph_retrieval_top_k=int(os.getenv("GRAPH_RETRIEVAL_TOP_K", "6")),
        graph_extract_max_chars=int(os.getenv("GRAPH_EXTRACT_MAX_CHARS", "4000")),
        graph_extract_max_tokens=int(os.getenv("GRAPH_EXTRACT_MAX_TOKENS", "300")),
        graph_max_triples=int(os.getenv("GRAPH_MAX_TRIPLES", "60")),
        graph_use_second_retrieval=os.getenv("GRAPH_USE_SECOND_RETRIEVAL", "true").lower() == "true",
        graph_second_retrieval_top_k=int(os.getenv("GRAPH_SECOND_RETRIEVAL_TOP_K", "4")),

        adaptive_router_temperature=float(os.getenv("ADAPTIVE_ROUTER_TEMPERATURE", "0.0")),
        adaptive_router_max_tokens=int(os.getenv("ADAPTIVE_ROUTER_MAX_TOKENS", "32")),
        adaptive_router_log_path=os.getenv("ADAPTIVE_ROUTER_LOG_PATH", "./logs/adaptive_router.csv"),

        agentic_candidates=os.getenv("AGENTIC_CANDIDATES", "standard,corrective,self_rag,fusion,hyde,graph"),
        agentic_max_candidates=int(os.getenv("AGENTIC_MAX_CANDIDATES", "3")),
        agentic_judge_temperature=float(os.getenv("AGENTIC_JUDGE_TEMPERATURE", "0.0")),
        agentic_judge_max_tokens=int(os.getenv("AGENTIC_JUDGE_MAX_TOKENS", "32")),
    )
