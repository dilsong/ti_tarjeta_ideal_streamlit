"""
Control segmentado estilo iOS para Streamlit.
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
            css = "seg-btn-active" if st.session_state[state_key] == i else "seg-btn"
            st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
            if st.button(opt, key=f"{key}_seg_{i}"):
                st.session_state[state_key] = i
            st.markdown("</div>", unsafe_allow_html=True)

    idx = st.session_state[state_key]
    return idx, options[idx]
