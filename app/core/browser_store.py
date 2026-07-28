"""
Persistencia por dispositivo (modo piloto).

En Streamlit Cloud el disco (/tmp) y localStorage NO sirven entre visitas.
La fuente de verdad es el propio enlace:

  ?ti=<id>&s=<datos comprimidos>

El usuario debe guardar en favoritos el enlace DESPUÉS de crear el PIN
(cuando ya aparece &s=…), porque ahí van sus datos.

Lab compartido: TI_USE_FILESYSTEM=1 → app/data/*.json
"""

from __future__ import annotations

import base64
import gzip
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
_SESSION_URL_WARN = "ti_url_state_warn"
_DEVICE_PARAM = "ti"
_STATE_PARAM = "s"
_DEVICE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
# Límite práctico de URL en móviles; si se pasa, avisamos.
_MAX_STATE_CHARS = 7000

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


def _qp_get(name: str) -> str:
    import streamlit as st

    raw = st.query_params.get(name, "")
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw).strip()


def _slim_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Quita historial voluminoso para caber en la URL."""
    slim = merge_with_defaults(bundle)
    notif = dict(slim.get("notificaciones") or {})
    notif["historial_enviados"] = []
    slim["notificaciones"] = notif
    return slim


def encode_bundle_to_token(bundle: dict[str, Any]) -> str:
    raw = json.dumps(_slim_bundle(bundle), separators=(",", ":"), ensure_ascii=False).encode(
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
    if isinstance(existing, str) and _valid_device_id(existing):
        if _qp_get(_DEVICE_PARAM).lower() != existing:
            st.query_params[_DEVICE_PARAM] = existing
        return existing

    from_url = _qp_get(_DEVICE_PARAM).lower()
    device_id = from_url if _valid_device_id(from_url) else uuid.uuid4().hex
    st.session_state[_SESSION_DEVICE] = device_id
    if _qp_get(_DEVICE_PARAM).lower() != device_id:
        st.query_params[_DEVICE_PARAM] = device_id
    return device_id


def _load_device_file(device_id: str) -> dict[str, Any] | None:
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


def _save_device_file(device_id: str, bundle: dict[str, Any]) -> None:
    """Caché local opcional; en Cloud puede borrarse al dormir la app."""
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


def _sync_state_to_url(bundle: dict[str, Any]) -> bool:
    """Escribe ?s= en la URL. True si cupo; False si es demasiado grande."""
    import streamlit as st

    token = encode_bundle_to_token(bundle)
    if len(token) > _MAX_STATE_CHARS:
        st.session_state[_SESSION_URL_WARN] = (
            "Tus datos son demasiado grandes para guardar en el enlace. "
            "Exporta un ZIP desde Ayuda como respaldo."
        )
        return False

    st.session_state.pop(_SESSION_URL_WARN, None)
    if _qp_get(_STATE_PARAM) != token:
        st.query_params[_STATE_PARAM] = token
    return True


def current_bookmark_url() -> str:
    """URL completa recomendada para favoritos (si el navegador la expone)."""
    import streamlit as st

    try:
        # Disponible en versiones recientes de Streamlit
        from urllib.parse import urlencode

        base = ""
        if hasattr(st, "context") and getattr(st.context, "headers", None):
            host = st.context.headers.get("Host") or st.context.headers.get("host")
            proto = st.context.headers.get("X-Forwarded-Proto") or "https"
            if host:
                base = f"{proto}://{host}/"
        params = {}
        ti = _qp_get(_DEVICE_PARAM)
        s = _qp_get(_STATE_PARAM)
        if ti:
            params[_DEVICE_PARAM] = ti
        if s:
            params[_STATE_PARAM] = s
        if base and params:
            return base + "?" + urlencode(params)
    except Exception:
        pass
    return ""


def has_url_state() -> bool:
    return bool(_qp_get(_STATE_PARAM))


def hydrate_from_localstorage() -> None:
    """Carga el bundle desde ?s= (prioridad) o archivo local de respaldo."""
    import streamlit as st

    if not use_browser_storage():
        st.session_state[_SESSION_HYDRATED] = True
        return

    if st.session_state.get(_SESSION_HYDRATED):
        return

    device_id = ensure_device_id()
    from_url = decode_token_to_bundle(_qp_get(_STATE_PARAM))
    from_file = _load_device_file(device_id)

    if from_url is not None:
        bundle = from_url
    elif from_file is not None:
        bundle = from_file
        # Recupera a la URL para que el favorito futuro sí persista
        _sync_state_to_url(bundle)
    else:
        bundle = empty_bundle()

    st.session_state[_SESSION_BUNDLE] = bundle
    st.session_state[_SESSION_HYDRATED] = True
    _save_device_file(device_id, bundle)


def get_bundle() -> dict[str, Any]:
    import streamlit as st

    if _SESSION_BUNDLE not in st.session_state:
        st.session_state[_SESSION_BUNDLE] = empty_bundle()
    return st.session_state[_SESSION_BUNDLE]


def replace_bundle(bundle: dict[str, Any]) -> None:
    import streamlit as st

    merged = merge_with_defaults(bundle)
    st.session_state[_SESSION_BUNDLE] = merged
    flush_bundle_to_localstorage(merged)


def set_section(section: str, data: Any) -> None:
    import streamlit as st

    bundle = get_bundle()
    bundle[section] = data
    st.session_state[_SESSION_BUNDLE] = bundle
    flush_bundle_to_localstorage(bundle)


def flush_bundle_to_localstorage(bundle: dict[str, Any] | None = None) -> None:
    """Persiste en la URL (?s=) y en caché de archivo."""
    if not use_browser_storage():
        return

    device_id = ensure_device_id()
    payload_obj = bundle if bundle is not None else get_bundle()
    _sync_state_to_url(payload_obj)
    _save_device_file(device_id, payload_obj)


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
