"""
Gráficos de detalle de tarjeta: torta con desglose y línea de fechas.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from app.components.theme import CARD_COLORS, ESTADO_COLORS, colores_mensaje_tarjeta
from app.core.consumos import CONSUMO_SIN_DETALLE, listar_consumos_por_tarjeta
from app.core.fechas import dias_entre, fecha_en_mes, formatear_fecha, hoy, proxima_fecha_por_dia
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import ejecutar_prueba_escenario, ultimo_corte, validar_ciclo
from app.i18n.translator import get_language, t

COLOR_DISP = ESTADO_COLORS["positivo"]
COLOR_DEUDA = ESTADO_COLORS["negativo"]
COLOR_CONSUMO = "#94A3B8"
COLOR_CONSUMO_CICLO = "#FACC15"
PALETA_CONSUMOS = ["#FACC15", "#FB923C", "#F87171", "#A78BFA", "#38BDF8", "#4ADE80", "#F472B6"]
TEXTO_GRAFICO = "#FFFFFF"
TEXTO_BORDE = "#0F172A"
COLOR_COMPRA_MARCA = "#FACC15"
_NIVELES_COMPRA_Y = (0.28, -0.28, 0.18, -0.18, 0.08, -0.08)


def _color_bloque(nombre: str, indice: int) -> str:
    if nombre == CONSUMO_SIN_DETALLE:
        return COLOR_CONSUMO
    h = int(hashlib.md5(nombre.encode()).hexdigest(), 16)
    return PALETA_CONSUMOS[h % len(PALETA_CONSUMOS)]


def _segmentos_torta(tarjeta: Tarjeta) -> list[dict]:
    """Tres bloques: disponibilidad, deuda del ciclo, consumos actuales."""
    limite = tarjeta.limite if tarjeta.limite > 0 else 1.0
    estado = validar_ciclo(tarjeta)
    segmentos: list[dict] = []

    if estado.disponibilidad > 0:
        pct = (estado.disponibilidad / limite) * 100
        segmentos.append(
            {
                "nombre": t("pantalla_lista_tarjetas.grafico_disponibilidad"),
                "monto": estado.disponibilidad,
                "pct": pct,
                "pct_txt": f"{pct:.0f}%",
                "color": COLOR_DISP,
                "tipo": "disponible",
            }
        )

    if estado.monto_adeudado_ciclo_anterior > 0:
        pct = (estado.monto_adeudado_ciclo_anterior / limite) * 100
        segmentos.append(
            {
                "nombre": t("pantalla_lista_tarjetas.grafico_deuda_ciclo"),
                "monto": estado.monto_adeudado_ciclo_anterior,
                "pct": pct,
                "pct_txt": f"{pct:.0f}%",
                "color": COLOR_DEUDA,
                "tipo": "deuda",
            }
        )

    for i, consumo in enumerate(estado.consumos_detalle):
        pct = (consumo.monto / limite) * 100
        color = COLOR_CONSUMO if consumo.nombre == CONSUMO_SIN_DETALLE else _color_bloque(consumo.nombre, i)
        segmentos.append(
            {
                "nombre": consumo.nombre,
                "monto": consumo.monto,
                "pct": pct,
                "pct_txt": f"{pct:.0f}%",
                "color": color if consumo.nombre != CONSUMO_SIN_DETALLE else COLOR_CONSUMO,
                "tipo": "consumo_ciclo",
            }
        )

    if not segmentos and tarjeta.adeudado > 0:
        pct = (tarjeta.adeudado / limite) * 100
        segmentos.append(
            {
                "nombre": CONSUMO_SIN_DETALLE,
                "monto": tarjeta.adeudado,
                "pct": pct,
                "pct_txt": f"{pct:.0f}%",
                "color": COLOR_CONSUMO,
                "tipo": "consumo_ciclo",
            }
        )

    return segmentos


def render_panel_validacion_ciclo(tarjeta: Tarjeta) -> None:
    """Panel con métricas del ciclo de facturación."""
    estado = validar_ciclo(tarjeta)
    idioma = get_language()

    st.caption(t("pantalla_lista_tarjetas.validacion_ciclo_titulo"))
    st.markdown(
        f'<div class="ti-metric-row">'
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("pantalla_lista_tarjetas.validacion_dias_corte")}</div>'
        f'<div class="ti-metric-value">{estado.dias_hasta_corte}</div>'
        f"</div>"
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("pantalla_lista_tarjetas.validacion_dias_pago")}</div>'
        f'<div class="ti-metric-value">{estado.dias_hasta_pago}</div>'
        f"</div>"
        f'<div class="ti-metric-cell">'
        f'<div class="ti-metric-label">{t("pantalla_lista_tarjetas.validacion_dias_pago_siguiente")}</div>'
        f'<div class="ti-metric-value">{estado.dias_hasta_pago_siguiente_ciclo}</div>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if estado.fecha_corte_proximo and estado.fecha_pago_proximo:
        st.caption(
            t(
                "pantalla_lista_tarjetas.validacion_fechas",
                corte=formatear_fecha(estado.fecha_corte_proximo, idioma),
                pago=formatear_fecha(estado.fecha_pago_proximo, idioma),
                pago_sig=formatear_fecha(estado.fecha_pago_siguiente_ciclo, idioma)
                if estado.fecha_pago_siguiente_ciclo
                else "—",
            )
        )


def render_prueba_escenario_ciclo() -> None:
    """Muestra en UI el escenario de prueba jun 13."""
    estado = ejecutar_prueba_escenario()
    st.markdown(f"**{t('pantalla_lista_tarjetas.prueba_escenario_titulo')}**")
    st.code(
        "\n".join(
            [
                f"{t('pantalla_lista_tarjetas.grafico_deuda_ciclo')}: ${estado.monto_adeudado_ciclo_anterior:,.2f}",
                f"{t('pantalla_lista_tarjetas.grafico_consumos_ciclo')}: ${estado.consumos_ciclo_actual:,.2f}",
                f"{t('pantalla_lista_tarjetas.consumo')} total: ${estado.monto_adeudado_actual:,.2f}",
                f"{t('pantalla_lista_tarjetas.disponible')}: ${estado.disponibilidad:,.2f}",
                f"{t('pantalla_lista_tarjetas.validacion_dias_corte')}: {estado.dias_hasta_corte}",
                f"{t('pantalla_lista_tarjetas.validacion_dias_pago')}: {estado.dias_hasta_pago}",
                f"{t('pantalla_lista_tarjetas.validacion_dias_pago_siguiente')}: {estado.dias_hasta_pago_siguiente_ciclo}",
            ]
        ),
        language=None,
    )


def render_grafico_limite(tarjeta: Tarjeta) -> None:
    """Torta con desglose de consumos + disponibilidad y leyenda detallada."""
    st.subheader(t("pantalla_lista_tarjetas.grafico_limite_titulo"))

    if tarjeta.limite <= 0:
        st.warning(t("pantalla_registrar_tarjeta.error_limite"))
        return

    segmentos = _segmentos_torta(tarjeta)
    if not segmentos:
        st.info(t("pantalla_lista_tarjetas.grafico_sin_consumos"))
        return

    df = pd.DataFrame(segmentos)
    df["etiqueta_pct"] = df.apply(
        lambda r: r["pct_txt"] if r["pct"] >= 7 else "",
        axis=1,
    )

    base = alt.Chart(df).encode(
        theta=alt.Theta("monto:Q", stack=True),
        color=alt.Color(
            "nombre:N",
            scale=alt.Scale(domain=df["nombre"].tolist(), range=df["color"].tolist()),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("nombre:N", title=""),
            alt.Tooltip("monto:Q", title=t("pantalla_lista_tarjetas.grafico_etiqueta_monto"), format=",.2f"),
            alt.Tooltip("pct_txt:N", title=t("pantalla_lista_tarjetas.grafico_etiqueta_pct")),
        ],
    )

    pie = base.mark_arc(innerRadius=52, outerRadius=122, cornerRadius=5, stroke=TEXTO_BORDE, strokeWidth=2)
    text = base.mark_text(
        radius=88,
        fontSize=14,
        fontWeight="bold",
        color=TEXTO_GRAFICO,
        stroke=TEXTO_BORDE,
        strokeWidth=1.2,
    ).encode(text="etiqueta_pct:N")

    chart = (pie + text).properties(height=320).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)

    for seg in segmentos:
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"background:#1E293B;border-radius:10px;padding:0.6rem 0.9rem;margin-bottom:0.35rem;"
            f"border-left:4px solid {seg['color']};'>"
            f"<span style='color:#F8FAFC;font-weight:600;font-size:0.95rem;'>{seg['nombre']}</span>"
            f"<span style='color:#E2E8F0;font-weight:600;'>${seg['monto']:,.0f} · {seg['pct_txt']}</span></div>",
            unsafe_allow_html=True,
        )


def _mensaje_fechas(
    ref,
    fecha_corte,
    fecha_pago,
    dias_pago: int,
    dias_corte: int,
    idioma: str,
) -> tuple[str, str]:
    hoy_txt = formatear_fecha(ref, idioma)
    corte_txt = formatear_fecha(fecha_corte, idioma)
    pago_txt = formatear_fecha(fecha_pago, idioma)

    if fecha_corte < ref:
        msg = t(
            "pantalla_lista_tarjetas.grafico_fechas_post_corte",
            hoy=hoy_txt,
            corte=corte_txt,
            pago=pago_txt,
            dias=dias_pago,
        )
        return msg, "info"

    if dias_pago <= 5:
        key = "grafico_fechas_mensaje_urgente"
        tipo = "warning"
    elif dias_pago <= 14:
        key = "grafico_fechas_mensaje_medio"
        tipo = "info"
    else:
        key = "grafico_fechas_mensaje_tranquilo"
        tipo = "success"

    msg = t(
        f"pantalla_lista_tarjetas.{key}",
        hoy=hoy_txt,
        corte=corte_txt,
        pago=pago_txt,
        dias=dias_pago,
        dias_corte=dias_corte,
    )
    return msg, tipo


def _corte_mes_anterior(fecha_corte: date, dia_corte: int) -> date:
    mes = fecha_corte.month - 1
    anio = fecha_corte.year
    if mes < 1:
        mes = 12
        anio -= 1
    return fecha_en_mes(anio, mes, dia_corte)


def _corte_siguiente_periodo(ultimo_corte_fecha: date, dia_corte: int) -> date:
    """Próximo corte estrictamente después del último corte aplicado."""
    mes = ultimo_corte_fecha.month + 1
    anio = ultimo_corte_fecha.year
    if mes > 12:
        mes = 1
        anio += 1
    return fecha_en_mes(anio, mes, dia_corte)


def _corte_abierto_proximo(tarjeta: Tarjeta, ref: date, ultimo: date) -> date:
    candidato = proxima_fecha_por_dia(tarjeta.dia_corte, ref)
    if candidato <= ultimo:
        return _corte_siguiente_periodo(ultimo, tarjeta.dia_corte)
    return candidato


def _severidad_mensaje_fechas(dias_pago: int, dias_atraso: int, deuda_ciclo: float) -> str:
    if deuda_ciclo > 0 and dias_atraso > 0:
        return "urgente"
    if dias_pago <= 5:
        return "urgente"
    if dias_pago <= 14:
        return "medio"
    return "normal"


def _render_mensaje_fechas_caja(tarjeta: Tarjeta, msg: str, severidad: str) -> None:
    c = colores_mensaje_tarjeta(tarjeta.color, severidad)
    st.markdown(
        f'<div style="background:{c["bg"]};border:1px solid {c["border"]};border-radius:12px;'
        f'padding:0.85rem 1rem;margin-bottom:0.75rem;color:{c["text"]};font-size:0.92rem;">'
        f"{msg}</div>",
        unsafe_allow_html=True,
    )


def _nombre_compra(consumo) -> str:
    nombre = (consumo.tienda_razon or "").strip()
    if not nombre or nombre == CONSUMO_SIN_DETALLE:
        return t("uso.consumo_sin_categoria")
    return nombre


def _consumos_en_ventana(id_tarjeta: str, desde: date, hasta: date) -> list:
    resultado = []
    for consumo in listar_consumos_por_tarjeta(id_tarjeta):
        f = date.fromisoformat(consumo.fecha)
        if f <= desde or f > hasta:
            continue
        resultado.append(consumo)
    return sorted(resultado, key=lambda c: c.fecha)


def _etiqueta_grupo_compras(items: list, idioma: str) -> str:
    if len(items) == 1:
        c = items[0]
        nombre = _nombre_compra(c)
        corto = f"{nombre[:10]}…" if len(nombre) > 11 else nombre
        return f"{corto} ${c.monto:,.0f}"
    total = sum(c.monto for c in items)
    return t("pantalla_lista_tarjetas.grafico_fechas_compras_grupo", n=len(items), total=total)


def _tooltip_grupo_compras(items: list) -> str:
    lineas = [f"{_nombre_compra(c)} · ${c.monto:,.2f}" for c in items]
    return " · ".join(lineas)


def _aplicar_stagger_hitos(filas: list[dict]) -> list[dict]:
    """Alterna altura de etiquetas cuando los hitos están muy cerca."""
    orden = sorted(range(len(filas)), key=lambda i: filas[i]["fecha"])
    slot = 0
    prev_ts = None
    for i in orden:
        ts = pd.Timestamp(filas[i]["fecha"])
        # En móvil, dos etiquetas separadas por una semana todavía se solapan.
        if prev_ts is not None and abs((ts - prev_ts).days) < 11:
            slot = 1 - slot
        else:
            slot = 0
        filas[i]["y_evento_txt"] = 0.34 + (0.20 * slot)
        filas[i]["y_fecha_txt"] = -0.34 - (0.20 * slot)
        prev_ts = ts
    return filas


def _nivel_marca_compra(idx: int) -> float:
    """Posición vertical del punto — sin etiquetas, solo evita coincidencia exacta."""
    return _NIVELES_COMPRA_Y[idx % len(_NIVELES_COMPRA_Y)]


def _preparar_marcadores_compras(
    tarjeta_id: str,
    desde: date,
    hasta: date,
    idioma: str,
) -> list[dict]:
    consumos = _consumos_en_ventana(tarjeta_id, desde, hasta)
    if not consumos:
        return []

    por_fecha: dict[date, list] = defaultdict(list)
    for c in consumos:
        por_fecha[date.fromisoformat(c.fecha)].append(c)

    marcadores: list[dict] = []
    for idx, (fecha, items) in enumerate(sorted(por_fecha.items())):
        marcadores.append(
            {
                "fecha": pd.Timestamp(fecha),
                "evento": _etiqueta_grupo_compras(items, idioma),
                "fecha_txt": formatear_fecha(fecha, idioma),
                "tipo": "compra",
                "y": _nivel_marca_compra(idx),
                "tooltip_detalle": _tooltip_grupo_compras(items),
            }
        )
    return marcadores


def _render_timeline_fechas(
    filas: list[dict],
    fecha_banda_inicio,
    fecha_banda_fin,
    color_banda: str,
    color_pago: str,
    altura: int = 200,
    marcadores_compras: list[dict] | None = None,
    idioma: str = "es",
) -> None:
    filas = _aplicar_stagger_hitos([dict(f) for f in filas])
    df = pd.DataFrame(filas)
    hay_compras = bool(marcadores_compras)
    y_scale = alt.Scale(domain=[-0.8, 0.8])
    x_axis = alt.Axis(format="%d %b", labelAngle=0, tickCount=5)
    x_enc = alt.X("fecha:T", title=t("pantalla_lista_tarjetas.grafico_eje_fechas"), axis=x_axis)
    y_enc = alt.Y("y:Q", axis=None, scale=y_scale)
    y_evento_enc = alt.Y("y_evento_txt:Q", axis=None, scale=y_scale)
    y_fecha_enc = alt.Y("y_fecha_txt:Q", axis=None, scale=y_scale)

    f_min = min(pd.Timestamp(f["fecha"]) for f in filas)
    f_max = max(pd.Timestamp(f["fecha"]) for f in filas)
    if marcadores_compras:
        f_min = min(f_min, min(m["fecha"] for m in marcadores_compras))
        f_max = max(f_max, max(m["fecha"] for m in marcadores_compras))

    band_df = pd.DataFrame(
        {
            "x": [pd.Timestamp(fecha_banda_inicio)],
            "x2": [pd.Timestamp(fecha_banda_fin)],
            "y": [-0.18],
            "y2": [0.18],
        }
    )
    banda = (
        alt.Chart(band_df)
        .mark_rect(color=color_banda, opacity=0.14, cornerRadius=4)
        .encode(
            x=alt.X("x:T", scale=alt.Scale(domain=[f_min, f_max])),
            x2="x2:T",
            y=alt.Y("y:Q", scale=y_scale, axis=None),
            y2="y2:Q",
        )
    )

    linea_df = pd.DataFrame({"fecha": [f_min, f_max], "y": [0.0, 0.0]})
    linea = (
        alt.Chart(linea_df)
        .mark_line(color="#475569", strokeWidth=5)
        .encode(x=x_enc, y=y_enc)
    )

    tipos = ["corte_inicio", "hoy", "corte", "pago", "atraso"]
    colores_map = {
        "corte_inicio": "#64748B",
        "hoy": "#F8FAFC",
        "corte": "#6366F1",
        "pago": color_pago,
        "atraso": ESTADO_COLORS["negativo"],
    }
    tipos_presentes = df["tipo"].tolist()
    domain = [tp for tp in tipos if tp in tipos_presentes]
    range_col = [colores_map[tp] for tp in domain]

    puntos = (
        alt.Chart(df)
        .mark_point(filled=True, size=320, stroke="#0F172A", strokeWidth=2)
        .encode(
            x=x_enc,
            y=y_enc,
            color=alt.Color("tipo:N", scale=alt.Scale(domain=domain, range=range_col), legend=None),
            tooltip=[
                alt.Tooltip("evento:N", title=""),
                alt.Tooltip("fecha_txt:N", title=t("pantalla_lista_tarjetas.grafico_eje_fechas")),
            ],
        )
    )

    nombre_arriba = (
        alt.Chart(df)
        .mark_text(fontSize=10, fontWeight="bold", color="#F8FAFC")
        .encode(x=x_enc, y=y_evento_enc, text="evento:N")
    )
    fecha_abajo = (
        alt.Chart(df)
        .mark_text(fontSize=10, color="#94A3B8")
        .encode(x=x_enc, y=y_fecha_enc, text="fecha_txt:N")
    )

    chart = banda + linea

    if marcadores_compras:
        df_compras = pd.DataFrame(marcadores_compras)
        compras_pts = (
            alt.Chart(df_compras)
            .mark_text(
                text="🛒",
                fontSize=16,
                color=COLOR_COMPRA_MARCA,
                baseline="middle",
            )
            .encode(
                x=x_enc,
                y=y_enc,
                tooltip=[
                    alt.Tooltip("tooltip_detalle:N", title=t("pantalla_lista_tarjetas.grafico_fechas_compra_tooltip")),
                    alt.Tooltip("fecha_txt:N", title=t("pantalla_lista_tarjetas.grafico_eje_fechas")),
                ],
            )
        )
        chart = chart + compras_pts

    chart = (
        (chart + puntos + nombre_arriba + fecha_abajo)
        .properties(height=altura)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor="#94A3B8", titleColor="#94A3B8", gridColor="#334155")
    )
    st.altair_chart(chart, use_container_width=True)

    if hay_compras:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.4rem;color:#94A3B8;'
            'font-size:0.82rem;margin-top:0.25rem;">'
            '<span style="color:#EAB308;font-size:1rem;line-height:1;">🛒</span>'
            f'<span>{t("pantalla_lista_tarjetas.grafico_fechas_compras_leyenda")}</span></div>',
            unsafe_allow_html=True,
        )


def _timeline_ciclo_cerrado(tarjeta: Tarjeta, ref, idioma: str, deuda: float) -> None:
    corte_cerrado = ultimo_corte(tarjeta, ref)
    inicio_cerrado = _corte_mes_anterior(corte_cerrado, tarjeta.dia_corte)
    pago_limite = proxima_fecha_por_dia(tarjeta.dia_pago, corte_cerrado)
    dias_atraso = max(0, dias_entre(pago_limite, ref)) if ref > pago_limite and deuda > 0 else 0
    impago_vencido = dias_atraso > 0

    inicio_txt = formatear_fecha(inicio_cerrado, idioma)
    cierre_txt = formatear_fecha(corte_cerrado, idioma)
    pago_txt = formatear_fecha(pago_limite, idioma)
    hoy_txt = formatear_fecha(ref, idioma)
    dias_para_pagar = max(0, dias_entre(ref, pago_limite))

    st.markdown(f"**{t('pantalla_lista_tarjetas.grafico_fechas_ciclo_cerrado_titulo')}**")
    if impago_vencido:
        st.caption(
            t(
                "pantalla_lista_tarjetas.grafico_fechas_ventana_cerrado",
                monto=deuda,
                cierre=cierre_txt,
                pago=pago_txt,
            )
        )
    else:
        st.caption(
            t(
                "pantalla_lista_tarjetas.grafico_fechas_ventana_cerrado_pendiente",
                monto=deuda,
                cierre=cierre_txt,
                pago=pago_txt,
                dias=dias_para_pagar,
            )
        )

    color_pago_cerrado = ESTADO_COLORS["negativo"] if impago_vencido else COLOR_DISP

    filas: list[dict] = [
        {
            "fecha": pd.Timestamp(inicio_cerrado),
            "evento": t("pantalla_lista_tarjetas.grafico_corte_inicio"),
            "fecha_txt": inicio_txt,
            "tipo": "corte_inicio",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(corte_cerrado),
            "evento": t("pantalla_lista_tarjetas.grafico_ciclo_cerrado_corte"),
            "fecha_txt": cierre_txt,
            "tipo": "corte",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(pago_limite),
            "evento": (
                t("pantalla_lista_tarjetas.grafico_ciclo_cerrado_pago")
                if impago_vencido
                else t("pantalla_lista_tarjetas.grafico_ciclo_cerrado_pago_limite")
            ),
            "fecha_txt": pago_txt,
            "tipo": "pago",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(ref),
            "evento": (
                t("pantalla_lista_tarjetas.grafico_fechas_dias_atraso", dias=dias_atraso)
                if impago_vencido
                else t("pantalla_lista_tarjetas.grafico_estas_aqui")
            ),
            "fecha_txt": hoy_txt,
            "tipo": "atraso" if impago_vencido else "hoy",
            "y": 0,
        },
    ]

    marcadores = _preparar_marcadores_compras(tarjeta.id, inicio_cerrado, corte_cerrado, idioma)
    _render_timeline_fechas(
        filas,
        inicio_cerrado,
        ref if impago_vencido else pago_limite,
        ESTADO_COLORS["negativo"],
        color_pago_cerrado,
        altura=180,
        marcadores_compras=marcadores,
        idioma=idioma,
    )
    return dias_atraso


def render_grafico_fechas(tarjeta: Tarjeta) -> None:
    st.subheader(t("pantalla_lista_tarjetas.grafico_fechas_titulo"))

    idioma = get_language()
    ref = hoy()
    estado = validar_ciclo(tarjeta, ref)
    deuda_ciclo = estado.monto_adeudado_ciclo_anterior
    fecha_inicio = ultimo_corte(tarjeta, ref)
    fecha_corte = _corte_abierto_proximo(tarjeta, ref, fecha_inicio)
    fecha_pago_obligacion = proxima_fecha_por_dia(tarjeta.dia_pago, ref)
    fecha_pago = proxima_fecha_por_dia(tarjeta.dia_pago, fecha_corte)
    dias_pago = max(0, dias_entre(ref, fecha_pago_obligacion))
    dias_corte = max(0, dias_entre(ref, fecha_corte))

    pago_vencido_cerrado = proxima_fecha_por_dia(tarjeta.dia_pago, fecha_inicio)
    dias_atraso = max(0, dias_entre(pago_vencido_cerrado, ref)) if ref > pago_vencido_cerrado and deuda_ciclo > 0 else 0

    msg, _ = _mensaje_fechas(ref, fecha_corte, fecha_pago_obligacion, dias_pago, dias_corte, idioma)
    severidad = _severidad_mensaje_fechas(dias_pago, dias_atraso, deuda_ciclo)
    _render_mensaje_fechas_caja(tarjeta, msg, severidad)

    if deuda_ciclo > 0:
        _timeline_ciclo_cerrado(tarjeta, ref, idioma, deuda_ciclo)
        st.markdown(f"**{t('pantalla_lista_tarjetas.grafico_fechas_ciclo_abierto_titulo')}**")

    hoy_txt = formatear_fecha(ref, idioma)
    inicio_txt = formatear_fecha(fecha_inicio, idioma)
    corte_txt = formatear_fecha(fecha_corte, idioma)
    pago_txt = formatear_fecha(fecha_pago, idioma)
    color_tarjeta = CARD_COLORS.get(tarjeta.color, CARD_COLORS["azul"])
    color_pago = COLOR_DISP if dias_pago > 14 else ESTADO_COLORS["medio"] if dias_pago > 5 else ESTADO_COLORS["negativo"]

    filas: list[dict] = [
        {
            "fecha": pd.Timestamp(fecha_inicio),
            "evento": t("pantalla_lista_tarjetas.grafico_corte_inicio"),
            "fecha_txt": inicio_txt,
            "tipo": "corte_inicio",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(ref),
            "evento": t("pantalla_lista_tarjetas.grafico_estas_aqui"),
            "fecha_txt": hoy_txt,
            "tipo": "hoy",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(fecha_corte),
            "evento": t("pantalla_lista_tarjetas.grafico_corte"),
            "fecha_txt": corte_txt,
            "tipo": "corte",
            "y": 0,
        },
        {
            "fecha": pd.Timestamp(fecha_pago),
            "evento": t("pantalla_lista_tarjetas.grafico_pago"),
            "fecha_txt": pago_txt,
            "tipo": "pago",
            "y": 0,
        },
    ]

    st.caption(
        t(
            "pantalla_lista_tarjetas.grafico_fechas_ventana_ciclo",
            inicio=inicio_txt,
            corte=corte_txt,
        )
    )
    marcadores = _preparar_marcadores_compras(tarjeta.id, fecha_inicio, ref, idioma)
    _render_timeline_fechas(
        filas,
        fecha_inicio,
        fecha_corte,
        color_tarjeta,
        color_pago,
        altura=200,
        marcadores_compras=marcadores,
        idioma=idioma,
    )
