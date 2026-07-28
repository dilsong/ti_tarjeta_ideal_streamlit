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

    # Data por dispositivo (?ti= en la URL) antes de PIN / i18n / pantallas.
    from app.core.browser_store import hydrate_from_localstorage, use_browser_storage

    hydrate_from_localstorage()

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
            from app.core.browser_store import has_url_state

            if has_url_state():
                st.success(
                    "Tus datos están en este enlace (se ve &s= en la barra). "
                    "Usa SIEMPRE este favorito para volver."
                )
            else:
                st.warning(
                    "Paso importante: crea tu PIN, luego mira la barra de direcciones. "
                    "Cuando aparezca &s= (enlace más largo), VUELVE a guardar ese favorito. "
                    "Si guardas solo ?ti= sin &s=, al volver te pedirá crear PIN otra vez."
                )
            warn = st.session_state.get("ti_url_state_warn")
            if warn:
                st.error(warn)
        else:
            st.warning(
                "Modo Lab (disco del servidor): todos ven el mismo PIN/datos. "
                "En Streamlit Cloud quita el secret TI_USE_FILESYSTEM y redespliega."
            )
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
