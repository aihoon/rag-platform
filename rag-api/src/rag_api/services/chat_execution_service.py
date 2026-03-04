"""Shared chat execution helpers for rag-api endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException

from ..config.settings import Settings
from .adaptive_rag_service import run_adaptive_rag
from .agentic_rag_service import run_agentic_rag
from .conversational_rag_service import run_conversational_rag
from .corrective_rag_service import run_corrective_rag
from .fusion_rag_service import run_fusion_rag
from .graph_rag_service import run_graph_rag
from .hyde_rag_service import run_hyde_rag
from .self_rag_service import run_self_rag
from .standard_rag_service import run_standard_rag


def _result_value(result: object, key: str, default=None):
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def get_rag_handlers() -> dict[str, Any]:
    return {
        "standard": run_standard_rag,
        "conversational": run_conversational_rag,
        "corrective": run_corrective_rag,
        "self_rag": run_self_rag,
        "fusion": run_fusion_rag,
        "hyde": run_hyde_rag,
        "graph": run_graph_rag,
        "adaptive": run_adaptive_rag,
        "agentic": run_agentic_rag,
    }


@dataclass(frozen=True)
class ChatExecutionResult:
    answer_text: str
    rag_type: str
    class_name: str
    company_id: Optional[int]
    machine_id: Optional[int]
    machine_cat: Optional[int]
    dashboard_id: Optional[int]
    model_id: Optional[int]
    source_chunks: list[Any]
    extra_meta: dict[str, Any]
    extra_external_sources: list[dict[str, Any]]


def execute_chat(
    *,
    settings: Settings,
    logger: Any,
    user_input: str,
    rag_type: str,
    class_name: Optional[str],
    company_id: Optional[int],
    machine_id: Optional[int],
    machine_cat: Optional[int],
    dashboard_id: Optional[int],
    model_id: Optional[int],
    chat_history: list[dict[str, str]],
) -> ChatExecutionResult:
    handlers = get_rag_handlers()
    if rag_type not in handlers:
        raise HTTPException(status_code=400, detail=f"Unsupported rag_type: {rag_type}")

    effective_class_name = class_name or settings.weaviate_default_class
    is_general_class = effective_class_name == settings.weaviate_general_class_name
    effective_company_id = None if is_general_class else company_id
    effective_machine_id = None if is_general_class else machine_id
    effective_machine_cat = None if is_general_class else machine_cat

    logger.info(
        "chat execution|class_name=%s|company_id=%s|machine_id=%s|machine_cat=%s|rag_type=%s|dashboard_id=%s|model_id=%s",
        effective_class_name,
        effective_company_id,
        effective_machine_id,
        effective_machine_cat,
        rag_type,
        dashboard_id,
        model_id,
    )

    handler = handlers[rag_type]
    result = handler(
        settings=settings,
        logger=logger,
        user_input=user_input,
        company_id=effective_company_id,
        machine_id=effective_machine_id,
        machine_cat=effective_machine_cat,
        class_name=effective_class_name,
        chat_history=chat_history,
    )

    extra_meta = _result_value(result, "meta", None)
    if not isinstance(extra_meta, dict):
        extra_meta = {}

    raw_external_sources = _result_value(result, "external_sources", [])
    extra_external_sources = [
        item for item in raw_external_sources if isinstance(item, dict)
    ]

    return ChatExecutionResult(
        answer_text=_result_value(result, "answer", ""),
        rag_type=rag_type,
        class_name=effective_class_name,
        company_id=effective_company_id,
        machine_id=effective_machine_id,
        machine_cat=effective_machine_cat,
        dashboard_id=dashboard_id,
        model_id=model_id,
        source_chunks=_result_value(result, "sources", []),
        extra_meta=extra_meta,
        extra_external_sources=extra_external_sources,
    )
