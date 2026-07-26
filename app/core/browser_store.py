"""
Persistencia por dispositivo (modo piloto).

Cada piloto tiene un ID en la URL (?ti=...) y un archivo JSON propio.
En Streamlit Cloud el localStorage de componentes NO persiste (iframe),
por eso usamos disco escribible + ID en el enlace.

- Cloud: /tmp/ti_tarjeta_ideal_devices/{id}.json
- Local piloto: app/data/devices/{id}.json
- Lab compartido: TI_USE_FILESYSTEM=1 → app/data/*.json (sin ID)
"""

from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

_SESSION_BUNDLE = "ti_local_bundle"
_SESSION_HYDRATED = "ti_local_hydrated"
_SESSION_DEVICE = "ti_device_id"
_DEVICE_PARAM = "ti"
_DEVICE_ID_RE = re.compile(r"^[a-f0-9]{32}$")

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


def _is_streamlit_cloud() -> bool:
    """Community Cloud monta el repo en /mount/src."""
    return os.path.isdir("/mount/src") or bool(
        os.environ.get("STREAMLIT_RUNTIME_ENV", "").strip()
    )


def use_browser_storage() -> bool:
    """True = data por dispositivo (piloto). False = app/data compartido (Lab)."""
    if _is_streamlit_cloud():
        return True
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


def _devices_dir() -> Path:
    if _is_streamlit_cloud():
        base = Path("/tmp/ti_tarjeta_ideal_devices")
    else:
        base = Path(__file__).resolve().parent.parent / "data" / "devices"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _device_path(device_id: str) -> Path:
    return _devices_dir() / f"{device_id}.json"


def _valid_device_id(value: str) -> bool:
    return bool(_DEVICE_ID_RE.match(value or ""))


def _read_query_device_id() -> str:
    import streamlit as st

    raw = st.query_params.get(_DEVICE_PARAM, "")
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw).strip().lower()


def ensure_device_id() -> str:
    """Obtiene o crea el ID del dispositivo y lo deja en la URL (?ti=...)."""
    import streamlit as st

    existing = st.session_state.get(_SESSION_DEVICE)
    if isinstance(existing, str) and _valid_device_id(existing):
        if _read_query_device_id() != existing:
            st.query_params[_DEVICE_PARAM] = existing
        return existing

    from_url = _read_query_device_id()
    if _valid_device_id(from_url):
        device_id = from_url
    else:
        device_id = uuid.uuid4().hex

    st.session_state[_SESSION_DEVICE] = device_id
    if _read_query_device_id() != device_id:
        st.query_params[_DEVICE_PARAM] = device_id
    return device_id


def _load_device_file(device_id: str) -> dict[str, Any]:
    path = _device_path(device_id)
    if not path.exists():
        return empty_bundle()
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return empty_bundle()
    return merge_with_defaults(raw if isinstance(raw, dict) else None)


def _save_device_file(device_id: str, bundle: dict[str, Any]) -> None:
    path = _device_path(device_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = merge_with_defaults(bundle)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def hydrate_from_localstorage() -> None:
    """
    Carga el bundle del dispositivo (?ti=) al iniciar.
    Mantiene el nombre histórico; ya no usa localStorage del navegador.
    """
    import streamlit as st

    if not use_browser_storage():
        st.session_state[_SESSION_HYDRATED] = True
        return

    if st.session_state.get(_SESSION_HYDRATED):
        return

    device_id = ensure_device_id()
    bundle = _load_device_file(device_id)
    st.session_state[_SESSION_BUNDLE] = bundle
    st.session_state[_SESSION_HYDRATED] = True
    # Si es la primera vez, materializa el archivo vacío
    if not _device_path(device_id).exists():
        _save_device_file(device_id, bundle)


def get_bundle() -> dict[str, Any]:
    import streamlit as st

    if _SESSION_BUNDLE not in st.session_state:
        st.session_state[_SESSION_BUNDLE] = empty_bundle()
    return st.session_state[_SESSION_BUNDLE]


def replace_bundle(bundle: dict[str, Any]) -> None:
    """Reemplaza el bundle completo (p. ej. importar ZIP) y persiste."""
    import streamlit as st

    merged = merge_with_defaults(bundle)
    st.session_state[_SESSION_BUNDLE] = merged
    flush_bundle_to_localstorage(merged)


def set_section(section: str, data: Any) -> None:
    """Actualiza una sección del bundle y la persiste en disco del dispositivo."""
    import streamlit as st

    bundle = get_bundle()
    bundle[section] = data
    st.session_state[_SESSION_BUNDLE] = bundle
    flush_bundle_to_localstorage(bundle)


def flush_bundle_to_localstorage(bundle: dict[str, Any] | None = None) -> None:
    """Persiste el bundle del dispositivo actual (nombre histórico)."""
    if not use_browser_storage():
        return

    device_id = ensure_device_id()
    payload_obj = bundle if bundle is not None else get_bundle()
    _save_device_file(device_id, payload_obj)


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
