"""Campos compartidos de intereses y pago mínimo para registrar/editar tarjeta."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.core.intereses import TASA_INTERES_DEFAULT, calcular_interes_diario
from app.core.tarjetas import Tarjeta
from app.i18n.translator import t


@dataclass
class DatosIntereses:
    tasa_interes_anual: float
    tasa_interes_mora: float | None
    tasa_es_estimada: bool
    pago_minimo_pct: float
    pago_minimo_piso: float
    pago_minimo_manual: float | None
    cargo_atraso: float | None


# Claves de widget que se reinician cuando el OCR trae valores nuevos.
CLAVES_WIDGET = (
    "_tasa_anual",
    "_usar_mora",
    "_tasa_mora",
    "_pago_manual_on",
    "_pago_manual_val",
    "_pago_pct",
    "_pago_piso",
    "_cargo_atraso",
)


def limpiar_widgets_intereses(key_prefix: str) -> None:
    """Borra el estado de los campos para que tomen los defaults nuevos."""
    for sufijo in CLAVES_WIDGET:
        st.session_state.pop(f"{key_prefix}{sufijo}", None)


def _default(prefill: dict[str, float] | None, clave: str, actual):
    """Prioriza lo detectado por OCR; si no hay, deja el valor actual."""
    valor = (prefill or {}).get(clave)
    return valor if valor is not None else actual


def render_campos_intereses(
    key_prefix: str,
    tarjeta: Tarjeta | None = None,
    prefill: dict[str, float] | None = None,
) -> DatosIntereses:
    """Formulario de tasas e interés diario calculado."""
    tasa_base = tarjeta.tasa_interes_anual if tarjeta else TASA_INTERES_DEFAULT
    tasa_default = _default(prefill, "apr", tasa_base)
    mora_default = _default(prefill, "penalty_apr", tarjeta.tasa_interes_mora if tarjeta else None)
    es_estimada = tarjeta.tasa_es_estimada if tarjeta else True
    pct_default = tarjeta.pago_minimo_pct if tarjeta else 5.0
    piso_default = tarjeta.pago_minimo_piso if tarjeta else 200.0
    manual_default = _default(
        prefill, "pago_minimo", tarjeta.pago_minimo_manual if tarjeta else None
    )
    cargo_default = _default(prefill, "cargo_atraso", tarjeta.cargo_atraso if tarjeta else None)

    st.markdown(f"**{t('intereses.seccion_titulo')}**")
    if es_estimada:
        st.info(t("intereses.aviso_tasa_estimada", tasa=TASA_INTERES_DEFAULT))

    tasa = st.number_input(
        t("intereses.tasa_anual"),
        min_value=0.0,
        max_value=200.0,
        value=float(tasa_default),
        step=0.5,
        format="%.2f",
        key=f"{key_prefix}_tasa_anual",
        help=t("intereses.tasa_anual_ayuda"),
    )

    usar_mora = st.checkbox(
        t("intereses.usar_mora"),
        value=mora_default is not None,
        key=f"{key_prefix}_usar_mora",
    )
    mora = None
    if usar_mora:
        mora = st.number_input(
            t("intereses.tasa_mora"),
            min_value=0.0,
            max_value=200.0,
            value=float(mora_default or tasa_default * 1.5),
            step=0.5,
            format="%.2f",
            key=f"{key_prefix}_tasa_mora",
        )

    cargo = st.number_input(
        t("intereses.cargo_atraso"),
        min_value=0.0,
        max_value=10000.0,
        value=float(cargo_default or 0.0),
        step=5.0,
        format="%.2f",
        key=f"{key_prefix}_cargo_atraso",
        help=t("intereses.cargo_atraso_ayuda"),
    )
    st.caption(t("intereses.cargo_atraso_nota"))
    cargo_atraso = cargo if cargo > 0 else None

    saldo_ref = tarjeta.adeudado_ciclo if tarjeta else 0.0
    diario = calcular_interes_diario(saldo_ref, tasa)
    st.caption(
        t(
            "intereses.interes_diario_calc",
            monto=diario,
            saldo=saldo_ref,
            tasa=tasa,
        )
    )

    with st.expander(t("intereses.pago_minimo_titulo"), expanded=manual_default is not None):
        st.caption(t("intereses.pago_minimo_subtitulo"))
        if (prefill or {}).get("pago_minimo") is not None:
            st.success(t("intereses.pago_minimo_detectado", monto=float(prefill["pago_minimo"])))
        usar_manual = st.checkbox(
            t("intereses.pago_minimo_manual_activar"),
            value=manual_default is not None,
            key=f"{key_prefix}_pago_manual_on",
        )
        manual = None
        if usar_manual:
            manual = st.number_input(
                t("intereses.pago_minimo_manual"),
                min_value=0.0,
                value=float(manual_default or 200.0),
                step=50.0,
                key=f"{key_prefix}_pago_manual_val",
            )
        else:
            pct = st.number_input(
                t("intereses.pago_minimo_pct"),
                min_value=1.0,
                max_value=100.0,
                value=float(pct_default),
                step=1.0,
                key=f"{key_prefix}_pago_pct",
            )
            piso = st.number_input(
                t("intereses.pago_minimo_piso"),
                min_value=0.0,
                value=float(piso_default),
                step=50.0,
                key=f"{key_prefix}_pago_piso",
            )
            pct_default = pct
            piso_default = piso

    tasa_es_estimada = False
    if tarjeta is None:
        tasa_es_estimada = abs(tasa - TASA_INTERES_DEFAULT) < 0.01
    elif tarjeta.tasa_es_estimada and abs(tasa - tarjeta.tasa_interes_anual) < 0.01:
        tasa_es_estimada = abs(tasa - TASA_INTERES_DEFAULT) < 0.01

    return DatosIntereses(
        tasa_interes_anual=tasa,
        tasa_interes_mora=mora,
        tasa_es_estimada=tasa_es_estimada,
        pago_minimo_pct=pct_default,
        pago_minimo_piso=piso_default,
        pago_minimo_manual=manual,
        cargo_atraso=cargo_atraso,
    )
