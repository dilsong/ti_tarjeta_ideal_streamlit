"""Ayuda: respaldo JSON + paquete ZIP de soporte."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from app.core.soporte import crear_paquete_soporte, nombre_archivo_export
from app.i18n.translator import t
from app.version import VERSION


def _bundle_sin_pin(bundle: dict[str, Any]) -> dict[str, Any]:
    out = dict(bundle)
    cfg = dict(out.get("config") or {})
    cfg.pop("pin_hash", None)
    cfg.pop("pin_salt", None)
    # Conservar idioma; PIN se recrea en el dispositivo destino.
    cfg["pin_configurado"] = False
    out["config"] = cfg
    return out


def _render_respaldo() -> None:
    from app.core.browser_store import get_bundle, merge_with_defaults, replace_bundle

    st.markdown(f"**{t('soporte.respaldo_titulo')}**")
    st.caption(t("soporte.respaldo_ayuda"))

    payload = _bundle_sin_pin(get_bundle())
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    nombre = f"ti_respaldo_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    st.download_button(
        t("soporte.boton_descargar_respaldo"),
        data=raw.encode("utf-8"),
        file_name=nombre,
        mime="application/json",
        key="soporte_download_respaldo",
        use_container_width=True,
    )

    st.markdown(f"**{t('soporte.restaurar_titulo')}**")
    st.caption(t("soporte.restaurar_ayuda"))
    archivo = st.file_uploader(
        t("soporte.restaurar_titulo"),
        type=["json"],
        key="soporte_upload_respaldo",
        label_visibility="collapsed",
    )
    if archivo is not None and st.button(
        t("soporte.boton_restaurar"),
        key="soporte_restore_btn",
        type="primary",
        use_container_width=True,
    ):
        try:
            data = json.loads(archivo.getvalue().decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid")
            merged = merge_with_defaults(data)
            # Conservar PIN actual del dispositivo si ya existe.
            actual = get_bundle()
            cfg_act = actual.get("config") or {}
            if cfg_act.get("pin_hash") and cfg_act.get("pin_salt"):
                merged_cfg = dict(merged.get("config") or {})
                merged_cfg["pin_hash"] = cfg_act["pin_hash"]
                merged_cfg["pin_salt"] = cfg_act["pin_salt"]
                merged_cfg["pin_configurado"] = True
                merged["config"] = merged_cfg
            if actual.get("device_id"):
                merged["device_id"] = actual["device_id"]
            replace_bundle(merged)
            st.success(t("soporte.restaurar_ok"))
            st.rerun()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            st.error(t("soporte.restaurar_error"))


def render() -> None:
    st.markdown(f"**{t('soporte.titulo')}**")
    st.caption(t("soporte.subtitulo", version=VERSION))

    _render_respaldo()
    st.divider()

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
