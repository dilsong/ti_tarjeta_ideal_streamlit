"""
Arranque limpio monousuario: sin PIN → sin tarjetas ni movimientos.

Garantiza que el primer uso (crear PIN) parta de tablas vacías
para probar el registro en 2 pasos desde cero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _write_json(path: Path, data: Any) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def vaciar_datos_usuario() -> None:
    """Borra tarjetas, pagos y consumos; deja config sin PIN (solo idioma)."""
    from app.core.browser_store import empty_bundle, get_bundle, replace_bundle, use_browser_storage

    if use_browser_storage():
        actual = get_bundle()
        idioma = (actual.get("config") or {}).get("idioma", "es")
        limpio = empty_bundle()
        limpio["config"]["idioma"] = idioma or "es"
        limpio["config"]["pin_hash"] = ""
        limpio["config"]["pin_salt"] = ""
        limpio["config"]["pin_configurado"] = False
        replace_bundle(limpio)
        return

    idioma = "es"
    cfg_path = _DATA_DIR / "config.json"
    if cfg_path.exists():
        try:
            with cfg_path.open(encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict) and cfg.get("idioma"):
                idioma = str(cfg["idioma"])
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    _write_json(_DATA_DIR / "tarjetas.json", [])
    _write_json(_DATA_DIR / "pagos.json", [])
    _write_json(_DATA_DIR / "consumos.json", [])
    _write_json(
        _DATA_DIR / "config.json",
        {"idioma": idioma, "pin_hash": "", "pin_salt": "", "pin_configurado": False},
    )


def asegurar_arranque_limpio_sin_pin() -> None:
    """
    Si no hay PIN registrado, deja la app en estado de primer uso:
    cero tarjetas / pagos / consumos.
    """
    from app.core.seguridad import pin_configurado

    if pin_configurado():
        return

    from app.core.browser_store import use_browser_storage

    if use_browser_storage():
        from app.core.browser_store import get_bundle, replace_bundle

        bundle = get_bundle()
        if bundle.get("tarjetas") or bundle.get("pagos") or bundle.get("consumos"):
            idioma = (bundle.get("config") or {}).get("idioma", "es")
            from app.core.browser_store import empty_bundle

            limpio = empty_bundle()
            limpio["config"]["idioma"] = idioma or "es"
            if isinstance(bundle.get("device_id"), str):
                limpio["device_id"] = bundle["device_id"]
            replace_bundle(limpio)
        return

    # Filesystem: vaciar tablas si aún hay residuos de Lab
    for nombre in ("tarjetas.json", "pagos.json", "consumos.json"):
        path = _DATA_DIR / nombre
        if not path.exists():
            _write_json(path, [])
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError):
            _write_json(path, [])
            continue
        if isinstance(data, list) and len(data) > 0:
            _write_json(path, [])
