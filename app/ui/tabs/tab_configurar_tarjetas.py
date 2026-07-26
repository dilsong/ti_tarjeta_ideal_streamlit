"""Tab Configurar Tarjetas — gestión, umbrales, alertas y ayuda."""

from __future__ import annotations

import streamlit as st

from app.core.tarjetas import Tarjeta, listar_tarjetas
from app.i18n.translator import t
from app.ui.tabs import tab_notificaciones, tab_soporte, tab_tarjetas

CFG_SEGMENT_KEY = "ti_cfg_segment"
_SEGMENTS = ("tarjetas", "umbrales", "alertas", "ayuda")


def render(tarjeta_sel: Tarjeta, on_edit, on_add) -> None:
    st.subheader(t("config_tarjetas.titulo"))
    st.caption(t("config_tarjetas.subtitulo"))

    if CFG_SEGMENT_KEY not in st.session_state:
        st.session_state[CFG_SEGMENT_KEY] = "tarjetas"

    labels = {
        "tarjetas": t("config_tarjetas.segment_tarjetas"),
        "umbrales": t("config_tarjetas.segment_umbrales"),
        "alertas": t("config_tarjetas.segment_alertas"),
        "ayuda": t("config_tarjetas.segment_soporte"),
    }

    st.markdown('<span class="ti-persist-tabs-marker"></span>', unsafe_allow_html=True)
    active = st.radio(
        "cfg_nav",
        list(_SEGMENTS),
        format_func=lambda s: labels[s],
        horizontal=True,
        label_visibility="collapsed",
        key=CFG_SEGMENT_KEY,
    )

    if active == "tarjetas":
        tab_tarjetas.render_gestion(listar_tarjetas(), on_edit, on_add)
    elif active == "umbrales":
        tab_tarjetas.render_umbrales(listar_tarjetas(), tarjeta_sel)
    elif active == "alertas":
        tab_notificaciones.render(embedded=True)
    else:
        tab_soporte.render()
