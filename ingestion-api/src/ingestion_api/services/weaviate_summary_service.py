"""Weaviate summary helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ..config.settings import Settings


@dataclass
class WeaviateSummaryStats:
    class_name: str
    total_count: int
    sampled_rows: int
    top_sources: list[tuple[str, int]]


def get_weaviate_summary(
    *,
    settings: Settings,
    logger: Any,
    class_name: str,
) -> WeaviateSummaryStats:
    base_url = settings.weaviate_url.rstrip("/")
    count_query = f'{{Aggregate{{{class_name}{{meta{{count}}}}}}}}'
    count_resp = requests.post(
        f"{base_url}/v1/graphql",
        json={"query": count_query},
        timeout=settings.request_timeout,
    )
    count_resp.raise_for_status()
    count_data = count_resp.json()
    total_count = (
        count_data.get("data", {})
        .get("Aggregate", {})
        .get(class_name, [{}])[0]
        .get("meta", {})
        .get("count", 0)
    )

    get_query = "{Get{%s(limit:200){source}}}" % class_name
    get_resp = requests.post(
        f"{base_url}/v1/graphql",
        json={"query": get_query},
        timeout=settings.request_timeout,
    )
    get_resp.raise_for_status()
    rows = get_resp.json().get("data", {}).get("Get", {}).get(class_name, [])
    source_counter: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source") or "unknown")
        source_counter[source] = source_counter.get(source, 0) + 1
    top_sources = sorted(source_counter.items(), key=lambda item: item[1], reverse=True)[:10]
    logger.info(
        "weaviate_summary done|class_name=%s|total=%s|sampled=%s",
        class_name,
        total_count,
        len(rows),
    )
    return WeaviateSummaryStats(
        class_name=class_name,
        total_count=int(total_count),
        sampled_rows=len(rows),
        top_sources=top_sources,
    )
