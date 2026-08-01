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
from app.ui.form_intereses import aplicar_prefill_a_widgets, limpiar_widgets_intereses


_SESSION_OCR = "reg_ocr_datos"
_SESSION_OCR_TEXTO = "reg_ocr_texto_visto"
SESSION_PREFILL = "reg_ocr_prefill"

# Campos del formulario de registro que deben quedar vacíos al empezar de cero.
_CLAVES_FORM = (
    "limite",
    "adeudado",
    "digitos",
    "corte",
    "pago",
    "url_app_banco",
    "swa_sel_banco",
    "swa_custom_banco",
    "swa_sel_nombre_tarjeta",
    "swa_custom_nombre_tarjeta",
)
_CLAVES_OCR = (_SESSION_OCR, _SESSION_OCR_TEXTO, SESSION_PREFILL, "reg_ocr_manual")


def _borrar(*claves: str) -> None:
    for clave in claves:
        try:
            st.session_state.pop(clave, None)
        except Exception:
            pass


def limpiar_formulario_registro() -> None:
    """Deja el formulario y el análisis en blanco (nueva tarjeta desde cero)."""
    _borrar(*_CLAVES_FORM, *_CLAVES_OCR)
    limpiar_widgets_intereses("reg")


def _aplicar_a_formulario(datos: DatosCaptura) -> None:
    """Rellena el formulario y borra valores viejos (p. ej. $2000 fantasma)."""
    limite = datos.limite
    saldo = datos.saldo
    if limite is not None and saldo is not None and saldo > limite:
        limite, saldo = saldo, limite

    # Siempre sobrescribir estos campos al aplicar OCR (evita $2000 / fechas viejas)
    st.session_state["limite"] = f"{limite:.2f}" if limite is not None else ""
    st.session_state["adeudado"] = f"{saldo:.2f}" if saldo is not None else ""
    st.session_state["digitos"] = datos.ultimos_digitos or ""
    st.session_state["corte"] = str(int(datos.dia_corte)) if datos.dia_corte is not None else ""
    st.session_state["pago"] = str(int(datos.dia_pago)) if datos.dia_pago is not None else ""

    if datos.nombre_tarjeta:
        st.session_state["swa_sel_nombre_tarjeta"] = datos.nombre_tarjeta

    # Intereses / pago mínimo / cargo: escribir directo en las claves de los widgets
    # (Streamlit ignora value= si la key ya existe; por eso hay que setear session_state).
    prefill: dict[str, float] = {}
    if datos.pago_minimo is not None:
        prefill["pago_minimo"] = float(datos.pago_minimo)
    if datos.apr is not None:
        prefill["apr"] = float(datos.apr)
    if datos.penalty_apr is not None:
        prefill["penalty_apr"] = float(datos.penalty_apr)
    if datos.late_fee is not None:
        prefill["cargo_atraso"] = float(datos.late_fee)
    st.session_state[SESSION_PREFILL] = prefill
    aplicar_prefill_a_widgets("reg", prefill)

    texto = (datos.texto_crudo or "").lower()
    sugeridos = [
        ("credit one", "Credit One"),
        ("capital one", "Capital One"),
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
        filas.append(f"- **{t('pantalla_registrar_tarjeta.limite')}:** ${datos.limite:,.2f}")
    if datos.saldo is not None:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.adeudado')}:** ${datos.saldo:,.2f}")
    if datos.disponible is not None:
        filas.append(f"- **{t('pantalla_lista_tarjetas.disponible')}:** ${datos.disponible:,.2f}")
    if datos.pago_minimo is not None:
        filas.append(f"- **{t('intereses.pago_minimo')}:** ${datos.pago_minimo:,.2f}")
    if datos.late_fee is not None:
        filas.append(
            f"- **{t('intereses.cargo_atraso_corto')}:** ${datos.late_fee:,.2f} "
            f"— _{t('intereses.cargo_atraso_nota_ocr')}_"
        )
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

    faltantes = [
        etiqueta
        for valor, etiqueta in (
            (datos.limite, t("pantalla_registrar_tarjeta.limite")),
            (datos.saldo, t("pantalla_registrar_tarjeta.adeudado")),
            (datos.dia_corte, t("pantalla_registrar_tarjeta.fecha_corte")),
            (datos.dia_pago, t("pantalla_registrar_tarjeta.fecha_pago")),
            (datos.ultimos_digitos, t("pantalla_registrar_tarjeta.ultimos_digitos")),
            (datos.pago_minimo, t("intereses.pago_minimo")),
            (datos.late_fee, t("intereses.cargo_atraso_corto")),
            (datos.apr, "APR"),
        )
        if valor is None
    ]
    if faltantes:
        st.caption(
            t("pantalla_registrar_tarjeta.ocr_no_detectado", campos=", ".join(faltantes))
        )


def render_ocr_para_registro() -> None:
    with st.expander(t("pantalla_registrar_tarjeta.ocr_titulo"), expanded=True):
        hay_ocr = ocr_disponible()
        captura = None

        if hay_ocr:
            st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda_con_foto"))
            captura = st.file_uploader(
                t("pantalla_registrar_tarjeta.ocr_uploader"),
                type=["png", "jpg", "jpeg", "webp"],
                key="reg_ocr_upload",
            )
            if captura:
                try:
                    st.image(Image.open(BytesIO(captura.getvalue())), use_container_width=True)
                except Exception:
                    st.caption(t("pantalla_registrar_tarjeta.ocr_imagen_invalida"))
            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual"),
                height=100,
                key="reg_ocr_manual",
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )
        else:
            st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda_solo_texto"))
            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual_solo"),
                height=120,
                key="reg_ocr_manual",
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )

        puede = bool(captura or (texto_manual or "").strip())
        c_analizar, c_limpiar = st.columns([3, 1])
        analizar = c_analizar.button(
            t("pantalla_registrar_tarjeta.ocr_analizar"),
            type="primary",
            use_container_width=True,
            disabled=not puede,
            key="reg_ocr_analizar",
        )
        if c_limpiar.button(
            t("pantalla_registrar_tarjeta.limpiar_formulario"),
            use_container_width=True,
            key="reg_ocr_limpiar",
            help=t("pantalla_registrar_tarjeta.limpiar_formulario_ayuda"),
        ):
            limpiar_formulario_registro()
            st.rerun()

        if analizar:
            # Análisis nuevo: descartar el resultado anterior para no mezclar datos.
            _borrar(_SESSION_OCR, _SESSION_OCR_TEXTO, SESSION_PREFILL)
            imagen = None
            if captura:
                try:
                    imagen = Image.open(BytesIO(captura.getvalue()))
                except Exception:
                    imagen = None
            datos = procesar_imagen_y_texto(imagen, texto_manual or "")
            st.session_state[_SESSION_OCR] = datos.to_dict()
            st.session_state[_SESSION_OCR_TEXTO] = datos.texto_crudo
            if captura and not hay_ocr and not (texto_manual or "").strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.texto_crudo.strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.tiene_datos_tarjeta() and not datos.tiene_tasas():
                st.warning(t("pantalla_registrar_tarjeta.ocr_sin_campos"))
                if datos.texto_crudo.strip():
                    st.info(t("pantalla_registrar_tarjeta.ocr_texto_sin_campos_hint"))

        raw = st.session_state.get(_SESSION_OCR)
        if raw:
            datos = DatosCaptura.from_dict(raw)
            st.markdown(f"**{t('pantalla_registrar_tarjeta.ocr_resultado')}**")
            _mostrar_resumen(datos)
            texto = st.session_state.get(_SESSION_OCR_TEXTO) or datos.texto_crudo
            if texto:
                with st.expander(
                    t("pantalla_registrar_tarjeta.ocr_ver_texto"),
                    expanded=not datos.tiene_datos_tarjeta(),
                ):
                    st.text(texto)
            if st.button(
                t("pantalla_registrar_tarjeta.ocr_usar"),
                type="primary",
                use_container_width=True,
                key="reg_ocr_usar",
                disabled=not datos.tiene_datos_tarjeta(),
            ):
                _aplicar_a_formulario(datos)
                st.success(t("pantalla_registrar_tarjeta.ocr_aplicado"))
                st.rerun()
