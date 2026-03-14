"""Shared Weaviate schema helpers for ingestion services."""

from __future__ import annotations

from typing import Any

import requests

from ..config.settings import Settings


def ensure_weaviate_class_properties(
    *,
    settings: Settings,
    class_name: str,
    properties: list[dict[str, Any]],
) -> None:
    base_url = settings.weaviate_url.rstrip("/")
    schema_resp = requests.get(
        f"{base_url}/v1/schema", timeout=settings.weaviate_request_timeout
    )
    schema_resp.raise_for_status()
    classes = schema_resp.json().get("classes", [])
    existing = {c.get("class") for c in classes}
    if class_name in existing:
        existing_props: list[dict[str, Any]] = []
        for item in classes:
            if item.get("class") == class_name:
                existing_props = item.get("properties", [])
                break
        existing_prop_names = {prop.get("name") for prop in existing_props}
        for prop in properties:
            prop_name = prop.get("name")
            if prop_name in existing_prop_names:
                continue
            prop_resp = requests.post(
                f"{base_url}/v1/schema/{class_name}/properties",
                json=prop,
                timeout=settings.weaviate_request_timeout,
            )
            prop_resp.raise_for_status()
        return
    body = {"class": class_name, "vectorizer": "none", "properties": properties}
    create_resp = requests.post(
        f"{base_url}/v1/schema", json=body, timeout=settings.weaviate_request_timeout
    )
    create_resp.raise_for_status()
