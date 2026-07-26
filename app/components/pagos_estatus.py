"""Módulo Actualizar estatus de la tarjeta en la solapa Pagos."""



from __future__ import annotations



import streamlit as st



from app.components.dialogo_pago_banco import confirmar_pago_en_banco

from app.core.tarjetas import Tarjeta

from app.core.validacion_ciclo import validar_ciclo_con_intereses

from app.i18n.translator import t





def _aviso_no_banco(

    tarjeta: Tarjeta | None = None,

    *,

    enlace_guia: bool = False,

    key_prefix: str = "",

) -> None:

    st.markdown(

        f'<div style="background:#422006;border:1px solid #FACC15;border-radius:12px;'

        f'padding:0.85rem 1rem;margin-bottom:1rem;color:#FDE68A;font-size:0.9rem;">'

        f'⚠️ {t("pagos_estatus.aviso_no_banco")}</div>',

        unsafe_allow_html=True,

    )

    if enlace_guia and tarjeta and st.button(

        t("tabs.pagos_ir_guia"),

        key=f"{key_prefix}pagos_ir_guia_{tarjeta.id}",

        use_container_width=True,

    ):

        from app.ui.helpers import GUIA_BANCO_KEY

        from app.ui.tabs.tab_guia import abrir_guia_bancaria



        st.session_state[GUIA_BANCO_KEY] = tarjeta.banco

        abrir_guia_bancaria(tarjeta)





def _dinero(valor: float) -> str:

    return f"${valor:,.2f}"





def render_actualizar_estatus(

    tarjeta: Tarjeta,

    *,

    enlace_guia: bool = False,

    key_prefix: str = "",

) -> None:

    st.markdown(f"**{t('pagos_estatus.titulo')}**")

    _aviso_no_banco(tarjeta, enlace_guia=enlace_guia, key_prefix=key_prefix)



    estado = validar_ciclo_con_intereses(tarjeta)

    deuda = estado.monto_adeudado_ciclo_anterior

    pago_min = estado.pago_minimo

    sin_deuda = deuda <= 0 and tarjeta.adeudado <= 0



    msg_key = f"{key_prefix}pago_msg_{tarjeta.id}"

    if msg_key in st.session_state:

        st.success(st.session_state.pop(msg_key))



    err_key = f"{key_prefix}pago_err_{tarjeta.id}"

    if err_key in st.session_state:

        st.error(st.session_state.pop(err_key))



    if st.button(

        f"🟩 {t('pagos_estatus.boton_total')}",

        key=f"{key_prefix}pago_total_{tarjeta.id}",

        type="primary",

        use_container_width=True,

        disabled=sin_deuda or deuda <= 0,

    ):

        confirmar_pago_en_banco(

            tarjeta,

            tipo="total",

            monto_txt=_dinero(deuda),

            msg_key=msg_key,

            key_prefix=key_prefix,

        )



    if st.button(

        f"🟨 {t('pagos_estatus.boton_minimo')}",

        key=f"{key_prefix}pago_minimo_{tarjeta.id}",

        use_container_width=True,

        disabled=sin_deuda or deuda <= 0,

    ):

        confirmar_pago_en_banco(

            tarjeta,

            tipo="minimo",

            monto_txt=_dinero(pago_min),

            msg_key=msg_key,

            key_prefix=key_prefix,

        )



    if st.button(

        f"🟦 {t('pagos_estatus.boton_personalizado')}",

        key=f"{key_prefix}pago_custom_{tarjeta.id}",

        use_container_width=True,

        disabled=sin_deuda,

    ):

        confirmar_pago_en_banco(

            tarjeta,

            tipo="personalizado",

            monto_txt=t("pagos_estatus.monto_personalizado_dialogo"),

            msg_key=msg_key,

            key_prefix=key_prefix,

        )


