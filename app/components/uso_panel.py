"""Panel de la solapa Uso: límite, ciclo pasado y ciclo nuevo."""

from __future__ import annotations

import streamlit as st

from app.components.theme import ESTADO_COLORS
from app.core.consumos import CONSUMO_SIN_DETALLE
from app.core.fechas import formatear_fecha
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import validar_ciclo
from app.core.vista_uso import DesgloseCicloPasado, VistaUso, calcular_vista_uso
from app.i18n.translator import get_language, t
from app.ui.helpers import fila_accion

COLOR_DISP = ESTADO_COLORS["positivo"]
COLOR_PASADO = ESTADO_COLORS["negativo"]
COLOR_NUEVO = "#6366F1"


def _pct(monto: float, limite: float) -> float:
    if limite <= 0:
        return 0.0
    return min(100.0, max(0.0, (monto / limite) * 100))


@st.dialog(" ", width="small")
def _dialog_costo_no_pagar(desglose: DesgloseCicloPasado) -> None:
    st.markdown(f"**{t('uso.costo_no_pagar_titulo')}**")
    st.caption(t("uso.costo_no_pagar_subtitulo"))
    st.markdown(
        f"- **${desglose.saldo_no_pagado:,.2f}** — {t('uso.linea_saldo_no_pagado')}\n\n"
        f"- **${desglose.interes_estimado:,.2f}** — {t('uso.linea_interes_arrastre')}"
    )
    st.markdown(f"**{t('uso.costo_total', total=desglose.costo_total)}**")
    st.caption(t("uso.costo_tasa_nota", tasa=desglose.tasa_aplicada, dias=desglose.dias_interes))
    st.divider()
    st.warning(t("uso.mensaje_costo_no_pagar"))


def _boton_ayuda(key: str, desglose: DesgloseCicloPasado) -> None:
    if st.button("?", key=key, help=t("intereses.ver_desglose")):
        _dialog_costo_no_pagar(desglose)


def _barra_limite(vista: VistaUso) -> None:
    limite = vista.limite if vista.limite > 0 else 1.0
    p_disp = _pct(vista.disponible, limite)
    p_pas = _pct(vista.ciclo_pasado_pendiente, limite)
    p_nuevo = _pct(vista.ciclo_nuevo_total, limite)

    st.markdown(
        f'<div style="margin-bottom:0.35rem;display:flex;justify-content:space-between;'
        f'color:#94A3B8;font-size:0.75rem;font-weight:600;">'
        f'<span>{t("pantalla_lista_tarjetas.limite")}: ${vista.limite:,.0f}</span>'
        f'<span>{t("uso.total_usado")}: ${vista.total_usado:,.0f}</span></div>'
        f'<div style="display:flex;height:18px;border-radius:10px;overflow:hidden;background:#334155;">'
        f'<div style="width:{p_disp:.1f}%;background:{COLOR_DISP};"></div>'
        f'<div style="width:{p_pas:.1f}%;background:{COLOR_PASADO};"></div>'
        f'<div style="width:{p_nuevo:.1f}%;background:{COLOR_NUEVO};"></div>'
        f"</div>"
        f'<div style="display:flex;gap:0.75rem;margin-top:0.45rem;flex-wrap:wrap;'
        f'color:#94A3B8;font-size:0.72rem;">'
        f'<span>● {t("uso.leyenda_disponible")}</span>'
        f'<span style="color:{COLOR_PASADO};">● {t("uso.leyenda_pasado")}</span>'
        f'<span style="color:{COLOR_NUEVO};">● {t("uso.leyenda_nuevo")}</span></div>',
        unsafe_allow_html=True,
    )


def _bloque_monto(
    titulo: str,
    monto: float,
    color: str,
    mensaje: str,
    key_ayuda: str | None = None,
    desglose: DesgloseCicloPasado | None = None,
) -> None:
    card_html = (
        f'<div style="background:#1E293B;border-radius:12px;padding:0.85rem 1rem;margin-bottom:0.35rem;'
        f'border-left:4px solid {color};">'
        f'<div style="color:#94A3B8;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
        f"{titulo}</div>"
        f'<div class="ti-money" style="color:#F8FAFC;font-size:1.75rem;font-weight:700;">${monto:,.2f}</div>'
        f'<div style="color:#CBD5E1;font-size:0.85rem;margin-top:0.45rem;">{mensaje}</div></div>'
    )
    if key_ayuda and desglose is not None:
        with fila_accion() as (c_main, c_btn):
            with c_main:
                st.markdown(card_html, unsafe_allow_html=True)
            with c_btn:
                _boton_ayuda(key_ayuda, desglose)
    else:
        st.markdown(card_html, unsafe_allow_html=True)


def _lista_ciclo_nuevo(vista: VistaUso) -> None:
    if vista.ciclo_nuevo_total <= 0:
        return
    for linea in vista.desglose_nuevo.lineas:
        nombre = (
            t("uso.consumo_sin_categoria")
            if linea.nombre == CONSUMO_SIN_DETALLE
            else linea.nombre
        )
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;background:#1E293B;'
            f'border-radius:10px;padding:0.55rem 0.85rem;margin-bottom:0.3rem;'
            f'border-left:4px solid {COLOR_NUEVO};">'
            f'<span style="color:#F8FAFC;font-weight:600;">{nombre}</span>'
            f'<span style="color:#E2E8F0;font-weight:600;">${linea.monto:,.2f}</span></div>',
            unsafe_allow_html=True,
        )


def render_panel_uso(tarjeta: Tarjeta) -> None:
    vista = calcular_vista_uso(tarjeta)
    estado = validar_ciclo(tarjeta)
    idioma = get_language()

    st.subheader(t("pantalla_lista_tarjetas.grafico_limite_titulo"))

    if vista.limite <= 0:
        st.warning(t("pantalla_registrar_tarjeta.error_limite"))
        return

    _barra_limite(vista)

    if vista.mostrar_ciclo_pasado and vista.desglose_pasado:
        d = vista.desglose_pasado
        if estado.dias_hasta_pago > 0:
            monto_pasado = vista.ciclo_pasado_pendiente
            pago_txt = formatear_fecha(estado.fecha_pago_proximo, idioma) if estado.fecha_pago_proximo else "—"
            subtitulo = t(
                "uso.ciclo_pasado_dentro_plazo",
                saldo=vista.ciclo_pasado_pendiente,
                dias=estado.dias_hasta_pago,
                pago=pago_txt,
            )
        elif d.interes_estimado > 0:
            monto_pasado = vista.ciclo_pasado_costo
            subtitulo = t(
                "uso.ciclo_pasado_incluye_interes",
                saldo=d.saldo_no_pagado,
                interes=d.interes_estimado,
            )
        else:
            monto_pasado = vista.ciclo_pasado_pendiente
            subtitulo = t("uso.ciclo_pasado_mensaje")
        _bloque_monto(
            t("uso.ciclo_pasado_titulo"),
            monto_pasado,
            COLOR_PASADO,
            subtitulo,
            key_ayuda=f"uso_pasado_{tarjeta.id}",
            desglose=vista.desglose_pasado,
        )

    _bloque_monto(
        t("uso.ciclo_nuevo_titulo"),
        vista.ciclo_nuevo_total,
        COLOR_NUEVO,
        t("uso.ciclo_nuevo_mensaje"),
    )
    _lista_ciclo_nuevo(vista)

    if vista.ciclo_nuevo_total <= 0:
        st.caption(t("uso.sin_compras_ciclo_nuevo"))

    _bloque_monto(
        t("pantalla_lista_tarjetas.disponible"),
        vista.disponible,
        COLOR_DISP,
        t("uso.disponible_mensaje"),
    )
