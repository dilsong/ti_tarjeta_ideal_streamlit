"""Modal de desglose del próximo ciclo (icono ?)."""

from __future__ import annotations

import streamlit as st

from app.core.intereses import DesgloseProximoCiclo, clave_mensaje_escenario
from app.i18n.translator import t


@st.dialog(" ", width="small")
def mostrar_desglose(desglose: DesgloseProximoCiclo) -> None:
    st.markdown(f"**{t('intereses.desglose_titulo')}**")
    st.caption(t("intereses.desglose_subtitulo"))
    st.markdown(
        f"- **${desglose.saldo_arrastrado:,.2f}** — {t('intereses.desglose_arrastre')}\n\n"
        f"- **${desglose.consumos_ciclo:,.2f}** — {t('intereses.desglose_consumos')}\n\n"
        f"- **${desglose.interes_estimado:,.2f}** — {t('intereses.desglose_interes')}\n\n"
        f"- **${desglose.interes_mora:,.2f}** — {t('intereses.desglose_mora')}"
    )
    st.markdown(f"**{t('intereses.desglose_total', total=desglose.total)}**")
    st.caption(t("intereses.desglose_nota_minimo"))
    st.divider()
    st.info(t(clave_mensaje_escenario(desglose.escenario)))


def boton_desglose(desglose: DesgloseProximoCiclo, key: str) -> None:
    if st.button("?", key=key, help=t("intereses.ver_desglose")):
        mostrar_desglose(desglose)
