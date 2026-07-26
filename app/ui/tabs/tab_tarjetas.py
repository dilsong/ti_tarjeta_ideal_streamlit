from __future__ import annotations



import streamlit as st



from app.components.theme import CARD_COLORS

from app.core.tarjetas import Tarjeta, guardar_tarjeta

from app.i18n.translator import t
from app.ui.helpers import fila_accion





def _guardar_umbral(tarjeta: Tarjeta, uso_pct: float | None, disp_min: float | None) -> None:

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

        umbral_uso_pct=uso_pct,

        umbral_disponible_min=disp_min,

        tasa_interes_anual=tarjeta.tasa_interes_anual,

        tasa_interes_mora=tarjeta.tasa_interes_mora,

        tasa_es_estimada=tarjeta.tasa_es_estimada,

        pago_minimo_pct=tarjeta.pago_minimo_pct,

        pago_minimo_piso=tarjeta.pago_minimo_piso,

        pago_minimo_manual=tarjeta.pago_minimo_manual,

        url_app_banco=tarjeta.url_app_banco,

        preferencia_banco=tarjeta.preferencia_banco,

    )

    guardar_tarjeta(actualizada)





def render_gestion(tarjetas: list[Tarjeta], on_edit, on_add) -> None:

    if not tarjetas:

        st.info(t("config_tarjetas.sin_tarjetas"))

        if st.button(t("pantalla_inicio.boton_agregar_tarjeta"), type="primary", use_container_width=True):

            on_add()

        return



    for tarjeta in tarjetas:
        color = CARD_COLORS.get(tarjeta.color, CARD_COLORS["azul"])
        with fila_accion() as (c_main, c_btn):
            with c_main:
                st.markdown(
                    f'<div style="background:#1E293B;border-radius:12px;padding:0.75rem 1rem;'
                    f'border-left:4px solid {color};">'
                    f'<strong style="color:#F8FAFC;">{tarjeta.nombre}</strong>'
                    f'<div style="color:#94A3B8;font-size:0.85rem;margin-top:0.25rem;">'
                    f'{tarjeta.banco} · •••• {tarjeta.ultimos_digitos}</div>'
                    f'<div style="color:#CBD5E1;font-size:0.82rem;margin-top:0.35rem;">'
                    f'{t("config_tarjetas.limite_resumen", limite=tarjeta.limite)}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with c_btn:
                if st.button("›", key=f"cfg_edit_{tarjeta.id}", help=t("common.editar")):
                    on_edit(tarjeta.id)



    if st.button(t("pantalla_inicio.boton_agregar_tarjeta"), key="cfg_add", type="primary", use_container_width=True):

        on_add()





def render_umbrales(tarjetas: list[Tarjeta], tarjeta_default: Tarjeta) -> None:
    if not tarjetas:
        st.info(t("config_tarjetas.sin_tarjetas"))
        return

    opciones = {f"{tj.banco} — {tj.nombre}": tj for tj in tarjetas}
    labels = list(opciones.keys())
    clave_default = f"{tarjeta_default.banco} — {tarjeta_default.nombre}"
    indice = labels.index(clave_default) if clave_default in labels else 0
    sel = st.selectbox(
        t("config_tarjetas.umbral_sel_tarjeta"),
        labels,
        index=indice,
        key="cfg_umbral_tarjeta",
    )
    tarjeta = opciones[sel]

    st.caption(t("tabs.umbral_subtitulo"))



    usar_pct = st.checkbox(
        t("tabs.umbral_usar_pct"),
        value=tarjeta.umbral_uso_pct is not None,
        key=f"umbral_pct_on_{tarjeta.id}",
    )

    pct_val = st.number_input(
        t("tabs.umbral_pct"),
        min_value=1.0,
        max_value=100.0,
        value=float(tarjeta.umbral_uso_pct if tarjeta.umbral_uso_pct is not None else 30.0),
        step=1.0,
        key=f"umbral_pct_val_{tarjeta.id}",
        disabled=not usar_pct,
        help=t("tabs.umbral_pct_rango"),
    )
    if usar_pct:
        st.caption(t("tabs.umbral_pct_recomendacion"))

    usar_min = st.checkbox(

        t("tabs.umbral_usar_min"),

        value=tarjeta.umbral_disponible_min is not None,

        key=f"umbral_min_on_{tarjeta.id}",

    )

    min_val = st.number_input(

        t("tabs.umbral_min"),

        min_value=0.0,

        value=float(tarjeta.umbral_disponible_min or 100.0),

        step=50.0,

        key=f"umbral_min_val_{tarjeta.id}",

        disabled=not usar_min,

    )



    if st.button(t("tabs.umbral_guardar"), key=f"umbral_save_{tarjeta.id}", type="primary", use_container_width=True):
        if usar_pct and not (1.0 <= float(pct_val) <= 100.0):
            st.error(t("tabs.umbral_pct_error_rango"))
        else:
            _guardar_umbral(
                tarjeta,
                pct_val if usar_pct else None,
                min_val if usar_min else None,
            )
            st.success(t("tabs.umbral_guardado"))
            st.rerun()


    if tarjeta.umbral_uso_pct is not None or tarjeta.umbral_disponible_min is not None:

        partes = []

        if tarjeta.umbral_uso_pct is not None:

            partes.append(t("tabs.umbral_activo_pct", pct=tarjeta.umbral_uso_pct))

        if tarjeta.umbral_disponible_min is not None:

            partes.append(t("tabs.umbral_activo_min", monto=tarjeta.umbral_disponible_min))

        st.info(" · ".join(partes))





def render(tarjeta: Tarjeta, on_edit, on_add) -> None:

    """Compatibilidad con imports legacy."""

    render_gestion([tarjeta], on_edit, on_add)

    st.divider()

    render_umbrales([tarjeta], tarjeta)


