"""
Sistema de traducciones multi-idioma (ES/EN) para Tarjeta Ideal.

Carga archivos JSON locales y expone la función t() para obtener textos
traducidos por clave anidada (ej: pantalla_inicio.titulo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_I18N_DIR = Path(__file__).parent
_SUPPORTED = ("es", "en")
_current_lang = "es"
_translations: dict[str, dict[str, Any]] = {}


def _load_language(lang: str) -> dict[str, Any]:
    """Carga el archivo JSON de un idioma."""
    path = _I18N_DIR / f"{lang}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def init_translator(lang: str = "es") -> None:
    """Inicializa el traductor con el idioma indicado."""
    global _current_lang, _translations
    if lang not in _SUPPORTED:
        lang = "es"
    _current_lang = lang
    if lang not in _translations:
        _translations[lang] = _load_language(lang)


def set_language(lang: str) -> None:
    """Cambia el idioma activo en tiempo de ejecución."""
    init_translator(lang)


def get_language() -> str:
    """Retorna el código del idioma activo."""
    return _current_lang


def t(key: str, **kwargs: Any) -> str:
    """
    Obtiene un texto traducido por clave anidada con puntos.

    Ejemplo: t("pantalla_inicio.titulo", nombre="Ana")
    """
    if not _translations:
        init_translator(_current_lang)

    parts = key.split(".")
    node: Any = _translations[_current_lang]
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]

    if not isinstance(node, str):
        return key

    if kwargs:
        try:
            return node.format(**kwargs)
        except (KeyError, ValueError):
            return node
    return node
