"""
Control segmentado estilo iOS para Streamlit.

Usa type primary/secondary porque el CSS sobre un <div> no envuelve el botón
real de Streamlit (son nodos hermanos), y por eso no se veía la selección.
"""

from __future__ import annotations

import streamlit as st


def segmented_control(
    options: list[str],
    key: str,
    default_index: int = 0,
) -> tuple[int, str]:
    """
    Renderiza botones segmentados horizontales.

    Returns:
        (índice seleccionado, valor seleccionado)
    """
    state_key = f"seg_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_index

    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        with cols[i]:
            activo = int(st.session_state[state_key]) == i
            if st.button(
                opt,
                key=f"{key}_seg_{i}",
                type="primary" if activo else "secondary",
                use_container_width=True,
            ):
                if int(st.session_state[state_key]) != i:
                    st.session_state[state_key] = i
                    st.rerun()

    idx = int(st.session_state[state_key])
    if idx < 0 or idx >= len(options):
        idx = 0
        st.session_state[state_key] = 0
    return idx, options[idx]
