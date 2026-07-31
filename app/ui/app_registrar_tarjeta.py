"""
Pantalla de registro de tarjeta de crédito.

Usa teclado nativo del dispositivo y permite agregar banco/nombre personalizados.
"""

from __future__ import annotations

import streamlit as st

from app.components.keyboard_numeric import entero_text_input, monto_text_input
from app.components.segmented_control import segmented_control
from app.components.select_with_add import persist_if_new, select_with_add
from app.components.theme import BANCOS_DEFAULT, CARD_COLORS
from app.core.enlaces_banco import url_catalogo
from app.core.tarjetas import EstiloTarjeta, Tarjeta, guardar_tarjeta
from app.i18n.translator import t
from app.ui.form_intereses import render_campos_intereses
from app.ui.helpers import language_selector
from app.ui.ocr_registro import SESSION_PREFILL, render_ocr_para_registro

NOMBRES_DEFAULT = ["Visa", "Mastercard", "American Express", "Platinum", "Gold"]
PREF_VALS = ["app", "web"]


def render(on_back, on_saved) -> None:
    language_selector()
    st.title(t("pantalla_registrar_tarjeta.titulo"))

    render_ocr_para_registro()

    banco = select_with_add(
        t("pantalla_registrar_tarjeta.banco"),
        BANCOS_DEFAULT,
        key="banco",
        categoria="bancos",
    )

    nombre = select_with_add(
        t("pantalla_registrar_tarjeta.nombre_tarjeta"),
        NOMBRES_DEFAULT,
        key="nombre_tarjeta",
        categoria="nombres_tarjeta",
    )

    limite = monto_text_input(t("pantalla_registrar_tarjeta.limite"), "limite", placeholder="0.00")
    adeudado = monto_text_input(t("pantalla_registrar_tarjeta.adeudado"), "adeudado", placeholder="0.00")

    digitos = st.text_input(
        t("pantalla_registrar_tarjeta.ultimos_digitos"),
        key="digitos",
        max_chars=4,
        placeholder="1234",
    )

    color_keys = list(CARD_COLORS.keys())
    color = st.selectbox(
        t("pantalla_registrar_tarjeta.color"),
        color_keys,
        format_func=lambda k: t(f"colores.{k}"),
    )

    estilo_opts = [
        t("pantalla_registrar_tarjeta.estilo_realista"),
        t("pantalla_registrar_tarjeta.estilo_solido"),
        t("pantalla_registrar_tarjeta.estilo_premium"),
    ]
    estilo_vals = [EstiloTarjeta.REALISTA.value, EstiloTarjeta.SOLIDO.value, EstiloTarjeta.PREMIUM.value]
    st.caption(t("pantalla_registrar_tarjeta.estilo"))
    estilo_idx, _ = segmented_control(estilo_opts, key="estilo")

    corte = entero_text_input(t("pantalla_registrar_tarjeta.fecha_corte"), "corte", placeholder="15")
    pago = entero_text_input(t("pantalla_registrar_tarjeta.fecha_pago"), "pago", placeholder="9")

    datos_int = render_campos_intereses("reg", prefill=st.session_state.get(SESSION_PREFILL))

    c_pref, c_ayuda = st.columns([8, 1], vertical_alignment="center")
    with c_pref:
        st.markdown(f"**{t('pantalla_registrar_tarjeta.preferencia_banco')}**")
    with c_ayuda:
        with st.popover("?"):
            st.markdown(t("pantalla_registrar_tarjeta.preferencia_banco_ayuda_larga"))

    preferencia = st.radio(
        t("pantalla_registrar_tarjeta.preferencia_banco"),
        PREF_VALS,
        format_func=lambda v: t(f"pantalla_registrar_tarjeta.preferencia_{v}"),
        horizontal=True,
        label_visibility="collapsed",
        key="preferencia_banco",
    )
    st.caption(t("pantalla_registrar_tarjeta.preferencia_banco_ayuda"))

    banco_limpio = (banco or "").strip()
    url_conocida = url_catalogo(banco_limpio, preferencia) if banco_limpio else None
    url_manual: str | None = None
    canal_lbl = t(f"pantalla_registrar_tarjeta.preferencia_{preferencia}")
    if banco_limpio and url_conocida:
        st.caption(
            t(
                "pantalla_registrar_tarjeta.url_app_auto",
                banco=banco_limpio,
                canal=canal_lbl,
            )
        )
    elif banco_limpio:
        url_manual = st.text_input(
            t("pantalla_registrar_tarjeta.url_app_banco"),
            key="url_app_banco",
            placeholder="https://",
            help=t("pantalla_registrar_tarjeta.url_app_banco_ayuda"),
        )

    error = st.empty()

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("common.volver"), key="back"):
            on_back()
    with c2:
        if st.button(t("pantalla_registrar_tarjeta.boton_guardar"), key="save", type="primary", use_container_width=True):
            if not banco.strip() or not nombre.strip() or len(digitos) != 4 or not digitos.isdigit():
                error.error(t("pantalla_registrar_tarjeta.error_campos"))
            elif limite <= 0:
                error.error(t("pantalla_registrar_tarjeta.error_limite"))
            elif adeudado > limite:
                error.error(t("pantalla_registrar_tarjeta.error_adeudado"))
            elif not (1 <= int(corte) <= 31 and 1 <= int(pago) <= 31):
                error.error(t("pantalla_registrar_tarjeta.error_campos"))
            else:
                persist_if_new("bancos", banco, BANCOS_DEFAULT)
                persist_if_new("nombres_tarjeta", nombre, NOMBRES_DEFAULT)
                tarjeta = Tarjeta.nueva(
                    banco=banco.strip(),
                    nombre=nombre.strip(),
                    limite=float(limite),
                    adeudado=float(adeudado),
                    ultimos_digitos=digitos,
                    color=color,
                    estilo=estilo_vals[estilo_idx],
                    dia_corte=int(corte),
                    dia_pago=int(pago),
                )
                tarjeta.tasa_interes_anual = datos_int.tasa_interes_anual
                tarjeta.tasa_interes_mora = datos_int.tasa_interes_mora
                tarjeta.tasa_es_estimada = datos_int.tasa_es_estimada
                tarjeta.pago_minimo_pct = datos_int.pago_minimo_pct
                tarjeta.pago_minimo_piso = datos_int.pago_minimo_piso
                tarjeta.pago_minimo_manual = datos_int.pago_minimo_manual
                tarjeta.cargo_atraso = datos_int.cargo_atraso
                tarjeta.preferencia_banco = preferencia
                # Solo override manual; bancos del catálogo se resuelven por preferencia.
                tarjeta.url_app_banco = (url_manual or "").strip() or None
                guardar_tarjeta(tarjeta)
                for clave in (SESSION_PREFILL, "reg_ocr_datos", "reg_ocr_texto_visto"):
                    st.session_state.pop(clave, None)
                st.success(t("pantalla_registrar_tarjeta.exito"))
                on_saved()


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    st.session_state.unlocked = True

    def back() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    def saved() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    render(back, saved)


if __name__ == "__main__":
    main()
