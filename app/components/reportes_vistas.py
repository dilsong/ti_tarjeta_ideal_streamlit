"""Vistas del módulo Reportes."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from app.components.reportes_print import _esc, html_ficha, html_prioridad, html_tabla
from app.components.theme import CARD_COLORS, ESTADO_COLORS, emoji_color, etiqueta_color_nombre, gradiente_tarjeta
from app.core.consumos import CONSUMO_SIN_DETALLE
from app.core.reportes import FilaReporte, FiltrosReporte, OrdenReporte, ResumenReporte, generar_reporte, ordenar_filas
from app.core.tarjetas import EstadoSalud
from app.core.validacion_ciclo import validar_ciclo_con_intereses
from app.core.vista_uso import VistaUso
from app.i18n.translator import get_language, t
from app.ui.helpers import fila_accion
from app.ui.tabs._badges import _label_salud, estado_riesgo_pago


REPORTES_CSS = """
<style>
.ti-rep-card {
    background: linear-gradient(135deg, var(--rep-color, #2563EB), #111827);
    border-radius: 16px; padding: 1.25rem; color: white;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35); margin-bottom: 1rem;
}
.ti-rep-metric {
    background: #1E293B; border-radius: 12px; padding: 0.85rem 1rem;
    margin-bottom: 0.5rem; border-left: 4px solid var(--rep-accent, #6366F1);
}
.ti-rep-metric-label { color: #94A3B8; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; }
.ti-rep-metric-value { color: #F8FAFC; font-size: clamp(0.95rem, 3.8vw, 1.35rem); font-weight: 700; white-space: nowrap; font-variant-numeric: tabular-nums; }
.ti-rep-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.ti-rep-table th { background: #1E293B; color: #94A3B8; padding: 0.55rem 0.4rem; text-align: left; }
.ti-rep-table td { padding: 0.5rem 0.4rem; color: #E2E8F0; border-bottom: 1px solid #334155; }
.ti-rep-table tr:nth-child(even) td { background: #1a2332; }
.ti-rep-resumen {
    background: #1E293B; border-radius: 12px; padding: 1rem; margin-top: 1rem;
    border: 1px solid #334155; color: #CBD5E1; font-size: 0.9rem;
}
.ti-rep-prioridad {
    background: #1E293B; border-radius: 10px; padding: 0.75rem 1rem;
    margin-bottom: 0.45rem; display: flex; justify-content: space-between; align-items: center;
    border-left: 4px solid #6366F1;
}
.ti-rep-filtros { background: #1E293B; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }
.ti-rep-salud-intro {
    background: #1E293B; border: 1px solid #334155; border-radius: 12px;
    padding: 0.85rem 1rem; margin-bottom: 1rem; color: #CBD5E1; font-size: 0.88rem; line-height: 1.45;
}
.ti-rep-salud-card {
    background: #0F172A; border: 1px solid #334155; border-radius: 14px;
    padding: 1rem 1rem 0.9rem; margin-bottom: 1rem;
}
.ti-rep-salud-card .ti-rep-salud-head {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;
}
.ti-rep-salud-card .ti-rep-salud-nombre { color: #F8FAFC; font-weight: 700; font-size: 1rem; }
.ti-rep-salud-card .ti-rep-salud-banco { color: #94A3B8; font-size: 0.82rem; margin-top: 0.2rem; }
.ti-rep-salud-msg { color: #E2E8F0; font-size: 0.92rem; line-height: 1.5; margin: 0.75rem 0 0.5rem; }
.ti-rep-salud-datos { color: #94A3B8; font-size: 0.78rem; line-height: 1.4; border-top: 1px solid #334155; padding-top: 0.55rem; margin-bottom: 0; }
.ti-rep-salud-pagos-hint {
    color: #F97316 !important;
    font-size: 0.85rem;
    font-weight: 600;
    margin-top: 0.65rem;
    margin-bottom: 0;
    line-height: 1.4;
}
</style>
"""


def _icono_tarjeta(fila: FilaReporte) -> str:
    return etiqueta_color_nombre(fila.tarjeta.color, fila.tarjeta.nombre)


@st.dialog(t("reportes.preview_titulo"), width="large")
def _preview_impresion(html: str, titulo: str) -> None:
    html_print = html.replace(
        "</body>",
        f"<button type='button' class='btn-print' onclick='window.print()'>"
        f"🖨 {_esc(t('reportes.imprimir'))}</button></body>",
    )
    components.html(html_print, height=520, scrolling=True)
    st.download_button(
        t("reportes.descargar_html"),
        html,
        file_name="reporte_tarjeta_ideal.html",
        mime="text/html",
        use_container_width=True,
    )


@st.dialog(" ", width="small")
def _desglose_ciclos(vista: VistaUso) -> None:
    st.markdown(f"**{t('reportes.desglose_titulo')}**")
    if vista.desglose_pasado and vista.ciclo_pasado_pendiente > 0:
        dp = vista.desglose_pasado
        st.markdown(f"**{t('uso.ciclo_pasado_titulo')}**")
        st.markdown(
            f"- **${dp.saldo_no_pagado:,.2f}** — {t('uso.linea_saldo_no_pagado')}\n\n"
            f"- **${dp.interes_estimado:,.2f}** — {t('uso.linea_interes_arrastre')}\n\n"
            f"**{t('uso.costo_total', total=dp.costo_total)}**"
        )
    if vista.ciclo_nuevo_total > 0:
        st.markdown(f"**{t('uso.ciclo_nuevo_titulo')}**")
        for ln in vista.desglose_nuevo.lineas:
            nombre = t("uso.consumo_sin_categoria") if ln.nombre == CONSUMO_SIN_DETALLE else ln.nombre
            st.markdown(f"- **${ln.monto:,.2f}** — {nombre}")
        st.markdown(f"**{t('uso.total_ciclo_nuevo', total=vista.ciclo_nuevo_total)}**")


def _boton_impresion(html: str, label: str, key: str) -> None:
    if st.button(label, key=key, use_container_width=True):
        _preview_impresion(html, t("reportes.preview_titulo"))

def render_filtros() -> FiltrosReporte:
    from app.core.reportes import opciones_filtro
    from app.core.vista_uso import calcular_vista_uso
    from app.core.tarjetas import listar_tarjetas

    bancos, tipos, _ = opciones_filtro()
    max_consumo = max(
        (calcular_vista_uso(t).total_usado for t in listar_tarjetas()),
        default=5000.0,
    )
    max_slider = max(1000.0, float(int(max_consumo / 500 + 1) * 500))

    st.markdown(f'<div class="ti-rep-filtros"><strong>{t("reportes.filtrar_por")}</strong></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        banco_opts = [t("reportes.todos")] + bancos
        banco_sel = st.selectbox(t("reportes.filtro_banco"), banco_opts, key="rep_f_banco")
        tipo_opts = [t("reportes.todos")] + tipos
        tipo_sel = st.selectbox(t("reportes.filtro_tipo"), tipo_opts, key="rep_f_tipo")
    with c2:
        estado_opts = [
            t("reportes.todos"),
            t("reportes.estado_bloqueado"),
            t("reportes.estado_acumulando"),
            t("reportes.estado_libre"),
        ]
        estado_sel = st.selectbox(t("reportes.filtro_estado"), estado_opts, key="rep_f_estado")

    usar_fechas = st.checkbox(t("reportes.usar_filtro_fecha"), value=False, key="rep_use_fecha")
    c3, c4, c5 = st.columns(3)
    with c3:
        compra_desde = st.date_input(
            t("reportes.compra_desde"),
            value=None,
            key="rep_f_compra_d",
            disabled=not usar_fechas,
        )
    with c4:
        compra_hasta = st.date_input(
            t("reportes.compra_hasta"),
            value=None,
            key="rep_f_compra_h",
            disabled=not usar_fechas,
        )
    with c5:
        rango_consumo = st.slider(
            t("reportes.rango_consumo"),
            0.0,
            max_slider,
            (0.0, max_slider),
            step=50.0,
            key="rep_f_consumo",
        )

    estado_map = {
        t("reportes.estado_bloqueado"): "bloqueado",
        t("reportes.estado_acumulando"): "acumulando",
        t("reportes.estado_libre"): "libre",
    }

    return FiltrosReporte(
        banco=None if banco_sel == t("reportes.todos") else banco_sel,
        tipo_tarjeta=None if tipo_sel == t("reportes.todos") else tipo_sel,
        estado_ciclo=estado_map.get(estado_sel),
        compra_desde=compra_desde if usar_fechas and compra_desde else None,
        compra_hasta=compra_hasta if usar_fechas and compra_hasta else None,
        consumo_min=rango_consumo[0] if rango_consumo[0] > 0 else None,
        consumo_max=rango_consumo[1] if rango_consumo[1] < max_slider else None,
    )


def _resumen_html(resumen: ResumenReporte) -> None:
    st.markdown(
        f'<div class="ti-rep-resumen">'
        f"<strong>{t('reportes.resumen_general')}</strong><br/>"
        f"{t('reportes.total_limite')}: <strong>${resumen.total_limite:,.2f}</strong><br/>"
        f"{t('reportes.total_consumo')}: <strong>${resumen.total_consumo:,.2f}</strong><br/>"
        f"{t('reportes.total_disponibilidad')}: <strong>${resumen.total_disponibilidad:,.2f}</strong><br/>"
        f"{t('reportes.tarjeta_cargada')}: <strong>{resumen.tarjeta_mas_cargada}</strong><br/>"
        f"{t('reportes.tarjeta_urgente')}: <strong>{resumen.tarjeta_mas_urgente}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_vista_individual(resumen: ResumenReporte) -> None:
    if not resumen.filas:
        st.info(t("reportes.sin_resultados"))
        return

    opciones = {f"{f.tarjeta.banco} — {f.tarjeta.nombre}": f for f in resumen.filas}
    sel = st.selectbox(t("reportes.seleccionar_tarjeta"), list(opciones.keys()), key="rep_sel_ind")
    fila = opciones[sel]
    tj = fila.tarjeta
    color = CARD_COLORS.get(tj.color, CARD_COLORS["azul"])
    grad = gradiente_tarjeta(tj.color)

    st.markdown(
        f'<div class="ti-rep-card" style="--rep-color:{color};background:{grad};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:1.1rem;font-weight:700;">{_icono_tarjeta(fila)} {tj.banco}</span>'
        f'<span style="opacity:0.85;">•••• {tj.ultimos_digitos}</span></div>'
        f'<div style="margin-top:0.5rem;font-size:1.25rem;font-weight:600;">{tj.nombre}</div>'
        f'<div style="opacity:0.8;font-size:0.85rem;margin-top:0.25rem;">{t("reportes.col_tipo")}: {fila.tipo}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    for col, label, val in [
        (m1, t("reportes.col_limite"), fila.limite),
        (m2, t("reportes.consumo_ciclo"), fila.consumo),
        (m3, t("reportes.col_disponible"), fila.disponibilidad),
    ]:
        with col:
            st.markdown(
                f'<div class="ti-rep-metric"><div class="ti-rep-metric-label">{label}</div>'
                f'<div class="ti-rep-metric-value ti-money">${val:,.2f}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<div class="ti-metric-row">'
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("reportes.col_corte")}</div>'
        f'<div class="ti-metric-value ti-metric-value--text">{fila.fecha_corte_txt}</div>'
        f"</div>"
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("reportes.col_pago")}</div>'
        f'<div class="ti-metric-value ti-metric-value--text">{fila.fecha_pago_txt}</div>'
        f"</div>"
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("reportes.col_ultima_compra")}</div>'
        f'<div class="ti-metric-value ti-metric-value--text">{fila.ultima_compra_txt}</div>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    estado_color = ESTADO_COLORS["negativo"] if fila.estado_ciclo.value in ("bloqueado", "ambos") else "#6366F1"
    if fila.estado_ciclo.value == "libre":
        estado_color = ESTADO_COLORS["positivo"]

    with fila_accion(6, 1) as (c_est, c_help):
        with c_est:
            st.markdown(
                f'<span class="ti-badge" style="background:{estado_color};">{t("reportes.col_estado_ciclo")}: '
                f"{fila.estado_ciclo_txt}</span>",
                unsafe_allow_html=True,
            )
        with c_help:
            if st.button("?", key=f"rep_desglose_{tj.id}", help=t("reportes.ver_desglose")):
                _desglose_ciclos(fila.vista)

    _boton_impresion(html_ficha(fila), t("reportes.imprimir_tarjeta"), f"rep_print_ind_{tj.id}")


def render_vista_agrupado(resumen: ResumenReporte) -> None:
    if not resumen.filas:
        st.info(t("reportes.sin_resultados"))
        return

    rows = ""
    for f in resumen.filas:
        rows += (
            f"<tr>"
            f"<td>{_icono_tarjeta(f)}</td>"
            f"<td>{f.tarjeta.banco}</td>"
            f"<td>${f.limite:,.0f}</td>"
            f"<td>${f.consumo:,.0f}</td>"
            f"<td>${f.disponibilidad:,.0f}</td>"
            f"<td>{f.fecha_corte_txt}</td>"
            f"<td>{f.fecha_pago_txt}</td>"
            f"<td>{f.ultima_compra_txt}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<table class="ti-rep-table"><thead><tr>'
        f"<th>{t('reportes.col_color')}</th>"
        f"<th>{t('reportes.col_banco')}</th>"
        f"<th>{t('reportes.col_limite')}</th>"
        f"<th>{t('reportes.col_consumo')}</th>"
        f"<th>{t('reportes.col_disponible')}</th>"
        f"<th>{t('reportes.col_corte')}</th>"
        f"<th>{t('reportes.col_pago')}</th>"
        f"<th>{t('reportes.col_ultima_compra')}</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )

    _resumen_html(resumen)
    _boton_impresion(html_tabla(resumen), t("reportes.imprimir_completo"), "rep_print_tabla")


def render_vista_prioridad(resumen: ResumenReporte) -> None:
    if not resumen.filas:
        st.info(t("reportes.sin_resultados"))
        return

    orden_opts = {
        t("reportes.orden_urgencia"): OrdenReporte.URGENCIA,
        t("reportes.orden_consumo"): OrdenReporte.CONSUMO,
        t("reportes.orden_riesgo"): OrdenReporte.RIESGO,
        t("reportes.orden_disponibilidad"): OrdenReporte.DISPONIBILIDAD,
        t("reportes.orden_alfabetico"): OrdenReporte.ALFABETICO,
    }
    orden_sel = st.selectbox(t("reportes.ordenar_por"), list(orden_opts.keys()), key="rep_orden")
    orden = orden_opts[orden_sel]
    filas = ordenar_filas(resumen.filas, orden)

    for i, f in enumerate(filas, 1):
        st.markdown(
            f'<div class="ti-rep-prioridad">'
            f"<span><strong>{i}.</strong> {_icono_tarjeta(f)} "
            f"<small style='color:#64748B'>{f.tarjeta.banco}</small></span>"
            f"<span style='text-align:right;font-size:0.85rem;'>"
            f"{t('reportes.col_pago')} {f.fecha_pago_txt}<br/>"
            f"{t('reportes.col_consumo')} <strong>${f.consumo:,.2f}</strong></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    _resumen_html(resumen)
    _boton_impresion(html_prioridad(filas, resumen), t("reportes.imprimir_ordenado"), "rep_print_prio")


def _mensaje_salud_tarjeta(
    fila: FilaReporte,
    estado,
    proy,
    riesgo: EstadoSalud,
) -> tuple[str, str]:
    """Mensaje principal + línea de datos compacta."""
    deuda = estado.monto_adeudado_ciclo_anterior
    acum = estado.consumos_ciclo_actual
    pago = fila.fecha_pago_txt

    if deuda <= 0 and acum <= 0:
        return t("reportes.salud_msg_libre"), ""

    if deuda <= 0 and acum > 0:
        msg = t(
            "reportes.salud_msg_solo_acumulando",
            monto=acum,
            corte=fila.fecha_corte_txt,
        )
        return msg, t("reportes.salud_dato_sin_pago_ahora")

    if riesgo == EstadoSalud.NEGATIVO:
        msg = t(
            "reportes.salud_msg_urgente",
            monto=deuda,
            dias=estado.dias_hasta_pago,
            pago=pago,
        )
    elif riesgo == EstadoSalud.MEDIO:
        if estado.dias_hasta_pago > 7:
            msg = t(
                "reportes.salud_msg_tranquilo",
                monto=deuda,
                dias=estado.dias_hasta_pago,
                pago=pago,
            )
        else:
            msg = t(
                "reportes.salud_msg_atencion",
                monto=deuda,
                dias=estado.dias_hasta_pago,
                pago=pago,
            )
    elif proy and proy.interes_estimado > 0:
        msg = t(
            "reportes.salud_msg_con_interes",
            monto=deuda,
            dias=estado.dias_hasta_pago,
            pago=pago,
            interes=proy.interes_estimado,
        )
    else:
        msg = t(
            "reportes.salud_msg_tranquilo",
            monto=deuda,
            dias=estado.dias_hasta_pago,
            pago=pago,
        )

    datos = ""
    if proy:
        partes = []
        if proy.pago_minimo > 0:
            partes.append(t("reportes.salud_dato_minimo", monto=proy.pago_minimo))
        if proy.interes_estimado > 0:
            partes.append(t("reportes.salud_dato_interes", monto=proy.interes_estimado))
        if proy.monto_acumulado_proximo_min > deuda + acum:
            partes.append(
                t("reportes.salud_dato_si_minimo", monto=proy.monto_acumulado_proximo_min)
            )
        datos = " · ".join(partes)
    return msg, datos


def render_vista_salud(resumen: ResumenReporte) -> None:
    if not resumen.filas:
        st.info(t("reportes.sin_resultados"))
        return

    st.markdown(
        f'<div class="ti-rep-salud-intro">'
        f"<strong>{t('reportes.salud_que_es')}</strong><br/>"
        f"{t('reportes.salud_para_que')}<br/><br/>"
        f"🖨 {t('reportes.salud_nota_impresion')}"
        f"</div>",
        unsafe_allow_html=True,
    )

    filas = sorted(resumen.filas, key=lambda f: (f.dias_hasta_pago, -f.consumo))
    urgentes = sum(1 for f in filas if estado_riesgo_pago(f.tarjeta) == EstadoSalud.NEGATIVO)
    if urgentes:
        st.warning(t("reportes.salud_resumen_urgente", n=urgentes))

    for fila in filas:
        tarjeta = fila.tarjeta
        estado = validar_ciclo_con_intereses(tarjeta)
        proy = estado.proyeccion_intereses
        riesgo = estado_riesgo_pago(tarjeta)
        riesgo_color = ESTADO_COLORS[riesgo.value]
        color = CARD_COLORS.get(tarjeta.color, CARD_COLORS["azul"])
        msg, datos = _mensaje_salud_tarjeta(fila, estado, proy, riesgo)

        datos_html = (
            f'<div class="ti-rep-salud-datos">{_esc(datos)}</div>' if datos else ""
        )
        deuda_ciclo = estado.monto_adeudado_ciclo_anterior
        pagos_hint_html = (
            f'<div class="ti-rep-salud-pagos-hint" style="color:#F97316 !important;font-weight:600;">'
            f"{_esc(t('reportes.salud_ir_pagos_sugerencia'))}</div>"
            if deuda_ciclo > 0
            else ""
        )
        st.markdown(
            f'<div class="ti-rep-salud-card" style="border-left:5px solid {color};">'
            f'<div class="ti-rep-salud-head">'
            f'<div>'
            f'<div class="ti-rep-salud-nombre">{emoji_color(tarjeta.color)} {_esc(tarjeta.nombre)}</div>'
            f'<div class="ti-rep-salud-banco">{_esc(tarjeta.banco)} · •••• {_esc(tarjeta.ultimos_digitos)}</div>'
            f"</div>"
            f'<span class="ti-badge" style="background:{riesgo_color};white-space:nowrap;flex-shrink:0;">'
            f"{_esc(_label_salud(riesgo))}</span>"
            f"</div>"
            f'<p class="ti-rep-salud-msg">{_esc(msg)}</p>'
            f"{datos_html}"
            f"{pagos_hint_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_reportes_content() -> None:
    st.markdown(REPORTES_CSS, unsafe_allow_html=True)
    filtros = render_filtros()
    resumen = generar_reporte(filtros, get_language())

    v1, v2, v3, v4 = st.tabs(
        [
            t("reportes.vista_individual"),
            t("reportes.vista_agrupado"),
            t("reportes.vista_prioridad"),
            t("reportes.vista_salud"),
        ]
    )
    with v1:
        render_vista_individual(resumen)
    with v2:
        render_vista_agrupado(resumen)
    with v3:
        render_vista_prioridad(resumen)
    with v4:
        render_vista_salud(resumen)
