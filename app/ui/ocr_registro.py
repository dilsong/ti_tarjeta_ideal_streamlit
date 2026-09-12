"""
OCR al registrar o editar tarjeta: captura → texto → rellenar formulario.
La foto es la vía preferida; pegar texto es respaldo.
"""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

import streamlit as st
from PIL import Image

from app.components.select_with_add import init_select_with_add
from app.components.theme import BANCOS_DEFAULT
from app.core.ocr_captura import DatosCaptura, ocr_disponible, procesar_imagen_y_texto
from app.core.salud_tarjeta import fmt_dinero
from app.i18n.translator import t
from app.ui.form_intereses import aplicar_prefill_a_widgets, limpiar_widgets_intereses

PREFIX_REG = "reg"
PREFIX_EDIT = "edit"

NOMBRES_TARJETA_DEFAULT = [
    "Visa",
    "Mastercard",
    "American Express",
    "Quicksilver",
    "Venture",
    "Savor",
    "Platinum",
    "Gold",
]

SESSION_OCR_DATOS = f"{PREFIX_REG}_ocr_datos"
SESSION_PREFILL = f"{PREFIX_REG}_ocr_prefill"

_CLAVES_FORM_REG = (
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


def _k(prefix: str, name: str) -> str:
    return f"{prefix}_ocr_{name}"


def _borrar(*claves: str) -> None:
    for clave in claves:
        try:
            st.session_state.pop(clave, None)
        except Exception:
            pass


def datos_ocr_pendientes(prefix: str = PREFIX_REG) -> DatosCaptura | None:
    """Datos OCR del último análisis (para persistir al guardar)."""
    raw = st.session_state.get(_k(prefix, "datos"))
    if not raw:
        return None
    return DatosCaptura.from_dict(raw)


def limpiar_formulario_registro() -> None:
    """Deja el formulario de registro y el análisis en blanco."""
    _borrar(
        *_CLAVES_FORM_REG,
        _k(PREFIX_REG, "datos"),
        _k(PREFIX_REG, "texto_visto"),
        _k(PREFIX_REG, "prefill"),
        _k(PREFIX_REG, "manual"),
    )
    limpiar_widgets_intereses(PREFIX_REG)


def limpiar_ocr_analisis(prefix: str) -> None:
    """Descarta solo el análisis OCR (no borra el formulario)."""
    _borrar(
        _k(prefix, "datos"),
        _k(prefix, "texto_visto"),
        _k(prefix, "prefill"),
        _k(prefix, "manual"),
    )


def sugerir_banco_en_select(select_key: str, texto: str) -> None:
    from app.core.ocr_captura import detectar_banco

    banco = detectar_banco(texto)
    if banco:
        init_select_with_add(select_key, "bancos", BANCOS_DEFAULT, banco, force=True)


def _aplicar_a_formulario(
    datos: DatosCaptura,
    *,
    prefix: str,
    widget_prefix: str,
    limite_key: str,
    adeudado_key: str,
    digitos_key: str,
    corte_key: str,
    pago_key: str,
    select_key_banco: str,
    select_key_nombre: str,
    extra: Callable[[DatosCaptura], None] | None = None,
) -> None:
    limite = datos.limite
    saldo = datos.saldo
    if limite is not None and saldo is not None and saldo > limite:
        limite, saldo = saldo, limite

    st.session_state[limite_key] = f"{limite:.2f}" if limite is not None else ""
    st.session_state[adeudado_key] = f"{saldo:.2f}" if saldo is not None else ""
    st.session_state[digitos_key] = datos.ultimos_digitos or ""
    st.session_state[corte_key] = str(int(datos.dia_corte)) if datos.dia_corte is not None else ""
    st.session_state[pago_key] = str(int(datos.dia_pago)) if datos.dia_pago is not None else ""

    if datos.nombre_tarjeta:
        init_select_with_add(
            select_key_nombre,
            "nombres_tarjeta",
            NOMBRES_TARJETA_DEFAULT,
            datos.nombre_tarjeta,
            force=True,
        )

    prefill: dict[str, float] = {}
    if datos.pago_minimo is not None:
        prefill["pago_minimo"] = float(datos.pago_minimo)
    if datos.apr is not None:
        prefill["apr"] = float(datos.apr)
    if datos.penalty_apr is not None:
        prefill["penalty_apr"] = float(datos.penalty_apr)
    if datos.late_fee is not None:
        prefill["cargo_atraso"] = float(datos.late_fee)
    st.session_state[_k(prefix, "prefill")] = prefill
    aplicar_prefill_a_widgets(widget_prefix, prefill)

    if datos.banco:
        init_select_with_add(select_key_banco, "bancos", BANCOS_DEFAULT, datos.banco, force=True)
    elif datos.texto_crudo:
        sugerir_banco_en_select(select_key_banco, datos.texto_crudo)

    if extra:
        extra(datos)


def _aplicar_extra_edit(datos: DatosCaptura) -> None:
    if datos.monto_vencido_atrasado is not None:
        st.session_state["edit_past_due"] = f"{max(0.0, float(datos.monto_vencido_atrasado)):.2f}"
    if datos.pago_sin_intereses is not None:
        st.session_state["edit_pago_sin_intereses"] = f"{float(datos.pago_sin_intereses):.2f}"
    elif datos.saldo is not None:
        st.session_state["edit_pago_sin_intereses"] = f"{float(datos.saldo):.2f}"


def _mostrar_resumen(datos: DatosCaptura) -> None:
    filas: list[str] = []
    if datos.banco:
        filas.append(f"- **{t('pantalla_registrar_tarjeta.banco')}:** {datos.banco}")
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
    if datos.pago_sin_intereses is not None:
        filas.append(
            f"- **{t('salud_tarjeta.pago_sin_intereses')}:** ${datos.pago_sin_intereses:,.2f}"
        )
    if datos.monto_vencido_atrasado is not None and datos.monto_vencido_atrasado > 0:
        filas.append(
            f"- **🚨 {t('salud_tarjeta.monto_vencido')}:** ${datos.monto_vencido_atrasado:,.2f}"
        )
        from app.components.caja_alerta import render_caja_alerta

        render_caja_alerta(
            t(
                "salud_tarjeta.alerta_ocr_detectado",
                monto=fmt_dinero(float(datos.monto_vencido_atrasado)),
            ),
            "urgente",
        )
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
        filas.append(f"- **{t('intereses.tasa_anual')}:** {datos.apr:.2f}%")
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
            (datos.pago_sin_intereses, t("salud_tarjeta.pago_sin_intereses")),
            (datos.late_fee, t("intereses.cargo_atraso_corto")),
            (datos.apr, t("intereses.tasa_anual")),
        )
        if valor is None
    ]
    if faltantes:
        st.caption(
            t("pantalla_registrar_tarjeta.ocr_no_detectado", campos=", ".join(faltantes))
        )


def _render_ocr_formulario(
    *,
    prefix: str,
    titulo_key: str,
    limpiar_callback: Callable[[], None],
    limpiar_label_key: str,
    limpiar_help_key: str,
    aplicar_kwargs: dict,
    expanded: bool = True,
) -> None:
    with st.expander(t(titulo_key), expanded=expanded):
        hay_ocr = ocr_disponible()
        captura = None

        if hay_ocr:
            st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda_con_foto"))
            captura = st.file_uploader(
                t("pantalla_registrar_tarjeta.ocr_uploader"),
                type=["png", "jpg", "jpeg", "webp", "pdf"],
                accept_multiple_files=True,
                key=_k(prefix, "upload"),
            )
            if captura:
                # accept_multiple_files → lista
                items = captura if isinstance(captura, list) else [captura]
                for item in items[:3]:
                    try:
                        if (item.type or "").endswith("pdf") or (item.name or "").lower().endswith(".pdf"):
                            st.caption(f"📄 {item.name}")
                        else:
                            st.image(Image.open(BytesIO(item.getvalue())), use_container_width=True)
                    except Exception:
                        st.caption(t("pantalla_registrar_tarjeta.ocr_imagen_invalida"))
            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual"),
                height=100,
                key=_k(prefix, "manual"),
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )
        else:
            # Siempre mostrar uploader aunque Tesseract no esté (PDF / pegar texto)
            st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda_solo_texto"))
            captura = st.file_uploader(
                "Sube aquí tu PDF o imágenes del estado de cuenta",
                type=["pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=_k(prefix, "upload_sin_ocr"),
            )
            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual_solo"),
                height=120,
                key=_k(prefix, "manual"),
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )

        puede = bool(captura or (texto_manual or "").strip())
        c_analizar, c_limpiar = st.columns([3, 1])
        analizar = c_analizar.button(
            t("pantalla_registrar_tarjeta.ocr_analizar"),
            type="primary",
            use_container_width=True,
            disabled=not puede,
            key=_k(prefix, "analizar"),
        )
        if c_limpiar.button(
            t(limpiar_label_key),
            use_container_width=True,
            key=_k(prefix, "limpiar"),
            help=t(limpiar_help_key),
        ):
            limpiar_callback()
            st.rerun()

        if analizar:
            from app.components.ti_loader import ti_spinner

            _borrar(_k(prefix, "datos"), _k(prefix, "texto_visto"), _k(prefix, "prefill"))
            imagen = None
            if captura:
                items = captura if isinstance(captura, list) else [captura]
                for item in items:
                    try:
                        if (item.type or "").endswith("pdf") or (item.name or "").lower().endswith(".pdf"):
                            continue
                        imagen = Image.open(BytesIO(item.getvalue()))
                        break
                    except Exception:
                        imagen = None
            with ti_spinner("Leyendo e interpretando…"):
                datos = procesar_imagen_y_texto(imagen, texto_manual or "")
            st.session_state[_k(prefix, "datos")] = datos.to_dict()
            st.session_state[_k(prefix, "texto_visto")] = datos.texto_crudo
            if captura and not hay_ocr and not (texto_manual or "").strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.texto_crudo.strip():
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif not datos.tiene_datos_tarjeta() and not datos.tiene_tasas():
                st.warning(t("pantalla_registrar_tarjeta.ocr_sin_campos"))
                if datos.texto_crudo.strip():
                    st.info(t("pantalla_registrar_tarjeta.ocr_texto_sin_campos_hint"))

        raw = st.session_state.get(_k(prefix, "datos"))
        if raw:
            datos = DatosCaptura.from_dict(raw)
            st.markdown(f"**{t('pantalla_registrar_tarjeta.ocr_resultado')}**")
            _mostrar_resumen(datos)
            texto = st.session_state.get(_k(prefix, "texto_visto")) or datos.texto_crudo
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
                key=_k(prefix, "usar"),
                disabled=not datos.tiene_datos_tarjeta(),
            ):
                _aplicar_a_formulario(datos, **aplicar_kwargs)
                st.success(t("pantalla_registrar_tarjeta.ocr_aplicado"))
                st.rerun()


def render_ocr_para_registro() -> None:
    _render_ocr_formulario(
        prefix=PREFIX_REG,
        titulo_key="pantalla_registrar_tarjeta.ocr_titulo",
        limpiar_callback=limpiar_formulario_registro,
        limpiar_label_key="pantalla_registrar_tarjeta.limpiar_formulario",
        limpiar_help_key="pantalla_registrar_tarjeta.limpiar_formulario_ayuda",
        aplicar_kwargs={
            "prefix": PREFIX_REG,
            "widget_prefix": PREFIX_REG,
            "limite_key": "limite",
            "adeudado_key": "adeudado",
            "digitos_key": "digitos",
            "corte_key": "corte",
            "pago_key": "pago",
            "select_key_banco": "banco",
            "select_key_nombre": "nombre_tarjeta",
        },
    )


def render_ocr_para_editar() -> None:
    _render_ocr_formulario(
        prefix=PREFIX_EDIT,
        titulo_key="pantalla_editar_tarjeta.ocr_titulo",
        limpiar_callback=lambda: limpiar_ocr_analisis(PREFIX_EDIT),
        limpiar_label_key="pantalla_editar_tarjeta.ocr_limpiar",
        limpiar_help_key="pantalla_editar_tarjeta.ocr_limpiar_ayuda",
        expanded=False,
        aplicar_kwargs={
            "prefix": PREFIX_EDIT,
            "widget_prefix": PREFIX_EDIT,
            "limite_key": "edit_limite",
            "adeudado_key": "edit_adeudado",
            "digitos_key": "edit_digitos",
            "corte_key": "edit_corte",
            "pago_key": "edit_pago",
            "select_key_banco": "edit_banco",
            "select_key_nombre": "edit_nombre",
            "extra": _aplicar_extra_edit,
        },
    )
