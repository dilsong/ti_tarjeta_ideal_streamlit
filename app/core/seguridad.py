"""
Gestión del PIN local encriptado (monousuario / PWA).

Persistencia: localStorage (PWA) o app/data/config.json (Lab).
La sesión st.session_state['autenticado'] NO se persiste: al recargar pide PIN,
pero nunca vuelve a pedir crearlo si ya está en storage.
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
    """True si esta instancia ya tiene PIN en DB/localStorage (no depende de la URL)."""
    config = _load_config()
    if config.get("pin_configurado") and config.get("pin_hash") and config.get("pin_salt"):
        return True
    return bool(config.get("pin_hash") and config.get("pin_salt"))


def crear_pin(pin: str) -> bool:
    """Crea y persiste un PIN de 4–6 dígitos; marca la instancia como configurada."""
    if not pin_valido(pin):
        return False

    salt = secrets.token_bytes(32)
    config = _load_config()
    config["pin_salt"] = salt.hex()
    config["pin_hash"] = _hash_pin(pin, salt)
    config["pin_configurado"] = True
    _save_config(config)
    return True


def verificar_pin(pin: str) -> bool:
    """Verifica el PIN contra el hash almacenado en storage."""
    if not pin_valido(pin):
        return False
    config = _load_config()
    salt_hex = config.get("pin_salt", "")
    pin_hash = config.get("pin_hash", "")
    if not salt_hex or not pin_hash:
        return False
    salt = bytes.fromhex(salt_hex)
    return _hash_pin(pin, salt) == pin_hash


def get_idioma() -> str:
    return _load_config().get("idioma", "es")


def set_idioma(idioma: str) -> None:
    config = _load_config()
    config["idioma"] = idioma
    _save_config(config)
