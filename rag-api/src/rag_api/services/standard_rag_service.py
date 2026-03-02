"""Standard RAG pipeline service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from langchain_openai import OpenAIEmbeddings
from langsmith import traceable
from langgraph.graph import END, StateGraph

from ..config.settings import Settings
from .rag_service_utils import (
    RetrievedChunk,
    _build_context,
    _format_history,
    _generate_answer,
    _retrieve_chunks,
)


class StandardRagState(TypedDict):
    user_input: str
    class_name: Optional[str]
    company_id: Optional[int]
    machine_cat: Optional[int]
    machine_id: Optional[int]
    chat_history: list[dict[str, str]]
    query_embedding: list[float]
    chunks: list[RetrievedChunk]
    answer: str
    system_prompt_override: str


@dataclass
class StandardResult:
    answer: str
    sources: list[RetrievedChunk]


def _build_graph(settings: Settings, logger: Any, embedder: OpenAIEmbeddings):
    graph = StateGraph(StandardRagState)

    def embed_node(state: StandardRagState) -> StandardRagState:
        query_embedding = embedder.embed_query(state["user_input"])
        return {**state, "query_embedding": query_embedding}

    def retrieve_node(state: StandardRagState) -> StandardRagState:
        chunks = _retrieve_chunks(
            settings=settings,
            logger=logger,
            query_embedding=state["query_embedding"],
            class_name=state["class_name"],
            company_id=state["company_id"],
            machine_cat=state["machine_cat"],
            machine_id=state["machine_id"],
        )
        return {**state, "chunks": chunks}

    def generate_node(state: StandardRagState) -> StandardRagState:
        context = _build_context(state["chunks"], settings.rag_max_context_chars)
        history_text = _format_history(state["chat_history"], settings.rag_history_turns)
        answer = _generate_answer(
            settings=settings,
            query=state["user_input"],
            context=context,
            history_text=history_text,
            system_prompt_override=state["system_prompt_override"],
        )
        return {**state, "answer": answer}

    graph.add_node("embed", embed_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.set_entry_point("embed")
    graph.add_edge("embed", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _load_standard_system_prompt(settings: Settings, logger: Any) -> str:
    prompt_path = settings.resolved_standard_rag_system_prompt_path()
    if prompt_path is None:
        return ""
    if not prompt_path.exists() or not prompt_path.is_file():
        logger.info("standard_rag system_prompt_path missing|path=%s", prompt_path)
        return ""
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    logger.info("standard_rag system_prompt loaded|path=%s|chars=%s", prompt_path, len(prompt_text))
    return prompt_text


@traceable(name="run_standard_rag", run_type="chain")
def run_standard_rag(
    *,
    settings: Settings,
    logger: Any,
    user_input: str,
    class_name: Optional[str],
    company_id: Optional[int],
    machine_cat: Optional[int],
    machine_id: Optional[int],
    chat_history: list[dict[str, str]],
) -> StandardResult:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for rag-api")

    embedder = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        timeout=settings.embedding_request_timeout,
    )
    graph = _build_graph(settings, logger, embedder)
    system_prompt_override = _load_standard_system_prompt(settings, logger)
    state: StandardRagState = {
        "user_input": user_input,
        "class_name": class_name,
        "company_id": company_id,
        "machine_id": machine_id,
        "machine_cat": machine_cat,
        "chat_history": chat_history,
        "query_embedding": [],
        "chunks": [],
        "answer": "",
        "system_prompt_override": system_prompt_override,
    }
    result_state = graph.invoke(state)
    result = StandardResult(
        answer=result_state["answer"],
        sources=result_state["chunks"],
    )

    return result
