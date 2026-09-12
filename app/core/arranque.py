"""
Arranque limpio monousuario: sin PIN en el dispositivo → sin tarjetas.

En PWA/Render NUNCA toca app/data/ del servidor.
Si ti_pin_created / PIN existe en localStorage, no vacía nada.
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


def asegurar_arranque_limpio_sin_pin() -> None:
    """
    Solo si el dispositivo NO tiene PIN: deja tarjetas/pagos/consumos vacíos.
    Si ya hay PIN (localStorage), no altera datos del usuario.
    """
    from app.core.browser_store import pin_flag_from_client, use_browser_storage
    from app.core.seguridad import pin_configurado

    if pin_configurado() or pin_flag_from_client():
        return

    if use_browser_storage():
        from app.core.browser_store import empty_bundle, get_bundle, replace_bundle

        bundle = get_bundle()
        if not (bundle.get("tarjetas") or bundle.get("pagos") or bundle.get("consumos")):
            return
        idioma = (bundle.get("config") or {}).get("idioma", "es")
        limpio = empty_bundle()
        limpio["config"]["idioma"] = idioma or "es"
        if isinstance(bundle.get("device_id"), str):
            limpio["device_id"] = bundle["device_id"]
        # Preservar device_id; no tocar localStorage de PIN (no hay)
        replace_bundle(limpio)
        return

    # Lab filesystem únicamente (fuera de Render)
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
