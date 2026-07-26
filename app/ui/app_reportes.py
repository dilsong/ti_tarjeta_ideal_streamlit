"""Pantalla del módulo Reportes."""

from __future__ import annotations

import streamlit as st

from app.components.reportes_vistas import render_reportes_content
from app.core.tarjetas import listar_tarjetas
from app.i18n.translator import t
from app.ui.helpers import language_selector


def render(on_back) -> None:
    language_selector()

    st.title(t("reportes.titulo"))
    st.caption(t("reportes.subtitulo"))

    if st.button(t("common.volver"), key="rep_volver", use_container_width=False):
        on_back()

    tarjetas = listar_tarjetas()
    if not tarjetas:
        st.info(t("reportes.sin_tarjetas"))
        return

    render_reportes_content()
