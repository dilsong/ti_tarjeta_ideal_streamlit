"""
Selector con opción de agregar banco o nombre que no exista.

Las opciones nuevas se guardan localmente en config.json.
"""

from __future__ import annotations

import streamlit as st

from app.core.catalogo import guardar_custom, opciones_combinadas
from app.i18n.translator import t


def select_with_add(
    label: str,
    options: list[str],
    key: str,
    categoria: str,
    default: str | None = None,
) -> str:
    """
    Selectbox con opción «Agregar otro» y campo de texto nativo.

    Args:
        label: Etiqueta visible.
        options: Opciones por defecto.
        key: Clave única Streamlit.
        categoria: 'bancos' o 'nombres_tarjeta' para persistencia local.
        default: Valor inicial si existe en la lista.
    """
    base = opciones_combinadas(categoria, options)
    add_label = t("common.agregar_otro")
    display_opts = base + [add_label]
    add_index = len(display_opts) - 1

    idx = 0
    if default and default in base:
        idx = base.index(default)

    selected_label = st.selectbox(label, display_opts, index=idx, key=f"swa_sel_{key}")

    if selected_label == add_label:
        custom = st.text_input(
            t("common.escribir_nuevo", campo=label),
            key=f"swa_custom_{key}",
            placeholder=t("common.placeholder_nuevo"),
        )
        return custom.strip()

    return selected_label


def persist_if_new(categoria: str, valor: str, options: list[str]) -> None:
    """Guarda en catálogo local si el valor no está en la lista default."""
    texto = valor.strip()
    if not texto:
        return
    if texto not in options:
        guardar_custom(categoria, texto)
