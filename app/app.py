"""
Punto de entrada principal — navegación y flujo de la app.

Ejecutar desde la raíz del proyecto:
    streamlit run streamlit_app.py

(No usar streamlit run app/app.py — conflicto de imports en Python.)
"""

from __future__ import annotations

import streamlit as st

from app.ui.app_editar_tarjeta import render as render_editar
from app.ui.app_inicio import render as render_inicio
from app.ui.app_registrar_tarjeta import render as render_registrar
from app.ui.helpers import init_i18n, render_pin_gate, setup_page
from app.core.fechas import hoy
from app.components.push_notificaciones import disparar_push_si_permitido, listar_alertas_push_hoy
from notificaciones.notificador_ciclos import ejecutar_notificaciones_diarias


def main() -> None:
    setup_page()

    # Data por dispositivo: hidratar localStorage antes de PIN / i18n / pantallas.
    from app.core.browser_store import hydrate_from_localstorage, use_browser_storage

    hydrate_from_localstorage()  # puede st.stop() mientras carga el JS

    init_i18n()

    if "unlocked" not in st.session_state:
        st.session_state.unlocked = False
    if "pagina" not in st.session_state:
        st.session_state.pagina = "inicio"

    def unlock() -> None:
        st.session_state.unlocked = True
        st.rerun()

    if not st.session_state.unlocked:
        if use_browser_storage():
            st.success("Modo piloto: data solo en este teléfono/navegador.")
        else:
            st.warning(
                "Modo Lab (disco del servidor): todos ven el mismo PIN/datos. "
                "En Streamlit Cloud quita el secret TI_USE_FILESYSTEM y redespliega."
            )
        render_pin_gate(unlock)
        return

    if st.session_state.get("notificaciones_enviadas_fecha") != hoy().isoformat():
        ejecutar_notificaciones_diarias()
        st.session_state.notificaciones_enviadas_fecha = hoy().isoformat()

    alertas_push = listar_alertas_push_hoy()
    disparar_push_si_permitido(alertas_push, f"push_native_{hoy().isoformat()}")

    def navigate(pagina: str) -> None:
        st.session_state.pagina = pagina
        st.rerun()

    def navigate_editar(tarjeta_id: str) -> None:
        # Recargar formulario desde la tarjeta guardada (preferencia, límite, etc.)
        st.session_state.pop("edit_tarjeta_id", None)
        for key in (
            "edit_limite",
            "edit_adeudado",
            "edit_corte",
            "edit_pago",
            "edit_preferencia_banco",
            "edit_digitos",
            "edit_url_app_banco",
            "seg_edit_estilo",
        ):
            st.session_state.pop(key, None)
        st.session_state.editar_tarjeta_id = tarjeta_id
        st.session_state.pagina = "editar"
        st.rerun()

    pagina = st.session_state.pagina

    if pagina == "registrar":
        render_registrar(lambda: navigate("inicio"), lambda: navigate("inicio"))
    elif pagina == "editar":
        tarjeta_id = st.session_state.get("editar_tarjeta_id", "")
        render_editar(lambda: navigate("inicio"), lambda: navigate("inicio"), tarjeta_id)
    else:
        render_inicio(navigate, navigate_editar)
