"""
Catálogo local de bancos y nombres de tarjeta personalizados.

Persiste opciones agregadas por el usuario en config.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONFIG_FILE = _DATA_DIR / "config.json"


def _load_config() -> dict[str, Any]:
    if not _CONFIG_FILE.exists():
        return {}
    with _CONFIG_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def listar_custom(categoria: str) -> list[str]:
    """Retorna opciones personalizadas guardadas (bancos o nombres_tarjeta)."""
    key = f"{categoria}_custom"
    return list(_load_config().get(key, []))


def guardar_custom(categoria: str, valor: str) -> None:
    """Agrega una opción personalizada si no existe."""
    texto = valor.strip()
    if not texto:
        return
    config = _load_config()
    key = f"{categoria}_custom"
    actuales: list[str] = list(config.get(key, []))
    if texto not in actuales:
        actuales.append(texto)
        config[key] = actuales
        _save_config(config)


def opciones_combinadas(categoria: str, defaults: list[str]) -> list[str]:
    """Une defaults con personalizados, sin duplicados."""
    custom = listar_custom(categoria)
    vistos: set[str] = set()
    resultado: list[str] = []
    for item in custom + defaults:
        if item not in vistos:
            vistos.add(item)
            resultado.append(item)
    return resultado
