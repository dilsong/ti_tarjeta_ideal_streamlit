"""
Persistencia 100% cliente (PWA / Render).

Arquitectura:
- Hosted (Render / Streamlit Cloud): SIEMPRE localStorage del dispositivo.
- Lab local: solo si TI_USE_FILESYSTEM=1 usa app/data/*.json.

PIN y tarjetas viven en el navegador; un redeploy de Render no los borra.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import uuid
from copy import deepcopy
from typing import Any

_SESSION_BUNDLE = "ti_local_bundle"
_SESSION_HYDRATED = "ti_local_hydrated"
_SESSION_DEVICE = "ti_device_id"
_SESSION_LS_FLUSH = "ti_ls_flush_seq"
_SESSION_PIN_FLAG = "ti_pin_created_flag"

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


def is_hosted_environment() -> bool:
    """Render / Cloud: disco efímero → nunca usar app/data para el usuario."""
    return _is_render() or _is_streamlit_cloud()


def use_browser_storage() -> bool:
    """
    True = localStorage del dispositivo.
    En Render/Cloud siempre True (ignora TI_USE_FILESYSTEM=1).
    Lab local: TI_USE_FILESYSTEM=1 → archivos; en caso contrario → localStorage.
    """
    if is_hosted_environment():
        return True
    flag = os.environ.get("TI_USE_FILESYSTEM", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return False
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


def _parse_bundle_raw(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return merge_with_defaults(parsed if isinstance(parsed, dict) else None)
        except (json.JSONDecodeError, TypeError):
            decoded = decode_token_to_bundle(raw)
            return decoded if decoded is not None else empty_bundle()
    return empty_bundle()


def _parse_auth_raw(raw: Any) -> dict[str, str]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    if data.get("pin_hash"):
        out["pin_hash"] = str(data["pin_hash"])
    if data.get("pin_salt"):
        out["pin_salt"] = str(data["pin_salt"])
    return out


def _apply_auth_into_bundle(bundle: dict[str, Any], auth: dict[str, str], pin_created: bool) -> dict[str, Any]:
    cfg = dict(bundle.get("config") or {})
    if auth.get("pin_hash") and auth.get("pin_salt"):
        cfg["pin_hash"] = auth["pin_hash"]
        cfg["pin_salt"] = auth["pin_salt"]
        cfg["pin_configurado"] = True
    elif pin_created and cfg.get("pin_hash") and cfg.get("pin_salt"):
        cfg["pin_configurado"] = True
    elif pin_created:
        # Bandera presente: no pedir crear PIN otra vez aunque falte hash (caso raro).
        cfg["pin_configurado"] = True
    bundle["config"] = cfg
    return bundle


def hydrate_from_localstorage() -> None:
    """
    Carga bundle + auth desde localStorage del dispositivo.
    Cuatro lecturas en paralelo (mismo tick de componentes).
    Si el bundle primario viene vacío, intenta la copia de respaldo.
    """
    import streamlit as st

    if not use_browser_storage():
        st.session_state[_SESSION_HYDRATED] = True
        return

    if st.session_state.get(_SESSION_HYDRATED):
        return

    from app.components.ti_storage import (
        STORAGE_KEY_AUTH,
        STORAGE_KEY_BUNDLE,
        STORAGE_KEY_BUNDLE_BACKUP,
        STORAGE_KEY_PIN_CREATED,
        ls_get,
    )

    raw_bundle = ls_get(STORAGE_KEY_BUNDLE, widget_key="ti_ls_hydrate_bundle")
    raw_backup = ls_get(STORAGE_KEY_BUNDLE_BACKUP, widget_key="ti_ls_hydrate_bundle_bak")
    raw_auth = ls_get(STORAGE_KEY_AUTH, widget_key="ti_ls_hydrate_auth")
    raw_flag = ls_get(STORAGE_KEY_PIN_CREATED, widget_key="ti_ls_hydrate_pin_flag")

    # Esperar a que los cuatro componentes contesten (None = aún no listo).
    if raw_bundle is None or raw_backup is None or raw_auth is None or raw_flag is None:
        return

    bundle = _parse_bundle_raw(raw_bundle)
    tiene_datos = bool(bundle.get("tarjetas") or bundle.get("pagos") or bundle.get("consumos"))
    if not tiene_datos:
        bak = _parse_bundle_raw(raw_backup)
        if bak.get("tarjetas") or bak.get("pagos") or bak.get("consumos"):
            bundle = bak

    auth = _parse_auth_raw(raw_auth)
    pin_created = str(raw_flag).strip() in ("1", "true", "yes", "on")
    if auth.get("pin_hash") and auth.get("pin_salt"):
        pin_created = True

    bundle = _apply_auth_into_bundle(bundle, auth, pin_created)

    if not bundle.get("device_id"):
        bundle["device_id"] = uuid.uuid4().hex

    st.session_state[_SESSION_DEVICE] = bundle["device_id"]
    st.session_state[_SESSION_BUNDLE] = bundle
    st.session_state[_SESSION_PIN_FLAG] = bool(
        pin_created or (bundle.get("config") or {}).get("pin_configurado")
    )
    st.session_state[_SESSION_HYDRATED] = True


def storage_ready() -> bool:
    import streamlit as st

    if not use_browser_storage():
        return True
    return bool(st.session_state.get(_SESSION_HYDRATED))


def pin_flag_from_client() -> bool:
    """True si el dispositivo ya creó PIN (localStorage / sesión hidratada)."""
    import streamlit as st

    if st.session_state.get(_SESSION_PIN_FLAG):
        return True
    cfg = read_config()
    return bool(cfg.get("pin_configurado") and cfg.get("pin_hash") and cfg.get("pin_salt"))


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


def persist_auth_keys(config: dict[str, Any]) -> None:
    """Escribe ti_pin_created + ti_app_auth_v1 en localStorage (doble vía)."""
    import streamlit as st

    from app.components.ti_storage import (
        STORAGE_KEY_AUTH,
        STORAGE_KEY_PIN_CREATED,
        inject_ls_write,
        ls_set,
    )

    pin_hash = str(config.get("pin_hash") or "")
    pin_salt = str(config.get("pin_salt") or "")
    if not (pin_hash and pin_salt):
        return

    st.session_state[_SESSION_PIN_FLAG] = True
    auth_json = json.dumps(
        {"pin_hash": pin_hash, "pin_salt": pin_salt, "pin_configurado": True},
        separators=(",", ":"),
    )
    seq = int(st.session_state.get(_SESSION_LS_FLUSH, 0))
    ls_set(STORAGE_KEY_PIN_CREATED, "1", widget_key=f"ti_ls_pin_flag_{seq}")
    ls_set(STORAGE_KEY_AUTH, auth_json, widget_key=f"ti_ls_auth_{seq}")
    inject_ls_write(STORAGE_KEY_PIN_CREATED, "1")
    inject_ls_write(STORAGE_KEY_AUTH, auth_json)


def flush_bundle_to_localstorage(bundle: dict[str, Any] | None = None) -> None:
    """Persiste bundle (+ auth si hay PIN) en localStorage del dispositivo."""
    import streamlit as st

    if not use_browser_storage():
        return

    payload_obj = merge_with_defaults(bundle if bundle is not None else get_bundle())
    if not payload_obj.get("device_id"):
        payload_obj["device_id"] = ensure_device_id()
        st.session_state[_SESSION_BUNDLE] = payload_obj

    from app.components.ti_storage import (
        STORAGE_KEY_BUNDLE,
        STORAGE_KEY_BUNDLE_BACKUP,
        inject_ls_write,
        ls_set,
    )

    seq = int(st.session_state.get(_SESSION_LS_FLUSH, 0)) + 1
    st.session_state[_SESSION_LS_FLUSH] = seq
    raw = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    ls_set(STORAGE_KEY_BUNDLE, raw, widget_key=f"ti_ls_flush_{seq}")
    ls_set(STORAGE_KEY_BUNDLE_BACKUP, raw, widget_key=f"ti_ls_flush_bak_{seq}")
    inject_ls_write(STORAGE_KEY_BUNDLE, raw)
    inject_ls_write(STORAGE_KEY_BUNDLE_BACKUP, raw)

    cfg = payload_obj.get("config") or {}
    if cfg.get("pin_hash") and cfg.get("pin_salt"):
        persist_auth_keys(cfg)


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
    if use_browser_storage() and current.get("pin_hash") and current.get("pin_salt"):
        persist_auth_keys(current)


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


def has_url_state() -> bool:
    return False


def current_bookmark_url() -> str:
    return ""
