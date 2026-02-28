"""Standard RAG pipeline service."""

from __future__ import annotations

from typing import Any, Optional

from langchain_openai import OpenAIEmbeddings
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import (
    _build_context,
    _format_history,
    _generate_answer,
    _retrieve_chunks,
)


@traceable(name="run_standard_rag", run_type="chain")
def run_standard_rag(
    *,
    settings: Settings,
    logger: Any,
    user_input: str,
    company_id: int,
    machine_id: Optional[int],
    machine_cat: Optional[str],
    chat_history: list[dict[str, str]],
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for rag-api")

    embedder = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        timeout=settings.embedding_request_timeout,
    )
    query_embedding = embedder.embed_query(user_input)

    # noinspection DuplicatedCode
    chunks = _retrieve_chunks(
        settings=settings,
        logger=logger,
        query_embedding=query_embedding,
        company_id=company_id,
        machine_id=machine_id,
        machine_cat=machine_cat,
    )
    context = _build_context(chunks, settings.rag_max_context_chars)
    history_text = _format_history(chat_history, settings.rag_history_turns)

    answer = _generate_answer(
        settings=settings,
        query=user_input,
        context=context,
        history_text=history_text,
    )

    return {
        "answer": answer,
        "sources": chunks,
    }
