"""Tab principal Mejor Opción — recomendación de tarjeta para compras."""

from __future__ import annotations

import streamlit as st

from app.core.tarjetas import Tarjeta
from app.i18n.translator import t
from app.ui.tabs import tab_comprar


def render(tarjetas: list[Tarjeta], tarjeta_sel: Tarjeta) -> None:
    st.subheader(t("tabs.mejor_opcion_titulo"))
    st.caption(t("tabs.mejor_opcion_subtitulo"))
    tab_comprar.render(tarjetas, tarjeta_sel)
