"""
Pantalla de edición de tarjeta de crédito — wizard en 2 pasos.
"""

from __future__ import annotations

import streamlit as st

from app.core.tarjetas import obtener_tarjeta
from app.i18n.translator import t
from app.ui.helpers import language_selector
from app.ui.wizard_tarjeta import render_wizard_editar


def render(on_back, on_saved, tarjeta_id: str) -> None:
    language_selector()
    st.title(t("pantalla_editar_tarjeta.titulo"))
    render_wizard_editar(on_back, on_saved, tarjeta_id)


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    st.session_state.unlocked = True

    tarjeta_id = st.session_state.get("editar_tarjeta_id", "")
    if not tarjeta_id:
        st.warning(t("pantalla_editar_tarjeta.error_no_encontrada"))
        return

    def back() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    def saved() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    render(back, saved, tarjeta_id)


if __name__ == "__main__":
    main()
