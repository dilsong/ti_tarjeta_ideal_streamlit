"""Ayuda: exportar paquete ZIP para enviar al desarrollador (sin UI de import)."""

from __future__ import annotations

import streamlit as st

from app.core.soporte import crear_paquete_soporte, nombre_archivo_export
from app.i18n.translator import t
from app.version import VERSION


def render() -> None:
    st.markdown(f"**{t('soporte.titulo')}**")
    st.caption(t("soporte.subtitulo", version=VERSION))
    st.caption(t("soporte.exportar_ayuda"))

    nota = st.text_input(
        t("soporte.nota_opcional"),
        key="soporte_nota_export",
        placeholder=t("soporte.nota_placeholder"),
    )

    try:
        paquete = crear_paquete_soporte(nota=nota, plataforma="lab")
    except OSError as exc:
        st.error(str(exc))
        return

    st.download_button(
        t("soporte.boton_descargar"),
        data=paquete,
        file_name=nombre_archivo_export(),
        mime="application/zip",
        key="soporte_download",
        type="primary",
        use_container_width=True,
        help=t("soporte.exportar_ayuda"),
    )
    st.caption(t("soporte.export_hint"))
