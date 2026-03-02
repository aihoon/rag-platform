"""Fusion RAG pipeline service (multi-query + RRF)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import RetrievedChunk, _build_context, _format_history, _generate_answer, _retrieve_chunks


def _generate_queries(*, settings: Settings, user_input: str, chat_history: list[dict[str, str]]) -> list[str]:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.fusion_query_temperature,
        max_tokens=settings.fusion_query_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Generate {n} diverse search queries that could retrieve complementary documents. "
                "Return one query per line and nothing else.",
            ),
            (
                "human",
                "Chat history:\n{history}\n\nUser question:\n{question}\n\nQueries:",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input, n=settings.fusion_query_count)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip()
    queries = [line.strip() for line in text.splitlines() if line.strip()]
    if user_input not in queries:
        queries.insert(0, user_input)
    return queries[: settings.fusion_query_count]


def _rrf_fuse(*, results: list[list[RetrievedChunk]], rrf_k: int) -> list[RetrievedChunk]:
    score_map: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}
    for chunks in results:
        for rank, chunk in enumerate(chunks, start=1):
            key = f"{chunk.source}|{chunk.page_number}|{chunk.file_upload_id}|{chunk.machine_id}"
            score_map[key] = score_map.get(key, 0.0) + 1.0 / (rrf_k + rank)
            if key not in chunk_map:
                chunk_map[key] = chunk
    ordered = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    return [chunk_map[key] for key, _ in ordered]


@dataclass
class FusionResult:
    answer: str
    sources: list[RetrievedChunk]
    queries: list[str]


@traceable(name="run_fusion_rag", run_type="chain")
def run_fusion_rag(
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

    queries = _generate_queries(
        settings=settings,
        user_input=user_input,
        chat_history=chat_history,
    )

    per_query_chunks: list[list[RetrievedChunk]] = []
    for query in queries:
        query_embedding = embedder.embed_query(query)
        chunks = _retrieve_chunks( ### ###
            settings=settings, ### ###
            logger=logger, ### ###
            query_embedding=query_embedding, ### ###
            company_id=company_id, ### ###
            machine_id=machine_id, ### ###
            machine_cat=machine_cat, ### ###
            class_name=class_name, ### ###
            top_k=settings.fusion_query_top_k, ### ###
        ) ### ###
        per_query_chunks.append(chunks)

    fused_chunks = _rrf_fuse(results=per_query_chunks, rrf_k=settings.fusion_rrf_k)
    fused_chunks = fused_chunks[: settings.fusion_final_top_k]

    context = _build_context(fused_chunks, settings.rag_max_context_chars)
    history_text = _format_history(chat_history, settings.rag_history_turns)
    answer = _generate_answer(
        settings=settings,
        query=user_input,
        context=context,
        history_text=history_text,
    )

    return {
        "answer": answer,
        "sources": fused_chunks,
        "meta": {
            "fusionQueries": queries,
            "fusionQueryCount": len(queries),
            "fusionFinalTopK": settings.fusion_final_top_k,
        },
    }
