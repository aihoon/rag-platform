"""Conversational RAG pipeline service (LangGraph-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from langsmith import traceable
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ..config.settings import Settings
from .rag_service_utils import (
    RetrievedChunk,
    _build_context,
    _format_history,
    _generate_answer,
    _retrieve_chunks,
)

from langgraph.graph import StateGraph, END


class ConversationalState(TypedDict):
    user_input: str
    standalone_question: str
    company_id: Optional[int] ### ###
    machine_id: Optional[int] ### ###
    machine_cat: Optional[int] ### ###
    class_name: Optional[str] ### ###
    chat_history: list[dict[str, str]]
    chunks: list[RetrievedChunk]
    answer: str

def _rewrite_question(
    *,
    settings: Settings,
    user_input: str,
    chat_history: list[dict[str, str]],
) -> str:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.chat_model_temperature,
        max_tokens=settings.chat_model_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Rewrite the user's question into a standalone question using the chat history.",
            ),
            (
                "human",
                "Chat history:\\n{history}\\n\\nUser question:\\n{question}\\n\\nStandalone question:",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input)
    response = llm.invoke(messages)
    return getattr(response, "content", "").strip()


def _build_graph(settings: Settings, logger: Any, embedder: Any):
    graph = StateGraph(ConversationalState)

    def rewrite_node(state: ConversationalState) -> ConversationalState:
        standalone_question = _rewrite_question(
            settings=settings,
            user_input=state["user_input"],
            chat_history=state["chat_history"],
        )
        return {**state, "standalone_question": standalone_question}

    def retrieve_node(state: ConversationalState) -> ConversationalState:
        query_embedding = embedder.embed_query(state["standalone_question"])
            chunks = _retrieve_chunks( ### ###
                settings=settings, ### ###
                logger=logger, ### ###
                query_embedding=query_embedding, ### ###
                company_id=state["company_id"], ### ###
                machine_id=state["machine_id"], ### ###
                machine_cat=state["machine_cat"], ### ###
                class_name=state.get("class_name"), ### ###
            ) ### ###
        return {**state, "chunks": chunks}

    def generate_node(state: ConversationalState) -> ConversationalState:
        context = _build_context(state["chunks"], settings.rag_max_context_chars)
        history_text = _format_history(state["chat_history"], settings.rag_history_turns)
        answer = _generate_answer(
            settings=settings,
            query=state["standalone_question"],
            context=context,
            history_text=history_text,
        )
        return {**state, "answer": answer}

    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


@dataclass
class ConversationalResult:
    answer: str
    sources: list[RetrievedChunk]


@traceable(name="run_conversational_rag", run_type="chain")
def run_conversational_rag(
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

    from langchain_openai import OpenAIEmbeddings

    embedder = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        timeout=settings.embedding_request_timeout,
    )
    standalone_question = _rewrite_question(
        settings=settings,
        user_input=user_input,
        chat_history=chat_history,
    )
    # query_embedding = embedder.embed_query(standalone_question)

    graph = _build_graph(settings, logger, embedder)
    state: ConversationalState = { ### ###
        "user_input": user_input, ### ###
        "standalone_question": standalone_question, ### ###
        "company_id": company_id, ### ###
        "class_name": class_name, ### ###
        "machine_id": machine_id, ### ###
        "machine_cat": machine_cat, ### ###
        "chat_history": chat_history, ### ###
        "chunks": [], ### ###
        "answer": "", ### ###
        #"query_embedding": query_embedding, ### ###
    } ### ###
    result_state = graph.invoke(state)
    return {
        "answer": result_state["answer"],
        "sources": result_state["chunks"],
    }
