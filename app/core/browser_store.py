"""
Persistencia monousuario (PWA con dominio fijo).

- Lab: TI_USE_FILESYSTEM=1 → app/data/*.json
- PWA / Render: localStorage del origen (sin ?ti= / &s= en la URL)

El PIN vive en el bundle (config.pin_hash / pin_salt) dentro de localStorage.
st.session_state['autenticado'] es solo de sesión: al recargar pide PIN, nunca recrearlo.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

_SESSION_BUNDLE = "ti_local_bundle"
_SESSION_HYDRATED = "ti_local_hydrated"
_SESSION_DEVICE = "ti_device_id"
_SESSION_LS_FLUSH = "ti_ls_flush_seq"

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
    return os.path.isdir("/mount/src")


def _is_render() -> bool:
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def use_browser_storage() -> bool:
    """True = localStorage PWA. False = app/data compartido (Lab)."""
    flag = os.environ.get("TI_USE_FILESYSTEM", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return False
    if flag in ("0", "false", "no", "off"):
        return True
    if _is_streamlit_cloud() or _is_render():
        return True
    return True


def empty_bundle() -> dict[str, Any]:
    return {
        "version": 1,
        "tarjetas": [],
        "pagos": [],
        "consumos": [],
        "config": {
            "pin_hash": "",
            "pin_salt": "",
            "idioma": "es",
            "pin_configurado": False,
        },
        "notificaciones": deepcopy(_DEFAULT_NOTIF),
        "device_id": "",
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
        # Marca explícita o implícita si ya hay hash
        if merged_cfg.get("pin_hash") and merged_cfg.get("pin_salt"):
            merged_cfg["pin_configurado"] = True
        base["config"] = merged_cfg
    notif = raw.get("notificaciones")
    if isinstance(notif, dict):
        merged_n = deepcopy(_DEFAULT_NOTIF)
        merged_n.update(notif)
        if not isinstance(merged_n.get("historial_enviados"), list):
            merged_n["historial_enviados"] = []
        base["notificaciones"] = merged_n
    if isinstance(raw.get("device_id"), str) and raw["device_id"]:
        base["device_id"] = raw["device_id"]
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


def encode_bundle_to_token(bundle: dict[str, Any]) -> str:
    raw = json.dumps(merge_with_defaults(bundle), separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    token = base64.urlsafe_b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")
    return token.rstrip("=")


def decode_token_to_bundle(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        pad = "=" * (-len(token) % 4)
        raw = gzip.decompress(base64.urlsafe_b64decode(token + pad))
        parsed = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return merge_with_defaults(parsed)


def _save_device_file(device_id: str, bundle: dict[str, Any]) -> None:
    if not device_id:
        return
    try:
        path = _device_path(device_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = merge_with_defaults(bundle)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError:
        pass


def _load_device_file(device_id: str) -> dict[str, Any] | None:
    if not device_id:
        return None
    path = _device_path(device_id)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    return merge_with_defaults(raw)


def ensure_device_id() -> str:
    import streamlit as st

    existing = st.session_state.get(_SESSION_DEVICE)
    if isinstance(existing, str) and len(existing) == 32:
        return existing

    bundle = st.session_state.get(_SESSION_BUNDLE)
    if isinstance(bundle, dict):
        did = bundle.get("device_id")
        if isinstance(did, str) and len(did) == 32:
            st.session_state[_SESSION_DEVICE] = did
            return did

    device_id = uuid.uuid4().hex
    st.session_state[_SESSION_DEVICE] = device_id
    return device_id


def hydrate_from_localstorage() -> None:
    """
    Carga el bundle desde localStorage (PWA) o marca listo en modo Lab.

    El componente JS puede devolver None en el primer tick; Streamlit re-ejecuta
    cuando llega el valor. No usa ni reescribe la URL de la app.
    """
    import streamlit as st

    if not use_browser_storage():
        st.session_state[_SESSION_HYDRATED] = True
        return

    if st.session_state.get(_SESSION_HYDRATED):
        return

    from app.components.ti_storage import STORAGE_KEY_BUNDLE, ls_get

    raw = ls_get(STORAGE_KEY_BUNDLE, widget_key="ti_ls_hydrate_get")

    # Primer tick: el componente aún no devolvió valor (None ≠ storage vacío).
    if raw is None:
        return

    bundle: dict[str, Any]
    if isinstance(raw, str) and raw.strip():
        # Preferir JSON directo; aceptar token gzip legado
        try:
            parsed = json.loads(raw)
            bundle = merge_with_defaults(parsed if isinstance(parsed, dict) else None)
        except (json.JSONDecodeError, TypeError):
            decoded = decode_token_to_bundle(raw)
            bundle = decoded if decoded is not None else empty_bundle()
    else:
        bundle = empty_bundle()

    if not bundle.get("device_id"):
        bundle["device_id"] = uuid.uuid4().hex

    st.session_state[_SESSION_DEVICE] = bundle["device_id"]
    st.session_state[_SESSION_BUNDLE] = bundle
    st.session_state[_SESSION_HYDRATED] = True
    _save_device_file(bundle["device_id"], bundle)


def storage_ready() -> bool:
    """True cuando ya se hidrató (Lab siempre True tras hydrate)."""
    import streamlit as st

    if not use_browser_storage():
        return True
    return bool(st.session_state.get(_SESSION_HYDRATED))


def get_bundle() -> dict[str, Any]:
    import streamlit as st

    if _SESSION_BUNDLE not in st.session_state:
        st.session_state[_SESSION_BUNDLE] = empty_bundle()
    return st.session_state[_SESSION_BUNDLE]


def replace_bundle(bundle: dict[str, Any]) -> None:
    import streamlit as st

    merged = merge_with_defaults(bundle)
    if not merged.get("device_id"):
        merged["device_id"] = ensure_device_id()
    st.session_state[_SESSION_BUNDLE] = merged
    st.session_state[_SESSION_DEVICE] = merged["device_id"]
    flush_bundle_to_localstorage(merged)


def set_section(section: str, data: Any) -> None:
    import streamlit as st

    bundle = get_bundle()
    bundle[section] = data
    st.session_state[_SESSION_BUNDLE] = bundle
    flush_bundle_to_localstorage(bundle)


def flush_bundle_to_localstorage(bundle: dict[str, Any] | None = None) -> None:
    """Persiste en localStorage del origen PWA (+ caché opcional en disco)."""
    import streamlit as st

    if not use_browser_storage():
        return

    payload_obj = merge_with_defaults(bundle if bundle is not None else get_bundle())
    if not payload_obj.get("device_id"):
        payload_obj["device_id"] = ensure_device_id()
        st.session_state[_SESSION_BUNDLE] = payload_obj

    device_id = str(payload_obj.get("device_id") or ensure_device_id())
    _save_device_file(device_id, payload_obj)

    from app.components.ti_storage import STORAGE_KEY_BUNDLE, ls_set

    seq = int(st.session_state.get(_SESSION_LS_FLUSH, 0)) + 1
    st.session_state[_SESSION_LS_FLUSH] = seq
    raw = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    ls_set(STORAGE_KEY_BUNDLE, raw, widget_key=f"ti_ls_flush_{seq}")


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
        return {"pin_hash": "", "pin_salt": "", "idioma": "es", "pin_configurado": False}
    return dict(cfg)


def write_config(config: dict[str, Any]) -> None:
    current = read_config()
    current.update(config)
    if current.get("pin_hash") and current.get("pin_salt"):
        current["pin_configurado"] = True
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


# --- Compat: APIs antiguas basadas en URL (no-ops / False) ---


def has_url_state() -> bool:
    """Deprecado: la PWA ya no guarda estado en la URL."""
    return False


def current_bookmark_url() -> str:
    """Deprecado: dominio fijo de la PWA; no se reescribe la URL."""
    return ""
