"""
Pantalla del abanico interactivo de tarjetas (wallet view).

Detalle con gráfico de torta, bloques de consumo y línea de fechas.
"""

from __future__ import annotations

import streamlit as st

from app.components.charts import (
    render_grafico_fechas,
    render_grafico_limite,
    render_panel_validacion_ciclo,
    render_prueba_escenario_ciclo,
)
from app.components.theme import ESTADO_COLORS
from app.core.tarjetas import EstadoSalud, listar_tarjetas
from app.i18n.translator import t
from app.ui.helpers import language_selector, render_abanico_tarjetas, render_resumen_financiero


def _estado_label(estado: EstadoSalud) -> str:
    return {
        EstadoSalud.POSITIVO: t("pantalla_lista_tarjetas.estado_positivo"),
        EstadoSalud.MEDIO: t("pantalla_lista_tarjetas.estado_medio"),
        EstadoSalud.NEGATIVO: t("pantalla_lista_tarjetas.estado_negativo"),
    }[estado]


def render(on_back, on_add, on_edit) -> None:
    language_selector()
    tarjetas = listar_tarjetas()

    st.title(t("pantalla_lista_tarjetas.titulo"))

    if not tarjetas:
        st.info(t("pantalla_lista_tarjetas.sin_tarjetas"))
        if st.button(t("pantalla_inicio.empty_cta"), key="add_empty", type="primary", use_container_width=True):
            on_add()
        if st.button(t("common.volver"), key="back_empty"):
            on_back()
        return

    sel_key = "fan_sel"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = 0
    sel = min(st.session_state[sel_key], len(tarjetas) - 1)

    st.caption(t("pantalla_lista_tarjetas.subtitulo_abanico"))

    sel = render_abanico_tarjetas(tarjetas, sel_key, key_prefix="lista")

    tarjeta = tarjetas[sel]
    render_resumen_financiero(tarjeta)
    render_panel_validacion_ciclo(tarjeta)
    estado = tarjeta.estado_salud()
    color = ESTADO_COLORS[estado.value]

    st.markdown(
        f'<span class="ti-badge" style="background:{color};">{_estado_label(estado)}</span> '
        f'<strong style="color:#F8FAFC;margin-left:0.5rem;">{tarjeta.nombre}</strong> · {tarjeta.banco}',
        unsafe_allow_html=True,
    )

    render_grafico_limite(tarjeta)
    render_grafico_fechas(tarjeta)

    with st.expander(t("pantalla_lista_tarjetas.prueba_escenario_titulo")):
        render_prueba_escenario_ciclo()

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(t("common.volver"), key="back_fan"):
            on_back()
    with c2:
        if st.button(t("common.editar"), key="edit_fan"):
            on_edit(tarjeta.id)
    with c3:
        if st.button(t("pantalla_inicio.boton_agregar_tarjeta"), key="add_fan"):
            on_add()


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    st.session_state.unlocked = True

    def back() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    def add() -> None:
        st.session_state.pagina = "registrar"
        st.rerun()

    def edit(tarjeta_id: str) -> None:
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

    render(back, add, edit)


if __name__ == "__main__":
    main()
