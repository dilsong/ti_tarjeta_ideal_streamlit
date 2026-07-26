"""Diálogo de confirmación antes de registrar un pago — TI no transfiere dinero."""

from __future__ import annotations

from typing import Literal

import streamlit as st

from app.components.keyboard_numeric import monto_text_input
from app.core.enlaces_banco import normalizar_preferencia, resolver_url_banco
from app.core.pagos import (
    registrar_abono_sugerido,
    registrar_pago_minimo,
    registrar_pago_personalizado,
    registrar_pago_total,
)
from app.core.tarjetas import Tarjeta
from app.i18n.translator import t

TipoPagoDialogo = Literal["total", "minimo", "personalizado", "abono"]


def _mensaje_exito(
    tipo: TipoPagoDialogo,
    *,
    monto_txt: str,
    es_pago_total: bool,
    escenario: str,
) -> str:
    if tipo == "total":
        return t("pagos_estatus.exito_total")
    if tipo == "minimo":
        return t("pagos_estatus.exito_minimo")
    if tipo == "personalizado":
        return t("pagos_estatus.exito_personalizado")
    clave = (
        "banner_sugerencia.exito_total"
        if es_pago_total
        else (
            "banner_sugerencia.exito_pago"
            if escenario == "ciclo_pendiente"
            else "banner_sugerencia.exito"
        )
    )
    return t(clave, monto=monto_txt)


def _registrar_pago(
    tarjeta: Tarjeta,
    tipo: TipoPagoDialogo,
    *,
    monto: float,
    es_pago_total: bool,
) -> None:
    if tipo == "total":
        registrar_pago_total(tarjeta.id)
    elif tipo == "minimo":
        registrar_pago_minimo(tarjeta.id)
    elif tipo == "personalizado":
        registrar_pago_personalizado(tarjeta.id, monto)
    elif es_pago_total:
        registrar_pago_total(tarjeta.id)
    else:
        registrar_abono_sugerido(tarjeta.id, monto)


def _etiqueta_abrir_banco(tarjeta: Tarjeta) -> str:
    pref = normalizar_preferencia(getattr(tarjeta, "preferencia_banco", None))
    if pref == "web":
        return t("banner_sugerencia.dialogo_ir_banco_web", banco=tarjeta.banco)
    return t("banner_sugerencia.dialogo_ir_banco_app", banco=tarjeta.banco)


@st.dialog(" ", width="small")
def confirmar_pago_en_banco(
    tarjeta: Tarjeta,
    *,
    tipo: TipoPagoDialogo,
    monto_txt: str,
    msg_key: str,
    monto: float = 0.0,
    es_pago_total: bool = False,
    escenario: str = "",
    key_prefix: str = "",
) -> None:
    st.markdown(f"**{t('banner_sugerencia.dialogo_titulo')}**")
    st.warning(
        t(
            "banner_sugerencia.dialogo_cuerpo",
            banco=tarjeta.banco,
            monto=monto_txt,
        )
    )

    url = resolver_url_banco(tarjeta)
    if url:
        st.link_button(
            _etiqueta_abrir_banco(tarjeta),
            url,
            use_container_width=True,
        )
    else:
        st.caption(t("banner_sugerencia.dialogo_sin_enlace"))

    monto_registro = monto
    if tipo == "personalizado":
        st.divider()
        st.caption(t("pagos_estatus.personalizado_label"))
        monto_registro = monto_text_input(
            t("pagos_estatus.monto_pagado"),
            f"{key_prefix}monto_pago_dialog_{tarjeta.id}",
        )

    st.divider()

    col_cancel, col_ok = st.columns(2)
    with col_cancel:
        if st.button(
            t("banner_sugerencia.dialogo_cancelar"),
            key=f"{key_prefix}dlg_pago_cancel_{tipo}_{tarjeta.id}",
            use_container_width=True,
        ):
            st.rerun()
    with col_ok:
        if st.button(
            t("banner_sugerencia.dialogo_registrar"),
            key=f"{key_prefix}dlg_pago_ok_{tipo}_{tarjeta.id}",
            type="primary",
            use_container_width=True,
        ):
            try:
                _registrar_pago(
                    tarjeta,
                    tipo,
                    monto=monto_registro,
                    es_pago_total=es_pago_total,
                )
                st.session_state[msg_key] = _mensaje_exito(
                    tipo,
                    monto_txt=monto_txt,
                    es_pago_total=es_pago_total,
                    escenario=escenario,
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
