"""Schemas for OpenAI-compatible chat endpoints used by LibreChat."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for older pydantic
    ConfigDict = None  # type: ignore


class ContentPart(BaseModel):
    type: str = "text"
    text: Optional[str] = None

    if ConfigDict is not None:
        model_config = ConfigDict(extra="allow")


class OpenAICompatMessage(BaseModel):
    role: str
    content: str | list[ContentPart] | None = None

    if ConfigDict is not None:
        model_config = ConfigDict(extra="allow")


class OpenAICompatChatRequest(BaseModel):
    model: str = "rag-conversational"
    messages: list[OpenAICompatMessage]
    stream: bool = False
    user: Optional[str] = None
    rag_type: Optional[str] = Field(default=None, alias="ragType")
    class_name: Optional[str] = Field(default=None, alias="className")
    company_id: Optional[int] = Field(default=0, alias="companyId")
    machine_cat: Optional[int] = Field(default=0, alias="machineCat")
    machine_id: Optional[int] = Field(default=0, alias="machineId")
    dashboard_id: Optional[int] = Field(default=None, alias="dashboardId")
    model_id: Optional[int] = Field(default=None, alias="modelId")

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")


class OpenAICompatModel(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "rag-api"


class OpenAICompatModelList(BaseModel):
    object: str = "list"
    data: list[OpenAICompatModel]


class OpenAICompatAssistantMessage(BaseModel):
    role: str = "assistant"
    content: str


class OpenAICompatChoice(BaseModel):
    index: int = 0
    message: OpenAICompatAssistantMessage
    finish_reason: str = "stop"


class OpenAICompatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAICompatChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[OpenAICompatChoice]
    usage: OpenAICompatUsage = Field(default_factory=OpenAICompatUsage)

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")
