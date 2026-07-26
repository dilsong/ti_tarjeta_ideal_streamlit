"""
Gestión del PIN local encriptado.

Primera vez: crear PIN de 4 dígitos.
Siguientes veces: verificar PIN.
Sin usuarios, perfiles ni autenticación remota.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONFIG_FILE = _DATA_DIR / "config.json"


def _load_config() -> dict[str, Any]:
    from app.core.browser_store import read_config, use_browser_storage

    if use_browser_storage():
        return read_config()
    if not _CONFIG_FILE.exists():
        return {"pin_hash": "", "pin_salt": "", "idioma": "es"}
    with _CONFIG_FILE.open(encoding="utf-8") as f:
        return json.load(f)


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
    config = _load_config()
    return bool(config.get("pin_hash") and config.get("pin_salt"))


def crear_pin(pin: str) -> bool:
    """Crea y persiste un PIN de 4 dígitos encriptado localmente."""
    if len(pin) != 4 or not pin.isdigit():
        return False

    salt = secrets.token_bytes(32)
    config = _load_config()
    config["pin_salt"] = salt.hex()
    config["pin_hash"] = _hash_pin(pin, salt)
    _save_config(config)
    return True


def verificar_pin(pin: str) -> bool:
    """Verifica el PIN contra el hash almacenado localmente."""
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
