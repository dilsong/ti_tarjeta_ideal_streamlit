"""Modal de desglose del próximo ciclo (icono ?)."""

from __future__ import annotations

import streamlit as st

from app.core.intereses import DesgloseProximoCiclo, clave_mensaje_escenario
from app.core.salud_tarjeta import fmt_dinero
from app.i18n.translator import t


@st.dialog(" ", width="small")
def mostrar_desglose(desglose: DesgloseProximoCiclo) -> None:
    st.markdown(f"**{t('intereses.desglose_titulo')}**")
    st.caption(t("intereses.desglose_subtitulo"))
    lineas = [
        f"- **{fmt_dinero(desglose.saldo_arrastrado)}** — {t('intereses.desglose_arrastre')}",
        f"- **{fmt_dinero(desglose.consumos_ciclo)}** — {t('intereses.desglose_consumos')}",
        f"- **{fmt_dinero(desglose.interes_estimado)}** — {t('intereses.desglose_interes')}",
        f"- **{fmt_dinero(desglose.interes_mora)}** — {t('intereses.desglose_mora')}",
    ]
    if desglose.cargo_atraso > 0:
        lineas.append(
            f"- **{fmt_dinero(desglose.cargo_atraso)}** — {t('intereses.desglose_cargo_atraso')}"
        )
    st.markdown("\n\n".join(lineas))
    st.markdown(f"**{t('intereses.desglose_total', total=fmt_dinero(desglose.total))}**")
    st.caption(t("intereses.desglose_nota_minimo"))
    st.divider()
    st.info(t(clave_mensaje_escenario(desglose.escenario)))


def boton_desglose(desglose: DesgloseProximoCiclo, key: str) -> None:
    if st.button("?", key=key, help=t("intereses.ver_desglose")):
        mostrar_desglose(desglose)
