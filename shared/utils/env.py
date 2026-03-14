"""Environment variable parsing helpers."""

from __future__ import annotations

import os


def get_str(env_name: str, default: str) -> str:
    return os.getenv(env_name, default)


def get_int(env_name: str, default: int) -> int:
    return int(os.getenv(env_name, str(default)))


def get_float(env_name: str, default: float) -> float:
    return float(os.getenv(env_name, str(default)))


def get_bool(env_name: str, default: bool) -> bool:
    return os.getenv(env_name, str(default)).lower() == "true"
