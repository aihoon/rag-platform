"""Agentic RAG pipeline service (basic multi-strategy).""" ###

from __future__ import annotations

from typing import Any, Optional ### ###

from langsmith import traceable ### ###
from langchain_core.prompts import ChatPromptTemplate ### ###
from langchain_openai import ChatOpenAI ### ###

from ..config.settings import Settings
from .adaptive_rag_service import run_adaptive_rag ### ###
from .standard_rag_service import run_standard_rag ### ###
from .corrective_rag_service import run_corrective_rag ### ###
from .self_rag_service import run_self_rag ### ###
from .fusion_rag_service import run_fusion_rag ### ###
from .hyde_rag_service import run_hyde_rag ### ###
from .graph_rag_service import run_graph_rag ### ###


def _judge_best( ### ###
    *, ### ###
    settings: Settings, ### ###
    user_input: str, ### ###
    candidates: list[dict[str, Any]], ### ###
) -> str: ### ###
    llm = ChatOpenAI( ### ###
        api_key=settings.openai_api_key, ### ###
        model=settings.chat_model, ### ###
        temperature=settings.agentic_judge_temperature, ### ###
        max_tokens=settings.agentic_judge_max_tokens, ### ###
        timeout=settings.chat_model_request_timeout, ### ###
    ) ### ###
    prompt = ChatPromptTemplate.from_messages( ### ###
        [ ### ###
            ( ### ###
                "system", ### ###
                "Select the best answer for the user question. Respond with only the candidate name.", ### ###
            ), ### ###
            ( ### ###
                "human", ### ###
                "Question:\\n{question}\\n\\nCandidates:\\n{candidates}\\n\\nBest:", ### ###
            ), ### ###
        ] ### ###
    ) ### ###
    lines = [] ### ###
    for item in candidates: ### ###
        name = item["name"] ### ###
        answer = item["result"].get("answer", "") ### ###
        src_count = len(item["result"].get("sources", [])) ### ###
        lines.append(f"- {name}: sources={src_count} answer={answer}") ### ###
    messages = prompt.format_messages(question=user_input, candidates="\\n".join(lines)) ### ###
    response = llm.invoke(messages) ### ###
    text = getattr(response, "content", "").strip().lower() ### ###
    for item in candidates: ### ###
        if item["name"].lower() == text: ### ###
            return item["name"] ### ###
    return candidates[0]["name"] ### ###


@traceable(name="run_agentic_rag", run_type="chain")
def run_agentic_rag(
    *,
    settings: Settings,
    logger: Any,
    user_input: str,
    company_id: Optional[int], ### ###
    class_name: Optional[str], ### ###
    machine_id: Optional[int], ### ###
    machine_cat: Optional[int], ### ###
    chat_history: list[dict[str, str]],
) -> dict[str, Any]: ### ###
    handlers = { ### ###
        "adaptive": run_adaptive_rag, ### ###
        "standard": run_standard_rag, ### ###
        "corrective": run_corrective_rag, ### ###
        "self_rag": run_self_rag, ### ###
        "fusion": run_fusion_rag, ### ###
        "hyde": run_hyde_rag, ### ###
        "graph": run_graph_rag, ### ###
    } ### ###
    candidates = [ ### ###
        name.strip() ### ###
        for name in settings.agentic_candidates.split(",") ### ###
        if name.strip() ### ###
    ] ### ###
    if not candidates: ### ###
        candidates = ["adaptive"] ### ###
    selected: list[dict[str, Any]] = [] ### ###
    for name in candidates[: settings.agentic_max_candidates]: ### ###
        handler = handlers.get(name) ### ###
        if handler is None: ### ###
            continue ### ###
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
        selected.append({"name": name, "result": result}) ### ###
    if not selected: ### ###
        fallback = run_adaptive_rag( ### ###
            settings=settings, ### ###
            logger=logger, ### ###
            user_input=user_input, ### ###
            company_id=company_id, ### ###
            machine_id=machine_id, ### ###
            machine_cat=machine_cat, ### ###
            class_name=class_name, ### ###
            chat_history=chat_history, ### ###
        ) ### ###
        return { ### ###
            "answer": fallback["answer"], ### ###
            "sources": fallback["sources"], ### ###
            "meta": {"agenticFallback": True}, ### ###
        } ### ###
    best_name = _judge_best( ### ###
        settings=settings, ### ###
        user_input=user_input, ### ###
        candidates=selected, ### ###
    ) ### ###
    best = next(item for item in selected if item["name"] == best_name) ### ###
    meta: dict[str, Any] = { ### ###
        "agenticCandidates": [item["name"] for item in selected], ### ###
        "agenticWinner": best_name, ### ###
    } ### ###
    if isinstance(best["result"], dict) and best["result"].get("meta"): ### ###
        meta.update(best["result"]["meta"]) ### ###
    return { ### ###
        "answer": best["result"]["answer"], ### ###
        "sources": best["result"]["sources"], ### ###
        "meta": meta, ### ###
    } ### ###
