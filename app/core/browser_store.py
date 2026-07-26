"""
Persistencia por dispositivo en el navegador (localStorage).

Cada usuario/piloto guarda su data SOLO en su teléfono/PC (origen del navegador).
No escribe a disco del servidor ni a GitHub.

Activación: por defecto ON en Streamlit.
Lab con JSON en disco (soporte/cargar_caso): TI_USE_FILESYSTEM=1
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

LS_KEY = "ti_tarjeta_ideal_v1"
_SESSION_BUNDLE = "ti_local_bundle"
_SESSION_HYDRATED = "ti_local_hydrated"
_SESSION_SAVE_N = "ti_local_save_n"
_EMPTY_SENTINEL = "__EMPTY__"

_DEFAULT_NOTIF: dict[str, Any] = {
    "notificar_dia_corte": True,
    "notificar_antes_corte": True,
    "dias_antes_corte": 3,
    "notificar_mitad_ciclo": True,
    "dias_mitad_ciclo": 10,
    "notificar_antes_pago": True,
    "dias_antes_pago": 3,
    "notificar_despues_pago": True,
    "notificar_dias_despues_corte": True,
    "notificar_inicio_ciclo": True,
    "ultima_ejecucion": None,
    "historial_enviados": [],
}


def use_browser_storage() -> bool:
    """True = localStorage del navegador. False = archivos en app/data (Lab PC)."""
    flag = os.environ.get("TI_USE_FILESYSTEM", "").strip().lower()
    return flag not in ("1", "true", "yes", "on")


def empty_bundle() -> dict[str, Any]:
    """Estructura en blanco alineada con tarjetas/pagos/consumos/config del Lab."""
    return {
        "version": 1,
        "tarjetas": [],
        "pagos": [],
        "consumos": [],
        "config": {
            "pin_hash": "",
            "pin_salt": "",
            "idioma": "es",
        },
        "notificaciones": deepcopy(_DEFAULT_NOTIF),
    }


def merge_with_defaults(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_bundle()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version") or 1)
    for key in ("tarjetas", "pagos", "consumos"):
        val = raw.get(key)
        base[key] = list(val) if isinstance(val, list) else []
    cfg = raw.get("config")
    if isinstance(cfg, dict):
        merged_cfg = dict(base["config"])
        merged_cfg.update(cfg)
        base["config"] = merged_cfg
    notif = raw.get("notificaciones")
    if isinstance(notif, dict):
        merged_n = deepcopy(_DEFAULT_NOTIF)
        merged_n.update(notif)
        if not isinstance(merged_n.get("historial_enviados"), list):
            merged_n["historial_enviados"] = []
        base["notificaciones"] = merged_n
    return base


def hydrate_from_localstorage() -> None:
    """
    Carga el bundle desde localStorage al iniciar.
    Si no hay data, inicializa en blanco y la guarda en el dispositivo.
    Puede llamar st.stop() mientras el componente JS termina de responder.
    """
    import streamlit as st

    if not use_browser_storage():
        st.session_state[_SESSION_HYDRATED] = True
        return

    if st.session_state.get(_SESSION_HYDRATED):
        return

    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError as exc:
        st.error(
            "Falta el paquete streamlit-js-eval para data local en el navegador.\n"
            "Ejecuta: pip install streamlit-js-eval"
        )
        st.stop()
        raise exc

    js = (
        "(function(){"
        f"var v=localStorage.getItem({json.dumps(LS_KEY)});"
        f"return (v===null||v==='') ? {json.dumps(_EMPTY_SENTINEL)} : v;"
        "})()"
    )
    raw = streamlit_js_eval(js_expressions=js, key="ti_hydrate_ls_v1")

    # Primera pasada: el componente aún no devolvió valor
    if raw is None:
        st.info("Cargando tu data local en este dispositivo…")
        st.stop()

    if raw == _EMPTY_SENTINEL:
        bundle = empty_bundle()
        st.session_state[_SESSION_BUNDLE] = bundle
        st.session_state[_SESSION_HYDRATED] = True
        flush_bundle_to_localstorage(bundle)
        return

    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        parsed = None

    bundle = merge_with_defaults(parsed if isinstance(parsed, dict) else None)
    st.session_state[_SESSION_BUNDLE] = bundle
    st.session_state[_SESSION_HYDRATED] = True


def get_bundle() -> dict[str, Any]:
    import streamlit as st

    if _SESSION_BUNDLE not in st.session_state:
        st.session_state[_SESSION_BUNDLE] = empty_bundle()
    return st.session_state[_SESSION_BUNDLE]


def replace_bundle(bundle: dict[str, Any]) -> None:
    """Reemplaza el bundle completo (p. ej. importar ZIP) y persiste en el dispositivo."""
    import streamlit as st

    merged = merge_with_defaults(bundle)
    st.session_state[_SESSION_BUNDLE] = merged
    flush_bundle_to_localstorage(merged)


def set_section(section: str, data: Any) -> None:
    """Actualiza una sección del bundle y la escribe en localStorage."""
    import streamlit as st

    bundle = get_bundle()
    bundle[section] = data
    st.session_state[_SESSION_BUNDLE] = bundle
    flush_bundle_to_localstorage(bundle)


def flush_bundle_to_localstorage(bundle: dict[str, Any] | None = None) -> None:
    """Escribe el bundle actual en localStorage del navegador (no al servidor)."""
    import streamlit as st
    import streamlit.components.v1 as components

    if not use_browser_storage():
        return

    payload_obj = bundle if bundle is not None else get_bundle()
    payload = json.dumps(payload_obj, ensure_ascii=False)
    n = int(st.session_state.get(_SESSION_SAVE_N, 0)) + 1
    st.session_state[_SESSION_SAVE_N] = n
    # components.html escribe en el cliente; no sube el JSON al repo ni al disco del server.
    components.html(
        f"<script>localStorage.setItem({json.dumps(LS_KEY)}, {json.dumps(payload)});</script>",
        height=0,
        width=0,
    )


# --- API usada por tarjetas / pagos / consumos / config / notificaciones ---


def read_tarjetas() -> list[dict[str, Any]]:
    return list(get_bundle().get("tarjetas") or [])


def write_tarjetas(data: list[dict[str, Any]]) -> None:
    set_section("tarjetas", list(data))


def read_pagos() -> list[dict[str, Any]]:
    return list(get_bundle().get("pagos") or [])


def write_pagos(data: list[dict[str, Any]]) -> None:
    set_section("pagos", list(data))


def read_consumos() -> list[dict[str, Any]]:
    return list(get_bundle().get("consumos") or [])


def write_consumos(data: list[dict[str, Any]]) -> None:
    set_section("consumos", list(data))


def read_config() -> dict[str, Any]:
    cfg = get_bundle().get("config")
    if not isinstance(cfg, dict):
        return {"pin_hash": "", "pin_salt": "", "idioma": "es"}
    return dict(cfg)


def write_config(config: dict[str, Any]) -> None:
    current = read_config()
    current.update(config)
    set_section("config", current)


def read_notificaciones() -> dict[str, Any]:
    notif = get_bundle().get("notificaciones")
    merged = deepcopy(_DEFAULT_NOTIF)
    if isinstance(notif, dict):
        merged.update(notif)
    if not isinstance(merged.get("historial_enviados"), list):
        merged["historial_enviados"] = []
    return merged


def write_notificaciones(config: dict[str, Any]) -> None:
    merged = deepcopy(_DEFAULT_NOTIF)
    merged.update(config)
    if not isinstance(merged.get("historial_enviados"), list):
        merged["historial_enviados"] = []
    set_section("notificaciones", merged)
