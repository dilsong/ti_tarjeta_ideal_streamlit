"""Solapa Guía — rutas bancarias y lectura de capturas."""

from __future__ import annotations

import streamlit as st

from app.core.tarjetas import Tarjeta
from app.i18n.translator import t
from ayuda.mapa_bancos import mapa_ayuda_bancaria


@st.dialog(t("tabs.guia_titulo"), width="large")
def abrir_guia_bancaria(tarjeta: Tarjeta) -> None:
    mapa_ayuda_bancaria(tarjeta_sel=tarjeta, key_prefix="guia_dlg_")


def render(tarjeta: Tarjeta) -> None:
    st.subheader(t("tabs.guia_titulo"))
    st.caption(t("tabs.guia_subtitulo"))
    mapa_ayuda_bancaria(tarjeta_sel=tarjeta)
