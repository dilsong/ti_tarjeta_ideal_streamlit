"""
Bloque OCR al registrar tarjeta: captura → texto → rellenar formulario.
La foto es la vía preferida; pegar texto es respaldo.
"""

from __future__ import annotations

from io import BytesIO

import streamlit as st
from PIL import Image

from app.core.ocr_captura import DatosCaptura, ocr_disponible, procesar_imagen_y_texto
from app.i18n.translator import t


_SESSION_OCR = "reg_ocr_datos"
_SESSION_OCR_TEXTO = "reg_ocr_texto_visto"


def _aplicar_a_formulario(datos: DatosCaptura) -> None:
    """Rellena keys del formulario de alta (antes del rerun)."""
    if datos.limite is not None:
        st.session_state["limite"] = f"{datos.limite:.2f}"
    if datos.saldo is not None:
        st.session_state["adeudado"] = f"{datos.saldo:.2f}"
    if datos.ultimos_digitos:
        st.session_state["digitos"] = datos.ultimos_digitos
    if datos.dia_corte is not None:
        st.session_state["corte"] = str(datos.dia_corte)
    if datos.dia_pago is not None:
        st.session_state["pago"] = str(datos.dia_pago)
    if datos.nombre_tarjeta:
        st.session_state["swa_sel_nombre_tarjeta"] = datos.nombre_tarjeta
    if datos.pago_minimo is not None:
        st.session_state["reg_pago_manual_on"] = True
        st.session_state["reg_pago_manual_val"] = float(datos.pago_minimo)
    if datos.apr is not None:
        st.session_state["reg_tasa_anual"] = float(datos.apr)
        st.session_state["reg_usar_mora"] = datos.penalty_apr is not None
    if datos.penalty_apr is not None:
        st.session_state["reg_tasa_mora"] = float(datos.penalty_apr)

    texto = (datos.texto_crudo or "").lower()
    sugeridos = [
        ("capital one", "Capital One"),
        ("credit one", "Credit One"),
        ("bank of america", "Bank of America"),
        ("wells fargo", "Wells Fargo"),
        ("american express", "American Express"),
        ("bbva", "BBVA"),
        ("banorte", "Banorte"),
        ("santander", "Santander"),
        ("scotiabank", "Scotiabank"),
        ("inbursa", "Inbursa"),
        ("chase", "Chase"),
        ("discover", "Discover"),
        ("citi", "Citi"),
        ("hsbc", "HSBC"),
    ]
    for needle, banco in sugeridos:
        if needle in texto:
            st.session_state["swa_sel_banco"] = banco
            break


def _mostrar_resumen(datos: DatosCaptura) -> None:
    filas: list[str] = []
    if datos.nombre_tarjeta:
        filas.append(
            f"- **{t('pantalla_registrar_tarjeta.nombre_tarjeta')}:** {datos.nombre_tarjeta}"
        )
    if datos.limite is not None:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.limite')}:** {datos.limite:,.2f}")
    if datos.saldo is not None:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.adeudado')}:** {datos.saldo:,.2f}")
    if datos.disponible is not None:
        filas.append(f"- **{t('pantalla_lista_tarjetas.disponible')}:** {datos.disponible:,.2f}")
    if datos.pago_minimo is not None:
        filas.append(f"- **Pago mínimo:** {datos.pago_minimo:,.2f}")
    if datos.late_fee is not None:
        filas.append(f"- **Cargo por atraso (hasta):** {datos.late_fee:,.2f}")
    if datos.dia_corte is not None:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.fecha_corte')}:** {datos.dia_corte}")
    if datos.dia_pago is not None:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.fecha_pago')}:** {datos.dia_pago}")
    if datos.ultimos_digitos:
        filas.append(
            f"- **{t('pantalla_registrar_tarjeta.ultimos_digitos')}:** {datos.ultimos_digitos}"
        )
    if datos.apr is not None:
        filas.append(f"- **APR / tasa anual:** {datos.apr:.2f}%")
    if not filas:
        st.warning(t("pantalla_registrar_tarjeta.ocr_sin_campos"))
        return
    st.markdown("\n".join(filas))


def render_ocr_para_registro() -> None:
    """Expander al inicio de Nueva tarjeta."""
    with st.expander(t("pantalla_registrar_tarjeta.ocr_titulo"), expanded=True):
        st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda"))
        if ocr_disponible():
            st.success(t("pantalla_registrar_tarjeta.ocr_listo"))
        else:
            st.warning(t("pantalla_registrar_tarjeta.ocr_instalar_lab"))

        captura = st.file_uploader(
            t("pantalla_registrar_tarjeta.ocr_uploader"),
            type=["png", "jpg", "jpeg", "webp"],
            key="reg_ocr_upload",
        )
        texto_manual = st.text_area(
            t("pantalla_registrar_tarjeta.ocr_texto_manual"),
            height=100,
            key="reg_ocr_manual",
            placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
        )

        if captura:
            try:
                st.image(Image.open(BytesIO(captura.getvalue())), use_container_width=True)
            except Exception:
                st.caption(t("pantalla_registrar_tarjeta.ocr_imagen_invalida"))

        puede = bool(captura or (texto_manual or "").strip())
        if st.button(
            t("pantalla_registrar_tarjeta.ocr_analizar"),
            type="primary",
            use_container_width=True,
            disabled=not puede,
            key="reg_ocr_analizar",
        ):
            imagen = None
            if captura:
                try:
                    imagen = Image.open(BytesIO(captura.getvalue()))
                except Exception:
                    imagen = None
            datos = procesar_imagen_y_texto(imagen, texto_manual or "")
            st.session_state[_SESSION_OCR] = datos.to_dict()
            st.session_state[_SESSION_OCR_TEXTO] = datos.texto_crudo
            if captura and not ocr_disponible() and not (texto_manual or "").strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.texto_crudo.strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.tiene_datos_tarjeta() and not datos.tiene_tasas():
                st.warning(t("pantalla_registrar_tarjeta.ocr_sin_campos"))

        raw = st.session_state.get(_SESSION_OCR)
        if raw:
            datos = DatosCaptura.from_dict(raw)
            st.markdown(f"**{t('pantalla_registrar_tarjeta.ocr_resultado')}**")
            _mostrar_resumen(datos)
            texto = st.session_state.get(_SESSION_OCR_TEXTO) or datos.texto_crudo
            if texto:
                with st.expander(t("pantalla_registrar_tarjeta.ocr_ver_texto")):
                    st.text(texto)
            if st.button(
                t("pantalla_registrar_tarjeta.ocr_usar"),
                type="primary",
                use_container_width=True,
                key="reg_ocr_usar",
            ):
                _aplicar_a_formulario(datos)
                st.success(t("pantalla_registrar_tarjeta.ocr_aplicado"))
                st.rerun()
