"""Componente Streamlit ↔ localStorage del origen PWA (ventana padre)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent
_ls = components.declare_component("ti_local_storage", path=str(_COMPONENT_DIR))

# Clave del bundle monousuario en el navegador / PWA instalada.
STORAGE_KEY_BUNDLE = "ti_app_bundle_v1"


def ls_get(storage_key: str, *, widget_key: str) -> Any:
    """Lee un string de localStorage. En el primer tick puede devolver None (pendiente)."""
    return _ls(mode="get", storage_key=storage_key, default=None, key=widget_key)


def ls_set(storage_key: str, value: str, *, widget_key: str) -> Any:
    """Escribe (o borra si value='') en localStorage."""
    return _ls(mode="set", storage_key=storage_key, value=value, default=None, key=widget_key)
