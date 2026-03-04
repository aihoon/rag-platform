"""OpenAI-compatible adapter endpoints for LibreChat custom endpoint integration."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from shared.observability.logger import PrintLogger
from shared.utils.request import resolve_logger, resolve_settings

from ...config.settings import load_settings
from ...services.chat_execution_service import execute_chat, get_rag_handlers
from ..schemas.openai_compat import (
    ContentPart,
    OpenAICompatChatRequest,
    OpenAICompatChatResponse,
    OpenAICompatChoice,
    OpenAICompatMessage,
    OpenAICompatModel,
    OpenAICompatModelList,
)

router = APIRouter(tags=["openai-compat"])


def _message_to_text(message: OpenAICompatMessage) -> str:
    content = message.content
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    text_parts: list[str] = []
    for item in content:
        if isinstance(item, ContentPart) and item.type == "text" and item.text:
            text_parts.append(item.text)
    return "\n".join(part.strip() for part in text_parts if part.strip()).strip()


def _derive_rag_type(model_name: str, explicit_rag_type: Optional[str]) -> str:
    if explicit_rag_type:
        return explicit_rag_type
    if model_name.startswith("rag-"):
        candidate = model_name.removeprefix("rag-")
        if candidate in get_rag_handlers():
            return candidate
    return "conversational"


def _build_chat_history(messages: list[OpenAICompatMessage]) -> tuple[str, list[dict[str, str]]]:
    rendered: list[dict[str, str]] = []
    last_user_input = ""
    for message in messages:
        if message.role not in {"system", "user", "assistant"}:
            continue
        text = _message_to_text(message)
        if not text:
            continue
        rendered.append({"role": message.role, "content": text})
        if message.role == "user":
            last_user_input = text

    if not last_user_input:
        raise HTTPException(status_code=400, detail="At least one user message is required.")

    if rendered and rendered[-1]["role"] == "user":
        rendered = rendered[:-1]

    return last_user_input, rendered


@router.get("/v1/models", response_model=OpenAICompatModelList)
async def list_models() -> OpenAICompatModelList:
    created = int(time.time())
    models = [
        OpenAICompatModel(id=f"rag-{rag_type}", created=created)
        for rag_type in get_rag_handlers()
    ]
    return OpenAICompatModelList(data=models)


@router.post("/v1/chat/completions", response_model=OpenAICompatChatResponse)
async def chat_completions(
    request: Request,
    payload: OpenAICompatChatRequest,
) -> OpenAICompatChatResponse:
    if payload.stream:
        raise HTTPException(
            status_code=400,
            detail="Streaming is not supported by rag-api OpenAI compatibility mode yet. "
                   "Set stream=false in LibreChat custom endpoint config.",
        )

    settings = resolve_settings(request, load_settings)
    logger = resolve_logger(request, PrintLogger())
    user_input, chat_history = _build_chat_history(payload.messages)
    rag_type = _derive_rag_type(payload.model, payload.rag_type)

    logger.info(
        "openai compat request|model=%s|rag_type=%s|"
        "class_name=%s|company_id=%s|machine_id=%s|machine_cat=%s|messages=%s",
        payload.model,
        rag_type,
        payload.class_name or settings.weaviate_default_class,
        payload.company_id,
        payload.machine_id,
        payload.machine_cat,
        len(payload.messages),
    )

    execution = execute_chat(
        settings=settings,
        logger=logger,
        user_input=user_input,
        rag_type=rag_type,
        class_name=payload.class_name,
        company_id=payload.company_id,
        machine_id=payload.machine_id,
        machine_cat=payload.machine_cat,
        dashboard_id=payload.dashboard_id,
        model_id=payload.model_id,
        chat_history=chat_history,
    )

    return OpenAICompatChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=payload.model,
        choices=[
            OpenAICompatChoice(
                message={"role": "assistant", "content": execution.answer_text},
            )
        ],
    )
