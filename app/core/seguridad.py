"""
Gestión del PIN (monousuario / PWA).

Producción (Render): PIN SOLO en localStorage del dispositivo
  - ti_pin_created = "1"
  - ti_app_auth_v1 = {pin_hash, pin_salt}
  - ti_app_bundle_v1.config

Lab local (TI_USE_FILESYSTEM=1, fuera de Render): app/data/config.json

st.session_state['autenticado'] es solo de sesión (al recargar pide PIN),
pero si ti_pin_created existe NUNCA vuelve a pedir crear el PIN.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONFIG_FILE = _DATA_DIR / "config.json"
_PIN_MIN = 4
_PIN_MAX = 6


def pin_valido(pin: str) -> bool:
    """PIN numérico de 4 a 6 dígitos."""
    return bool(pin) and pin.isdigit() and _PIN_MIN <= len(pin) <= _PIN_MAX


def _load_config() -> dict[str, Any]:
    from app.core.browser_store import read_config, use_browser_storage

    if use_browser_storage():
        return read_config()
    if not _CONFIG_FILE.exists():
        return {"pin_hash": "", "pin_salt": "", "idioma": "es", "pin_configurado": False}
    with _CONFIG_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"pin_hash": "", "pin_salt": "", "idioma": "es", "pin_configurado": False}
    return data


def _save_config(config: dict[str, Any]) -> None:
    from app.core.browser_store import use_browser_storage, write_config

    # En hosted / PWA siempre localStorage (write_config ya persiste auth keys).
    if use_browser_storage():
        write_config(config)
        return
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _hash_pin(pin: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 120_000)
    return digest.hex()


def pin_configurado() -> bool:
    """
    True si el dispositivo ya tiene PIN.
    Prioridad: bandera ti_pin_created / hash en localStorage hidratado.
    Nunca depende del disco de Render.
    """
    from app.core.browser_store import pin_flag_from_client, use_browser_storage

    if use_browser_storage():
        if pin_flag_from_client():
            return True
        config = _load_config()
        return bool(config.get("pin_hash") and config.get("pin_salt"))

    config = _load_config()
    if config.get("pin_configurado") and config.get("pin_hash") and config.get("pin_salt"):
        return True
    return bool(config.get("pin_hash") and config.get("pin_salt"))


def crear_pin(pin: str) -> bool:
    """Crea PIN y lo marca en localStorage (ti_pin_created + hash/salt)."""
    if not pin_valido(pin):
        return False

    salt = secrets.token_bytes(32)
    config = _load_config()
    config["pin_salt"] = salt.hex()
    config["pin_hash"] = _hash_pin(pin, salt)
    config["pin_configurado"] = True
    _save_config(config)

    # Refuerzo explícito en el cliente (además de write_config).
    from app.core.browser_store import use_browser_storage

    if use_browser_storage():
        from app.core.browser_store import persist_auth_keys

        persist_auth_keys(config)
    return True


def verificar_pin(pin: str) -> bool:
    """Verifica el PIN contra el hash en storage del dispositivo."""
    if not pin_valido(pin):
        return False
    config = _load_config()
    salt_hex = config.get("pin_salt", "")
    pin_hash = config.get("pin_hash", "")
    if not salt_hex or not pin_hash:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    return _hash_pin(pin, salt) == pin_hash


def get_idioma() -> str:
    return _load_config().get("idioma", "es")


def set_idioma(idioma: str) -> None:
    config = _load_config()
    config["idioma"] = idioma
    _save_config(config)
