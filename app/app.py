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
from app.ui.helpers import init_i18n, render_licencia_expirada, render_pin_gate, setup_page
from app.core.fechas import hoy
from app.core.licencia import licencia_expirada
from app.core.seguridad import pin_configurado
from app.components.push_notificaciones import disparar_push_si_permitido, listar_alertas_push_hoy, registrar_pwa
from notificaciones.notificador_ciclos import ejecutar_notificaciones_diarias


def main() -> None:
    setup_page()

    # Data por dispositivo (?ti= en la URL) antes de licencia / PIN / pantallas.
    from app.core.browser_store import hydrate_from_localstorage, use_browser_storage

    hydrate_from_localstorage()
    init_i18n()

    # 1) Licencia de prueba — bloqueo total si expiró
    if licencia_expirada():
        render_licencia_expirada()
        return

    # 2) Primer uso: sin PIN → tablas vacías (registro 2 pasos desde cero)
    from app.core.arranque import asegurar_arranque_limpio_sin_pin

    asegurar_arranque_limpio_sin_pin()

    if "unlocked" not in st.session_state:
        st.session_state.unlocked = False
    if "pagina" not in st.session_state:
        st.session_state.pagina = "inicio"

    # Nunca mantener sesión desbloqueada sin PIN configurado
    if st.session_state.unlocked and not pin_configurado():
        st.session_state.unlocked = False

    def unlock() -> None:
        if not pin_configurado():
            st.session_state.unlocked = False
            return
        st.session_state.unlocked = True
        st.rerun()

    # 3) Monousuario: toda la UI detrás del PIN
    if not st.session_state.unlocked or not pin_configurado():
        st.session_state.unlocked = False
        if use_browser_storage():
            from app.core.browser_store import has_url_state

            if has_url_state() and pin_configurado():
                st.success(
                    "Tus datos están en este enlace (se ve &s= en la barra). "
                    "Usa SIEMPRE este favorito para volver."
                )
            elif not pin_configurado():
                st.info(
                    "Primer uso: crea tu PIN (4 a 6 dígitos). "
                    "La app inicia sin tarjetas para que registres desde cero."
                )
            else:
                st.warning(
                    "Paso importante: tras desbloquear, mira la barra de direcciones. "
                    "Cuando aparezca &s=, guarda ese favorito."
                )
            warn = st.session_state.get("ti_url_state_warn")
            if warn:
                st.error(warn)
        else:
            st.info("Modo Lab: usando archivos en app/data/ (PIN y tarjetas de este PC).")
        render_pin_gate(unlock)
        return

    if st.session_state.pop("ti_pedir_guardar_favorito", False):
        st.warning(
            "PIN creado. Mira la barra de direcciones: debe verse **&s=** (enlace largo). "
            "Guarda ESE favorito ahora (borra el anterior si solo tenía ?ti=). "
            "Si no, al volver te pedirá crear PIN otra vez."
        )

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
