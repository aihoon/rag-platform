"""Table extraction service using pdfplumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from pdfplumber.page import Page


@dataclass
class ExtractedTable:
    page: int
    table_id: str
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]
    parser_confidence: float
    table_title: str = ""
    context_before: str = ""
    context_after: str = ""


def _normalize_cell(cell: Any) -> str:
    if cell is None:
        return ""
    return str(cell).strip()


def _estimate_parser_confidence(rows: list[list[str]]) -> float:
    if not rows:
        return 0.0
    total_cells = sum(len(r) for r in rows if r)
    if total_cells <= 0:
        return 0.0
    non_empty_cells = 0
    for row in rows:
        for cell in row:
            if _normalize_cell(cell):
                non_empty_cells += 1
    return round(non_empty_cells / float(total_cells), 4)


def _extract_context_text(
    *, page: Page, bbox: tuple[float, float, float, float]
) -> tuple[str, str]:
    x0, top, x1, bottom = bbox
    page_width = float(page.width)
    page_height = float(page.height)
    before_top = 0.0
    before_bottom = max(0.0, float(top) - 2.0)
    after_top = min(page_height, float(bottom) + 2.0)
    after_bottom = page_height

    before_text = ""
    after_text = ""
    if before_bottom > before_top:
        before_text = (
            page.crop((0.0, before_top, page_width, before_bottom)).extract_text() or ""
        ).strip()
    if after_bottom > after_top:
        after_text = (
            page.crop((0.0, after_top, page_width, after_bottom)).extract_text() or ""
        ).strip()

    before_text = before_text[-260:]
    after_text = after_text[:260]
    return before_text, after_text


def _guess_table_title(*, context_before: str) -> str:
    if not context_before:
        return ""
    lines = [line.strip() for line in context_before.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:120]


def extract_tables_from_pdf(*, pdf_path: Path, logger: Any) -> list[ExtractedTable]:
    extracted: list[ExtractedTable] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if not tables:
                continue
            for table_index, table in enumerate(tables, start=1):
                raw_rows = table.extract() or []
                rows = [
                    [_normalize_cell(cell) for cell in row] for row in raw_rows if row
                ]
                confidence = _estimate_parser_confidence(rows)
                table_bbox = tuple(table.bbox) if table.bbox else (0.0, 0.0, 0.0, 0.0)
                context_before, context_after = _extract_context_text(
                    page=page, bbox=table_bbox
                )
                table_title = _guess_table_title(context_before=context_before)
                extracted.append(
                    ExtractedTable(
                        page=page_index,
                        table_id=f"p{page_index}_t{table_index}",
                        bbox=table_bbox,
                        rows=rows,
                        parser_confidence=confidence,
                        table_title=table_title,
                        context_before=context_before,
                        context_after=context_after,
                    )
                )
    logger.info("table_extract done|pdf=%s|tables=%s", str(pdf_path), len(extracted))
    return extracted
