"""Guía bancaria, OCR de capturas y actualización de tasas en tarjetas."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image

from app.components.theme import BANCOS_DEFAULT
from app.core.intereses import BASE_DIAS_ANIO
from app.core.tarjetas import Tarjeta, guardar_tarjeta, listar_tarjetas
from app.i18n.translator import t

BANCOS_USA = [
    "Credit One",
    "Capital One",
    "Chase",
    "Discover",
    "Bank of America",
    "Wells Fargo",
    "Citi",
    "American Express",
]

OTRO_BANCO = "Otro banco"

BANCO_SLUG: dict[str, str] = {
    "Credit One": "credit_one",
    "Capital One": "capital_one",
    "Chase": "chase",
    "Discover": "discover",
    "Bank of America": "bank_of_america",
    "Wells Fargo": "wells_fargo",
    "Citi": "citi",
    "American Express": "american_express",
    "BBVA": "bbva",
    "Banorte": "banorte",
    "Santander": "santander",
    "HSBC": "hsbc",
    "Scotiabank": "scotiabank",
    "Inbursa": "inbursa",
    OTRO_BANCO: "otro",
}


@dataclass
class GuiaBanco:
    secciones: list[str]
    palabras_clave: list[str]
    ejemplos: list[str] = field(default_factory=list)


def _catalogo_guias() -> dict[str, dict]:
    from app.i18n.translator import get_language

    lang = get_language()
    path = Path(__file__).resolve().parent.parent / "app" / "i18n" / f"guias_{lang}.json"
    if not path.exists():
        path = Path(__file__).resolve().parent.parent / "app" / "i18n" / "guias_es.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _slug_banco(banco: str) -> str:
    return BANCO_SLUG.get(banco, "otro")


def _etiqueta_banco(nombre: str) -> str:
    if nombre == OTRO_BANCO:
        return t("ayuda_bancos.otro_banco")
    return nombre


@dataclass
class ResultadosOCR:
    apr: float | None = None
    penalty_apr: float | None = None
    late_fee: float | None = None
    annual_fee: float | None = None
    daily_rate: float | None = None
    finance_charge: float | None = None
    texto_crudo: str = ""

    def tiene_datos(self) -> bool:
        return any(
            v is not None
            for v in (
                self.apr,
                self.penalty_apr,
                self.late_fee,
                self.annual_fee,
                self.daily_rate,
                self.finance_charge,
            )
        )

    def tiene_tasas_aplicables(self) -> bool:
        return self.apr is not None or self.penalty_apr is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "apr": self.apr,
            "penalty_apr": self.penalty_apr,
            "late_fee": self.late_fee,
            "annual_fee": self.annual_fee,
            "finance_charge": self.finance_charge,
        }


def listar_bancos_guia() -> list[str]:
    vistos: set[str] = set()
    orden: list[str] = []
    for nombre in list(BANCOS_DEFAULT) + BANCOS_USA:
        if nombre not in vistos:
            vistos.add(nombre)
            orden.append(nombre)
    if OTRO_BANCO not in vistos:
        orden.append(OTRO_BANCO)
    return orden


def _guia_para_banco(banco: str) -> GuiaBanco:
    slug = _slug_banco(banco)
    raw = _catalogo_guias().get(slug, _catalogo_guias().get("otro", {}))
    return GuiaBanco(
        secciones=list(raw.get("secciones", [])),
        palabras_clave=list(raw.get("palabras_clave", [])),
        ejemplos=list(raw.get("ejemplos", [])),
    )


def seleccionar_banco(banco_sugerido: str | None = None, *, key_prefix: str = "") -> str:
    from app.ui.helpers import GUIA_BANCO_KEY

    preselect = st.session_state.pop(GUIA_BANCO_KEY, None)
    bancos = listar_bancos_guia()
    idx = 0
    candidato = preselect or banco_sugerido
    if candidato and candidato in bancos:
        idx = bancos.index(candidato)
    return st.selectbox(
        t("ayuda_bancos.seleccionar_banco"),
        bancos,
        index=idx,
        format_func=_etiqueta_banco,
        key=f"{key_prefix}ayuda_bancos_banco",
    )


def mostrar_mapa_ayuda(banco: str) -> None:
    guia = _guia_para_banco(banco)
    st.subheader(t("ayuda_bancos.guia_titulo", banco=banco))
    st.markdown(f"**{t('ayuda_bancos.secciones_probables')}**")
    for sec in guia.secciones:
        st.markdown(f"- {sec}")
    st.markdown(f"**{t('ayuda_bancos.palabras_clave')}**")
    st.markdown(", ".join(f"`{k}`" for k in guia.palabras_clave))
    if guia.ejemplos:
        st.markdown(f"**{t('ayuda_bancos.ejemplos_tipicos')}**")
        for ej in guia.ejemplos:
            st.markdown(f"- {ej}")
    st.info(t("ayuda_bancos.instruccion_captura"))


def _ocr_disponible() -> bool:
    """True si el binario Tesseract responde (no basta con el paquete pip)."""
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except (TesseractNotFoundError, OSError):
        return False


def _texto_desde_imagen(imagen: Image.Image) -> str:
    if not _ocr_disponible():
        return ""
    import pytesseract
    from pytesseract import TesseractNotFoundError

    try:
        return pytesseract.image_to_string(imagen)
    except (TesseractNotFoundError, OSError):
        return ""



def _extraer_float(match: re.Match[str]) -> float:
    return float(match.group(1).replace(",", "."))


def extraer_datos_financieros(texto: str) -> ResultadosOCR:
    resultados = ResultadosOCR(texto_crudo=texto)
    if not texto.strip():
        return resultados

    patrones_apr = [
        r"(?:Purchase\s+)?APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+(?:de\s+)?inter[eé]s\s+(?:ordinari[ao]\s+)?anual[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+anual\s+ordinari[ao][:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"(?:Annual\s+Percentage\s+Rate|APR)\s*(?:for\s+Purchases)?[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
    ]
    for pat in patrones_apr:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultados.apr = _extraer_float(m)
            break

    m = re.search(r"Penalty\s+APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
    if m:
        resultados.penalty_apr = _extraer_float(m)
    if resultados.penalty_apr is None:
        m = re.search(r"Tasa\s+moratoria[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
        if m:
            resultados.penalty_apr = _extraer_float(m)

    for pat in (
        r"Late\s+(?:Payment\s+)?Fee[:\s]*(?:up\s+to\s+)?\$?([\d]+(?:[.,]\d+)?)",
        r"Comisi[oó]n\s+por\s+pago\s+tard[ií]o[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Comisi[oó]n\s+por\s+atraso[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultados.late_fee = _extraer_float(m)
            break

    for pat in (
        r"Annual\s+Fee[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Anualidad[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultados.annual_fee = _extraer_float(m)
            break

    m = re.search(r"Daily\s+Periodic\s+Rate[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
    if m:
        resultados.daily_rate = _extraer_float(m)

    for pat in (
        r"Finance\s+Charge[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Interest\s+Charged[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Intereses\s+(?:del\s+periodo|cargo)[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Inter[eé]s\s+cobrado[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultados.finance_charge = _extraer_float(m)
            break

    return resultados


def procesar_captura(imagen: Image.Image, texto_manual: str = "") -> ResultadosOCR:
    texto_ocr = _texto_desde_imagen(imagen)
    texto = "\n".join(p for p in (texto_ocr, texto_manual) if p.strip())
    return extraer_datos_financieros(texto)


def generar_resumen(resultados: ResultadosOCR) -> None:
    st.subheader(t("ayuda_bancos.resumen_titulo"))
    if not resultados.tiene_datos():
        st.warning(t("ayuda_bancos.sin_datos"))
        return

    if resultados.late_fee is not None or resultados.finance_charge is not None:
        st.markdown(t("ayuda_bancos.interpretacion_cargos"))
    elif resultados.penalty_apr is not None:
        st.markdown(t("ayuda_bancos.interpretacion_mora"))
    else:
        st.markdown(t("ayuda_bancos.interpretacion_tasas"))

    if resultados.late_fee is not None:
        st.markdown(f"- {t('ayuda_bancos.linea_late_fee', monto=resultados.late_fee)}")

    if resultados.finance_charge is not None:
        st.markdown(f"- {t('ayuda_bancos.linea_finance', monto=resultados.finance_charge)}")

    if resultados.penalty_apr is not None:
        st.markdown(f"- {t('ayuda_bancos.linea_penalty', apr=resultados.penalty_apr)}")

    if resultados.apr is not None:
        mensual = resultados.apr / 12
        diaria = resultados.apr / BASE_DIAS_ANIO
        st.markdown(f"- {t('ayuda_bancos.linea_apr', apr=resultados.apr)}")
        st.markdown(f"- {t('ayuda_bancos.linea_mensual', tasa=mensual)}")
        st.markdown(f"- {t('ayuda_bancos.linea_diaria', tasa=diaria, base=BASE_DIAS_ANIO)}")

    if resultados.annual_fee is not None:
        st.markdown(f"- {t('ayuda_bancos.linea_annual_fee', monto=resultados.annual_fee)}")

    if resultados.daily_rate is not None:
        st.markdown(f"- {t('ayuda_bancos.linea_daily', tasa=resultados.daily_rate)}")

    st.info(t("ayuda_bancos.resumen_info"))


def _render_aplicar_opcional(
    resultados: ResultadosOCR,
    tarjetas: list[Tarjeta],
    tarjeta_default: Tarjeta | None,
    *,
    key_prefix: str = "",
    ocr_session_key: str = "ayuda_ocr_resultados",
) -> None:
    if not resultados.tiene_tasas_aplicables():
        return

    with st.expander(t("ayuda_bancos.aplicar_opcional_titulo"), expanded=False):
        st.caption(t("ayuda_bancos.aplicar_opcional_nota"))
        tarjeta = seleccionar_tarjeta_para_actualizar(
            tarjetas, tarjeta_default, key_prefix=key_prefix
        )
        if tarjeta is None:
            return

        aplicar_apr = resultados.apr is not None
        aplicar_mora = resultados.penalty_apr is not None
        if aplicar_apr:
            st.checkbox(
                t("ayuda_bancos.aplicar_apr", apr=resultados.apr),
                value=True,
                key=f"{key_prefix}ayuda_aplicar_apr",
            )
        if aplicar_mora:
            st.checkbox(
                t("ayuda_bancos.aplicar_mora", apr=resultados.penalty_apr),
                value=True,
                key=f"{key_prefix}ayuda_aplicar_mora",
            )

        if st.button(
            t("ayuda_bancos.aplicar_boton"),
            key=f"{key_prefix}ayuda_aplicar_btn",
            use_container_width=True,
        ):
            a_aplicar = ResultadosOCR()
            if aplicar_apr and st.session_state.get(f"{key_prefix}ayuda_aplicar_apr", True):
                a_aplicar.apr = resultados.apr
            if aplicar_mora and st.session_state.get(f"{key_prefix}ayuda_aplicar_mora", True):
                a_aplicar.penalty_apr = resultados.penalty_apr
            if not a_aplicar.apr and not a_aplicar.penalty_apr:
                st.warning(t("ayuda_bancos.nada_que_aplicar"))
                return
            actualizada = actualizar_tarjeta(tarjeta, a_aplicar)
            st.success(t("ayuda_bancos.exito", nombre=actualizada.nombre))
            st.session_state.pop(ocr_session_key, None)
            st.rerun()


def seleccionar_tarjeta_para_actualizar(
    tarjetas: list[Tarjeta],
    tarjeta_default: Tarjeta | None = None,
    *,
    key_prefix: str = "",
) -> Tarjeta | None:
    if not tarjetas:
        st.warning(t("ayuda_bancos.sin_tarjetas"))
        return None
    etiquetas = [f"{tj.banco} — {tj.nombre} (•••• {tj.ultimos_digitos})" for tj in tarjetas]
    idx = 0
    if tarjeta_default:
        for i, tj in enumerate(tarjetas):
            if tj.id == tarjeta_default.id:
                idx = i
                break
    sel = st.selectbox(
        t("ayuda_bancos.seleccionar_tarjeta"),
        range(len(etiquetas)),
        format_func=lambda i: etiquetas[i],
        index=idx,
        key=f"{key_prefix}ayuda_bancos_tarjeta",
    )
    return tarjetas[sel]


def actualizar_tarjeta(tarjeta: Tarjeta, resultados: ResultadosOCR) -> Tarjeta:
    nueva_tasa = resultados.apr if resultados.apr is not None else tarjeta.tasa_interes_anual
    nueva_mora = resultados.penalty_apr if resultados.penalty_apr is not None else tarjeta.tasa_interes_mora
    tasa_confirmada = resultados.apr is not None or resultados.penalty_apr is not None

    actualizada = Tarjeta(
        id=tarjeta.id,
        banco=tarjeta.banco,
        nombre=tarjeta.nombre,
        limite=tarjeta.limite,
        adeudado=tarjeta.adeudado,
        ultimos_digitos=tarjeta.ultimos_digitos,
        color=tarjeta.color,
        estilo=tarjeta.estilo,
        dia_corte=tarjeta.dia_corte,
        dia_pago=tarjeta.dia_pago,
        adeudado_ciclo=tarjeta.adeudado_ciclo,
        fecha_corte_aplicada=tarjeta.fecha_corte_aplicada,
        umbral_uso_pct=tarjeta.umbral_uso_pct,
        umbral_disponible_min=tarjeta.umbral_disponible_min,
        tasa_interes_anual=nueva_tasa,
        tasa_interes_mora=nueva_mora,
        tasa_es_estimada=False if tasa_confirmada else tarjeta.tasa_es_estimada,
        pago_minimo_pct=tarjeta.pago_minimo_pct,
        pago_minimo_piso=tarjeta.pago_minimo_piso,
        pago_minimo_manual=tarjeta.pago_minimo_manual,
    )
    guardar_tarjeta(actualizada)
    return actualizada


def mapa_ayuda_bancaria(tarjeta_sel: Tarjeta | None = None, *, key_prefix: str = "guia_tab_") -> None:
    tarjetas = listar_tarjetas()
    banco_sugerido = tarjeta_sel.banco if tarjeta_sel else None
    ocr_key = f"{key_prefix}ayuda_ocr_resultados"
    ocr_texto_key = f"{key_prefix}ayuda_ocr_texto"

    banco = seleccionar_banco(banco_sugerido, key_prefix=key_prefix)
    mostrar_mapa_ayuda(banco)

    st.divider()
    st.markdown(f"**{t('ayuda_bancos.subir_captura')}**")
    captura = st.file_uploader(
        t("ayuda_bancos.uploader_label"),
        type=["png", "jpg", "jpeg", "webp"],
        key=f"{key_prefix}ayuda_bancos_captura",
    )
    texto_manual = st.text_area(
        t("ayuda_bancos.texto_manual"),
        placeholder=t("ayuda_bancos.texto_manual_placeholder"),
        height=120,
        key=f"{key_prefix}ayuda_bancos_texto_manual",
    )
    if captura:
        imagen_prev = Image.open(BytesIO(captura.getvalue()))
        st.image(imagen_prev, caption=t("ayuda_bancos.vista_previa"), use_container_width=True)
    if not _ocr_disponible():
        st.info(
            t("ayuda_bancos.ocr_no_disponible")
            + " Puedes pegar el texto de la captura en el cuadro de abajo y analizar."
        )

    puede_analizar = bool(captura or texto_manual.strip())
    resultados: ResultadosOCR | None = None

    if puede_analizar and st.button(
        t("ayuda_bancos.analizar"),
        type="primary",
        use_container_width=True,
        key=f"{key_prefix}ayuda_bancos_analizar",
    ):
        imagen = Image.open(BytesIO(captura.getvalue())) if captura else Image.new("RGB", (1, 1), "white")
        resultados = procesar_captura(imagen, texto_manual=texto_manual)
        if captura and not resultados.texto_crudo.strip() and not texto_manual.strip():
            st.warning(
                "No se pudo leer texto de la imagen (OCR no disponible). "
                "Pega el texto de la captura en el cuadro manual y vuelve a analizar."
            )
        st.session_state[ocr_key] = resultados.to_dict()
        st.session_state[ocr_texto_key] = resultados.texto_crudo

    if ocr_key in st.session_state:
        data = st.session_state[ocr_key]
        resultados = ResultadosOCR(
            apr=data.get("apr"),
            penalty_apr=data.get("penalty_apr"),
            late_fee=data.get("late_fee"),
            annual_fee=data.get("annual_fee"),
            daily_rate=data.get("daily_rate"),
            finance_charge=data.get("finance_charge"),
            texto_crudo=st.session_state.get(ocr_texto_key, ""),
        )
        st.divider()
        generar_resumen(resultados)
        if resultados.tiene_datos():
            _render_aplicar_opcional(
                resultados,
                tarjetas,
                tarjeta_sel,
                key_prefix=key_prefix,
                ocr_session_key=ocr_key,
            )
