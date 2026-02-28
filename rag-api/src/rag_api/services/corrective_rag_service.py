"""Corrective RAG pipeline service (LangGraph-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

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
    company_id: int
    machine_id: Optional[int]
    machine_cat: Optional[str]
    chat_history: list[dict[str, str]]
    chunks: list[RetrievedChunk]
    relevant_chunks: list[RetrievedChunk]
    relevance_ratio: float
    relevant_count: int
    retry_count: int
    used_fallback: bool
    answer: str


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


def _build_graph(settings: Settings, logger: Any, embedder: Any):
    graph = StateGraph(CorrectiveState)

    def retrieve_node(state: CorrectiveState) -> CorrectiveState:
        top_k = (
            settings.weaviate_retrieval_top_k
            if state["retry_count"] == 0
            else settings.crag_fallback_top_k
        )
        query_embedding = embedder.embed_query(state["query"])
        chunks = _retrieve_chunks(
            settings=settings,
            logger=logger,
            query_embedding=query_embedding,
            company_id=state["company_id"],
            machine_id=state["machine_id"],
            machine_cat=state["machine_cat"],
            top_k=top_k,
        )
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
        context = _build_context(chosen, settings.rag_max_context_chars)
        history_text = _format_history(state["chat_history"], settings.rag_history_turns)
        answer = _generate_answer(
            settings=settings,
            query=state["user_input"],
            context=context,
            history_text=history_text,
        )
        return {**state, "answer": answer}

    def route_after_grade(state: CorrectiveState) -> str:
        enough_docs = state["relevant_count"] >= settings.crag_min_relevant_docs
        enough_ratio = state["relevance_ratio"] >= settings.crag_min_relevance_ratio
        if enough_docs and enough_ratio:
            return "generate"
        if state["retry_count"] < settings.crag_max_retries:
            return "rewrite"
        return "generate"

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "rewrite": "rewrite",
            "generate": "generate",
        },
    )
    graph.add_edge("rewrite", "retrieve")
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

    graph = _build_graph(settings, logger, embedder)
    state: CorrectiveState = {
        "user_input": user_input,
        "query": user_input,
        "company_id": company_id,
        "machine_id": machine_id,
        "machine_cat": machine_cat,
        "chat_history": chat_history,
        "chunks": [],
        "relevant_chunks": [],
        "relevance_ratio": 0.0,
        "relevant_count": 0,
        "retry_count": 0,
        "used_fallback": False,
        "answer": "",
    }
    result_state = graph.invoke(state)
    sources = result_state["relevant_chunks"] or result_state["chunks"]
    return {
        "answer": result_state["answer"],
        "sources": sources,
        "meta": {
            "usedFallback": result_state["used_fallback"],
            "retryCount": result_state["retry_count"],
            "relevantDocs": result_state["relevant_count"],
            "relevanceRatio": round(result_state["relevance_ratio"], 3),
        },
    }
