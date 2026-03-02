"""Graph RAG pipeline service (LLM-extracted graph over retrieved chunks)."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import RetrievedChunk, _build_context, _format_history, _generate_answer, _retrieve_chunks


def _normalize_triples(triples_text: str) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for line in triples_text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            continue
        head, rel, tail = parts
        if not head or not rel or not tail:
            continue
        rel_norm = rel.upper()
        triple = f"{head} | {rel_norm} | {tail}"
        key = triple.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(triple)
    return normalized


def _extract_graph(*, settings: Settings, user_input: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    raw_text = "\n\n".join(chunk.content.strip() for chunk in chunks if chunk.content)
    snippet = raw_text[: settings.graph_extract_max_chars]
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=0.0,
        max_tokens=settings.graph_extract_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract key entities and relations as triples in the form: ENTITY_A | RELATION | ENTITY_B. "
                "Return one triple per line. If none, return empty.",
            ),
            (
                "human",
                "Question:\n{question}\n\nText:\n{text}\n\nTriples:",
            ),
        ]
    )
    messages = prompt.format_messages(question=user_input, text=snippet)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip()
    triples = [line.strip() for line in text.splitlines() if "|" in line]
    normalized = _normalize_triples("\n".join(triples))
    return "\n".join(normalized[: settings.graph_max_triples])


@traceable(name="run_graph_rag", run_type="chain")
def run_graph_rag(
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
    query_embedding = embedder.embed_query(user_input)

    chunks = _retrieve_chunks( ### ###
        settings=settings, ### ###
        logger=logger, ### ###
        query_embedding=query_embedding, ### ###
        company_id=company_id, ### ###
        machine_id=machine_id, ### ###
        machine_cat=machine_cat, ### ###
        class_name=class_name, ### ###
        top_k=settings.graph_retrieval_top_k, ### ###
    ) ### ###

    graph_text = _extract_graph(
        settings=settings,
        user_input=user_input,
        chunks=chunks,
    )

    if settings.graph_use_second_retrieval and graph_text:
        graph_query = " ".join(
            part.strip()
            for line in graph_text.splitlines()
            for part in line.split("|")
            if part.strip()
        )
        graph_embedding = embedder.embed_query(graph_query)
        extra_chunks = _retrieve_chunks( ### ###
            settings=settings, ### ###
            logger=logger, ### ###
            query_embedding=graph_embedding, ### ###
            company_id=company_id, ### ###
            machine_id=machine_id, ### ###
            machine_cat=machine_cat, ### ###
            class_name=class_name, ### ###
            top_k=settings.graph_second_retrieval_top_k, ### ###
        ) ### ###
        chunks = chunks + [
            chunk for chunk in extra_chunks if chunk not in chunks
        ]

    context = _build_context(chunks, settings.rag_max_context_chars)
    if graph_text:
        context = f"Graph:\n{graph_text}\n\nContext:\n{context}"

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
        "meta": {
            "graphTriples": len([line for line in graph_text.splitlines() if line.strip()]),
            "graphRetrievalTopK": settings.graph_retrieval_top_k,
            "graphSecondRetrieval": settings.graph_use_second_retrieval,
        },
    }
