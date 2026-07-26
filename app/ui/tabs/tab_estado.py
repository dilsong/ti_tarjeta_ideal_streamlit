from __future__ import annotations

import streamlit as st

from app.components.charts import render_panel_validacion_ciclo
from app.core.tarjetas import Tarjeta
from app.core.vista_uso import calcular_vista_uso
from app.ui.helpers import render_resumen_financiero
from app.ui.tabs._badges import render_badges_tarjeta
from app.i18n.translator import t


def render(tarjeta: Tarjeta) -> None:
    vista = calcular_vista_uso(tarjeta)
    render_resumen_financiero(tarjeta, vista)
    render_panel_validacion_ciclo(tarjeta)
    render_badges_tarjeta(tarjeta)

    if vista.total_usado > 0:
        partes = [t("estado.desglose_usado", total=vista.total_usado)]
        if vista.ciclo_pasado_pendiente > 0:
            partes.append(
                t("estado.desglose_pasado", monto=vista.ciclo_pasado_pendiente)
            )
        if vista.ciclo_nuevo_total > 0:
            partes.append(
                t("estado.desglose_nuevo", monto=vista.ciclo_nuevo_total)
            )
        st.markdown(
            f'<p class="ti-detail-caption">{" · ".join(partes)}</p>',
            unsafe_allow_html=True,
        )
