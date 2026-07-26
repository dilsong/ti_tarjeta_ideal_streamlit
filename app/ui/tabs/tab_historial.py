"""Historial de movimientos de una tarjeta."""

from __future__ import annotations

from datetime import date

import streamlit as st

from app.core.consumos import listar_consumos_por_tarjeta
from app.core.fechas import formatear_fecha
from app.core.pagos import EstatusPago, listar_pagos_por_tarjeta
from app.core.tarjetas import Tarjeta
from app.i18n.translator import get_language, t


def _etiqueta_pago(estatus: str) -> str:
    if estatus == EstatusPago.TOTAL.value:
        return t("historial.pago_total")
    if estatus == EstatusPago.MINIMO.value:
        return t("historial.pago_minimo")
    return t("historial.pago_personalizado")


def render(tarjeta: Tarjeta) -> None:
    idioma = get_language()
    filtro = st.radio(
        t("historial.filtro"),
        [
            t("historial.filtro_todos"),
            t("historial.filtro_consumos"),
            t("historial.filtro_pagos"),
        ],
        horizontal=True,
        key=f"hist_filtro_{tarjeta.id}",
        label_visibility="collapsed",
    )

    movimientos: list[tuple[date, str, float, str]] = []

    if filtro in (t("historial.filtro_todos"), t("historial.filtro_consumos")):
        for c in listar_consumos_por_tarjeta(tarjeta.id):
            detalle = c.tienda_razon if c.tienda_razon else t("historial.consumo")
            movimientos.append((date.fromisoformat(c.fecha), "consumo", c.monto, detalle))

    if filtro in (t("historial.filtro_todos"), t("historial.filtro_pagos")):
        for p in listar_pagos_por_tarjeta(tarjeta.id):
            movimientos.append(
                (date.fromisoformat(p.fecha), "pago", p.monto, _etiqueta_pago(p.estatus_pago))
            )

    movimientos.sort(key=lambda m: m[0], reverse=True)

    if not movimientos:
        st.info(t("historial.vacio"))
        return

    for fecha, tipo, monto, detalle in movimientos:
        fecha_txt = formatear_fecha(fecha, idioma)
        if tipo == "consumo":
            color = "#EF4444"
            signo = "−"
            etiqueta = t("historial.etiq_consumo")
        else:
            color = "#22C55E"
            signo = "+"
            etiqueta = t("historial.etiq_pago")

        st.markdown(
            f'<div style="background:#1E293B;border-radius:10px;padding:0.65rem 0.85rem;'
            f"margin-bottom:0.35rem;border-left:3px solid {color};"
            f'"><div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="color:#94A3B8;font-size:0.78rem;">{fecha_txt} · {etiqueta}</span>'
            f'<div style="color:#E2E8F0;font-size:0.92rem;margin-top:0.15rem;">{detalle}</div></div>'
            f'<strong style="color:{color};font-size:1rem;">{signo}${monto:,.2f}</strong>'
            f"</div></div>",
            unsafe_allow_html=True,
        )
