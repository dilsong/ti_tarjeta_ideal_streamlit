"""
Pantalla de registro de tarjeta de crédito — wizard en 2 pasos.
"""

from __future__ import annotations

import streamlit as st

from app.i18n.translator import t
from app.ui.helpers import language_selector
from app.ui.wizard_tarjeta import render_wizard_registro


def render(on_back, on_saved) -> None:
    language_selector()
    st.title(t("pantalla_registrar_tarjeta.titulo"))
    render_wizard_registro(on_back, on_saved)


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    st.session_state.autenticado = True
    st.session_state.unlocked = True

    def back() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    def saved() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    render(back, saved)


if __name__ == "__main__":
    main()
