"""Image chunk building service."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI
from shared.schemas.ingestion import ImageChunk
from shared.schemas.chunk_type import ChunkType

from ...config.settings import Settings
from .extract_service import ExtractedImage


def _build_image_summary_fallback(*, image: ExtractedImage) -> str:
    return (
        f"{image.page}페이지 {image.figure_number} 이미지입니다. "
        f"분류={image.image_class}. "
        "문서 검색을 위해 추출된 이미지 설명입니다."
    )


@traceable(name="image_summary_vision", run_type="llm")
def _build_image_summary_with_vision(
    *, settings: Settings, logger: Any, image: ExtractedImage
) -> str:
    if not settings.openai_api_key:
        logger.info(
            "llm_call skip|component=image_summary_vision|reason=no_openai_api_key|image_id=%s",
            image.image_id,
        )
        return _build_image_summary_fallback(image=image)
    image_path = Path(image.image_path)
    if not image_path.exists():
        logger.info(
            "llm_call skip|component=image_summary_vision|reason=image_path_missing|image_id=%s|path=%s",
            image.image_id,
            image.image_path,
        )
        return _build_image_summary_fallback(image=image)
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        data_url = f"data:image/png;base64,{image_b64}"
        logger.info(
            "llm_call start|component=image_summary_vision|model=%s|image_id=%s|page=%s|figure=%s",
            settings.image_summary_model,
            image.image_id,
            image.page,
            image.figure_number,
        )
        client = wrap_openai(OpenAI(api_key=settings.openai_api_key))
        response = client.chat.completions.create(
            model=settings.image_summary_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 기술 문서 이미지를 검색용으로 요약하는 도우미입니다. "
                        "개체, 구조, 라벨, 추세 단서, 실무적 의미를 중심으로 요약하세요. "
                        "요약은 한국어로 2~4문장으로 간결하게 작성하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Figure={image.figure_number}, "
                            f"page={image.page}, "
                            f"class={image.image_class}. "
                            f"한국어로 요약해 주세요.",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=220,
        )
        content = (response.choices[0].message.content or "").strip()
        if content:
            logger.info(
                "llm_call done|component=image_summary_vision|model=%s|image_id=%s|output_chars=%s",
                settings.image_summary_model,
                image.image_id,
                len(content),
            )
            return content
    except Exception as exc:
        logger.warning(
            "llm_call fail|component=image_summary_vision|model=%s|image_id=%s|detail=%s",
            settings.image_summary_model,
            image.image_id,
            exc,
        )
    return _build_image_summary_fallback(image=image)


def _build_image_ocr(*, image: ExtractedImage, settings: Settings) -> str:
    if not settings.image_ocr_enabled:
        return ""
    text = (image.ocr_text or "").strip()
    if len(text) < settings.image_min_ocr_chars:
        return ""
    return text


def _build_image_context(*, image: ExtractedImage) -> str:
    return (image.surrounding_context or "").strip()


def _make_image_chunk(
    *,
    doc_id: str,
    file_name: str,
    image: ExtractedImage,
    chunk_type: ChunkType,
    content: str,
    bbox_text: str,
    ingest_version: int,
    embedding_model: str,
    embedding_version: int,
    created_at: str,
) -> ImageChunk:
    return ImageChunk(
        doc_id=doc_id,
        file_name=file_name,
        page=image.page,
        image_id=image.image_id,
        figure_number=image.figure_number,
        chunk_type=chunk_type.value,
        content=content,
        bbox=bbox_text,
        image_path=image.image_path,
        image_class=image.image_class,
        ocr_text=image.ocr_text,
        surrounding_context=image.surrounding_context,
        ingest_version=ingest_version,
        embedding_model=embedding_model,
        embedding_dim=0,
        embedding_version=embedding_version,
        created_at=created_at,
    )


def build_image_chunks(
    *,
    settings: Settings,
    logger: Any,
    doc_id: str,
    file_name: str,
    ingest_version: int,
    embedding_model: str,
    embedding_version: int,
    extracted_images: list[ExtractedImage],
) -> list[ImageChunk]:
    now_iso = datetime.now(timezone.utc).isoformat()
    chunks: list[ImageChunk] = []

    for image in extracted_images:
        logger.info(
            "image chunk start|doc_id=%s|image_id=%s|page=%s|figure=%s|class=%s",
            doc_id,
            image.image_id,
            image.page,
            image.figure_number,
            image.image_class,
        )
        bbox_text = str(
            {
                "x0": image.bbox[0],
                "top": image.bbox[1],
                "x1": image.bbox[2],
                "bottom": image.bbox[3],
            }
        )
        summary_text = _build_image_summary_with_vision(
            settings=settings, logger=logger, image=image
        )
        ocr_text = _build_image_ocr(image=image, settings=settings)
        context_text = _build_image_context(image=image)
        logger.info(
            "image chunk contents|doc_id=%s|image_id=%s|summary_chars=%s|ocr_chars=%s|context_chars=%s",
            doc_id,
            image.image_id,
            len(summary_text),
            len(ocr_text),
            len(context_text),
        )

        chunks.append(
            _make_image_chunk(
                doc_id=doc_id,
                file_name=file_name,
                image=image,
                chunk_type=ChunkType.IMAGE_SUMMARY,
                content=summary_text,
                bbox_text=bbox_text,
                ingest_version=ingest_version,
                embedding_model=embedding_model,
                embedding_version=embedding_version,
                created_at=now_iso,
            )
        )
        if ocr_text:
            chunks.append(
                _make_image_chunk(
                    doc_id=doc_id,
                    file_name=file_name,
                    image=image,
                    chunk_type=ChunkType.IMAGE_OCR,
                    content=ocr_text,
                    bbox_text=bbox_text,
                    ingest_version=ingest_version,
                    embedding_model=embedding_model,
                    embedding_version=embedding_version,
                    created_at=now_iso,
                )
            )
        if context_text:
            chunks.append(
                _make_image_chunk(
                    doc_id=doc_id,
                    file_name=file_name,
                    image=image,
                    chunk_type=ChunkType.IMAGE_CONTEXT,
                    content=context_text,
                    bbox_text=bbox_text,
                    ingest_version=ingest_version,
                    embedding_model=embedding_model,
                    embedding_version=embedding_version,
                    created_at=now_iso,
                )
            )
        logger.info(
            "image chunk done|doc_id=%s|image_id=%s|chunk_types=%s",
            doc_id,
            image.image_id,
            ",".join(
                sorted(
                    {
                        chunk.chunk_type
                        for chunk in chunks
                        if chunk.image_id == image.image_id
                    }
                )
            ),
        )
    return chunks
