"""Deterministic ID helpers."""

from __future__ import annotations

import uuid

DEFAULT_NAMESPACE = uuid.NAMESPACE_URL


def deterministic_uuid_from_parts(
    *, parts: list[str], namespace: uuid.UUID = DEFAULT_NAMESPACE
) -> str:
    seed = "|".join(parts)
    return str(uuid.uuid5(namespace, seed))
