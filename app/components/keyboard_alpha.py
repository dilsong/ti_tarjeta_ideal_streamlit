"""
Entrada de texto nativa — usa el teclado del dispositivo.
"""

from __future__ import annotations

import streamlit as st


def alpha_input(
    label: str,
    key: str,
    value: str = "",
    max_chars: int | None = None,
    placeholder: str = "",
) -> str:
    """Campo de texto nativo (nombre, banco custom, etc.)."""
    kwargs: dict = {
        "label": label,
        "key": key,
        "value": value,
        "placeholder": placeholder,
    }
    if max_chars:
        kwargs["max_chars"] = max_chars
    return st.text_input(**kwargs)
