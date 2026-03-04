"""
title: RAG API Pipe
authors: MachineGPT
version: 0.1.0
required_open_webui_version: 0.6.0
license: MIT
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional
from urllib import error, request

from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        RAG_API_BASE_URL: str = Field(
            default=os.getenv("RAG_API_BASE_URL", "http://host.docker.internal:8054/v1"),
            description="OpenAI-compatible base URL for rag-api behind the load balancer.",
        )
        RAG_API_KEY: str = Field(
            default=os.getenv("RAG_API_KEY", "dummy-key-not-used"),
            description="Bearer token sent to rag-api. Current adapter ignores it but Open WebUI expects a value.",
        )
        REQUEST_TIMEOUT_SEC: int = Field(
            default=int(os.getenv("RAG_API_REQUEST_TIMEOUT_SEC", "180")),
            description="Timeout for requests to rag-api.",
        )

    class UserValves(BaseModel):
        rag_type: str = Field(
            default="standard",
            description="RAG type to run. Default: standard.",
            json_schema_extra={
                "enum": [
                    "standard",
                    "conversational",
                    "corrective",
                    "self_rag",
                    "fusion",
                    "hyde",
                    "graph",
                    "adaptive",
                    "agentic",
                ]
            },
        )
        class_name: str = Field(
            default="General",
            description="Target class name. Default: General.",
            json_schema_extra={"enum": ["General", "Machine"]},
        )
        company_id: int = Field(default=0, description="Company filter. Default: 0.")
        machine_cat: int = Field(default=0, description="Machine category filter. Default: 0.")
        machine_id: int = Field(default=0, description="Machine filter. Default: 0.")

    def __init__(self):
        self.type = "manifold"
        self.id = "rag-api"
        self.name = "aihoon/"
        self.valves = self.Valves()
        self.user_valves = self.UserValves()

    # noinspection PyMethodMayBeStatic
    def pipes(self):
        return [
            {"id": "chat", "name": "RAG API Chat"},
        ]

    # noinspection PyMethodMayBeStatic
    def _user_valve_value(self, __user__: Optional[dict[str, Any]], key: str, default: Any) -> Any:
        if not __user__:
            return default
        valves = __user__.get("valves")
        if valves is None:
            return default
        if isinstance(valves, dict):
            return valves.get(key, default)
        return getattr(valves, key, default)

    def pipe(
        self,
        model_id: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        body: Optional[dict[str, Any]] = None,
        __user__: Optional[dict[str, Any]] = None,
    ) -> str:
        body = body or {}
        messages = messages or body.get("messages") or []
        rag_type = (str(self._user_valve_value(__user__, "rag_type", "conversational")).
                    strip() or "conversational")
        class_name = (str(self._user_valve_value(__user__, "class_name", "General")).
                      strip() or "General")
        company_id = int(self._user_valve_value(__user__, "company_id", 0))
        machine_cat = int(self._user_valve_value(__user__, "machine_cat", 0))
        machine_id = int(self._user_valve_value(__user__, "machine_id", 0))

        payload = {
            "model": model_id or f"rag-{rag_type}",
            "stream": False,
            "messages": messages,
            "user": (__user__ or {}).get("id"),
            "ragType": rag_type,
            "className": class_name,
            "companyId": company_id,
            "machineCat": machine_cat,
            "machineId": machine_id,
        }

        endpoint = f"{self.valves.RAG_API_BASE_URL.rstrip('/')}/chat/completions"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.valves.RAG_API_KEY}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.valves.REQUEST_TIMEOUT_SEC) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return f"rag-api HTTP {exc.code}: {detail}"
        except Exception as exc:
            return f"rag-api request failed: {exc}"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return f"rag-api returned non-JSON response: {raw}"

        choices = data.get("choices", [])
        if not choices:
            return f"rag-api returned no choices: {data}"

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return f"rag-api returned empty message: {data}"
