"""Shared class/label definitions used across ingestion and rag services."""

from __future__ import annotations

from enum import Enum


class RagClassName(str, Enum):
    GENERAL = "General"
    MACHINE = "Machine"
    PHYSICAL_AI = "Physical_AI"
    EDGECROSS_POLICY = "EdgeCross_Policy"


CLASS_DISPLAY_NAME_BY_KEY: dict[str, str] = {
    RagClassName.GENERAL.value: "General (일반)",
    RagClassName.MACHINE.value: "Machine (설비/장비)",
    RagClassName.PHYSICAL_AI.value: "Physical AI",
    RagClassName.EDGECROSS_POLICY.value: "EdgeCross 회사 규정 안내",
}


CLASS_OPTIONS: list[str] = [item.value for item in RagClassName]
DEFAULT_CLASS_NAME: str = RagClassName.GENERAL.value
DEFAULT_NEO4J_LABEL: str = RagClassName.GENERAL.value


def class_display_name(class_name: str) -> str:
    return CLASS_DISPLAY_NAME_BY_KEY.get(class_name, class_name)


def build_openwebui_class_enum_snippet() -> str:
    enum_values = ", ".join(f'"{item.value}"' for item in RagClassName)
    return f'json_schema_extra={{"enum": [{enum_values}]}}'


def build_openwebui_uservalves_class_field_snippet() -> str:
    return (
        "class_name: str = Field("
        '\n    default="General",'
        '\n    description="Target class name. Default: General.",'
        f"\n    {build_openwebui_class_enum_snippet()},"
        "\n)"
    )
