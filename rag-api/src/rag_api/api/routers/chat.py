"""Chat router for standard RAG."""

from __future__ import annotations

from typing import Optional
import uuid

from fastapi import APIRouter, Request, Response, HTTPException
from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings

from ...api.schemas.chat import ChatRequest, ChatResponse, SourceDocument, ExternalSource ### ###
from ...config.settings import load_settings
from ...services.standard_rag_service import run_standard_rag
from ...services.conversational_rag_service import run_conversational_rag
from ...services.corrective_rag_service import run_corrective_rag
from ...services.self_rag_service import run_self_rag
from ...services.fusion_rag_service import run_fusion_rag
from ...services.hyde_rag_service import run_hyde_rag
from ...services.graph_rag_service import run_graph_rag
from ...services.adaptive_rag_service import run_adaptive_rag
from ...services.agentic_rag_service import run_agentic_rag

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

    rag_type = payload.service.rag_type
    handlers = {
        "standard": run_standard_rag,
        "conversational": run_conversational_rag,
        "corrective": run_corrective_rag,
        "self_rag": run_self_rag,
        "fusion": run_fusion_rag,
        "hyde": run_hyde_rag,
        "graph": run_graph_rag,
        "adaptive": run_adaptive_rag,
        "agentic": run_agentic_rag,
    }
    if rag_type not in handlers:
        raise HTTPException(status_code=400, detail=f"Unsupported rag_type: {rag_type}")

    class_name = payload.service.class_name or settings.weaviate_machine_class_name ### ###
    is_general_class = class_name == settings.weaviate_general_class_name ### ###
    company_id = None if is_general_class else payload.service.company_id ### ###
    machine_id = None if is_general_class else payload.service.machine_id ### ###
    machine_cat = None if is_general_class else payload.service.machine_cat ### ###
    chat_id = ensure_chat_id(payload.chat_id)
    response.headers["X-Chat-ID"] = chat_id

    store = _get_chat_store(request)
    history = store.get(chat_id, [])

    logger.info(
        "chat request|chat_id=%s|class_name=%s|company_id=%s|machine_id=%s|machine_cat=%s|rag_type=%s|dashboard_id=%s|model_id=%s", ### ###
        chat_id,
        class_name, ### ###
        company_id,
        machine_id, ### ###
        machine_cat, ### ###
        payload.service.rag_type,
        payload.service.dashboard_id,
        payload.service.model_id,
    )

    # Function Dispatch, Function Dispatch Table, Dictionary based function routing
    handler = handlers[rag_type] ### ###
    result = handler( ### ###
        settings=settings, ### ###
        logger=logger, ### ###
        user_input=payload.user_input, ### ###
        company_id=company_id, ### ###
        machine_id=machine_id, ### ###
        machine_cat=machine_cat, ### ###
        class_name=class_name, ### ###
        chat_history=history, ### ###
    ) ### ###

    history = history + [
        {"role": "user", "content": payload.user_input},
        {"role": "assistant", "content": result["answer"]},
    ]
    store[chat_id] = history

    sources = [
        SourceDocument(
            content=chunk.content, ### ###
            source=chunk.source, ### ###
            page_number=chunk.page_number, ### ###
            company_id=chunk.company_id, ### ###
            machine_id=chunk.machine_id, ### ###
            file_upload_id=chunk.file_upload_id, ### ###
            machine_cat=chunk.machine_cat, ### ###
            distance=chunk.distance, ### ###
        )
        for chunk in result["sources"]
    ]

    meta = { ### ###
        "chatId": chat_id, ### ###
        "className": class_name, ### ###
        "companyId": company_id, ### ###
        "machineId": machine_id, ### ###
        "machineCat": machine_cat, ### ###
        "ragType": payload.service.rag_type, ### ###
        "dashboardId": payload.service.dashboard_id, ### ###
        "modelId": payload.service.model_id, ### ###
    } ### ###
    if isinstance(result, dict) and result.get("meta"):
        meta.update(result["meta"])

    external_sources = [ ### ###
        ExternalSource(**item) ### ###
        for item in result.get("external_sources", []) ### ###
        if isinstance(item, dict) ### ###
    ] ### ###
    return ChatResponse(
        message=result["answer"],
        intent=f"{rag_type}_rag",
        sources=sources,
        external_sources=external_sources, ### ###
        meta=meta,
    )
