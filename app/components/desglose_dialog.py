"""Modal de desglose del próximo ciclo (icono ?)."""

from __future__ import annotations

import streamlit as st

from app.core.intereses import DesgloseProximoCiclo, clave_mensaje_escenario
from app.i18n.translator import t


@st.dialog(" ", width="small")
def mostrar_desglose(desglose: DesgloseProximoCiclo) -> None:
    st.markdown(f"**{t('intereses.desglose_titulo')}**")
    st.caption(t("intereses.desglose_subtitulo"))
    lineas = [
        f"- **${desglose.saldo_arrastrado:,.2f}** — {t('intereses.desglose_arrastre')}",
        f"- **${desglose.consumos_ciclo:,.2f}** — {t('intereses.desglose_consumos')}",
        f"- **${desglose.interes_estimado:,.2f}** — {t('intereses.desglose_interes')}",
        f"- **${desglose.interes_mora:,.2f}** — {t('intereses.desglose_mora')}",
    ]
    if desglose.cargo_atraso > 0:
        lineas.append(
            f"- **${desglose.cargo_atraso:,.2f}** — {t('intereses.desglose_cargo_atraso')}"
        )
    st.markdown("\n\n".join(lineas))
    st.markdown(f"**{t('intereses.desglose_total', total=desglose.total)}**")
    st.caption(t("intereses.desglose_nota_minimo"))
    st.divider()
    st.info(t(clave_mensaje_escenario(desglose.escenario)))


def boton_desglose(desglose: DesgloseProximoCiclo, key: str) -> None:
    if st.button("?", key=key, help=t("intereses.ver_desglose")):
        mostrar_desglose(desglose)
