"""Shared RAG helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ..config.settings import Settings


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided context to answer the question. "
    "If the context does not contain the answer, say you don't know. "
    "Keep the answer concise and factual."
)


@dataclass
class RetrievedChunk:
    content: str
    source: str
    page_number: int
    machine_id: str
    file_upload_id: str
    machine_cat: str
    distance: Optional[float] = None


def _format_history(history: Iterable[dict[str, str]], max_turns: int) -> str:
    if not history:
        return ""
    trimmed = list(history)[-max_turns * 2 :]
    lines = [f"{item['role'].capitalize()}: {item['content']}" for item in trimmed]
    return "\n".join(lines)


def _build_context(chunks: list[RetrievedChunk], max_chars: int) -> str:
    if not chunks:
        return ""
    sections: list[str] = []
    total = 0
    for chunk in chunks:
        header = f"Source: {chunk.source} | page {chunk.page_number}"
        body = chunk.content.strip()
        block = f"{header}\n{body}"
        remaining = max_chars - total
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining]
        sections.append(block)
        total += len(block)
        if total >= max_chars:
            break
    return "\n\n---\n\n".join(sections)


def _build_graphql_query(
    class_name: str,
    vector: list[float],
    limit: int,
    machine_id: Optional[int],
    machine_cat: Optional[str],
) -> str:
    vector_json = json.dumps(vector)
    where_clause = ""
    clauses = []
    if machine_id is not None:
        clauses.append(
            "{"
            "path: [\"machine_id\"], "
            "operator: Equal, "
            f"valueText: \"{machine_id}\""
            "}"
        )
    if machine_cat:
        clauses.append(
            "{"
            "path: [\"machine_cat\"], "
            "operator: Equal, "
            f"valueText: \"{machine_cat}\""
            "}"
        )
    if len(clauses) == 1:
        where_clause = f"where: {clauses[0]},"
    elif len(clauses) > 1:
        joined = ", ".join(clauses)
        where_clause = f"where: {{operator: And, operands: [{joined}]}},"
    return (
        "{\n"
        "  Get {\n"
        f"    {class_name}(\n"
        f"      nearVector: {{vector: {vector_json}}},\n"
        f"      limit: {limit},\n"
        f"      {where_clause}\n"
        "    ) {\n"
        "      content\n"
        "      source\n"
        "      page_number\n"
        "      machine_id\n"
        "      file_upload_id\n"
        "      machine_cat\n"
        "      _additional { distance }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


@traceable(name="rag_retrieval", run_type="tool")
def _retrieve_chunks(
    *,
    settings: Settings,
    logger: Any,
    query_embedding: list[float],
    company_id: int,
    machine_id: Optional[int],
    machine_cat: Optional[str],
    top_k: Optional[int] = None,
) -> list[RetrievedChunk]:
    class_name = f"{settings.weaviate_class_prefix}{company_id}"
    limit = settings.weaviate_retrieval_top_k if top_k is None else top_k
    query = _build_graphql_query(
        class_name=class_name,
        vector=query_embedding,
        limit=limit,
        machine_id=machine_id,
        machine_cat=machine_cat,
    )
    base_url = settings.weaviate_url.rstrip("/")
    resp = requests.post(
        f"{base_url}/v1/graphql",
        json={"query": query},
        timeout=settings.weaviate_request_timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise ValueError(f"weaviate graphql errors: {payload['errors']}")

    results = payload.get("data", {}).get("Get", {}).get(class_name, [])
    chunks: list[RetrievedChunk] = []
    for item in results:
        additional = item.get("_additional", {}) if isinstance(item, dict) else {}
        distance = additional.get("distance")
        if settings.rag_min_score_distance >= 0 and distance is not None:
            if distance > settings.rag_min_score_distance:
                continue
        chunks.append(
            RetrievedChunk(
                content=str(item.get("content", "")),
                source=str(item.get("source", "")),
                page_number=int(item.get("page_number", 0) or 0),
                machine_id=str(item.get("machine_id", "")),
                file_upload_id=str(item.get("file_upload_id", "")),
                machine_cat=str(item.get("machine_cat", "")),
                distance=distance,
            )
        )
    logger.info(
        f"retrieval done|class_name={class_name}|query_len={len(query_embedding)}|hits={len(chunks)}"
    )
    return chunks


@traceable(name="rag_generate", run_type="llm")
def _generate_answer(
    *,
    settings: Settings,
    query: str,
    context: str,
    history_text: str,
) -> str:
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.chat_model_temperature,
        max_tokens=settings.chat_model_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )

    system_prompt = settings.rag_system_prompt.strip() or DEFAULT_SYSTEM_PROMPT
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Question: {question}\n\nContext:\n{context}\n\nChat history:\n{history}",
            ),
        ]
    )
    messages = prompt.format_messages(question=query, context=context, history=history_text)
    response = llm.invoke(messages)
    return getattr(response, "content", "").strip()
