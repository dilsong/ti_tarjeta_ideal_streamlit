"""
Pantalla principal de Tarjeta Ideal — hub con abanico global y solapas.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.components.caja_alerta import html_cuadro_deuda_clara, render_caja_alerta
from app.components.theme import CARD_COLORS
from app.core.asesor_diario import generar_brief_tarjeta
from app.components.dialogo_pago_banco import confirmar_pago_en_banco
from app.core.estrategia_deuda import MONTO_EXTRA_DEFAULT, recomendar_abono_extra
from app.core.pagos import calcular_sugerencia_abono
from app.core.salud_tarjeta import tiene_atraso
from app.core.tarjetas import listar_tarjetas
from app.i18n.translator import get_language, t
from app.ui.helpers import render_abanico_global, render_page_header
from app.ui.tabs import (
    tab_configurar_tarjetas,
    tab_guia,
    tab_mejor_opcion,
    tab_mis_tarjetas,
    tab_reportes,
)
from notificaciones.notificador_ciclos import evaluar_notificaciones_tarjeta


def _dinero(valor: float) -> str:
    return f"${valor:,.2f}"


def _render_banner_alerta(texto: str, nivel: str) -> None:
    """Banner con HTML — st.warning interpreta $ como LaTeX y rompe el texto."""
    render_caja_alerta(texto, nivel)


def _mensaje_sugerencia(sug) -> tuple[str, str]:
    monto = _dinero(sug.monto)
    deuda = _dinero(sug.deuda_ciclo)

    if sug.escenario == "past_due":
        principal = t(
            "banner_sugerencia.past_due_urgente",
            monto=monto,
            dias=sug.dias_restantes,
        )
        secundaria = t("banner_sugerencia.past_due_nota_ciclo", ciclo=deuda)
        return f"{principal}\n\n{secundaria}", ""

    if sug.escenario == "ciclo_pendiente":
        if sug.es_pago_total:
            principal = t(
                "banner_sugerencia.ciclo_pendiente_total",
                deuda=deuda,
                monto=monto,
                dias=sug.dias_restantes,
            )
        else:
            principal = t(
                "banner_sugerencia.ciclo_pendiente_parcial",
                deuda=deuda,
                monto=monto,
                despues=_dinero(sug.foto_despues),
            )
        secundaria = (
            t("banner_sugerencia.recomienda_pago_historial", monto=monto)
            if sug.usa_historial
            else t("banner_sugerencia.nota_interes_ya_genera")
        )
    else:
        if sug.usa_historial:
            principal = t(
                "banner_sugerencia.ciclo_abierto_historial",
                monto=monto,
                antes=_dinero(sug.foto_antes),
                despues=_dinero(sug.foto_despues),
            )
        else:
            principal = t(
                "banner_sugerencia.ciclo_abierto_base",
                monto=monto,
                antes=_dinero(sug.foto_antes),
                despues=_dinero(sug.foto_despues),
            )
        secundaria = t("banner_sugerencia.recomienda_historial", monto=monto) if sug.usa_historial else ""
    return principal, secundaria


def _render_boton_abono(tarjeta, sugerencia, msg_key: str) -> None:
    st.caption(t("banner_sugerencia.aviso_no_banco"))
    monto_btn = _dinero(sugerencia.monto)
    etiqueta_boton = (
        t("banner_sugerencia.boton_pago_total", monto=monto_btn)
        if sugerencia.es_pago_total
        else t("banner_sugerencia.boton_pago_parcial", monto=monto_btn)
        if sugerencia.escenario == "ciclo_pendiente"
        else t("banner_sugerencia.boton_abono", monto=monto_btn)
    )
    if st.button(
        etiqueta_boton,
        key=f"banner_abono_{tarjeta.id}",
        type="primary",
        use_container_width=True,
    ):
        confirmar_pago_en_banco(
            tarjeta,
            tipo="abono",
            monto_txt=monto_btn,
            monto=sugerencia.monto,
            es_pago_total=sugerencia.es_pago_total,
            escenario=sugerencia.escenario,
            msg_key=msg_key,
        )


def _borde_asesor(tarjeta) -> str:
    """Color del borde del asesor = color exacto de la tarjeta del abanico."""
    return CARD_COLORS.get(getattr(tarjeta, "color", "") or "azul", CARD_COLORS["azul"])


def _render_prioridad_unificada(tarjeta) -> None:
    """
    Un solo cuadro de prioridad para la tarjeta del abanico + botón de acción.
    Con Past Due: VENCIDO (HOY) + CICLO ACTUAL, sin banners duplicados.
    """
    msg_key = f"banner_abono_ok_{tarjeta.id}"
    if msg_key in st.session_state:
        st.success(st.session_state.pop(msg_key))

    brief = generar_brief_tarjeta(tarjeta)
    sugerencia = calcular_sugerencia_abono(tarjeta)
    notif = evaluar_notificaciones_tarjeta(tarjeta)
    borde = _borde_asesor(tarjeta)

    if tiene_atraso(tarjeta):
        deuda_html = html_cuadro_deuda_clara(tarjeta, get_language(), envolver=False)
        nota_vieja = ""
        if brief.datos_desactualizados:
            nota_vieja = (
                f'<div class="ti-asesor-msg" style="margin-top:0.65rem;opacity:0.9;">'
                f"{escape(t('asesor_diario.datos_viejos', dias=brief.dias_sin_actividad))}"
                f"</div>"
            )
        st.markdown(
            f'<div class="ti-asesor-hoy" style="border-left:4px solid {borde};">'
            f'<div class="ti-asesor-saludo">{escape(brief.saludo)}</div>'
            f"{deuda_html or ''}"
            f"{nota_vieja}"
            f"</div>",
            unsafe_allow_html=True,
        )
        if sugerencia:
            _render_boton_abono(tarjeta, sugerencia, msg_key)
        return

    # Sin Past Due: brief del asesor (borde = color de la tarjeta del abanico)
    st.markdown(
        f'<div class="ti-asesor-hoy" style="border-left:4px solid {borde};">'
        f'<div class="ti-asesor-saludo">{escape(brief.saludo)}</div>'
        f'<div class="ti-asesor-msg">{escape(brief.mensaje)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    if sugerencia:
        # El brief ya habla del pago; solo botón + caption (sin segundo banner rojo)
        if brief.tono not in ("urgente", "atencion") or sugerencia.escenario == "ciclo_abierto":
            principal, secundaria = _mensaje_sugerencia(sugerencia)
            cuerpo = principal
            if secundaria:
                cuerpo = f"{principal}\n\n{secundaria}"
            if notif and not notif.urgente:
                cuerpo = f"{cuerpo}\n\n{notif.mensaje}"
            nivel = (
                "urgente"
                if sugerencia.urgente or sugerencia.escenario == "past_due"
                else "warn"
                if sugerencia.escenario == "ciclo_pendiente"
                else "info"
            )
            _render_banner_alerta(cuerpo, nivel)
        _render_boton_abono(tarjeta, sugerencia, msg_key)
        return

    if notif:
        _render_banner_alerta(notif.mensaje, "urgente" if notif.urgente else "info")


def _render_tip_estrategia(tarjetas, tarjeta_sel) -> None:
    """
    Tip Avalancha solo si aporta info NUEVA: otra tarjeta distinta a la del abanico.
    """
    if len(tarjetas) < 2:
        return
    tip = recomendar_abono_extra(tarjetas, MONTO_EXTRA_DEFAULT)
    if not tip:
        return
    if tip.tarjeta.id == tarjeta_sel.id:
        return
    st.markdown(f"**{t('estrategia.titulo')}**")
    _render_banner_alerta(tip.mensaje, "urgente" if tip.urgente else "info")


def _render_empty(on_navigate) -> None:
    render_page_header(t("pantalla_inicio.empty_titulo"))
    st.info(t("pantalla_inicio.empty_subtitulo"))

    for key in ("empty_beneficio_1", "empty_beneficio_2", "empty_beneficio_3", "empty_beneficio_4"):
        st.markdown(f'<div class="ti-benefit">✦ {t(f"pantalla_inicio.{key}")}</div>', unsafe_allow_html=True)

    if st.button(t("pantalla_inicio.empty_cta"), key="empty_cta", type="primary", use_container_width=True):
        on_navigate("registrar")


def _render_with_cards(on_navigate, on_edit) -> None:
    tarjetas = listar_tarjetas()

    render_page_header(
        t("pantalla_inicio.titulo"),
        t("pantalla_lista_tarjetas.subtitulo_abanico"),
    )

    sel = render_abanico_global(tarjetas)
    tarjeta_sel = tarjetas[sel]

    # Un solo bloque de prioridad + botón (sin banners duplicados arriba)
    _render_prioridad_unificada(tarjeta_sel)
    # Tip solo si apunta a OTRA tarjeta
    _render_tip_estrategia(tarjetas, tarjeta_sel)

    main_ids = ("mejor", "tarjetas", "guia", "config", "reportes")
    main_labels = {
        "mejor": t("tabs.mejor_opcion"),
        "tarjetas": t("tabs.tarjetas"),
        "guia": t("tabs.guia"),
        "config": t("tabs.configurar"),
        "reportes": t("tabs.reportes"),
    }
    if "ti_main_tab" not in st.session_state:
        st.session_state["ti_main_tab"] = "mejor"

    st.markdown('<span class="ti-persist-tabs-marker"></span>', unsafe_allow_html=True)
    active = st.radio(
        "main_nav",
        main_ids,
        format_func=lambda tid: main_labels[tid],
        horizontal=True,
        label_visibility="collapsed",
        key="ti_main_tab",
    )

    ayudas = {
        "mejor": t("tabs.ayuda_mejor"),
        "tarjetas": t("tabs.ayuda_tarjetas"),
        "guia": t("tabs.ayuda_guia"),
        "config": t("tabs.ayuda_config"),
        "reportes": t("tabs.ayuda_reportes"),
    }
    st.caption(ayudas.get(active, ""))

    if active == "mejor":
        tab_mejor_opcion.render(tarjetas, tarjeta_sel)
    elif active == "tarjetas":
        tab_mis_tarjetas.render(tarjeta_sel)
    elif active == "guia":
        tab_guia.render(tarjeta_sel)
    elif active == "config":
        tab_configurar_tarjetas.render(
            tarjeta_sel,
            on_edit,
            lambda: on_navigate("registrar"),
        )
    else:
        tab_reportes.render()


def render(on_navigate, on_edit) -> None:
    tarjetas = listar_tarjetas()
    if not tarjetas:
        _render_empty(on_navigate)
    else:
        _render_with_cards(on_navigate, on_edit)


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    if "pagina" not in st.session_state:
        st.session_state.pagina = "inicio"
    st.session_state.autenticado = True
    st.session_state.unlocked = True

    def nav(p: str) -> None:
        st.session_state.pagina = p
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

    render(nav, edit)


if __name__ == "__main__":
    main()
