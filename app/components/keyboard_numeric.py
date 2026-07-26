"""
Entrada numérica con text_input — teclado nativo del celular, sin botones +/-.
"""

from __future__ import annotations

import streamlit as st


def parse_monto(texto: str) -> float:
    """Convierte texto a float (acepta coma o punto decimal)."""
    limpio = (texto or "").strip().replace(",", ".")
    if not limpio:
        return 0.0
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def monto_text_input(label: str, key: str, placeholder: str = "0.00") -> float:
    """Caja de texto para montos."""
    valor = st.text_input(label, key=key, placeholder=placeholder)
    return parse_monto(valor)


def entero_text_input(label: str, key: str, placeholder: str = "1") -> int:
    """Caja de texto para enteros (días del mes, etc.)."""
    valor = st.text_input(label, key=key, placeholder=placeholder, max_chars=2)
    try:
        return int(parse_monto(valor))
    except (ValueError, OverflowError):
        return 0
