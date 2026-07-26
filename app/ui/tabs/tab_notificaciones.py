"""
Configuración de notificaciones de ciclo — TI Asesor Financiero.
"""

from __future__ import annotations

import streamlit as st

from app.components.push_notificaciones import render_solicitud_permiso
from app.i18n.translator import t
from notificaciones.notificador_ciclos import (
    DEFAULT_CONFIG,
    cargar_config_notificaciones,
    guardar_config_notificaciones,
)


def render(*, embedded: bool = False) -> None:
    if not embedded:
        st.subheader(t("notificaciones.titulo"))
        st.caption(t("notificaciones.subtitulo"))

    config = cargar_config_notificaciones()

    with st.form("form_notificaciones"):
        st.markdown(f"**{t('notificaciones.seccion_antes_corte')}**")
        notificar_antes_corte = st.checkbox(
            t("notificaciones.antes_corte"),
            value=config.get("notificar_antes_corte", DEFAULT_CONFIG["notificar_antes_corte"]),
        )
        dias_antes_corte = st.number_input(
            t("notificaciones.dias_antes_corte"),
            min_value=1,
            max_value=14,
            value=int(config.get("dias_antes_corte", DEFAULT_CONFIG["dias_antes_corte"])),
            disabled=not notificar_antes_corte,
        )

        st.markdown(f"**{t('notificaciones.seccion_dia_corte')}**")
        notificar_dia_corte = st.checkbox(
            t("notificaciones.dia_corte"),
            value=config.get("notificar_dia_corte", DEFAULT_CONFIG["notificar_dia_corte"]),
        )

        st.markdown(f"**{t('notificaciones.seccion_mitad')}**")
        notificar_mitad = st.checkbox(
            t("notificaciones.mitad_ciclo"),
            value=config.get("notificar_mitad_ciclo", DEFAULT_CONFIG["notificar_mitad_ciclo"]),
        )
        dias_mitad = st.number_input(
            t("notificaciones.dias_mitad"),
            min_value=1,
            max_value=28,
            value=int(config.get("dias_mitad_ciclo", DEFAULT_CONFIG["dias_mitad_ciclo"])),
            disabled=not notificar_mitad,
        )

        st.markdown(f"**{t('notificaciones.seccion_antes_pago')}**")
        notificar_antes_pago = st.checkbox(
            t("notificaciones.antes_pago"),
            value=config.get("notificar_antes_pago", DEFAULT_CONFIG["notificar_antes_pago"]),
        )
        dias_antes_pago = st.number_input(
            t("notificaciones.dias_antes_pago"),
            min_value=1,
            max_value=14,
            value=int(config.get("dias_antes_pago", DEFAULT_CONFIG["dias_antes_pago"])),
            disabled=not notificar_antes_pago,
        )

        st.markdown(f"**{t('notificaciones.seccion_impago')}**")
        notificar_despues_pago = st.checkbox(
            t("notificaciones.despues_pago"),
            value=config.get("notificar_despues_pago", DEFAULT_CONFIG["notificar_despues_pago"]),
        )
        notificar_despues_corte = st.checkbox(
            t("notificaciones.despues_corte"),
            value=config.get(
                "notificar_dias_despues_corte",
                DEFAULT_CONFIG["notificar_dias_despues_corte"],
            ),
        )
        notificar_inicio = st.checkbox(
            t("notificaciones.inicio_ciclo"),
            value=config.get("notificar_inicio_ciclo", DEFAULT_CONFIG["notificar_inicio_ciclo"]),
        )

        if st.form_submit_button(t("notificaciones.guardar"), type="primary", use_container_width=True):
            nueva = {
                **config,
                "notificar_antes_corte": notificar_antes_corte,
                "dias_antes_corte": int(dias_antes_corte),
                "notificar_dia_corte": notificar_dia_corte,
                "notificar_mitad_ciclo": notificar_mitad,
                "dias_mitad_ciclo": int(dias_mitad),
                "notificar_antes_pago": notificar_antes_pago,
                "dias_antes_pago": int(dias_antes_pago),
                "notificar_despues_pago": notificar_despues_pago,
                "notificar_dias_despues_corte": notificar_despues_corte,
                "notificar_inicio_ciclo": notificar_inicio,
            }
            guardar_config_notificaciones(nueva)
            st.success(t("notificaciones.guardado_ok"))
            st.rerun()

    st.caption(t("notificaciones.nota_un_dia"))

    st.divider()
    render_solicitud_permiso(compacto=False)

    if st.button(t("notificaciones.restaurar"), use_container_width=True):
        guardar_config_notificaciones(dict(DEFAULT_CONFIG))
        st.success(t("notificaciones.restaurado_ok"))
        st.rerun()
