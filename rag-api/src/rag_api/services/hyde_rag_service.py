"""HyDE RAG pipeline service (hypothetical document embedding)."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langsmith import traceable

from ..config.settings import Settings
from .rag_service_utils import _build_context, _format_history, _generate_answer, _retrieve_chunks


def _generate_hypothesis(*, settings: Settings, user_input: str, chat_history: list[dict[str, str]]) -> str:
    history_text = _format_history(chat_history, settings.rag_history_turns)
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        temperature=settings.hyde_hypothesis_temperature,
        max_tokens=settings.hyde_hypothesis_max_tokens,
        timeout=settings.chat_model_request_timeout,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Write a concise hypothetical answer to the user's question. "
                "Do not cite sources. Keep it factual and neutral.",
            ),
            (
                "human",
                "Chat history:\n{history}\n\nUser question:\n{question}\n\nHypothetical answer:",
            ),
        ]
    )
    messages = prompt.format_messages(history=history_text, question=user_input)
    response = llm.invoke(messages)
    return getattr(response, "content", "").strip()


@traceable(name="run_hyde_rag", run_type="chain")
def run_hyde_rag(
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

    hypothesis = _generate_hypothesis(
        settings=settings,
        user_input=user_input,
        chat_history=chat_history,
    )
    query_text = hypothesis or user_input
    query_embedding = embedder.embed_query(query_text)

    chunks = _retrieve_chunks( ### ###
        settings=settings, ### ###
        logger=logger, ### ###
        query_embedding=query_embedding, ### ###
        company_id=company_id, ### ###
        machine_id=machine_id, ### ###
        machine_cat=machine_cat, ### ###
        class_name=class_name, ### ###
        top_k=settings.hyde_retrieval_top_k, ### ###
    ) ### ###

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
        "meta": {
            "hydeHypothesis": hypothesis,
            "hydeRetrievalTopK": settings.hyde_retrieval_top_k,
        },
    }
