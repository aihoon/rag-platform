"""Table quality gate service."""

from __future__ import annotations

from dataclasses import dataclass

from ...config.settings import Settings

from .normalize_service import NormalizedTable


@dataclass
class TableQualityResult:
    needs_review: bool
    parser_confidence: float
    empty_cell_ratio: float
    header_inconsistency: float
    reason: str


def evaluate_table_quality(
    *, settings: Settings, table: NormalizedTable
) -> TableQualityResult:
    parser_confidence = float(table.parser_confidence)

    total_cells = 0
    empty_cells = 0
    for row in table.rows:
        for value in row.values():
            total_cells += 1
            if not str(value).strip():
                empty_cells += 1
    empty_ratio = (empty_cells / total_cells) if total_cells > 0 else 1.0

    header_len = len(table.column_names)
    inconsistent_rows = 0
    for row in table.rows:
        if len(row.keys()) != header_len:
            inconsistent_rows += 1
    header_inconsistency = (inconsistent_rows / len(table.rows)) if table.rows else 0.0

    reasons: list[str] = []
    if parser_confidence < settings.table_min_parser_confidence:
        reasons.append("low_parser_confidence")
    if empty_ratio > settings.table_max_empty_cell_ratio:
        reasons.append("high_empty_cell_ratio")
    if header_inconsistency > settings.table_max_header_inconsistency:
        reasons.append("high_header_inconsistency")

    return TableQualityResult(
        needs_review=bool(reasons),
        parser_confidence=parser_confidence,
        empty_cell_ratio=round(empty_ratio, 4),
        header_inconsistency=round(header_inconsistency, 4),
        reason=",".join(reasons),
    )
