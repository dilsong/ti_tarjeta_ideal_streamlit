"""Badges de salud del límite y riesgo de pago."""

from __future__ import annotations

import streamlit as st

from app.components.theme import ESTADO_COLORS
from app.core.tarjetas import EstadoSalud, Tarjeta
from app.core.validacion_ciclo import estado_riesgo_pago
from app.i18n.translator import t


def _label_salud(estado: EstadoSalud) -> str:
    return {
        EstadoSalud.POSITIVO: t("pantalla_lista_tarjetas.estado_positivo"),
        EstadoSalud.MEDIO: t("pantalla_lista_tarjetas.estado_medio"),
        EstadoSalud.NEGATIVO: t("pantalla_lista_tarjetas.estado_negativo"),
    }[estado]


def render_badges_tarjeta(tarjeta: Tarjeta) -> None:
    salud = tarjeta.estado_salud()
    riesgo = estado_riesgo_pago(tarjeta)
    st.markdown(
        f'<span class="ti-badge" style="background:{ESTADO_COLORS[salud.value]};">'
        f'{t("tabs.estado_badge_limite")}: {_label_salud(salud)}</span> '
        f'<span class="ti-badge" style="background:{ESTADO_COLORS[riesgo.value]};margin-left:0.35rem;">'
        f'{t("tabs.estado_badge_pago")}: {_label_salud(riesgo)}</span> '
        f'<strong style="color:#F8FAFC;margin-left:0.5rem;">{tarjeta.nombre}</strong> · {tarjeta.banco}',
        unsafe_allow_html=True,
    )
