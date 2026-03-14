"""Table normalization service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedTable:
    page: int
    table_id: str
    bbox: str
    table_title: str
    section_title: str
    header_path: list[str]
    column_names: list[str]
    column_schema: str
    units: list[str]
    parser_confidence: float
    rows: list[dict[str, Any]]
    context_before: str = ""
    context_after: str = ""


def _infer_dtype(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "unknown"
    normalized = text.replace(",", "")
    if normalized.isdigit():
        return "int"
    try:
        float(normalized)
        return "float"
    except ValueError:
        pass
    if "-" in text and len(text) >= 8:
        return "date"
    return "text"


def normalize_extracted_table(
    *,
    page: int,
    table_id: str,
    bbox: tuple[float, float, float, float],
    rows: list[list[str]],
    parser_confidence: float,
    table_title: str = "",
    context_before: str = "",
    context_after: str = "",
) -> NormalizedTable:
    if not rows:
        return NormalizedTable(
            page=page,
            table_id=table_id,
            bbox=str({"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]}),
            table_title=table_title,
            section_title="",
            context_before=context_before,
            context_after=context_after,
            header_path=[],
            column_names=[],
            column_schema="{}",
            units=[],
            parser_confidence=parser_confidence,
            rows=[],
        )

    header = [str(c).strip() or f"column_{idx+1}" for idx, c in enumerate(rows[0])]
    data_rows = rows[1:] if len(rows) > 1 else []

    normalized_rows: list[dict[str, Any]] = []
    for row in data_rows:
        cells = list(row) + [""] * max(0, len(header) - len(row))
        normalized_rows.append(
            {header[i]: str(cells[i]).strip() for i in range(len(header))}
        )

    schema = {name: "unknown" for name in header}
    for row in normalized_rows:
        for name, val in row.items():
            dtype = _infer_dtype(str(val))
            if dtype != "unknown" and schema.get(name, "unknown") == "unknown":
                schema[name] = dtype

    return NormalizedTable(
        page=page,
        table_id=table_id,
        bbox=str({"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]}),
        table_title=table_title,
        section_title="",
        context_before=context_before,
        context_after=context_after,
        header_path=header,
        column_names=header,
        column_schema=str(schema),
        units=[],
        parser_confidence=parser_confidence,
        rows=normalized_rows,
    )
