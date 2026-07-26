"""Solapa Reportes — visualizar, comparar e imprimir tarjetas."""

from __future__ import annotations

import streamlit as st

from app.components.reportes_vistas import render_reportes_content
from app.i18n.translator import t


def render() -> None:
    st.caption(t("reportes.subtitulo"))
    render_reportes_content()
