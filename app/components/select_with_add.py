"""
Selector con opción de agregar banco o nombre que no exista.

Las opciones nuevas se guardan localmente en config.json.
"""

from __future__ import annotations

import streamlit as st

from app.core.catalogo import guardar_custom, opciones_combinadas
from app.i18n.translator import t


def init_select_with_add(
    key: str,
    categoria: str,
    options: list[str],
    valor: str | None,
    *,
    force: bool = False,
) -> None:
    """Pre-carga session_state del selectbox (sin index= en el widget)."""
    sel_key = f"swa_sel_{key}"
    custom_key = f"swa_custom_{key}"
    if not force and sel_key in st.session_state:
        return
    base = opciones_combinadas(categoria, options)
    add_label = t("common.agregar_otro")
    texto = (valor or "").strip()
    if not texto:
        st.session_state.pop(sel_key, None)
        st.session_state.pop(custom_key, None)
        return
    if texto in base:
        st.session_state[sel_key] = texto
        st.session_state.pop(custom_key, None)
    else:
        st.session_state[sel_key] = add_label
        st.session_state[custom_key] = texto


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
        default: Valor inicial — solo se escribe en session_state si la clave no existe.
    """
    if default:
        init_select_with_add(key, categoria, options, default)

    base = opciones_combinadas(categoria, options)
    add_label = t("common.agregar_otro")
    display_opts = base + [add_label]

    selected_label = st.selectbox(label, display_opts, key=f"swa_sel_{key}")

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
