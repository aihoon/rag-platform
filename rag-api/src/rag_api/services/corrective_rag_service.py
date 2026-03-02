"""Corrective RAG pipeline service (LangGraph-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict, List, Dict ### ###

import csv ### ###
import requests
import time ### ###
from datetime import datetime, timezone ### ###
from pathlib import Path ### ###
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import StateGraph, END
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import (
    RetrievedChunk,
    _build_context,
    _format_history,
    _generate_answer,
    _retrieve_chunks,
)


class CorrectiveState(TypedDict):
    user_input: str
    query: str
    class_name: Optional[str]
    company_id: Optional[int]
    machine_cat: Optional[int]
    machine_id: Optional[int]
    chat_history: list[dict[str, str]]
    chunks: list[RetrievedChunk]
    relevant_chunks: list[RetrievedChunk]
    relevance_ratio: float
    relevant_count: int
    retry_count: int
    used_fallback: bool
    answer: str
    external_context: str
    external_results: list[dict[str, Any]]


def _rewrite_query(
    *,
    settings: Settings,
    user_input: str,
    chat_history: list[dict[str, str]],
) -> str:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=0.0,
        max_tokens=64,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Rewrite the question into a concise search query. "
                "Keep key entities and add missing keywords if helpful.",
            ),
            (
                "human",
                "Chat history:\n{history}\n\nUser question:\n{question}\n\nSearch query:",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input)
    response = llm.invoke(messages)
    return getattr(response, "content", "").strip()


def _grade_chunk_relevance(
    *,
    settings: Settings,
    query: str,
    chunk: RetrievedChunk,
) -> bool:
    content = chunk.content.strip()
    if not content:
        return False
    snippet = content[: settings.crag_grader_max_chars]
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=0.0,
        max_tokens=4,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a relevance grader. Reply with only 'yes' or 'no'.",
            ),
            (
                "human",
                "Question:\n{question}\n\nDocument:\n{document}\n\nRelevant?",
            ),
        ]
    )
    messages = prompt.format_messages(question=query, document=snippet)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip().lower()
    return text.startswith("y")


def _tavily_search(
    *,
    settings: Settings,
    query: str,
) -> tuple[str, list[dict[str, Any]]]:
    if not settings.tavily_api_key:
        return "", []
    payload = { ### ###
        "query": query, ### ###
        "search_depth": settings.tavily_search_depth, ### ###
        "max_results": settings.tavily_max_results, ### ###
        "include_answer": settings.tavily_include_answer, ### ###
        "include_raw_content": settings.tavily_include_raw_content, ### ###
    } ### ###
    headers = { ### ###
        "Authorization": f"Bearer {settings.tavily_api_key}", ### ###
        "Content-Type": "application/json", ### ###
    } ### ###
    resp = requests.post( ### ###
        "https://api.tavily.com/search", ### ###
        json=payload, ### ###
        headers=headers, ### ###
        timeout=settings.tavily_request_timeout, ### ###
    ) ### ###
    resp.raise_for_status() ### ###
    data = resp.json() ### ###
    answer = str(data.get("answer", "")).strip() ### ###
    results = data.get("results", []) or [] ### ###
    context_parts: list[str] = [] ### ###
    if answer: ### ###
        context_parts.append(f"[Tavily Answer]\n{answer}") ### ###
    for item in results: ### ###
        content = str(item.get("content") or item.get("snippet") or "").strip() ### ###
        title = str(item.get("title") or "").strip() ### ###
        if not content: ### ###
            continue ### ###
        header = f"[Tavily Result] {title}".strip() ### ###
        context_parts.append(f"{header}\n{content}") ### ###
    external_context = "\n\n".join(context_parts).strip() ### ###
    if len(external_context) > settings.rag_max_context_chars: ### ###
        external_context = external_context[: settings.rag_max_context_chars] ### ###
    return external_context, results ### ###


def _tavily_results_to_chunks( ### ###
    results: list[dict[str, Any]], ### ###
) -> list[RetrievedChunk]: ### ###
    chunks: list[RetrievedChunk] = [] ### ###
    for item in results: ### ###
        content = str(item.get("content") or item.get("snippet") or "").strip() ### ###
        if not content: ### ###
            continue ### ###
        source = str(item.get("url") or item.get("title") or "tavily").strip() ### ###
        chunks.append( ### ###
            RetrievedChunk( ### ###
                content=content, ### ###
                source=source, ### ###
                page_number=0, ### ###
                company_id=0, ### ###
                machine_id=0, ### ###
                file_upload_id="tavily", ### ###
                machine_cat=0, ### ###
                distance=None, ### ###
            ) ### ###
        ) ### ###
    return chunks ### ###


def _tavily_results_to_external_sources( ### ###
    results: list[dict[str, Any]], ### ###
    max_chars: int, ### ###
) -> list[dict[str, Any]]: ### ###
    external_sources: list[dict[str, Any]] = [] ### ###
    seen: set[tuple[str, str]] = set() ### ###
    for item in results: ### ###
        content = str(item.get("content") or item.get("snippet") or "").strip() ### ###
        title = str(item.get("title") or "").strip() ### ###
        url = str(item.get("url") or "").strip() ### ###
        key = (url, content[:128]) ### ###
        if key in seen: ### ###
            continue ### ###
        seen.add(key) ### ###
        if max_chars > 0 and len(content) > max_chars: ### ###
            content = f"{content[:max_chars]}..." ### ###
        external_sources.append( ### ###
            { ### ###
                "title": title or None, ### ###
                "url": url or None, ### ###
                "content": content or None, ### ###
            } ### ###
        ) ### ###
    return external_sources ### ###


def _append_external_sources_log( ### ###
    *, ### ###
    log_path: str, ### ###
    query: str, ### ###
    user_input: str, ### ###
    rag_type: str, ### ###
    class_name: Optional[str], ### ###
    company_id: Optional[int], ### ###
    machine_id: Optional[int], ### ###
    machine_cat: Optional[int], ### ###
    external_summary: str, ### ###
    external_sources: list[dict[str, Any]], ### ###
) -> None: ### ###
    if not external_sources: ### ###
        return ### ###
    path = Path(log_path) ### ###
    path.parent.mkdir(parents=True, exist_ok=True) ### ###
    is_new = not path.exists() ### ###
    with path.open("a", newline="", encoding="utf-8") as handle: ### ###
        writer = csv.writer(handle) ### ###
        if is_new: ### ###
            writer.writerow( ### ###
                [ ### ###
                    "timestamp", ### ###
                    "rag_type", ### ###
                    "class_name", ### ###
                    "company_id", ### ###
                    "machine_id", ### ###
                    "machine_cat", ### ###
                    "query", ### ###
                    "user_input", ### ###
                    "external_summary", ### ###
                    "title", ### ###
                    "url", ### ###
                    "content", ### ###
                ] ### ###
            ) ### ###
        timestamp = datetime.now(timezone.utc).isoformat() ### ###
        for item in external_sources: ### ###
            writer.writerow( ### ###
                [ ### ###
                    timestamp, ### ###
                    rag_type, ### ###
                    class_name or "", ### ###
                    company_id if company_id is not None else "", ### ###
                    machine_id if machine_id is not None else "", ### ###
                    machine_cat if machine_cat is not None else "", ### ###
                    query, ### ###
                    user_input, ### ###
                    external_summary, ### ###
                    item.get("title") or "", ### ###
                    item.get("url") or "", ### ###
                    item.get("content") or "", ### ###
                ] ### ###
            ) ### ###


def _summarize_external_sources( ### ###
    *, ### ###
    settings: Settings, ### ###
    query: str, ### ###
    external_sources: list[dict[str, Any]], ### ###
) -> str: ### ###
    if not external_sources: ### ###
        return "" ### ###
    llm = ChatOpenAI( ### ###
        api_key=settings.openai_api_key, ### ###
        model=settings.chat_model, ### ###
        temperature=settings.tavily_summary_temperature, ### ###
        max_tokens=settings.tavily_summary_max_tokens, ### ###
        timeout=settings.chat_model_request_timeout, ### ###
    ) ### ###
    snippets = [] ### ###
    for item in external_sources: ### ###
        title = item.get("title") or "" ### ###
        content = item.get("content") or "" ### ###
        if not content: ### ###
            continue ### ###
        snippets.append(f"Title: {title}\nContent: {content}") ### ###
    joined = "\n\n---\n\n".join(snippets) ### ###
    prompt = ChatPromptTemplate.from_messages( ### ###
        [ ### ###
            ( ### ###
                "system", ### ###
                "Summarize the external sources for the user's question. " ### ###
                "Be concise and factual. If sources are irrelevant, say so.", ### ###
            ), ### ###
            ( ### ###
                "human", ### ###
                "Question:\n{question}\n\nSources:\n{sources}\n\nSummary:", ### ###
            ), ### ###
        ] ### ###
    ) ### ###
    messages = prompt.format_messages(question=query, sources=joined) ### ###
    response = llm.invoke(messages) ### ###
    return getattr(response, "content", "").strip() ### ###


def _build_graph(settings: Settings, logger: Any, embedder: Any):
    graph = StateGraph(CorrectiveState)

    def retrieve_node(state: CorrectiveState) -> CorrectiveState:
        top_k = (
            settings.weaviate_retrieval_top_k
            if state["retry_count"] == 0
            else settings.crag_fallback_top_k
        )
        query_embedding = embedder.embed_query(state["query"])
        chunks = _retrieve_chunks( ### ###
            settings=settings, ### ###
            logger=logger, ### ###
            query_embedding=query_embedding, ### ###
            company_id=state["company_id"], ### ###
            machine_id=state["machine_id"], ### ###
            machine_cat=state["machine_cat"], ### ###
            class_name=state.get("class_name"), ### ###
            top_k=top_k, ### ###
        ) ### ###
        return {**state, "chunks": chunks}

    def grade_node(state: CorrectiveState) -> CorrectiveState:
        relevant: list[RetrievedChunk] = []
        for chunk in state["chunks"]:
            if _grade_chunk_relevance(settings=settings, query=state["query"], chunk=chunk):
                relevant.append(chunk)
        total = len(state["chunks"])
        relevant_count = len(relevant)
        ratio = (relevant_count / total) if total else 0.0
        return {
            **state,
            "relevant_chunks": relevant,
            "relevant_count": relevant_count,
            "relevance_ratio": ratio,
        }

    def rewrite_node(state: CorrectiveState) -> CorrectiveState:
        rewritten = _rewrite_query(
            settings=settings,
            user_input=state["user_input"],
            chat_history=state["chat_history"],
        )
        return {
            **state,
            "query": rewritten or state["query"],
            "retry_count": state["retry_count"] + 1,
            "used_fallback": True,
        }

    def generate_node(state: CorrectiveState) -> CorrectiveState:
        chosen = state["relevant_chunks"] or state["chunks"]
        context = _build_context(chosen, settings.rag_max_context_chars) ### ###
        if state.get("external_context"): ### ###
            context = f"{context}\n\n---\n\n{state['external_context']}" if context else state["external_context"] ### ###
        history_text = _format_history(state["chat_history"], settings.rag_history_turns)
        answer = _generate_answer(
            settings=settings,
            query=state["user_input"],
            context=context,
            history_text=history_text,
        )
        return {**state, "answer": answer}

    def external_search_node(state: CorrectiveState) -> CorrectiveState: ### ###
        external_context, external_results = "", [] ### ###
        max_attempts = max(1, settings.tavily_max_retries + 1) ### ###
        for attempt in range(max_attempts): ### ###
            try: ### ###
                external_context, external_results = _tavily_search( ### ###
                    settings=settings, ### ###
                    query=state["query"], ### ###
                ) ### ###
                break ### ###
            except Exception as exc: ### ###
                logger.info(f"tavily search failed|attempt={attempt + 1}|error={exc}") ### ###
                if attempt + 1 >= max_attempts: ### ###
                    break ### ###
                delay = settings.tavily_retry_backoff_sec * (2 ** attempt) ### ###
                time.sleep(delay) ### ###
        return { ### ###
            **state, ### ###
            "external_context": external_context, ### ###
            "external_results": external_results, ### ###
        } ### ###

    def route_after_grade(state: CorrectiveState) -> str:
        enough_docs = state["relevant_count"] >= settings.crag_min_relevant_docs
        enough_ratio = state["relevance_ratio"] >= settings.crag_min_relevance_ratio
        if enough_docs and enough_ratio:
            return "generate"
        if state["retry_count"] < settings.crag_max_retries: ### ###
            return "rewrite" ### ###
        if settings.tavily_api_key: ### ###
            return "external_search" ### ###
        return "generate" ### ###

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("external_search", external_search_node) ### ###
    graph.add_node("generate", generate_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "rewrite": "rewrite",
            "generate": "generate", ### ###
            "external_search": "external_search", ### ###
        },
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("external_search", "generate") ### ###
    graph.add_edge("generate", END)
    return graph.compile()


@dataclass
class CorrectiveResult:
    answer: str
    sources: list[RetrievedChunk]
    used_fallback: bool
    retry_count: int
    relevance_ratio: float
    relevant_count: int


@traceable(name="run_corrective_rag", run_type="chain")
def run_corrective_rag(
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

    embedder = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        timeout=settings.embedding_request_timeout,
    )

    graph = _build_graph(settings, logger, embedder)
    state: CorrectiveState = { ### ###
        "user_input": user_input, ### ###
        "query": user_input, ### ###
        "company_id": company_id, ### ###
        "class_name": class_name, ### ###
        "machine_id": machine_id, ### ###
        "machine_cat": machine_cat, ### ###
        "chat_history": chat_history, ### ###
        "chunks": [], ### ###
        "relevant_chunks": [], ### ###
        "relevance_ratio": 0.0, ### ###
        "relevant_count": 0, ### ###
        "retry_count": 0, ### ###
        "used_fallback": False, ### ###
        "answer": "", ### ###
        "external_context": "", ### ###
        "external_results": [], ### ###
    } ### ###
    result_state = graph.invoke(state)
    sources = result_state["relevant_chunks"] or result_state["chunks"] ### ###
    external_chunks = _tavily_results_to_chunks(result_state.get("external_results", [])) ### ###
    if external_chunks: ### ###
        sources = sources + external_chunks ### ###
    external_sources = _tavily_results_to_external_sources( ### ###
        result_state.get("external_results", []), ### ###
        settings.tavily_result_max_chars, ### ###
    ) ### ###
    external_summary = _summarize_external_sources( ### ###
        settings=settings, ### ###
        query=result_state.get("query", ""), ### ###
        external_sources=external_sources, ### ###
    ) ### ###
    _append_external_sources_log( ### ###
        log_path=settings.tavily_external_log_path, ### ###
        query=result_state.get("query", ""), ### ###
        user_input=user_input, ### ###
        rag_type="corrective", ### ###
        class_name=class_name, ### ###
        company_id=company_id, ### ###
        machine_id=machine_id, ### ###
        machine_cat=machine_cat, ### ###
        external_summary=external_summary, ### ###
        external_sources=external_sources, ### ###
    ) ### ###
    logger.info( ### ###
        "crag result|external_search_used=%s|external_result_count=%s", ### ###
        bool(result_state.get("external_results")), ### ###
        len(result_state.get("external_results", [])), ### ###
    ) ### ###
    return {
        "answer": result_state["answer"],
        "sources": sources,
        "external_sources": external_sources, ### ###
        "meta": {
            "usedFallback": result_state["used_fallback"],
            "retryCount": result_state["retry_count"],
            "relevantDocs": result_state["relevant_count"],
            "relevanceRatio": round(result_state["relevance_ratio"], 3),
            "externalSearchUsed": bool(result_state.get("external_results")), ### ###
            "externalResultCount": len(result_state.get("external_results", [])), ### ###
            "externalSources": external_sources, ### ###
            "externalSummary": external_summary, ### ###
        },
    }
