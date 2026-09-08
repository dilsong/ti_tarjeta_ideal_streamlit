"""Cajas de alerta HTML — evita que Streamlit interprete $ como LaTeX."""

from __future__ import annotations

from html import escape

import streamlit as st

from app.core.fechas import formatear_fecha, hoy
from app.core.salud_tarjeta import evaluar_prioridad_pago, fmt_dinero, tiene_atraso
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import validar_ciclo
from app.i18n.translator import get_language, t


def render_caja_alerta(texto: str, nivel: str = "urgente") -> None:
    clase = {
        "urgente": "ti-banner-alerta--urgente",
        "warn": "ti-banner-alerta--warn",
        "info": "ti-banner-alerta--info",
    }.get(nivel, "ti-banner-alerta--urgente")
    cuerpo = escape(texto).replace("\n", "<br/>")
    st.markdown(
        f'<div class="ti-banner-alerta {clase}">{cuerpo}</div>',
        unsafe_allow_html=True,
    )


def _bloque_deuda(titulo: str, monto: str, subtitulo: str, *, urgente: bool = False) -> str:
    color_monto = "#FCA5A5" if urgente else "#BFDBFE"
    return (
        f'<div class="ti-deuda-bloque{" ti-deuda-bloque--urgente" if urgente else ""}">'
        f'<div class="ti-deuda-etiq">{escape(titulo)}</div>'
        f'<div class="ti-deuda-monto" style="color:{color_monto};">{escape(monto)}</div>'
        f'<div class="ti-deuda-sub">{escape(subtitulo)}</div>'
        f"</div>"
    )


def html_cuadro_deuda_clara(
    tarjeta: Tarjeta,
    idioma: str | None = None,
    *,
    envolver: bool = True,
) -> str:
    """Dos bloques: VENCIDO (HOY) y CICLO ACTUAL (fecha límite)."""
    lang = idioma or get_language()
    prio = evaluar_prioridad_pago(tarjeta)
    estado = validar_ciclo(tarjeta, hoy())
    pago_txt = (
        formatear_fecha(estado.fecha_pago_proximo, lang)
        if estado.fecha_pago_proximo
        else "—"
    )

    partes: list[str] = []
    if prio.monto_urgente > 0 and tiene_atraso(tarjeta):
        partes.append(
            _bloque_deuda(
                t("salud_tarjeta.etiq_vencido"),
                fmt_dinero(prio.monto_urgente),
                t(
                    "salud_tarjeta.etiq_vencido_sub",
                    dias=prio.dias_atraso_mora,
                ),
                urgente=True,
            )
        )
    if prio.monto_ciclo > 0:
        partes.append(
            _bloque_deuda(
                t("salud_tarjeta.etiq_ciclo"),
                fmt_dinero(prio.monto_ciclo),
                t(
                    "salud_tarjeta.etiq_ciclo_sub",
                    pago=pago_txt,
                    dias=prio.dias_hasta_pago_ciclo,
                ),
            )
        )

    if not partes:
        return ""

    cuerpo = "".join(partes)
    if not envolver:
        return cuerpo
    return (
        '<div class="ti-banner-alerta ti-banner-alerta--urgente ti-deuda-clara">'
        + cuerpo
        + "</div>"
    )


def render_cuadro_deuda_clara(tarjeta: Tarjeta, idioma: str | None = None) -> None:
    html = html_cuadro_deuda_clara(tarjeta, idioma)
    if html:
        st.markdown(html, unsafe_allow_html=True)
