"""Weaviate delete service for Weaviate objects."""

from __future__ import annotations

import requests

from ..config.settings import Settings


def delete_chunks(
    *,
    settings: Settings,
    file_upload_id: int,
    file_name: str,
    class_name: str | None,
) -> dict:
    resolved_class_name = class_name or settings.weaviate_default_class
    clauses = [
        f"{{path:[\\\"file_upload_id\\\"],operator:Equal,valueText:\\\"{file_upload_id}\\\"}}",
        f"{{path:[\\\"source\\\"],operator:Equal,valueText:\\\"{file_name}\\\"}}",
    ]
    where_clause = ",".join(clauses)
    query = f"""{{Get{{{resolved_class_name}(where:{{operator:And,operands:[{where_clause}]}}){{_additional{{id}}}}}}}}"""
    resp = requests.post(
        f"{settings.weaviate_url.rstrip('/')}/v1/graphql",
        json={"query": query},
        timeout=settings.request_timeout,
    )
    resp.raise_for_status()
    rows = resp.json().get("data", {}).get("Get", {}).get(resolved_class_name, [])
    ids = [row.get("_additional", {}).get("id") for row in rows if row.get("_additional", {}).get("id")]

    for object_id in ids:
        delete_resp = requests.delete(
            f"{settings.weaviate_url.rstrip('/')}/v1/objects/{object_id}",
            params={"class": resolved_class_name},
            timeout=settings.request_timeout,
        )
        delete_resp.raise_for_status()

    return {
        "status": "ok",
        "class_name": resolved_class_name,
        "deleted_count": len(ids),
        "deleted_ids": ids,
    }
