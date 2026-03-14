"""Weaviate delete service for Weaviate objects."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import requests

from ..config.settings import Settings


def _escape_graphql_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _class_exists(*, settings: Settings, class_name: str) -> bool:
    resp = requests.get(
        f"{settings.weaviate_url.rstrip('/')}/v1/schema",
        timeout=settings.weaviate_request_timeout,
    )
    resp.raise_for_status()
    classes = resp.json().get("classes", [])
    return any((item or {}).get("class") == class_name for item in classes)


def _list_class_names(*, settings: Settings) -> list[str]:
    resp = requests.get(
        f"{settings.weaviate_url.rstrip('/')}/v1/schema",
        timeout=settings.weaviate_request_timeout,
    )
    resp.raise_for_status()
    classes = resp.json().get("classes", [])
    return [
        str((item or {}).get("class") or "").strip()
        for item in classes
        if str((item or {}).get("class") or "").strip()
    ]


def _normalize_name(value: str) -> str:
    text = str(value or "").strip()
    text = unicodedata.normalize("NFC", text)
    if not text:
        return ""
    return Path(text).name


def _collect_objects_for_class(*, settings: Settings, class_name: str) -> list[dict]:
    collected: list[dict] = []
    offset = 0
    page_size = 500
    while True:
        query = f"""{{Get{{{class_name}(limit:{page_size},offset:{offset}){{source file_upload_id _additional{{id}}}}}}}}"""
        resp = requests.post(
            f"{settings.weaviate_url.rstrip('/')}/v1/graphql",
            json={"query": query},
            timeout=settings.weaviate_request_timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"weaviate graphql list failed|class={class_name}|status={resp.status_code}|body={(resp.text or '')[:1000]}"
            )
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(
                f"weaviate graphql list failed|class={class_name}|errors={payload.get('errors')}"
            )
        rows = payload.get("data", {}).get("Get", {}).get(class_name, [])
        if not rows:
            break
        collected.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return collected


def _fetch_ids_by_where(
    *, settings: Settings, class_name: str, where_clause: str
) -> list[str]:
    collected: list[str] = []
    offset = 0
    page_size = 500
    while True:
        query = f"""{{Get{{{class_name}(where:{where_clause},limit:{page_size},offset:{offset}){{_additional{{id}}}}}}}}"""
        resp = requests.post(
            f"{settings.weaviate_url.rstrip('/')}/v1/graphql",
            json={"query": query},
            timeout=settings.weaviate_request_timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"weaviate graphql delete lookup failed|status={resp.status_code}|body={(resp.text or '')[:1000]}|query={query[:1000]}"
            )
        rows = resp.json().get("data", {}).get("Get", {}).get(class_name, [])
        if not rows:
            break
        collected.extend(
            [
                row.get("_additional", {}).get("id")
                for row in rows
                if row.get("_additional", {}).get("id")
            ]
        )
        if len(rows) < page_size:
            break
        offset += page_size
    return collected


def delete_chunks(
    *,
    settings: Settings,
    file_upload_id: int,
    file_name: str,
    class_name: str | None,
) -> dict:
    all_classes = _list_class_names(settings=settings)
    if class_name:
        target_classes = [class_name] if class_name in all_classes else []
    else:
        target_classes = list(all_classes)
    if not target_classes:
        return {
            "status": "ok",
            "class_name": class_name or "__all__",
            "deleted_count": 0,
            "deleted_ids": [],
        }
    input_name = _normalize_name(file_name)
    input_file_upload_id = str(file_upload_id).strip()
    deleted_ids: list[str] = []
    for target_class in target_classes:
        objects = _collect_objects_for_class(settings=settings, class_name=target_class)
        class_ids: list[str] = []
        for item in objects:
            object_id = str((item or {}).get("_additional", {}).get("id") or "").strip()
            if not object_id:
                continue
            row_file_upload_id = str(
                (item or {}).get("file_upload_id", "") or ""
            ).strip()
            row_source_name = _normalize_name(str((item or {}).get("source", "") or ""))
            match_by_id = bool(input_file_upload_id) and (
                row_file_upload_id == input_file_upload_id
            )
            match_by_name = bool(input_name) and (row_source_name == input_name)
            if match_by_id or match_by_name:
                class_ids.append(object_id)
        for object_id in class_ids:
            delete_resp = requests.delete(
                f"{settings.weaviate_url.rstrip('/')}/v1/objects/{object_id}",
                params={"class": target_class},
                timeout=settings.weaviate_request_timeout,
            )
            delete_resp.raise_for_status()
        deleted_ids.extend(class_ids)

    return {
        "status": "ok",
        "class_name": class_name or "__all__",
        "deleted_count": len(deleted_ids),
        "deleted_ids": sorted(set(deleted_ids)),
    }
