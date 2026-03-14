"""Image extraction service using pdfplumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pdfplumber
from pdfplumber.page import Page


class _TesseractModule(Protocol):
    def image_to_string(self, image: Any) -> str: ...


try:
    import pytesseract as _pytesseract
except ImportError:  # pragma: no cover
    _pytesseract = None

pytesseract: _TesseractModule | None = _pytesseract

from ...config.settings import Settings


@dataclass
class ExtractedImage:
    page: int
    image_id: str
    figure_number: str
    bbox: tuple[float, float, float, float]
    image_path: str
    image_class: str
    ocr_text: str
    surrounding_context: str


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, top, x1, bottom = bbox
    return max(0.0, x1 - x0) * max(0.0, bottom - top)


def _iou(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax0, at, ax1, ab = a
    bx0, bt, bx1, bb = b
    ix0 = max(ax0, bx0)
    it = max(at, bt)
    ix1 = min(ax1, bx1)
    ib = min(ab, bb)
    inter = max(0.0, ix1 - ix0) * max(0.0, ib - it)
    if inter <= 0:
        return 0.0
    union = _bbox_area(a) + _bbox_area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union


def _classify_image(
    *, ocr_text: str, context: str, area_ratio: float, settings: Settings
) -> str:
    lowered = f"{ocr_text}\n{context}".lower()
    if (
        area_ratio <= settings.image_decorative_max_area_ratio
        and len((ocr_text or "").strip()) <= settings.image_decorative_max_ocr_chars
    ):
        return "decorative"
    if len((ocr_text or "").strip()) >= 20:
        return "text_heavy"
    if any(
        token in lowered
        for token in (
            "chart",
            "graph",
            "plot",
            "kpi",
            "bar",
            "line",
            "scatter",
            "heatmap",
        )
    ):
        return "data_viz"
    return "semantic"


def _extract_ocr_text(
    *,
    page: Page,
    bbox: tuple[float, float, float, float],
    settings: Settings,
) -> str:
    cropped = page.crop(bbox)
    if settings.image_ocr_enabled and pytesseract is not None:
        try:
            pil_image = cropped.to_image(resolution=200).original
            text = (pytesseract.image_to_string(pil_image) or "").strip()
            if text:
                return text
        except (OSError, RuntimeError, TypeError, ValueError):
            pass
    return (cropped.extract_text() or "").strip()


def extract_images_from_pdf(
    *, pdf_path: Path, settings: Settings, logger: Any
) -> list[ExtractedImage]:
    extracted: list[ExtractedImage] = []
    output_root = Path(settings.image_extract_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_area = max(1.0, float(page.width) * float(page.height))
            table_bboxes = [tuple(t.bbox) for t in page.find_tables() if t.bbox]
            page_images = list(page.images or [])
            page_count = 0
            for image_index, image_obj in enumerate(page_images, start=1):
                logger.info(
                    "image extract candidate|page=%s|image_index=%s",
                    page_index,
                    image_index,
                )
                if page_count >= settings.image_max_per_page:
                    logger.info(
                        "image extract skip|max_per_page|page=%s|image_index=%s|max_per_page=%s",
                        page_index,
                        image_index,
                        settings.image_max_per_page,
                    )
                    break
                bbox = (
                    float(image_obj.get("x0", 0.0) or 0.0),
                    float(image_obj.get("top", 0.0) or 0.0),
                    float(image_obj.get("x1", 0.0) or 0.0),
                    float(image_obj.get("bottom", 0.0) or 0.0),
                )
                area_ratio = _bbox_area(bbox) / page_area
                if area_ratio < settings.image_min_area_ratio:
                    logger.info(
                        "image extract skip|min_area|page=%s|image_index=%s|"
                        "area_ratio=%.6f|min_area_ratio=%.6f",
                        page_index,
                        image_index,
                        area_ratio,
                        settings.image_min_area_ratio,
                    )
                    continue
                if any(_iou(bbox, table_bbox) >= 0.30 for table_bbox in table_bboxes):
                    logger.info(
                        "image extract skip|overlap_table|page=%s|image_index=%s",
                        page_index,
                        image_index,
                    )
                    continue
                image_id = f"p{page_index}_img{image_index}"
                figure_number = f"Figure {image_index}"
                image_file = (
                    output_root / f"{pdf_path.stem}_p{page_index}_img{image_index}.png"
                )
                try:
                    page.crop(bbox).to_image(resolution=150).save(
                        str(image_file), format="PNG"
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    logger.warning(
                        "image extract save_fail|page=%s|image_id=%s|detail=%s",
                        page_index,
                        image_id,
                        exc,
                    )
                    continue
                surrounding = (page.extract_text() or "").strip()[
                    : settings.image_context_window_chars
                ]
                ocr_text = _extract_ocr_text(page=page, bbox=bbox, settings=settings)
                image_class = _classify_image(
                    ocr_text=ocr_text,
                    context=surrounding,
                    area_ratio=area_ratio,
                    settings=settings,
                )
                if image_class == "decorative":
                    logger.info(
                        "image extract skip|decorative|page=%s|image_id=%s|"
                        "area_ratio=%.6f|ocr_chars=%s",
                        page_index,
                        image_id,
                        area_ratio,
                        len((ocr_text or "").strip()),
                    )
                    continue
                logger.info(
                    "image extract accepted|page=%s|image_id=%s|"
                    "figure=%s|class=%s|area_ratio=%.6f|ocr_chars=%s",
                    page_index,
                    image_id,
                    figure_number,
                    image_class,
                    area_ratio,
                    len((ocr_text or "").strip()),
                )
                extracted.append(
                    ExtractedImage(
                        page=page_index,
                        image_id=image_id,
                        figure_number=figure_number,
                        bbox=bbox,
                        image_path=str(image_file),
                        image_class=image_class,
                        ocr_text=ocr_text,
                        surrounding_context=surrounding,
                    )
                )
                page_count += 1
    logger.info("image_extract done|pdf=%s|images=%s", str(pdf_path), len(extracted))
    return extracted
