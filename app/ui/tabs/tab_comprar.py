from __future__ import annotations

import streamlit as st

from app.components.keyboard_numeric import monto_text_input
from app.core.ciclo import calcular_disponibilidad
from app.core.consumos import registrar_consumo
from app.core.recomendador import evaluar_tarjeta_abanico, generar_frase_compra_corta, recomendar_tarjeta
from app.core.tarjetas import Tarjeta
from app.i18n.translator import t


def _render_registro_consumo(rec: dict) -> None:
    st.markdown(f"**{t('pantalla_inicio.usar_monto_tarjeta', nombre=rec['nombre'])}** · ${rec['monto']:,.2f}")

    tienda = st.text_input(
        t("pantalla_inicio.tienda_razon"),
        key="tienda_razon_consumo",
        placeholder=t("pantalla_inicio.tienda_razon_placeholder"),
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("common.cancelar"), key="cancel_consumo"):
            st.session_state.pop("mostrar_registro_consumo", None)
            st.rerun()
    with c2:
        if st.button(t("pantalla_inicio.confirmar_consumo"), key="confirm_consumo", type="primary", use_container_width=True):
            registrar_consumo(rec["id_tarjeta"], rec["monto"], tienda or None)
            st.session_state.pop("ultima_rec", None)
            st.session_state.pop("mostrar_registro_consumo", None)
            st.success(t("pantalla_inicio.consumo_registrado"))
            st.rerun()


def _guardar_rec(tarjeta: Tarjeta, monto: float, mensaje: str, origen: str, frase_corta: str = "") -> None:
    st.session_state["ultima_rec"] = {
        "id_tarjeta": tarjeta.id,
        "nombre": tarjeta.nombre,
        "monto": monto,
        "mensaje": mensaje,
        "frase_corta": frase_corta,
        "origen": origen,
    }
    st.session_state.pop("ultima_rec_error", None)
    st.session_state.pop("mostrar_registro_consumo", None)


def _calcular_recomendacion(tarjetas, monto: float) -> None:
    rec = recomendar_tarjeta(tarjetas, monto)
    if rec.tarjeta:
        _guardar_rec(rec.tarjeta, monto, rec.mensaje, "recomendada", rec.frase_corta)
        idx = next((i for i, tj in enumerate(tarjetas) if tj.id == rec.tarjeta.id), None)
        if idx is not None:
            from app.ui.helpers import TARJETA_SEL_KEY

            st.session_state[TARJETA_SEL_KEY] = idx
    else:
        st.session_state.pop("ultima_rec", None)
        st.session_state.pop("mostrar_registro_consumo", None)
        st.session_state["ultima_rec_error"] = rec.mensaje


def _evaluar_abanico(tarjeta_sel: Tarjeta, monto: float) -> None:
    ev = evaluar_tarjeta_abanico(tarjeta_sel, monto)
    frase = generar_frase_compra_corta(tarjeta_sel, monto)
    _guardar_rec(tarjeta_sel, monto, ev.resumen, "abanico", frase)


def _render_disponibles_compra(tarjetas: list[Tarjeta], tarjeta_sel: Tarjeta) -> None:
    from html import escape

    chips = []
    for tj in tarjetas:
        disp = calcular_disponibilidad(tj)
        sel = " ti-disp-chip--sel" if tj.id == tarjeta_sel.id else ""
        chips.append(
            f'<span class="ti-disp-chip{sel}">'
            f"{escape(tj.nombre)} · <strong>${disp:,.2f}</strong></span>"
        )
    st.markdown(f'<div class="ti-disp-row">{"".join(chips)}</div>', unsafe_allow_html=True)
    st.caption(t("asesor_compra.disponible_ahora"))


def _render_resultado_compra(ultima: dict, tarjeta_sel: Tarjeta, monto: float) -> None:
    from html import escape

    frase = ultima.get("frase_corta") or ultima.get("mensaje", "")
    tarjeta_rec = ultima.get("id_tarjeta")
    from app.core.tarjetas import obtener_tarjeta

    tj = obtener_tarjeta(tarjeta_rec) if tarjeta_rec else None
    puede = tj is not None and calcular_disponibilidad(tj) >= monto
    cls = "ti-compra-resultado" if puede else "ti-compra-resultado ti-compra-resultado--warn"
    origen = ultima.get("origen", "recomendada")

    if origen == "abanico":
        _render_pros_contras(tarjeta_sel, monto)
    elif ultima.get("id_tarjeta") == tarjeta_sel.id:
        st.markdown(
            f'<div style="background:#14532D;border:1px solid #22C55E;border-radius:10px;'
            f'padding:0.5rem 0.75rem;margin-bottom:0.5rem;color:#BBF7D0;">'
            f'★ {t("tabs.comprar_recomendada")}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="{cls}"><strong>{escape(frase)}</strong></div>',
        unsafe_allow_html=True,
    )
    if ultima.get("mensaje") and ultima.get("mensaje") != frase:
        st.caption(ultima["mensaje"])


def _render_pros_contras(tarjeta_sel: Tarjeta, monto: float) -> None:
    ev = evaluar_tarjeta_abanico(tarjeta_sel, monto)
    st.markdown(
        f'<div style="background:#1E3A5F;border:1px solid #3B82F6;border-radius:10px;'
        f'padding:0.5rem 0.75rem;margin-bottom:0.5rem;color:#BFDBFE;">'
        f'💳 {t("tabs.comprar_abanico_sel")}: <strong>{tarjeta_sel.nombre}</strong> · {tarjeta_sel.banco}'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.info(ev.resumen)

    if ev.pros:
        st.markdown(f"**{t('tabs.comprar_pros')}**")
        for pro in ev.pros:
            st.markdown(
                f'<div style="background:#14532D;border-left:3px solid #22C55E;border-radius:6px;'
                f'padding:0.4rem 0.65rem;margin-bottom:0.3rem;color:#BBF7D0;font-size:0.9rem;">'
                f"✓ {pro}</div>",
                unsafe_allow_html=True,
            )

    if ev.contras:
        st.markdown(f"**{t('tabs.comprar_contras')}**")
        for contra in ev.contras:
            st.markdown(
                f'<div style="background:#422006;border-left:3px solid #EAB308;border-radius:6px;'
                f'padding:0.4rem 0.65rem;margin-bottom:0.3rem;color:#FEF9C3;font-size:0.9rem;">'
                f"⚠ {contra}</div>",
                unsafe_allow_html=True,
            )

    if not ev.puede_comprar:
        st.error(t("tabs.comprar_contra_decision"))


def render(tarjetas: list[Tarjeta], tarjeta_sel: Tarjeta) -> None:
    _render_disponibles_compra(tarjetas, tarjeta_sel)
    monto = monto_text_input(t("pantalla_inicio.monto_compra"), "monto_compra")

    c_rec, c_ab = st.columns(2)
    with c_rec:
        if st.button(t("pantalla_inicio.boton_recomendar"), key="recomendar", type="primary", use_container_width=True):
            _calcular_recomendacion(tarjetas, monto)
            st.rerun()
    with c_ab:
        if st.button(t("tabs.comprar_boton_abanico"), key="abanico_comprar", use_container_width=True):
            if monto <= 0:
                st.session_state.pop("ultima_rec", None)
                st.session_state["ultima_rec_error"] = t("tabs.comprar_monto_invalido")
            else:
                _evaluar_abanico(tarjeta_sel, monto)
            st.rerun()

    err = st.session_state.get("ultima_rec_error")
    if err:
        st.warning(err)

    ultima = st.session_state.get("ultima_rec")
    if ultima and ultima.get("monto") == monto:
        with st.container():
            _render_resultado_compra(ultima, tarjeta_sel, monto)

            if st.button(t("pantalla_inicio.boton_usar_monto"), key="usar_monto", type="primary", use_container_width=True):
                st.session_state["mostrar_registro_consumo"] = True
                st.rerun()

            if st.session_state.get("mostrar_registro_consumo"):
                _render_registro_consumo(ultima)
