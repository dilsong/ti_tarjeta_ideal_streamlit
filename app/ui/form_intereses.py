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


# Claves de widget que el OCR puede rellenar.
CLAVES_WIDGET = (
    "_tasa_anual",
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


def aplicar_prefill_a_widgets(key_prefix: str, prefill: dict[str, float]) -> None:
    """
    Escribe los valores OCR directamente en las claves de los widgets.
    Debe llamarse ANTES de crear los widgets (o antes de un rerun).
    """
    if not prefill:
        return
    limpiar_widgets_intereses(key_prefix)
    if "apr" in prefill:
        st.session_state[f"{key_prefix}_tasa_anual"] = float(prefill["apr"])
    if "penalty_apr" in prefill:
        st.session_state[f"{key_prefix}_tasa_mora"] = float(prefill["penalty_apr"])
    if "cargo_atraso" in prefill:
        st.session_state[f"{key_prefix}_cargo_atraso"] = float(prefill["cargo_atraso"])
    if "pago_minimo" in prefill:
        st.session_state[f"{key_prefix}_pago_manual_on"] = True
        st.session_state[f"{key_prefix}_pago_manual_val"] = float(prefill["pago_minimo"])


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

    abrir_mora = (mora_default is not None) or (cargo_default is not None)
    abrir_minimo = manual_default is not None

    st.markdown(f"**{t('intereses.seccion_titulo')}**")
    if es_estimada and not (prefill or {}).get("apr"):
        st.info(t("intereses.aviso_tasa_estimada", tasa=TASA_INTERES_DEFAULT))

    if prefill:
        avisos: list[str] = []
        if prefill.get("pago_minimo") is not None:
            avisos.append(t("intereses.pago_minimo_detectado", monto=float(prefill["pago_minimo"])))
        if prefill.get("cargo_atraso") is not None:
            avisos.append(
                t("intereses.cargo_atraso_detectado", monto=float(prefill["cargo_atraso"]))
            )
        if prefill.get("penalty_apr") is not None:
            avisos.append(t("intereses.tasa_mora_detectada", tasa=float(prefill["penalty_apr"])))
        if prefill.get("apr") is not None:
            avisos.append(t("intereses.apr_detectada", tasa=float(prefill["apr"])))
        if avisos:
            st.success(" · ".join(avisos))

    # value= solo si la clave aún no existe (OCR ya la pudo haber escrito).
    tasa_kwargs: dict = {
        "min_value": 0.0,
        "max_value": 200.0,
        "step": 0.5,
        "format": "%.2f",
        "key": f"{key_prefix}_tasa_anual",
        "help": t("intereses.tasa_anual_ayuda"),
    }
    if f"{key_prefix}_tasa_anual" not in st.session_state:
        tasa_kwargs["value"] = float(tasa_default)
    tasa = st.number_input(t("intereses.tasa_anual"), **tasa_kwargs)

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

    with st.expander(t("intereses.mora_titulo"), expanded=abrir_mora):
        st.caption(t("intereses.mora_subtitulo"))

        mora_kwargs: dict = {
            "min_value": 0.0,
            "max_value": 200.0,
            "step": 0.5,
            "format": "%.2f",
            "key": f"{key_prefix}_tasa_mora",
            "help": t("intereses.tasa_mora_ayuda"),
        }
        if f"{key_prefix}_tasa_mora" not in st.session_state:
            mora_kwargs["value"] = float(mora_default) if mora_default is not None else 0.0
        mora_val = st.number_input(t("intereses.tasa_mora"), **mora_kwargs)
        mora = float(mora_val) if mora_val and mora_val > 0 else None

        cargo_kwargs: dict = {
            "min_value": 0.0,
            "max_value": 10000.0,
            "step": 5.0,
            "format": "%.2f",
            "key": f"{key_prefix}_cargo_atraso",
            "help": t("intereses.cargo_atraso_ayuda"),
        }
        if f"{key_prefix}_cargo_atraso" not in st.session_state:
            cargo_kwargs["value"] = float(cargo_default or 0.0)
        cargo = st.number_input(t("intereses.cargo_atraso"), **cargo_kwargs)
        st.caption(t("intereses.cargo_atraso_nota"))
        cargo_atraso = float(cargo) if cargo and cargo > 0 else None

    with st.expander(t("intereses.pago_minimo_titulo"), expanded=abrir_minimo):
        st.caption(t("intereses.pago_minimo_subtitulo"))

        on_key = f"{key_prefix}_pago_manual_on"
        if on_key not in st.session_state:
            st.session_state[on_key] = manual_default is not None
        usar_manual = st.checkbox(
            t("intereses.pago_minimo_manual_activar"),
            key=on_key,
        )
        manual = None
        if usar_manual:
            man_kwargs: dict = {
                "min_value": 0.0,
                "step": 1.0,
                "format": "%.2f",
                "key": f"{key_prefix}_pago_manual_val",
            }
            if f"{key_prefix}_pago_manual_val" not in st.session_state:
                man_kwargs["value"] = float(manual_default or 0.0)
            manual = st.number_input(t("intereses.pago_minimo_manual"), **man_kwargs)
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
        pago_minimo_manual=float(manual) if manual and manual > 0 else None,
        cargo_atraso=cargo_atraso,
    )
