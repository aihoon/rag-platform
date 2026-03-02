"""Shared Weaviate summary helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class WeaviateSummaryStats:
    class_name: str
    total_count: int
    sampled_rows: int
    top_sources: list[tuple[str, int]]
    classes: list[str]


def get_weaviate_summary(
    *,
    weaviate_url: str,
    timeout_sec: int,
    default_class: str,
    logger: Any,
    class_name: str | None = None,
) -> WeaviateSummaryStats:
    base_url = weaviate_url.rstrip("/")
    effective_class = class_name or default_class
    schema_resp = requests.get(f"{base_url}/v1/schema", timeout=timeout_sec)
    schema_resp.raise_for_status()
    classes = schema_resp.json().get("classes", [])
    class_names = [item.get("class") for item in classes if item.get("class")]
    if not class_names or effective_class not in class_names:
        logger.info(
            "weaviate_summary empty|class_name=%s|classes=%s",
            effective_class,
            class_names,
        )
        return WeaviateSummaryStats(
            class_name=effective_class,
            total_count=0,
            sampled_rows=0,
            top_sources=[],
            classes=class_names,
        )

    count_query = f"{{Aggregate{{{effective_class}{{meta{{count}}}}}}}}"
    count_resp = requests.post(
        f"{base_url}/v1/graphql",
        json={"query": count_query},
        timeout=timeout_sec,
    )
    count_resp.raise_for_status()
    count_data = count_resp.json()
    total_count = (
        count_data.get("data", {})
        .get("Aggregate", {})
        .get(effective_class, [{}])[0]
        .get("meta", {})
        .get("count", 0)
    )

    get_query = "{Get{%s(limit:200){source}}}" % effective_class
    get_resp = requests.post(
        f"{base_url}/v1/graphql",
        json={"query": get_query},
        timeout=timeout_sec,
    )
    get_resp.raise_for_status()
    rows = get_resp.json().get("data", {}).get("Get", {}).get(effective_class, [])
    source_counter = Counter(str(row.get("source") or "unknown") for row in rows)
    logger.info(
        "weaviate_summary done|class_name=%s|total=%s|sampled=%s",
        effective_class,
        total_count,
        len(rows),
    )
    return WeaviateSummaryStats(
        class_name=effective_class,
        total_count=int(total_count),
        sampled_rows=len(rows),
        top_sources=source_counter.most_common(10),
        classes=class_names,
    )
