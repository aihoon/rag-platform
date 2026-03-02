"""Adaptive RAG pipeline service."""

from __future__ import annotations

from typing import Any, Optional
import csv
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ..config.settings import Settings
from .conversational_rag_service import run_conversational_rag
from .corrective_rag_service import run_corrective_rag
from .standard_rag_service import run_standard_rag
from .rag_service_utils import _format_history
from .self_rag_service import run_self_rag
from .fusion_rag_service import run_fusion_rag
from .hyde_rag_service import run_hyde_rag
from .graph_rag_service import run_graph_rag

_SELF_RAG_HINTS = ("cite", "citation", "source", "출처", "근거")
_CORRECTIVE_HINTS = ("why", "how", "compare", "difference", "cause", "relationship", "tradeoff")
_FUSION_HINTS = ("list", "enumerate", "all", "many", "various", "overview", "summary", "비교", "정리")
_HYDE_HINTS = ("hypothesis", "assume", "suppose", "추정", "가정")
_GRAPH_HINTS = ("relation", "relationship", "graph", "network", "연관", "관계")


def _log_router_event(*, settings: Settings, data: dict[str, Any]) -> None:
    path = Path(settings.adaptive_router_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "route",
                "reason",
                "source",
                "raw",
                "chat_history",
                "input_len",
                "company_id",
                "machine_id",
                "machine_cat",
            ],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(data)


def _heuristic_route(*, user_input: str) -> Optional[str]:
    lowered = user_input.lower()
    if any(token in lowered for token in _SELF_RAG_HINTS):
        return "self_rag"
    if any(token in lowered for token in _GRAPH_HINTS):
        return "graph"
    if any(token in lowered for token in _HYDE_HINTS):
        return "hyde"
    if any(token in lowered for token in _FUSION_HINTS):
        return "fusion"
    if any(token in lowered for token in _CORRECTIVE_HINTS):
        return "corrective"
    return None


def _route_strategy(*, settings: Settings, user_input: str, chat_history: list[dict[str, str]]) -> tuple[str, str]:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.adaptive_router_temperature,
        max_tokens=settings.adaptive_router_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a routing classifier for RAG. Respond with only one token: "
                "standard, corrective, self_rag, fusion, hyde, or graph. Use self_rag if "
                "the answer likely requires self-checking of factual support. Use fusion "
                "if the user asks for lists, comparisons, or broad coverage. Use hyde if "
                "a hypothetical answer would help retrieval. Use graph if relationships "
                "between entities are central. Use corrective if the question is ambiguous, "
                "requires multi-step reasoning over multiple docs, or likely needs query "
                "refinement. Otherwise use standard.",
            ),
            (
                "human",
                "Chat history:\n{history}\n\nUser question:\n{question}\n\nRoute:",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip().lower()
    if "graph" in text:
        return "graph"
    if "hyde" in text:
        return "hyde"
    if "fusion" in text:
        return "fusion"
    if "self" in text:
        return "self_rag"
    if "corrective" in text:
        return "corrective"
    return "standard", text


@traceable(name="run_adaptive_rag", run_type="chain")
def run_adaptive_rag(
    *,
    settings: Settings,
    logger: Any,
    user_input: str,
    company_id: Optional[int], ### ###
    class_name: Optional[str], ### ###
    machine_id: Optional[int], ### ###
    machine_cat: Optional[int], ### ###
    chat_history: list[dict[str, str]],
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for rag-api")

    if chat_history:
        route = "conversational"
        reason = "history_present"
        router_source = "history"
        router_raw = "history_present"
    else:
        heuristic = _heuristic_route(user_input=user_input)
        if heuristic:
            route = heuristic
            reason = "heuristic"
            router_source = "heuristic"
            router_raw = heuristic
        else:
            route, router_raw = _route_strategy(
            settings=settings,
            user_input=user_input,
            chat_history=chat_history,
            )
            reason = "llm_router"
            router_source = "llm"

    handlers = { ### ###
        "standard": run_standard_rag, ### ###
        "conversational": run_conversational_rag, ### ###
        "corrective": run_corrective_rag, ### ###
        "self_rag": run_self_rag, ### ###
        "fusion": run_fusion_rag, ### ###
        "hyde": run_hyde_rag, ### ###
        "graph": run_graph_rag, ### ###
    } ### ###
    handler = handlers.get(route, run_standard_rag)
    result = handler( ### ###
        settings=settings, ### ###
        logger=logger, ### ###
        user_input=user_input, ### ###
        company_id=company_id, ### ###
        machine_id=machine_id, ### ###
        machine_cat=machine_cat, ### ###
        class_name=class_name, ### ###
        chat_history=chat_history, ### ###
    ) ### ###

    meta = {}
    if isinstance(result, dict) and result.get("meta"):
        meta.update(result["meta"])
    meta.update(
        {
            "adaptiveRoute": route,
            "adaptiveReason": reason,
            "adaptiveRouterSource": router_source,
            "adaptiveRouterRaw": router_raw,
        }
    )
    logger.info(
        "adaptive_rag|route=%s|reason=%s|source=%s|raw=%s|chat_history=%s|input_len=%s",
        route,
        reason,
        router_source,
        router_raw,
        bool(chat_history),
        len(user_input),
    )
    _log_router_event(
        settings=settings,
        data={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "route": route,
            "reason": reason,
            "source": router_source,
            "raw": router_raw,
            "chat_history": bool(chat_history),
            "input_len": len(user_input),
            "company_id": company_id,
            "machine_id": machine_id,
            "machine_cat": machine_cat,
        },
    )

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "meta": meta,
    }
