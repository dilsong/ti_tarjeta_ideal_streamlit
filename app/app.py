"""
Punto de entrada principal — navegación y flujo de la app.

Ejecutar desde la raíz del proyecto:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from app.ui.app_editar_tarjeta import render as render_editar
from app.ui.app_inicio import render as render_inicio
from app.ui.app_registrar_tarjeta import render as render_registrar
from app.ui.helpers import init_i18n, render_licencia_expirada, render_pin_gate, setup_page
from app.core.fechas import hoy
from app.core.licencia import licencia_expirada
from app.core.seguridad import pin_configurado
from app.components.push_notificaciones import disparar_push_si_permitido, listar_alertas_push_hoy, registrar_pwa
from notificaciones.notificador_ciclos import ejecutar_notificaciones_diarias

_AUTH_KEY = "autenticado"


def main() -> None:
    setup_page()

    from app.core.browser_store import hydrate_from_localstorage, storage_ready

    hydrate_from_localstorage()
    # Esperar a que el bridge de localStorage entregue el bundle (sin tocar la URL)
    if not storage_ready():
        st.caption("Cargando…")
        return

    init_i18n()

    if licencia_expirada():
        render_licencia_expirada()
        return

    from app.core.arranque import asegurar_arranque_limpio_sin_pin

    asegurar_arranque_limpio_sin_pin()

    if _AUTH_KEY not in st.session_state:
        st.session_state[_AUTH_KEY] = False
    # Compat con pantallas que aún leen unlocked
    if "unlocked" not in st.session_state:
        st.session_state.unlocked = False

    if "pagina" not in st.session_state:
        st.session_state.pagina = "inicio"

    # Sesión viva solo en memoria: sin PIN en storage → nunca autenticado
    if st.session_state.get(_AUTH_KEY) and not pin_configurado():
        st.session_state[_AUTH_KEY] = False
        st.session_state.unlocked = False

    def unlock() -> None:
        if not pin_configurado():
            st.session_state[_AUTH_KEY] = False
            st.session_state.unlocked = False
            return
        st.session_state[_AUTH_KEY] = True
        st.session_state.unlocked = True
        st.rerun()

    autenticado = bool(st.session_state.get(_AUTH_KEY)) and pin_configurado()

    if not autenticado:
        st.session_state[_AUTH_KEY] = False
        st.session_state.unlocked = False
        if not pin_configurado():
            st.info(
                "Primer uso: crea tu PIN de seguridad (4 a 6 dígitos). "
                "Quedará guardado en este dispositivo; no tendrás que crearlo de nuevo."
            )
        render_pin_gate(unlock)
        return

    if st.session_state.get("notificaciones_enviadas_fecha") != hoy().isoformat():
        ejecutar_notificaciones_diarias()
        st.session_state.notificaciones_enviadas_fecha = hoy().isoformat()

    alertas_push = listar_alertas_push_hoy()
    registrar_pwa()
    disparar_push_si_permitido(alertas_push, f"push_native_{hoy().isoformat()}")

    def navigate(pagina: str) -> None:
        st.session_state.pagina = pagina
        st.rerun()

    def navigate_editar(tarjeta_id: str) -> None:
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
