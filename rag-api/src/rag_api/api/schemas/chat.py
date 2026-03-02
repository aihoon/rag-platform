"""Schema definitions for the chat endpoint."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for older pydantic
    ConfigDict = None  # type: ignore


class ServicePayload(BaseModel):
    rag_type: str = Field(default="standard", alias="ragType")
    class_name: Optional[str] = Field(default=None, alias="className")
    company_id: Optional[int] = Field(default=0, alias="companyId")
    machine_cat: Optional[int] = Field(default=0, alias="machineCat")
    machine_id: Optional[int] = Field(default=0, alias="machineId")
    dashboard_id: Optional[int] = Field(default=None, alias="dashboardId")
    model_id: Optional[int] = Field(default=None, alias="modelId")

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")


class SourceDocument(BaseModel):
    content: str
    source: str
    page_number: int
    class_name: str = Field(default="General", alias="className")
    company_id: int
    machine_cat: int
    machine_id: int
    file_upload_id: str
    distance: Optional[float] = None

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExternalSource(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
### 

class ChatRequest(BaseModel):
    user_input: str = Field(..., alias="userInput")
    chat_id: Optional[str] = Field(default=None, alias="chatId")
    user_id: Optional[str] = Field(default=None, alias="userId")
    service: ServicePayload

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChatResponse(BaseModel):
    message: str
    intent: str = "standard_rag"
    streaming: bool = False
    sources: list[SourceDocument] = Field(default_factory=list)
    external_sources: list[ExternalSource] = Field(default_factory=list, alias="externalSources")
    meta: dict[str, Any] = Field(default_factory=dict)

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="allow")
