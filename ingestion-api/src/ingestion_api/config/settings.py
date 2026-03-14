"""Application settings for ingestion-api."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shared.schemas.rag_class import DEFAULT_CLASS_NAME, RagClassName
from shared.utils.env import get_str, get_int, get_float, get_bool


@dataclass(frozen=True)
class Settings:

    debug: bool = True

    ingestion_api_url: str = "http://0.0.0.0:4590"
    ingestion_api_root_path: str = ""
    ingestion_api_log_path: str = "./logs/ingestion-api.log"
    ingestion_api_log_level: str = "INFO"
    ingestion_api_log_name: str = "ingestion-api"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    neo4j_triple_model: str = "gpt-4o-mini"
    image_summary_model: str = "gpt-4o-mini"

    embedding_chunk_size: int = 800
    embedding_chunk_overlap: int = 200
    embedding_request_timeout: int = 30

    ingestion_ui_db_path: str = ""

    weaviate_url: str = "http://localhost:8080"
    # weaviate_log_path: str = "./logs/weaviate-db.log"
    # weaviate_class_prefix: str = "rag"
    weaviate_request_timeout: int = 30
    # weaviate_general_class_name: str = RagClassName.GENERAL.value
    weaviate_machine_class_name: str = RagClassName.MACHINE.value
    weaviate_default_class: str = DEFAULT_CLASS_NAME

    neo4j_enabled: bool = True
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_password"
    neo4j_database: str = "neo4j"
    neo4j_default_label: str = DEFAULT_CLASS_NAME
    neo4j_extract_triples: bool = True
    neo4j_extract_max_chars: int = 4000
    neo4j_triple_max_tokens: int = 200
    neo4j_max_triples_per_chunk: int = 20

    table_enabled: bool = True
    table_fail_policy: str = "fail_open"
    table_min_parser_confidence: float = 0.75
    table_max_empty_cell_ratio: float = 0.30
    table_max_header_inconsistency: float = 0.20
    table_embedding_version: int = 1

    image_enabled: bool = True
    image_ocr_enabled: bool = True
    image_fail_policy: str = "fail_open"
    image_min_area_ratio: float = 0.015
    image_decorative_max_area_ratio: float = 0.04
    image_decorative_max_ocr_chars: int = 6
    image_max_per_page: int = 8
    image_extract_dir: str = "./data/extracted_images"
    image_context_window_chars: int = 800
    image_min_ocr_chars: int = 10

    def resolved_ingestion_ui_db_path(self) -> Path:
        if self.ingestion_ui_db_path:
            return Path(self.ingestion_ui_db_path).expanduser().resolve()
        return (
            Path(__file__).resolve().parents[4]
            / "ingestion-ui"
            / "data"
            / "ingestion_ui.db"
        ).resolve()


def load_settings() -> Settings:
    _d = Settings()

    return Settings(
        debug=get_bool("DEBUG", _d.debug),
        ingestion_ui_db_path=get_str("INGESTION_UI_DB_PATH", _d.ingestion_ui_db_path),
        ingestion_api_url=get_str("INGESTION_API_URL", _d.ingestion_api_url),
        ingestion_api_root_path=get_str(
            "INGESTION_API_ROOT_PATH", _d.ingestion_api_root_path
        ),
        ingestion_api_log_path=get_str(
            "INGESTION_API_LOG_PATH", _d.ingestion_api_log_path
        ),
        ingestion_api_log_level=get_str(
            "INGESTION_API_LOG_LEVEL", _d.ingestion_api_log_level
        ),
        ingestion_api_log_name=get_str(
            "INGESTION_API_LOG_NAME", _d.ingestion_api_log_name
        ),
        openai_api_key=get_str("OPENAI_API_KEY", _d.openai_api_key),
        embedding_model=get_str("EMBEDDING_MODEL", _d.embedding_model),
        neo4j_triple_model=get_str("NEO4J_TRIPLE_MODEL", _d.neo4j_triple_model),
        image_summary_model=get_str("IMAGE_SUMMARY_MODEL", _d.image_summary_model),
        embedding_chunk_size=get_int("EMBEDDING_CHUNK_SIZE", _d.embedding_chunk_size),
        embedding_chunk_overlap=get_int(
            "EMBEDDING_CHUNK_OVERLAP", _d.embedding_chunk_overlap
        ),
        embedding_request_timeout=get_int(
            "EMBEDDING_REQUEST_TIMEOUT_SEC", _d.embedding_request_timeout
        ),
        weaviate_url=get_str("WEAVIATE_URL", _d.weaviate_url),
        # weaviate_log_path=get_str("WEAVIATE_LOG_PATH", _d.weaviate_log_path),
        # weaviate_class_prefix=get_str("WEAVIATE_CLASS_PREFIX", _d.weaviate_class_prefix),
        weaviate_request_timeout=get_int(
            "WEAVIATE_REQUEST_TIMEOUT_SEC", _d.weaviate_request_timeout
        ),
        # weaviate_general_class_name=get_str("WEAVIATE_GENERAL_CLASS_NAME", _d.weaviate_general_class_name),
        weaviate_machine_class_name=get_str(
            "WEAVIATE_MACHINE_CLASS_NAME", _d.weaviate_machine_class_name
        ),
        weaviate_default_class=get_str(
            "WEAVIATE_DEFAULT_CLASS", _d.weaviate_default_class
        ),
        neo4j_enabled=get_bool("NEO4J_ENABLED", _d.neo4j_enabled),
        neo4j_uri=get_str("NEO4J_URI", _d.neo4j_uri),
        neo4j_user=get_str("NEO4J_USER", _d.neo4j_user),
        neo4j_password=get_str("NEO4J_PASSWORD", _d.neo4j_password),
        neo4j_database=get_str("NEO4J_DATABASE", _d.neo4j_database),
        neo4j_default_label=get_str("NEO4J_DEFAULT_LABEL", _d.neo4j_default_label),
        neo4j_extract_triples=get_bool(
            "NEO4J_EXTRACT_TRIPLES", _d.neo4j_extract_triples
        ),
        neo4j_extract_max_chars=get_int(
            "NEO4J_EXTRACT_MAX_CHARS", _d.neo4j_extract_max_chars
        ),
        neo4j_triple_max_tokens=get_int(
            "NEO4J_TRIPLE_MAX_TOKENS", _d.neo4j_triple_max_tokens
        ),
        neo4j_max_triples_per_chunk=get_int(
            "NEO4J_MAX_TRIPLES_PER_CHUNK", _d.neo4j_max_triples_per_chunk
        ),
        table_enabled=get_bool("TABLE_ENABLED", _d.table_enabled),
        table_fail_policy=get_str("TABLE_FAIL_POLICY", _d.table_fail_policy),
        table_min_parser_confidence=get_float(
            "TABLE_MIN_PARSER_CONFIDENCE", _d.table_min_parser_confidence
        ),
        table_max_empty_cell_ratio=get_float(
            "TABLE_MAX_EMPTY_CELL_RATIO", _d.table_max_empty_cell_ratio
        ),
        table_max_header_inconsistency=get_float(
            "TABLE_MAX_HEADER_INCONSISTENCY", _d.table_max_header_inconsistency
        ),
        table_embedding_version=get_int(
            "TABLE_EMBEDDING_VERSION", _d.table_embedding_version
        ),
        image_enabled=get_bool("IMAGE_ENABLED", _d.image_enabled),
        image_ocr_enabled=get_bool("IMAGE_OCR_ENABLED", _d.image_ocr_enabled),
        image_fail_policy=get_str("IMAGE_FAIL_POLICY", _d.image_fail_policy),
        image_min_area_ratio=get_float("IMAGE_MIN_AREA_RATIO", _d.image_min_area_ratio),
        image_decorative_max_area_ratio=get_float(
            "IMAGE_DECORATIVE_MAX_AREA_RATIO", _d.image_decorative_max_area_ratio
        ),
        image_decorative_max_ocr_chars=get_int(
            "IMAGE_DECORATIVE_MAX_OCR_CHARS", _d.image_decorative_max_ocr_chars
        ),
        image_max_per_page=get_int("IMAGE_MAX_PER_PAGE", _d.image_max_per_page),
        image_extract_dir=get_str("IMAGE_EXTRACT_DIR", _d.image_extract_dir),
        image_context_window_chars=get_int(
            "IMAGE_CONTEXT_WINDOW_CHARS", _d.image_context_window_chars
        ),
        image_min_ocr_chars=get_int("IMAGE_MIN_OCR_CHARS", _d.image_min_ocr_chars),
    )
