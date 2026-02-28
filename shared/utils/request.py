"""Shared request helpers for resolving app state dependencies."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Request


def resolve_settings(request: Request, loader: Callable[[], Any]) -> Any:
    return getattr(request.app.state, "settings", loader())


def resolve_logger(request: Request, default_logger: Any) -> Any:
    return getattr(request.app.state, "logger", default_logger)
