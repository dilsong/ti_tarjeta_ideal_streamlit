"""
Alta / edición de tarjeta en 2 pasos guiados:
  Paso 1 — Reglas del banco (estado de cuenta)
  Paso 2 — Saldos en tiempo real (app del banco)
"""

from __future__ import annotations

from io import BytesIO

import streamlit as st
from PIL import Image

from app.components.keyboard_numeric import entero_text_input, monto_text_input, parse_monto
from app.components.segmented_control import segmented_control
from app.components.select_with_add import (
    init_select_with_add,
    persist_if_new,
    select_with_add,
)
from app.components.theme import BANCOS_DEFAULT, CARD_COLORS
from app.core.enlaces_banco import url_catalogo
from app.core.ocr_captura import (
    DatosCaptura,
    ocr_disponible,
    pdf_disponible,
    procesar_fuentes_captura,
    procesar_ocr_saldos,
)
from app.core.salud_tarjeta import fmt_dinero
from app.core.tarjetas import EstiloTarjeta, Tarjeta, guardar_tarjeta, obtener_tarjeta
from app.i18n.translator import t
from app.ui.form_intereses import aplicar_prefill_a_widgets, render_campos_intereses

NOMBRES_DEFAULT = ["Visa", "Mastercard", "American Express", "Platinum", "Gold"]
PREF_VALS = ["app", "web"]
ESTILO_VALS = [EstiloTarjeta.REALISTA.value, EstiloTarjeta.SOLIDO.value, EstiloTarjeta.PREMIUM.value]


def _paso_key(prefix: str) -> str:
    return f"{prefix}_wizard_paso"


def _ocr_key(prefix: str, paso: int) -> str:
    return f"{prefix}_ocr_p{paso}_datos"


def _prefill_key(prefix: str, paso: int) -> str:
    return f"{prefix}_ocr_p{paso}_prefill"


def _render_stepper(paso: int) -> None:
    c1, c2 = st.columns(2)
    with c1:
        cls = "primary" if paso == 1 else "secondary"
        st.markdown(
            f'<div style="padding:0.45rem 0.65rem;border-radius:8px;text-align:center;'
            f'background:{"#1E3A5F" if paso == 1 else "#1E293B"};'
            f'border:1px solid {"#3B82F6" if paso == 1 else "#334155"};">'
            f'<strong>{t("wizard_tarjeta.paso1_badge")}</strong></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="padding:0.45rem 0.65rem;border-radius:8px;text-align:center;'
            f'background:{"#1E3A5F" if paso == 2 else "#1E293B"};'
            f'border:1px solid {"#3B82F6" if paso == 2 else "#334155"};">'
            f'<strong>{t("wizard_tarjeta.paso2_badge")}</strong></div>',
            unsafe_allow_html=True,
        )


def _aplicar_ocr_paso1(prefix: str, datos: DatosCaptura) -> None:
    from app.ui.ocr_registro import NOMBRES_TARJETA_DEFAULT, sugerir_banco_en_select

    if datos.limite is not None:
        st.session_state[f"{prefix}_limite"] = f"{datos.limite:.2f}"
    if datos.dia_corte is not None:
        st.session_state[f"{prefix}_corte"] = str(int(datos.dia_corte))
    if datos.dia_pago is not None:
        st.session_state[f"{prefix}_pago"] = str(int(datos.dia_pago))
    if datos.ultimos_digitos:
        st.session_state[f"{prefix}_digitos"] = datos.ultimos_digitos

    select_banco = f"{prefix}_banco" if prefix == "reg" else "edit_banco"
    select_nombre = f"{prefix}_nombre_tarjeta" if prefix == "reg" else "edit_nombre"
    if datos.nombre_tarjeta:
        init_select_with_add(
            select_nombre,
            "nombres_tarjeta",
            NOMBRES_TARJETA_DEFAULT,
            datos.nombre_tarjeta,
            force=True,
        )
    if datos.texto_crudo:
        sugerir_banco_en_select(select_banco, datos.texto_crudo)

    prefill: dict[str, float] = {}
    if datos.apr is not None:
        prefill["apr"] = float(datos.apr)
    if datos.penalty_apr is not None:
        prefill["penalty_apr"] = float(datos.penalty_apr)
    if datos.late_fee is not None:
        prefill["cargo_atraso"] = float(datos.late_fee)
    if datos.pago_minimo is not None:
        prefill["pago_minimo"] = float(datos.pago_minimo)
    st.session_state[_prefill_key(prefix, 1)] = prefill
    aplicar_prefill_a_widgets(prefix, prefill)


def _aplicar_ocr_paso2(prefix: str, datos: DatosCaptura) -> None:
    saldo_hoy = datos.current_balance if datos.current_balance is not None else datos.saldo
    saldo_cierre = datos.statement_balance if datos.statement_balance is not None else datos.pago_sin_intereses

    if saldo_hoy is not None:
        st.session_state[f"{prefix}_adeudado"] = f"{saldo_hoy:.2f}"
    if saldo_cierre is not None:
        st.session_state[f"{prefix}_saldo_cierre"] = f"{saldo_cierre:.2f}"
    if datos.pago_minimo is not None:
        st.session_state[f"{prefix}_pago_min_hoy"] = f"{datos.pago_minimo:.2f}"
    if datos.monto_vencido_atrasado is not None:
        st.session_state[f"{prefix}_past_due"] = f"{max(0.0, float(datos.monto_vencido_atrasado)):.2f}"


def _mostrar_resumen_ocr(datos: DatosCaptura, paso: int) -> None:
    filas: list[str] = []
    if paso == 1:
        campos = (
            (datos.limite, t("wizard_tarjeta.campo_limite")),
            (datos.dia_corte, t("pantalla_registrar_tarjeta.fecha_corte")),
            (datos.dia_pago, t("pantalla_registrar_tarjeta.fecha_pago")),
            (datos.apr, t("intereses.tasa_anual")),
            (datos.late_fee, t("intereses.cargo_atraso_corto")),
            (datos.pago_minimo, t("intereses.pago_minimo")),
        )
    else:
        saldo_hoy = datos.current_balance if datos.current_balance is not None else datos.saldo
        saldo_cierre = datos.statement_balance if datos.statement_balance is not None else datos.pago_sin_intereses
        campos = (
            (saldo_cierre, t("wizard_tarjeta.campo_saldo_cierre")),
            (saldo_hoy, t("wizard_tarjeta.campo_saldo_hoy")),
            (datos.pago_minimo, t("wizard_tarjeta.campo_pago_min_hoy")),
            (datos.monto_vencido_atrasado, t("salud_tarjeta.monto_vencido")),
        )
    for valor, etiqueta in campos:
        if valor is not None:
            if isinstance(valor, float):
                filas.append(f"- **{etiqueta}:** ${valor:,.2f}" if valor > 31 else f"- **{etiqueta}:** {valor}")
            else:
                filas.append(f"- **{etiqueta}:** {valor}")
    if filas:
        st.markdown("\n".join(filas))
    else:
        st.warning(t("pantalla_registrar_tarjeta.ocr_sin_campos"))


def _es_pdf_upload(archivo) -> bool:
    nombre = (getattr(archivo, "name", "") or "").lower()
    mime = (getattr(archivo, "type", "") or "").lower()
    return mime == "application/pdf" or nombre.endswith(".pdf")


def _abrir_imagen_upload(archivo) -> Image.Image | None:
    try:
        return Image.open(BytesIO(archivo.getvalue()))
    except Exception:
        return None


def _render_ocr_bloque(
    prefix: str,
    paso: int,
    procesar_fn,
    aplicar_fn,
) -> None:
    ocr_k = _ocr_key(prefix, paso)
    hay_ocr = ocr_disponible()
    titulo = t("wizard_tarjeta.ocr_p1_titulo") if paso == 1 else t("wizard_tarjeta.ocr_p2_titulo")
    ayuda = t("wizard_tarjeta.ocr_p1_ayuda") if paso == 1 else t("wizard_tarjeta.ocr_p2_ayuda")
    multi = paso == 1

    with st.expander(titulo, expanded=True):
        st.caption(ayuda)
        capturas: list = []
        # Paso 1: PDF + varias imágenes (reglas pueden venir en varios documentos).
        # Paso 2: una captura de la app (saldos).
        mostrar_uploader = multi or hay_ocr
        if mostrar_uploader:
            tipos = ["png", "jpg", "jpeg", "pdf"] if multi else ["png", "jpg", "jpeg", "webp"]
            label = (
                t("wizard_tarjeta.ocr_uploader_multi")
                if multi
                else t("wizard_tarjeta.ocr_uploader")
            )
            subido = st.file_uploader(
                label,
                type=tipos,
                accept_multiple_files=multi,
                key=f"{prefix}_ocr_p{paso}_upload",
            )
            if multi:
                capturas = list(subido or [])
            elif subido is not None:
                capturas = [subido]

            if capturas:
                n_pdf = sum(1 for f in capturas if _es_pdf_upload(f))
                n_img = len(capturas) - n_pdf
                if multi and len(capturas) > 1:
                    st.caption(
                        t(
                            "wizard_tarjeta.ocr_multi_resumen",
                            n=len(capturas),
                            imgs=n_img,
                            pdfs=n_pdf,
                        )
                    )
                for archivo in capturas:
                    if _es_pdf_upload(archivo):
                        st.info(f"📄 {archivo.name} — {t('wizard_tarjeta.ocr_pdf_hint')}")
                    else:
                        img = _abrir_imagen_upload(archivo)
                        if img is not None:
                            st.image(img, use_container_width=True, caption=archivo.name)
                        else:
                            st.caption(t("pantalla_registrar_tarjeta.ocr_imagen_invalida"))

            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual"),
                height=90,
                key=f"{prefix}_ocr_p{paso}_manual",
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )
        else:
            st.caption(t("pantalla_registrar_tarjeta.ocr_ayuda_solo_texto"))
            texto_manual = st.text_area(
                t("pantalla_registrar_tarjeta.ocr_texto_manual_solo"),
                height=100,
                key=f"{prefix}_ocr_p{paso}_manual",
                placeholder=t("pantalla_registrar_tarjeta.ocr_texto_placeholder"),
            )

        puede = bool(capturas or (texto_manual or "").strip())
        if st.button(
            t("pantalla_registrar_tarjeta.ocr_analizar"),
            type="primary",
            use_container_width=True,
            disabled=not puede,
            key=f"{prefix}_ocr_p{paso}_analizar",
        ):
            imagenes: list[Image.Image] = []
            pdfs: list[bytes] = []
            for archivo in capturas:
                if _es_pdf_upload(archivo):
                    pdfs.append(archivo.getvalue())
                else:
                    img = _abrir_imagen_upload(archivo)
                    if img is not None:
                        imagenes.append(img)

            if multi:
                if imagenes and not hay_ocr:
                    st.warning(t("pantalla_registrar_tarjeta.ocr_no_disponible_pegar"))
                imgs = imagenes if hay_ocr else []
                if pdfs and not pdf_disponible():
                    st.error(t("wizard_tarjeta.ocr_pdf_no_disponible"))
                    datos = procesar_fuentes_captura(
                        imagenes=imgs,
                        texto_manual=texto_manual or "",
                    )
                else:
                    datos = procesar_fuentes_captura(
                        imagenes=imgs,
                        pdfs_bytes=pdfs,
                        texto_manual=texto_manual or "",
                    )
            else:
                imagen = imagenes[0] if imagenes else None
                datos = procesar_fn(imagen, texto_manual or "")

            st.session_state[ocr_k] = datos.to_dict()
            if (
                not datos.texto_crudo.strip()
                and not imagenes
                and not (texto_manual or "").strip()
                and (not pdfs or not datos.tiene_algo())
            ):
                st.error(t("pantalla_registrar_tarjeta.ocr_fallo"))
            elif pdfs and not datos.texto_crudo.strip() and not imagenes:
                st.warning(t("wizard_tarjeta.ocr_pdf_sin_texto"))
            elif paso == 1 and not datos.tiene_reglas_banco():
                st.warning(t("wizard_tarjeta.ocr_p1_sin_reglas"))
            elif paso == 2 and not datos.tiene_saldos_hoy():
                st.warning(t("wizard_tarjeta.ocr_p2_sin_saldos"))
            elif multi and (len(imagenes) + len(pdfs)) > 1 and datos.tiene_reglas_banco():
                st.success(t("wizard_tarjeta.ocr_multi_ok"))

        raw = st.session_state.get(ocr_k)
        if raw:
            datos = DatosCaptura.from_dict(raw)
            st.markdown(f"**{t('pantalla_registrar_tarjeta.ocr_resultado')}**")
            _mostrar_resumen_ocr(datos, paso)
            if st.button(
                t("pantalla_registrar_tarjeta.ocr_usar"),
                type="primary",
                use_container_width=True,
                key=f"{prefix}_ocr_p{paso}_usar",
            ):
                aplicar_fn(prefix, datos)
                st.success(t("pantalla_registrar_tarjeta.ocr_aplicado"))
                st.rerun()


def _keys_form(prefix: str) -> dict[str, str]:
    if prefix == "reg":
        return {
            "banco": "banco",
            "nombre": "nombre_tarjeta",
            "limite": "limite",
            "adeudado": "adeudado",
            "digitos": "digitos",
            "corte": "corte",
            "pago": "pago",
            "saldo_cierre": "saldo_cierre",
            "pago_min_hoy": "pago_min_hoy",
            "past_due": "past_due",
            "preferencia": "preferencia_banco",
            "url": "url_app_banco",
            "color": "color",
            "estilo_seg": "estilo",
        }
    return {
        "banco": "edit_banco",
        "nombre": "edit_nombre",
        "limite": "edit_limite",
        "adeudado": "edit_adeudado",
        "digitos": "edit_digitos",
        "corte": "edit_corte",
        "pago": "edit_pago",
        "saldo_cierre": "edit_pago_sin_intereses",
        "pago_min_hoy": "edit_pago_min_hoy",
        "past_due": "edit_past_due",
        "preferencia": "edit_preferencia_banco",
        "url": "edit_url_app_banco",
        "color": "edit_color",
        "estilo_seg": "edit_estilo",
    }


def _init_form_desde_tarjeta(prefix: str, tarjeta: Tarjeta) -> None:
    k = _keys_form(prefix)
    init_select_with_add("edit_banco" if prefix != "reg" else "banco", "bancos", BANCOS_DEFAULT, tarjeta.banco, force=True)
    init_select_with_add(
        "edit_nombre" if prefix != "reg" else "nombre_tarjeta",
        "nombres_tarjeta",
        NOMBRES_DEFAULT,
        tarjeta.nombre,
        force=True,
    )
    st.session_state[k["limite"]] = f"{tarjeta.limite:.2f}"
    st.session_state[k["adeudado"]] = f"{tarjeta.adeudado:.2f}"
    st.session_state[k["corte"]] = str(tarjeta.dia_corte)
    st.session_state[k["pago"]] = str(tarjeta.dia_pago)
    st.session_state[k["digitos"]] = tarjeta.ultimos_digitos
    psi = tarjeta.pago_sin_intereses or tarjeta.adeudado_ciclo
    st.session_state[k["saldo_cierre"]] = f"{float(psi):.2f}" if psi and psi > 0 else "0.00"
    st.session_state[k["past_due"]] = f"{float(tarjeta.monto_vencido_atrasado or 0):.2f}"
    pm = tarjeta.pago_minimo_manual
    st.session_state[k["pago_min_hoy"]] = f"{float(pm):.2f}" if pm and pm > 0 else "0.00"
    pref = (tarjeta.preferencia_banco or "app").strip().lower()
    st.session_state[k["preferencia"]] = "web" if pref == "web" else "app"
    color_keys = list(CARD_COLORS.keys())
    st.session_state[k["color"]] = tarjeta.color if tarjeta.color in color_keys else "azul"
    estilo_map = {EstiloTarjeta.REALISTA.value: 0, EstiloTarjeta.SOLIDO.value: 1, EstiloTarjeta.PREMIUM.value: 2}
    st.session_state[f"seg_{k['estilo_seg']}"] = estilo_map.get(tarjeta.estilo, 1)


def _render_paso1(prefix: str, tarjeta: Tarjeta | None) -> bool:
    """Paso 1 — reglas. Devuelve True si el usuario avanzó al paso 2."""
    st.markdown(f"### {t('wizard_tarjeta.paso1_titulo')}")
    st.caption(t("wizard_tarjeta.paso1_texto"))

    _render_ocr_bloque(prefix, 1, None, _aplicar_ocr_paso1)

    k = _keys_form(prefix)
    banco = select_with_add(
        t("pantalla_registrar_tarjeta.banco"),
        BANCOS_DEFAULT,
        key=k["banco"],
        categoria="bancos",
    )
    nombre = select_with_add(
        t("pantalla_registrar_tarjeta.nombre_tarjeta"),
        NOMBRES_DEFAULT,
        key=k["nombre"],
        categoria="nombres_tarjeta",
    )
    digitos = st.text_input(
        t("pantalla_registrar_tarjeta.ultimos_digitos"),
        key=k["digitos"],
        max_chars=4,
        placeholder="1234",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        limite = monto_text_input(t("wizard_tarjeta.campo_limite"), k["limite"], placeholder="2000.00")
    with c2:
        corte = entero_text_input(t("pantalla_registrar_tarjeta.fecha_corte"), k["corte"], placeholder="5")
    with c3:
        pago = entero_text_input(t("pantalla_registrar_tarjeta.fecha_pago"), k["pago"], placeholder="15")

    prefill = st.session_state.get(_prefill_key(prefix, 1))
    datos_int = render_campos_intereses(prefix, tarjeta, prefill=prefill)

    err = st.empty()
    if st.button(t("wizard_tarjeta.btn_siguiente"), type="primary", use_container_width=True, key=f"{prefix}_paso1_next"):
        if not banco.strip() or not nombre.strip() or len(digitos) != 4 or not digitos.isdigit():
            err.error(t("pantalla_registrar_tarjeta.error_campos"))
        elif limite <= 0:
            err.error(t("pantalla_registrar_tarjeta.error_limite"))
        elif not (1 <= int(corte) <= 31 and 1 <= int(pago) <= 31):
            err.error(t("pantalla_registrar_tarjeta.error_campos"))
        else:
            st.session_state[_paso_key(prefix)] = 2
            st.session_state[f"{prefix}_datos_int"] = datos_int
            st.rerun()
    return False


def _render_paso2(
    prefix: str,
    tarjeta: Tarjeta | None,
    on_back,
    on_saved,
    *,
    editar_id: str | None = None,
) -> None:
    st.markdown(f"### {t('wizard_tarjeta.paso2_titulo')}")
    st.caption(t("wizard_tarjeta.paso2_texto"))

    _render_ocr_bloque(prefix, 2, procesar_ocr_saldos, _aplicar_ocr_paso2)

    k = _keys_form(prefix)
    limite = parse_monto(str(st.session_state.get(k["limite"], "0")))

    c1, c2 = st.columns(2)
    with c1:
        saldo_cierre = monto_text_input(
            t("wizard_tarjeta.campo_saldo_cierre"),
            k["saldo_cierre"],
            placeholder="244.58",
        )
    with c2:
        saldo_hoy = monto_text_input(
            t("wizard_tarjeta.campo_saldo_hoy"),
            k["adeudado"],
            placeholder="272.01",
        )

    c3, c4 = st.columns(2)
    with c3:
        pago_min_hoy = monto_text_input(
            t("wizard_tarjeta.campo_pago_min_hoy"),
            k["pago_min_hoy"],
            placeholder="30.00",
        )
    with c4:
        past_due = monto_text_input(
            t("salud_tarjeta.monto_vencido"),
            k["past_due"],
            placeholder="0.00",
        )

    if limite > 0 and saldo_hoy >= 0:
        disp = max(0.0, limite - saldo_hoy)
        st.info(t("wizard_tarjeta.disponible_calc", monto=fmt_dinero(disp)))

    st.divider()
    st.markdown(f"**{t('wizard_tarjeta.seccion_apariencia')}**")

    color_keys = list(CARD_COLORS.keys())
    if k["color"] not in st.session_state:
        st.session_state[k["color"]] = "azul"
    color = st.selectbox(
        t("pantalla_registrar_tarjeta.color"),
        color_keys,
        format_func=lambda c: t(f"colores.{c}"),
        key=k["color"],
    )

    estilo_opts = [
        t("pantalla_registrar_tarjeta.estilo_realista"),
        t("pantalla_registrar_tarjeta.estilo_solido"),
        t("pantalla_registrar_tarjeta.estilo_premium"),
    ]
    st.caption(t("pantalla_registrar_tarjeta.estilo"))
    estilo_idx, _ = segmented_control(estilo_opts, key=k["estilo_seg"])

    c_pref, _ = st.columns([8, 1])
    with c_pref:
        st.markdown(f"**{t('pantalla_registrar_tarjeta.preferencia_banco')}**")
    preferencia = st.radio(
        t("pantalla_registrar_tarjeta.preferencia_banco"),
        PREF_VALS,
        format_func=lambda v: t(f"pantalla_registrar_tarjeta.preferencia_{v}"),
        horizontal=True,
        label_visibility="collapsed",
        key=k["preferencia"],
    )

    banco_limpio = (st.session_state.get(f"swa_sel_{k['banco']}", "") or "").strip()
    url_conocida = url_catalogo(banco_limpio, preferencia) if banco_limpio else None
    url_manual: str | None = None
    if banco_limpio and url_conocida:
        st.caption(
            t(
                "pantalla_registrar_tarjeta.url_app_auto",
                banco=banco_limpio,
                canal=t(f"pantalla_registrar_tarjeta.preferencia_{preferencia}"),
            )
        )
    elif banco_limpio:
        if k["url"] not in st.session_state:
            st.session_state[k["url"]] = ""
        url_manual = st.text_input(
            t("pantalla_registrar_tarjeta.url_app_banco"),
            key=k["url"],
            placeholder="https://",
        )

    err = st.empty()
    c_back, c_save = st.columns(2)
    with c_back:
        if st.button(t("wizard_tarjeta.btn_anterior"), key=f"{prefix}_paso2_back", use_container_width=True):
            st.session_state[_paso_key(prefix)] = 1
            st.rerun()
    with c_save:
        guardar = st.button(
            t("pantalla_registrar_tarjeta.boton_guardar") if prefix == "reg" else t("common.guardar"),
            key=f"{prefix}_paso2_save",
            type="primary",
            use_container_width=True,
        )

    if guardar:
        banco = (st.session_state.get(f"swa_sel_{k['banco']}", "") or "").strip()
        add_lbl = t("common.agregar_otro")
        if banco == add_lbl:
            banco = (st.session_state.get(f"swa_custom_{k['banco']}", "") or "").strip()
        nombre = (st.session_state.get(f"swa_sel_{k['nombre']}", "") or "").strip()
        if nombre == add_lbl:
            nombre = (st.session_state.get(f"swa_custom_{k['nombre']}", "") or "").strip()
        digitos = str(st.session_state.get(k["digitos"], ""))
        corte = st.session_state.get(k["corte"], "1")
        pago = st.session_state.get(k["pago"], "1")
        datos_int = st.session_state.get(f"{prefix}_datos_int")
        if datos_int is None and tarjeta:
            from app.ui.form_intereses import DatosIntereses

            datos_int = DatosIntereses(
                tasa_interes_anual=tarjeta.tasa_interes_anual,
                tasa_interes_mora=tarjeta.tasa_interes_mora,
                tasa_es_estimada=tarjeta.tasa_es_estimada,
                pago_minimo_pct=tarjeta.pago_minimo_pct,
                pago_minimo_piso=tarjeta.pago_minimo_piso,
                pago_minimo_manual=tarjeta.pago_minimo_manual,
                cargo_atraso=tarjeta.cargo_atraso,
            )

        if not banco or not nombre or len(digitos) != 4 or not digitos.isdigit():
            err.error(t("pantalla_registrar_tarjeta.error_campos"))
        elif limite <= 0:
            err.error(t("pantalla_registrar_tarjeta.error_limite"))
        elif saldo_hoy > limite:
            err.error(t("pantalla_registrar_tarjeta.error_adeudado"))
        elif not (1 <= int(corte) <= 31 and 1 <= int(pago) <= 31):
            err.error(t("pantalla_registrar_tarjeta.error_campos"))
        elif datos_int is None:
            err.error(t("wizard_tarjeta.error_volver_paso1"))
        else:
            persist_if_new("bancos", banco, BANCOS_DEFAULT)
            persist_if_new("nombres_tarjeta", nombre, NOMBRES_DEFAULT)
            pago_min_manual = float(pago_min_hoy) if pago_min_hoy > 0 else datos_int.pago_minimo_manual
            if pago_min_manual and pago_min_manual > 0:
                datos_int.pago_minimo_manual = pago_min_manual

            saldo_ciclo = float(saldo_cierre) if saldo_cierre > 0 else float(saldo_hoy)
            pago_sin_int = float(saldo_cierre) if saldo_cierre > 0 else None

            if editar_id and tarjeta:
                manual = (url_manual or "").strip() or None
                actualizada = Tarjeta(
                    id=tarjeta.id,
                    banco=banco.strip(),
                    nombre=nombre.strip(),
                    limite=float(limite),
                    adeudado=float(saldo_hoy),
                    ultimos_digitos=digitos,
                    color=color,
                    estilo=ESTILO_VALS[estilo_idx],
                    dia_corte=int(corte),
                    dia_pago=int(pago),
                    adeudado_ciclo=saldo_ciclo,
                    fecha_corte_aplicada=tarjeta.fecha_corte_aplicada,
                    umbral_uso_pct=tarjeta.umbral_uso_pct,
                    umbral_disponible_min=tarjeta.umbral_disponible_min,
                    tasa_interes_anual=datos_int.tasa_interes_anual,
                    tasa_interes_mora=datos_int.tasa_interes_mora,
                    tasa_es_estimada=datos_int.tasa_es_estimada,
                    pago_minimo_pct=datos_int.pago_minimo_pct,
                    pago_minimo_piso=datos_int.pago_minimo_piso,
                    pago_minimo_manual=datos_int.pago_minimo_manual,
                    cargo_atraso=datos_int.cargo_atraso,
                    monto_vencido_atrasado=max(0.0, float(past_due)),
                    pago_sin_intereses=pago_sin_int,
                    preferencia_banco=preferencia,
                    url_app_banco=manual,
                )
                guardar_tarjeta(actualizada)
                st.session_state.pop(f"{prefix}_tarjeta_id", None)
                st.success(t("pantalla_editar_tarjeta.exito"))
                on_saved()
            else:
                nueva = Tarjeta.nueva(
                    banco=banco.strip(),
                    nombre=nombre.strip(),
                    limite=float(limite),
                    adeudado=float(saldo_hoy),
                    ultimos_digitos=digitos,
                    color=color,
                    estilo=ESTILO_VALS[estilo_idx],
                    dia_corte=int(corte),
                    dia_pago=int(pago),
                )
                nueva.tasa_interes_anual = datos_int.tasa_interes_anual
                nueva.tasa_interes_mora = datos_int.tasa_interes_mora
                nueva.tasa_es_estimada = datos_int.tasa_es_estimada
                nueva.pago_minimo_pct = datos_int.pago_minimo_pct
                nueva.pago_minimo_piso = datos_int.pago_minimo_piso
                nueva.pago_minimo_manual = datos_int.pago_minimo_manual
                nueva.cargo_atraso = datos_int.cargo_atraso
                nueva.preferencia_banco = preferencia
                nueva.monto_vencido_atrasado = max(0.0, float(past_due))
                nueva.pago_sin_intereses = pago_sin_int
                nueva.adeudado_ciclo = saldo_ciclo
                nueva.url_app_banco = (url_manual or "").strip() or None
                guardar_tarjeta(nueva)
                _limpiar_wizard(prefix)
                st.success(t("pantalla_registrar_tarjeta.exito"))
                on_saved()


def _limpiar_wizard(prefix: str) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(f"{prefix}_wizard") or key.startswith(f"{prefix}_ocr_p"):
            st.session_state.pop(key, None)
    st.session_state.pop(f"{prefix}_datos_int", None)
    if prefix == "reg":
        from app.ui.ocr_registro import limpiar_formulario_registro

        limpiar_formulario_registro()


def render_wizard_registro(on_back, on_saved) -> None:
    prefix = "reg"
    if _paso_key(prefix) not in st.session_state:
        st.session_state[_paso_key(prefix)] = 1

    _render_stepper(st.session_state[_paso_key(prefix)])

    if st.session_state[_paso_key(prefix)] == 1:
        _render_paso1(prefix, None)
        if st.button(t("common.volver"), key="reg_wizard_back_top"):
            on_back()
    else:
        _render_paso2(prefix, None, on_back, on_saved)


def render_wizard_editar(on_back, on_saved, tarjeta_id: str) -> None:
    prefix = "edit"
    tarjeta = obtener_tarjeta(tarjeta_id)
    if tarjeta is None:
        st.error(t("pantalla_editar_tarjeta.error_no_encontrada"))
        if st.button(t("common.volver"), key="edit_wizard_back_missing"):
            on_back()
        return

    if st.session_state.get(f"{prefix}_tarjeta_id") != tarjeta_id:
        _init_form_desde_tarjeta(prefix, tarjeta)
        st.session_state[f"{prefix}_tarjeta_id"] = tarjeta_id
        st.session_state[_paso_key(prefix)] = 1

    if _paso_key(prefix) not in st.session_state:
        st.session_state[_paso_key(prefix)] = 1

    _render_stepper(st.session_state[_paso_key(prefix)])

    if st.session_state[_paso_key(prefix)] == 1:
        _render_paso1(prefix, tarjeta)
        if st.button(t("common.volver"), key="edit_wizard_back_top"):
            on_back()
    else:
        _render_paso2(prefix, tarjeta, on_back, on_saved, editar_id=tarjeta_id)
