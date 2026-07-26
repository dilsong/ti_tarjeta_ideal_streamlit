"""Simulación de intereses — vista simplificada para la solapa Pagos."""

from __future__ import annotations

import streamlit as st

from app.components.desglose_dialog import boton_desglose
from app.core.intereses import generar_desglose_proximo_ciclo
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import validar_ciclo_con_intereses
from app.i18n.translator import t
from app.ui.helpers import fila_accion


def _aviso_tasa_estimada(tasa: float, banco: str) -> None:
    st.markdown(
        f'<div style="background:#422006;border:1px solid #FACC15;border-radius:12px;'
        f'padding:0.85rem 1rem;margin-bottom:1rem;color:#FDE68A;font-size:0.9rem;">'
        f'⚠️ {t("intereses.aviso_tasa_corta", tasa=tasa, banco=banco)}</div>',
        unsafe_allow_html=True,
    )


def _monto_grande(label: str, valor: float) -> None:
    st.markdown(
        f'<div style="background:#1E293B;border-radius:12px;padding:0.85rem 1rem;margin-bottom:0.5rem;">'
        f'<div style="color:#CBD5E1;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
        f"{label}</div>"
        f'<div class="ti-money" style="color:#F8FAFC;font-size:1.75rem;font-weight:700;">'
        f"${valor:,.2f}</div></div>",
        unsafe_allow_html=True,
    )


def _monto_grande_con_desglose(label: str, valor: float, desglose, key: str) -> None:
    with fila_accion() as (c_main, c_btn):
        with c_main:
            st.markdown(
                f'<div style="background:#1E293B;border-radius:12px;padding:0.85rem 1rem;margin-bottom:0.5rem;">'
                f'<div style="color:#CBD5E1;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
                f"{label}</div>"
                f'<div class="ti-money" style="color:#F8FAFC;font-size:1.75rem;font-weight:700;">'
                f"${valor:,.2f}</div></div>",
                unsafe_allow_html=True,
            )
        with c_btn:
            boton_desglose(desglose, key)


def render_panel_intereses(tarjeta: Tarjeta, *, key_prefix: str = "") -> None:
    estado = validar_ciclo_con_intereses(tarjeta)
    proy = estado.proyeccion_intereses
    if proy is None:
        return

    st.markdown(f"**{t('intereses.panel_titulo')}**")

    if tarjeta.tasa_es_estimada:
        _aviso_tasa_estimada(proy.tasa_aplicada, tarjeta.banco)

    desglose_prox = generar_desglose_proximo_ciclo(tarjeta, estado, proy)

    _monto_grande(t("intereses.monto_pagar_ciclo"), proy.monto_pagar_ciclo)
    _monto_grande(t("intereses.pago_minimo"), proy.pago_minimo)
    _monto_grande_con_desglose(
        t("intereses.monto_proximo_ciclo"),
        proy.monto_acumulado_proximo_min,
        desglose_prox,
        f"{key_prefix}desglose_prox_{tarjeta.id}",
    )

    if proy.monto_pagar_ciclo <= 0:
        st.success(t("intereses.sin_deuda_ciclo"))
