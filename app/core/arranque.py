"""
Arranque limpio monousuario.

En PWA/Render NUNCA toca app/data/ del servidor ni borra el bundle del dispositivo.
Si falta el PIN pero hay tarjetas/pagos, se conservan (Safari vs ícono / flag fallida).
El wipe de lab (filesystem) solo aplica fuera de browser storage.
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
    Browser/PWA: no-op (nunca vaciar tarjetas por ausencia de PIN).
    Lab filesystem: si no hay PIN, deja listas vacías para demos locales.
    """
    from app.core.browser_store import pin_flag_from_client, use_browser_storage
    from app.core.seguridad import pin_configurado

    if pin_configurado() or pin_flag_from_client():
        return

    # Crítico: en dispositivo real, un PIN no leído NO autoriza borrar datos.
    if use_browser_storage():
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
