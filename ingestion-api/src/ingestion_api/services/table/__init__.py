"""Table ingestion services package."""

from .extract_service import ExtractedTable, extract_tables_from_pdf
from .normalize_service import NormalizedTable, normalize_extracted_table
from .chunk_service import build_table_chunks
from .quality_service import TableQualityResult, evaluate_table_quality

from .weaviate_service import ensure_table_fields_on_class, upsert_table_chunks

__all__ = [
    "ExtractedTable",
    "extract_tables_from_pdf",
    "NormalizedTable",
    "normalize_extracted_table",
    "build_table_chunks",
    "TableQualityResult",
    "evaluate_table_quality",
    "ensure_table_fields_on_class",
    "upsert_table_chunks",
]
