"""Helpers for user-facing required-field validation messages."""

from __future__ import annotations

from app.i18n.translator import t


def validar_requeridos(pares: list[tuple[str, bool]]) -> list[str]:
    """pares = [(label, ok)]. Return labels where ok is False."""
    return [label for label, ok in pares if not ok]


def mensaje_campos_faltantes(faltantes: list[str]) -> str:
    """Build user-facing error listing missing required fields."""
    if not faltantes:
        return ""
    return t("validacion.error_faltan", lista=", ".join(faltantes))


def mensaje_campos_revisa(faltantes: list[str]) -> str:
    """Softer review hint listing incomplete fields."""
    if not faltantes:
        return ""
    return t("validacion.error_revisa", lista=", ".join(faltantes))


def marca_obligatorio(label: str) -> str:
    """Append the required-field marker to a widget label."""
    return f"{label}{t('validacion.campo_obligatorio_marca')}"
