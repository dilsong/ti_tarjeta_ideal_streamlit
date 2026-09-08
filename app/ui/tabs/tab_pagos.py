from __future__ import annotations

import streamlit as st

from app.components.caja_alerta import render_cuadro_deuda_clara, render_caja_alerta
from app.components.intereses_panel import render_panel_intereses
from app.components.pagos_estatus import render_actualizar_estatus
from app.components.theme import CARD_COLORS, ESTADO_COLORS
from app.core.estrategia_deuda import MONTO_EXTRA_DEFAULT, recomendar_abono_extra
from app.core.fechas import formatear_fecha
from app.core.salud_tarjeta import evaluar_prioridad_pago, fmt_dinero, tiene_atraso
from app.core.tarjetas import EstadoSalud, Tarjeta, listar_tarjetas
from app.core.validacion_ciclo import validar_ciclo_con_intereses
from app.i18n.translator import get_language, t
from app.ui.helpers import TARJETA_SEL_KEY, fila_accion
from app.ui.tabs._badges import _label_salud, estado_riesgo_pago


def _urgencia_score(tarjeta: Tarjeta) -> tuple[int, int, float, float]:
    estado = validar_ciclo_con_intereses(tarjeta)
    mora = 0 if tiene_atraso(tarjeta) else 1
    return (
        mora,
        estado.dias_hasta_pago,
        -estado.monto_adeudado_ciclo_anterior,
        -estado.consumos_ciclo_actual,
    )


def _bordes_tarjeta(seleccionada: bool, color_tarjeta: str) -> str:
    if seleccionada:
        return (
            f"border-top:2px solid #6366F1;border-right:2px solid #6366F1;"
            f"border-bottom:2px solid #6366F1;border-left:5px solid {color_tarjeta};"
        )
    return (
        f"border-top:1px solid #334155;border-right:1px solid #334155;"
        f"border-bottom:1px solid #334155;border-left:5px solid {color_tarjeta};"
    )


def _html_tarjeta_pago(
    tarjeta: Tarjeta,
    tarjeta_sel: Tarjeta,
    estado,
    riesgo: EstadoSalud,
    idioma: str,
) -> str:
    color_tarjeta = CARD_COLORS.get(tarjeta.color, CARD_COLORS["azul"])
    seleccionada = tarjeta.id == tarjeta_sel.id
    bordes = _bordes_tarjeta(seleccionada, color_tarjeta)
    monto = estado.monto_adeudado_ciclo_anterior
    acum = estado.consumos_ciclo_actual
    riesgo_color = ESTADO_COLORS[riesgo.value]
    pago_txt = (
        formatear_fecha(estado.fecha_pago_proximo, idioma)
        if estado.fecha_pago_proximo
        else "—"
    )
    if tiene_atraso(tarjeta):
        prio = evaluar_prioridad_pago(tarjeta)
        monto_html = (
            f'<div class="ti-deuda-etiq">{t("salud_tarjeta.etiq_vencido")}</div>'
            f'<span style="color:#EF4444;font-weight:700;font-size:1.35rem;">'
            f'{fmt_dinero(prio.monto_urgente)}</span>'
            f'<div style="color:#94A3B8;font-size:0.78rem;margin-top:0.35rem;line-height:1.35;">'
            f'{t("salud_tarjeta.etiq_vencido_corto")}</div>'
            f'<div style="color:#64748B;font-size:0.75rem;margin-top:0.5rem;">'
            f'{t("salud_tarjeta.etiq_ciclo")}: {fmt_dinero(prio.monto_ciclo)}</div>'
        )
        dias_html = (
            f'<span style="color:#EF4444;font-weight:600;font-size:0.82rem;text-align:right;'
            f'line-height:1.35;">{t("tabs.pagos_mora_hoy", dias=prio.dias_atraso_mora)}</span>'
        )
    else:
        monto_html = (
            f'<div class="ti-deuda-etiq">{t("salud_tarjeta.etiq_ciclo")}</div>'
            f'<span style="color:#EF4444;font-weight:700;font-size:1.35rem;">'
            f'{fmt_dinero(monto)}</span>'
            f'<div style="color:#94A3B8;font-size:0.78rem;margin-top:0.35rem;line-height:1.35;">'
            f'{t("salud_tarjeta.etiq_ciclo_sub", pago=pago_txt, dias=estado.dias_hasta_pago)}</div>'
        )
        dias_html = (
            f'<span style="color:#E2E8F0;font-size:0.9rem;text-align:right;">'
            f'{estado.dias_hasta_pago} {t("tabs.pagos_dias")}<br/>{pago_txt}</span>'
        )
    acum_html = ""
    if acum > 0:
        acum_html = (
            f'<div style="color:#6366F1;font-size:0.82rem;margin-top:0.35rem;font-weight:600;">'
            f'{t("tabs.pagos_etiq_acumulando")}: {fmt_dinero(acum)}</div>'
        )

    return (
        f'<div style="background:#1E293B;border-radius:12px;padding:0.75rem 1rem;margin-bottom:0.5rem;'
        f'{bordes}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<strong style="color:#F8FAFC;font-size:1.05rem;">{tarjeta.nombre}</strong>'
        f'<span class="ti-badge" style="background:{riesgo_color};">{_label_salud(riesgo)}</span></div>'
        f'<div style="color:#94A3B8;font-size:0.85rem;margin-top:0.35rem;">'
        f'{tarjeta.banco} · •••• {tarjeta.ultimos_digitos}</div>'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:0.5rem;">'
        f'<div>{monto_html}{acum_html}</div>{dias_html}'
        f'</div></div>'
    )


def _render_lista_tarjetas(tarjetas: list[Tarjeta], tarjeta_sel: Tarjeta, idioma: str) -> None:
    ordenadas = sorted(tarjetas, key=_urgencia_score)

    for tarjeta in ordenadas:
        estado = validar_ciclo_con_intereses(tarjeta)
        riesgo = estado_riesgo_pago(tarjeta)
        idx = next(i for i, tj in enumerate(tarjetas) if tj.id == tarjeta.id)

        with fila_accion(11, 1) as (c_card, c_sel):
            with c_card:
                st.markdown(
                    _html_tarjeta_pago(tarjeta, tarjeta_sel, estado, riesgo, idioma),
                    unsafe_allow_html=True,
                )
            with c_sel:
                if st.button("›", key=f"pagos_sel_{tarjeta.id}", help=t("tabs.pagos_ver_detalle")):
                    st.session_state[TARJETA_SEL_KEY] = idx
                    st.rerun()
        st.markdown("<div style='height:0.15rem;'></div>", unsafe_allow_html=True)


def _render_mensaje_estado(estado_sel, riesgo_sel: EstadoSalud, tarjeta: Tarjeta, idioma: str) -> None:
    deuda = estado_sel.monto_adeudado_ciclo_anterior
    acum = estado_sel.consumos_ciclo_actual
    pago_txt = formatear_fecha(estado_sel.fecha_pago_proximo, idioma) if estado_sel.fecha_pago_proximo else "—"

    if tiene_atraso(tarjeta):
        render_cuadro_deuda_clara(tarjeta, idioma)
        return

    if deuda <= 0 and acum <= 0:
        st.success(t("tabs.pagos_sin_deuda"))
    elif deuda <= 0 and acum > 0:
        render_caja_alerta(
            t("tabs.pagos_sin_deuda_con_acumulado", monto=fmt_dinero(acum)),
            "info",
        )
    elif riesgo_sel == EstadoSalud.NEGATIVO:
        render_caja_alerta(
            t("tabs.pagos_urgente", monto=fmt_dinero(deuda), dias=estado_sel.dias_hasta_pago),
            "urgente",
        )
    elif riesgo_sel == EstadoSalud.MEDIO and estado_sel.dias_hasta_pago <= 7:
        render_caja_alerta(
            t("tabs.pagos_atencion", monto=fmt_dinero(deuda), dias=estado_sel.dias_hasta_pago),
            "warn",
        )
    elif deuda > 0:
        render_caja_alerta(
            t(
                "tabs.pagos_tranquilo",
                monto=fmt_dinero(deuda),
                dias=estado_sel.dias_hasta_pago,
                pago=pago_txt,
            ),
            "info",
        )


def render(tarjeta_sel: Tarjeta, *, compacto: bool = False, key_prefix: str = "") -> None:
    tarjetas = listar_tarjetas()
    idioma = get_language()

    if compacto:
        st.markdown(f"**{t('tabs.pagos_detalle')} · {tarjeta_sel.nombre}**")
        st.caption(t("tabs.pagos_subtitulo_tarjeta"))
    else:
        st.subheader(t("tabs.pagos_titulo"))
        st.caption(t("tabs.pagos_subtitulo"))
        tip = recomendar_abono_extra(tarjetas, MONTO_EXTRA_DEFAULT)
        if tip and len(tarjetas) >= 2 and tip.tarjeta.id != tarjeta_sel.id:
            st.markdown(f"**{t('estrategia.titulo')}**")
            render_caja_alerta(tip.mensaje, "urgente" if tip.urgente else "info")
        _render_lista_tarjetas(tarjetas, tarjeta_sel, idioma)
        st.divider()
        st.markdown(f"**{t('tabs.pagos_detalle')} · {tarjeta_sel.nombre}**")

    estado_sel = validar_ciclo_con_intereses(tarjeta_sel)
    riesgo_sel = estado_riesgo_pago(tarjeta_sel)
    _render_mensaje_estado(estado_sel, riesgo_sel, tarjeta_sel, idioma)

    st.divider()
    render_panel_intereses(tarjeta_sel, key_prefix=key_prefix)

    st.divider()
    render_actualizar_estatus(tarjeta_sel, enlace_guia=compacto, key_prefix=key_prefix)
