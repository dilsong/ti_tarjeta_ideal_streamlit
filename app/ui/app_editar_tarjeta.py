"""
Pantalla de edición de tarjeta de crédito existente.
"""

from __future__ import annotations

import streamlit as st

from app.components.keyboard_numeric import entero_text_input, monto_text_input, parse_monto
from app.components.segmented_control import segmented_control
from app.components.select_with_add import persist_if_new, select_with_add
from app.components.theme import BANCOS_DEFAULT, CARD_COLORS
from app.core.enlaces_banco import url_catalogo
from app.core.tarjetas import EstiloTarjeta, Tarjeta, guardar_tarjeta, obtener_tarjeta
from app.i18n.translator import t
from app.ui.form_intereses import render_campos_intereses
from app.ui.helpers import language_selector

NOMBRES_DEFAULT = ["Visa", "Mastercard", "American Express", "Platinum", "Gold"]
PREF_VALS = ["app", "web"]


def _estilo_index(estilo: str) -> int:
    mapa = {
        EstiloTarjeta.REALISTA.value: 0,
        EstiloTarjeta.SOLIDO.value: 1,
        EstiloTarjeta.PREMIUM.value: 2,
    }
    return mapa.get(estilo, 1)


def _es_override_manual(banco: str, url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    u = str(url).strip()
    return u not in {
        url_catalogo(banco, "app"),
        url_catalogo(banco, "web"),
    }


def _cargar_campos_desde_tarjeta(tarjeta: Tarjeta) -> None:
    st.session_state.edit_tarjeta_id = tarjeta.id
    st.session_state.edit_limite = f"{tarjeta.limite:.2f}"
    st.session_state.edit_adeudado = f"{tarjeta.adeudado:.2f}"
    st.session_state.edit_corte = str(tarjeta.dia_corte)
    st.session_state.edit_pago = str(tarjeta.dia_pago)
    pref = (tarjeta.preferencia_banco or "app").strip().lower()
    st.session_state.edit_preferencia_banco = "web" if pref == "web" else "app"
    st.session_state.edit_digitos = tarjeta.ultimos_digitos
    st.session_state.seg_edit_estilo = _estilo_index(tarjeta.estilo)


def render(on_back, on_saved, tarjeta_id: str) -> None:
    language_selector()
    tarjeta = obtener_tarjeta(tarjeta_id)
    if tarjeta is None:
        st.error(t("pantalla_editar_tarjeta.error_no_encontrada"))
        if st.button(t("common.volver"), key="back_missing"):
            on_back()
        return

    if st.session_state.get("edit_tarjeta_id") != tarjeta_id:
        _cargar_campos_desde_tarjeta(tarjeta)

    # Si el límite quedó vacío tras un rerun (p. ej. al cambiar App/Web), restaurar.
    if parse_monto(str(st.session_state.get("edit_limite", ""))) <= 0 and tarjeta.limite > 0:
        st.session_state.edit_limite = f"{tarjeta.limite:.2f}"

    st.title(t("pantalla_editar_tarjeta.titulo"))

    banco = select_with_add(
        t("pantalla_registrar_tarjeta.banco"),
        BANCOS_DEFAULT,
        key="edit_banco",
        categoria="bancos",
        default=tarjeta.banco,
    )

    nombre = select_with_add(
        t("pantalla_registrar_tarjeta.nombre_tarjeta"),
        NOMBRES_DEFAULT,
        key="edit_nombre",
        categoria="nombres_tarjeta",
        default=tarjeta.nombre,
    )

    limite = monto_text_input(t("pantalla_registrar_tarjeta.limite"), "edit_limite", placeholder="2000.00")
    adeudado = monto_text_input(t("pantalla_registrar_tarjeta.adeudado"), "edit_adeudado", placeholder="0.00")

    digitos = st.text_input(
        t("pantalla_registrar_tarjeta.ultimos_digitos"),
        key="edit_digitos",
        max_chars=4,
        placeholder="1234",
    )

    color_keys = list(CARD_COLORS.keys())
    color_idx = color_keys.index(tarjeta.color) if tarjeta.color in color_keys else 0
    color = st.selectbox(
        t("pantalla_registrar_tarjeta.color"),
        color_keys,
        index=color_idx,
        format_func=lambda k: t(f"colores.{k}"),
    )

    estilo_opts = [
        t("pantalla_registrar_tarjeta.estilo_realista"),
        t("pantalla_registrar_tarjeta.estilo_solido"),
        t("pantalla_registrar_tarjeta.estilo_premium"),
    ]
    estilo_vals = [EstiloTarjeta.REALISTA.value, EstiloTarjeta.SOLIDO.value, EstiloTarjeta.PREMIUM.value]
    st.caption(t("pantalla_registrar_tarjeta.estilo"))
    estilo_idx, _ = segmented_control(estilo_opts, key="edit_estilo", default_index=_estilo_index(tarjeta.estilo))

    corte = entero_text_input(t("pantalla_registrar_tarjeta.fecha_corte"), "edit_corte", placeholder="21")
    pago = entero_text_input(t("pantalla_registrar_tarjeta.fecha_pago"), "edit_pago", placeholder="25")

    datos_int = render_campos_intereses("edit", tarjeta)

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
        key="edit_preferencia_banco",
    )
    st.caption(t("pantalla_registrar_tarjeta.cambiar_preferencia"))

    banco_limpio = (banco or "").strip()
    url_conocida = url_catalogo(banco_limpio, preferencia) if banco_limpio else None
    override_actual = tarjeta.url_app_banco if _es_override_manual(tarjeta.banco, tarjeta.url_app_banco) else None
    canal_lbl = t(f"pantalla_registrar_tarjeta.preferencia_{preferencia}")

    if banco_limpio and url_conocida and not override_actual:
        st.caption(
            t(
                "pantalla_registrar_tarjeta.url_app_auto",
                banco=banco_limpio,
                canal=canal_lbl,
            )
        )
        url_manual = None
    else:
        url_manual = st.text_input(
            t("pantalla_registrar_tarjeta.url_app_banco"),
            value=override_actual or "",
            key="edit_url_app_banco",
            placeholder="https://",
            help=t("pantalla_registrar_tarjeta.url_app_banco_ayuda"),
        )

    error = st.empty()

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("common.volver"), key="edit_back"):
            on_back()
    with c2:
        if st.button(t("common.guardar"), key="edit_save", type="primary", use_container_width=True):
            # Releer límite del session_state por si el widget quedó vacío en el rerun
            limite_guardar = limite if limite > 0 else parse_monto(str(st.session_state.get("edit_limite", "")))
            if limite_guardar <= 0 and tarjeta.limite > 0:
                limite_guardar = float(tarjeta.limite)
                st.session_state.edit_limite = f"{limite_guardar:.2f}"

            if not banco.strip() or not nombre.strip() or len(digitos) != 4 or not digitos.isdigit():
                error.error(t("pantalla_registrar_tarjeta.error_campos"))
            elif limite_guardar <= 0:
                error.error(t("pantalla_registrar_tarjeta.error_limite"))
            elif adeudado > limite_guardar:
                error.error(t("pantalla_registrar_tarjeta.error_adeudado"))
            elif not (1 <= int(corte) <= 31 and 1 <= int(pago) <= 31):
                error.error(t("pantalla_registrar_tarjeta.error_campos"))
            else:
                persist_if_new("bancos", banco, BANCOS_DEFAULT)
                persist_if_new("nombres_tarjeta", nombre, NOMBRES_DEFAULT)
                manual = (url_manual or "").strip() or None
                if manual and not _es_override_manual(banco.strip(), manual):
                    manual = None
                actualizada = Tarjeta(
                    id=tarjeta.id,
                    banco=banco.strip(),
                    nombre=nombre.strip(),
                    limite=float(limite_guardar),
                    adeudado=float(adeudado),
                    ultimos_digitos=digitos,
                    color=color,
                    estilo=estilo_vals[estilo_idx],
                    dia_corte=int(corte),
                    dia_pago=int(pago),
                    adeudado_ciclo=tarjeta.adeudado_ciclo,
                    fecha_corte_aplicada=tarjeta.fecha_corte_aplicada,
                    umbral_uso_pct=tarjeta.umbral_uso_pct,
                    umbral_disponible_min=tarjeta.umbral_disponible_min,
                    tasa_interes_anual=datos_int.tasa_interes_anual,
                    tasa_interes_mora=datos_int.tasa_interes_mora,
                    tasa_es_estimada=datos_int.tasa_es_estimada,
                    pago_minimo_pct=datos_int.pago_minimo_pct,
                    pago_minimo_piso=datos_int.pago_minimo_piso,
                    pago_minimo_manual=datos_int.pago_minimo_manual,
                    preferencia_banco=preferencia,
                    url_app_banco=manual,
                )
                guardar_tarjeta(actualizada)
                st.session_state.pop("edit_tarjeta_id", None)
                st.success(t("pantalla_editar_tarjeta.exito"))
                on_saved()


def main() -> None:
    from app.ui.helpers import init_i18n, setup_page

    setup_page()
    init_i18n()
    st.session_state.unlocked = True

    tarjeta_id = st.session_state.get("editar_tarjeta_id", "")
    if not tarjeta_id:
        st.warning(t("pantalla_editar_tarjeta.error_no_encontrada"))
        return

    def back() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    def saved() -> None:
        st.session_state.pagina = "inicio"
        st.rerun()

    render(back, saved, tarjeta_id)


if __name__ == "__main__":
    main()
