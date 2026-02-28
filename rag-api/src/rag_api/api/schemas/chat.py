"""Schema definitions for the chat endpoint."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - fallback for older pydantic
    ConfigDict = None  # type: ignore


class ServicePayload(BaseModel): ### 
    rag_type: str = Field(default="standard", alias="ragType") ### 
    company_id: Optional[int] = Field(default=None, alias="companyId") ### 
    machine_cat: Optional[str] = Field(default=None, alias="machineCat") ### 
    machine_id: Optional[int] = Field(default=None, alias="machineId") ### 
    dashboard_id: Optional[int] = Field(default=None, alias="dashboardId") ### 
    model_id: Optional[int] = Field(default=None, alias="modelId") ### 

    if ConfigDict is not None: ### 
        model_config = ConfigDict(populate_by_name=True, extra="allow") ### 


class SourceDocument(BaseModel):
    content: str
    source: str
    page_number: int
    machine_id: str
    file_upload_id: str
    machine_cat: str
    distance: Optional[float] = None


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
    meta: dict[str, Any] = Field(default_factory=dict)
