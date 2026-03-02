"""Self-RAG pipeline service (approximation based on Self-RAG)."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import _build_context, _format_history, _generate_answer, _retrieve_chunks


def _should_retrieve(*, settings: Settings, user_input: str, chat_history: list[dict[str, str]]) -> bool:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.selfrag_router_temperature,
        max_tokens=settings.selfrag_router_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Decide if retrieval is required. Reply with only 'yes' or 'no'. "
                "Use 'yes' if the question needs specific facts, citations, or "
                "document-grounded answers. Use 'no' if it is general knowledge "
                "or can be answered without documents.",
            ),
            (
                "human",
                "Chat history:\n{history}\n\nUser question:\n{question}\n\nRetrieve? (yes/no)",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip().lower()
    return text.startswith("y")


def _rewrite_query(*, settings: Settings, user_input: str, chat_history: list[dict[str, str]]) -> str:
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
                "Rewrite the question into a concise search query. Keep key entities "
                "and add missing keywords if helpful.",
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


def _grade_support(*, settings: Settings, question: str, answer: str, context: str) -> bool:
    snippet = context[: settings.selfrag_grader_max_chars]
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
                "Check whether the answer is fully supported by the context. Reply with only 'yes' or 'no'. "
                "If any claim is not supported, reply 'no'.",
            ),
            (
                "human",
                "Question:\n{question}\n\nAnswer:\n{answer}\n\nContext:\n{context}\n\nSupported? (yes/no)",
            ),
        ]
    )
    messages = prompt.format_messages(question=question, answer=answer, context=snippet)
    response = llm.invoke(messages)
    text = getattr(response, "content", "").strip().lower()
    return text.startswith("y")


@traceable(name="run_self_rag", run_type="chain")
def run_self_rag(
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

    query = user_input
    attempts = 0
    used_retrieval = False
    chunks = []
    answer = ""
    supported = False

    should_retrieve = _should_retrieve(
        settings=settings,
        user_input=user_input,
        chat_history=chat_history,
    )
    logger.info(
        "self_rag|should_retrieve=%s",
        should_retrieve,
    )

    while True:
        if should_retrieve or attempts > 0:
            used_retrieval = True
            query_embedding = embedder.embed_query(query)
            chunks = _retrieve_chunks( ### ###
                settings=settings, ### ###
                logger=logger, ### ###
                query_embedding=query_embedding, ### ###
                company_id=company_id, ### ###
                machine_id=machine_id, ### ###
                machine_cat=machine_cat, ### ###
                class_name=class_name, ### ###
                top_k=settings.selfrag_retrieval_top_k, ### ###
            ) ### ###
        context = _build_context(chunks, settings.rag_max_context_chars)
        history_text = _format_history(chat_history, settings.rag_history_turns)
        answer = _generate_answer(
            settings=settings,
            query=user_input,
            context=context,
            history_text=history_text,
        )
        supported = _grade_support(
            settings=settings,
            question=user_input,
            answer=answer,
            context=context,
        )
        if supported or attempts >= settings.selfrag_max_retries:
            break
        attempts += 1
        query = _rewrite_query(
            settings=settings,
            user_input=user_input,
            chat_history=chat_history,
        ) or query
        should_retrieve = True

    logger.info(
        "self_rag|used_retrieval=%s|attempts=%s|supported=%s|chunks=%s",
        used_retrieval,
        attempts,
        supported,
        len(chunks),
    )
    return {
        "answer": answer,
        "sources": chunks,
        "meta": {
            "selfragUsedRetrieval": used_retrieval,
            "selfragAttempts": attempts,
            "selfragSupported": supported,
        },
    }
