"""Chat router for standard RAG."""

from __future__ import annotations

from typing import Optional
import uuid

from fastapi import APIRouter, Request, Response
from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings

from ...api.schemas.chat import ChatRequest, ChatResponse, SourceDocument, ExternalSource
from ...config.settings import load_settings
from ...services.chat_execution_service import execute_chat

router = APIRouter(tags=["chat"])


def _get_chat_store(request: Request) -> dict[str, list[dict[str, str]]]:
    store = getattr(request.app.state, "chat_store", None)
    if store is None:
        store = {}
        request.app.state.chat_store = store
    return store


def ensure_chat_id(chat_id: Optional[str]) -> str:
    return chat_id or str(uuid.uuid4())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, response: Response, payload: ChatRequest) -> ChatResponse:
    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())

    chat_id = ensure_chat_id(payload.chat_id)
    response.headers["X-Chat-ID"] = chat_id

    store = _get_chat_store(request)
    history = store.get(chat_id, [])

    logger.info(
        "chat request|chat_id=%s|class_name=%s|company_id=%s|machine_id=%s|machine_cat=%s|rag_type=%s|dashboard_id=%s|model_id=%s",
        chat_id,
        payload.service.class_name or settings.weaviate_default_class,
        payload.service.company_id,
        payload.service.machine_id,
        payload.service.machine_cat,
        payload.service.rag_type,
        payload.service.dashboard_id,
        payload.service.model_id,
    )

    execution = execute_chat(
        settings=settings,
        logger=logger,
        user_input=payload.user_input,
        rag_type=payload.service.rag_type,
        class_name=payload.service.class_name,
        company_id=payload.service.company_id,
        machine_id=payload.service.machine_id,
        machine_cat=payload.service.machine_cat,
        dashboard_id=payload.service.dashboard_id,
        model_id=payload.service.model_id,
        chat_history=history,
    )

    history = history + [
        {"role": "user", "content": payload.user_input},
        {"role": "assistant", "content": execution.answer_text},
    ]
    store[chat_id] = history

    sources = [
        SourceDocument(
            content=chunk.content,
            source=chunk.source,
            page_number=chunk.page_number,
            className=execution.class_name,
            company_id=chunk.company_id,
            machine_id=chunk.machine_id,
            file_upload_id=chunk.file_upload_id,
            machine_cat=chunk.machine_cat,
            distance=chunk.distance,
        )
        for chunk in execution.source_chunks
    ]

    meta = {
        "chatId": chat_id,
        "className": execution.class_name,
        "companyId": execution.company_id,
        "machineId": execution.machine_id,
        "machineCat": execution.machine_cat,
        "ragType": execution.rag_type,
        "dashboardId": execution.dashboard_id,
        "modelId": execution.model_id,
    }
    meta.update(execution.extra_meta)

    external_sources = [
        ExternalSource(**item)
        for item in execution.extra_external_sources
    ]
    return ChatResponse(
        message=execution.answer_text,
        intent=f"{execution.rag_type}_rag",
        sources=sources,
        externalSources=external_sources,
        meta=meta,
    )
