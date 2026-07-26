"""Tab Mis Tarjetas — vistas secundarias de la tarjeta seleccionada."""



from __future__ import annotations



import streamlit as st



from app.core.tarjetas import Tarjeta

from app.i18n.translator import t

from app.ui.tabs import tab_estado, tab_fechas, tab_historial, tab_pagos, tab_uso





def render(tarjeta_sel: Tarjeta) -> None:

    st.subheader(t("tabs.tarjetas_titulo"))

    st.caption(

        t(

            "tabs.tarjetas_subtitulo",

            nombre=tarjeta_sel.nombre,

            banco=tarjeta_sel.banco,

            digitos=tarjeta_sel.ultimos_digitos,

        )

    )



    pane_est, pane_uso, pane_fec, pane_pag, pane_hist = st.tabs(

        [

            t("tabs.estado"),

            t("tabs.uso"),

            t("tabs.fechas"),

            t("tabs.pagos"),

            t("tabs.historial"),

        ]

    )



    with pane_est:

        tab_estado.render(tarjeta_sel)

    with pane_uso:

        tab_uso.render(tarjeta_sel)

    with pane_fec:

        tab_fechas.render(tarjeta_sel)

    with pane_pag:

        tab_pagos.render(tarjeta_sel, compacto=True)

    with pane_hist:

        tab_historial.render(tarjeta_sel)

