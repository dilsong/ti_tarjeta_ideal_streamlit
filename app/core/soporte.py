"""
Export / import de paquetes de soporte para depuración en el Lab Streamlit.

- Export: el usuario (o el lab) genera un ZIP con sus JSON (sin PIN).
- Import: en tu PC cargás ese ZIP para reproducir el caso (con backup previo).
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from app.version import PRODUCTO, VERSION

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_NOTIF_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "notificaciones_usuario.json"

_ARCHIVOS_DATA = ("tarjetas.json", "pagos.json", "consumos.json", "config.json")


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _leer_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _config_sin_pin(config: dict[str, Any] | None) -> dict[str, Any]:
    """Quita hash/salt del PIN — nunca viajan en el paquete de soporte."""
    if not config:
        return {"idioma": "es"}
    limpio = {k: v for k, v in config.items() if k not in ("pin_hash", "pin_salt")}
    limpio.setdefault("idioma", "es")
    return limpio


def crear_paquete_soporte(*, nota: str = "", plataforma: str = "lab") -> bytes:
    """Genera un ZIP en memoria listo para descarga."""
    meta = {
        "producto": PRODUCTO,
        "version_ti": VERSION,
        "exportado_en": _ahora_iso(),
        "plataforma": plataforma,
        "nota": (nota or "").strip(),
        "incluye_pin": False,
    }

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        for nombre in _ARCHIVOS_DATA:
            path = _DATA_DIR / nombre
            data = _leer_json(path)
            if nombre == "config.json":
                data = _config_sin_pin(data if isinstance(data, dict) else None)
            elif data is None:
                data = [] if nombre != "config.json" else {"idioma": "es"}
            zf.writestr(nombre, json.dumps(data, ensure_ascii=False, indent=2))

        if _NOTIF_FILE.exists():
            notif = _leer_json(_NOTIF_FILE)
            if notif is not None:
                zf.writestr(
                    "notificaciones_usuario.json",
                    json.dumps(notif, ensure_ascii=False, indent=2),
                )

    return buf.getvalue()


def nombre_archivo_export() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"ti_soporte_{stamp}.zip"


def _backup_data_actual() -> Path:
    """Copia app/data a un respaldo con marca de tiempo."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = _DATA_DIR.parent / "data_backups" / f"antes_import_{stamp}"
    destino.mkdir(parents=True, exist_ok=True)
    if _DATA_DIR.exists():
        for path in _DATA_DIR.iterdir():
            if path.is_file():
                shutil.copy2(path, destino / path.name)
    return destino


def _validar_paquete(zf: zipfile.ZipFile) -> dict[str, Any]:
    nombres = set(zf.namelist())
    if "meta.json" not in nombres:
        raise ValueError("El ZIP no es un paquete TI válido (falta meta.json).")
    if "tarjetas.json" not in nombres:
        raise ValueError("El ZIP no es un paquete TI válido (falta tarjetas.json).")
    meta = json.loads(zf.read("meta.json").decode("utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("meta.json inválido.")
    return meta


def importar_paquete_soporte(contenido: bytes) -> dict[str, Any]:
    """
    Restaura data del ZIP en app/data (tras backup).
    Conserva el PIN local actual del lab (no importa pin del paquete).
    """
    backup = _backup_data_actual()
    pin_actual = {}
    config_actual = _leer_json(_DATA_DIR / "config.json")
    if isinstance(config_actual, dict):
        if config_actual.get("pin_hash"):
            pin_actual["pin_hash"] = config_actual["pin_hash"]
        if config_actual.get("pin_salt"):
            pin_actual["pin_salt"] = config_actual["pin_salt"]

    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(contenido), "r") as zf:
        meta = _validar_paquete(zf)
        for nombre in _ARCHIVOS_DATA:
            if nombre not in zf.namelist():
                continue
            raw = json.loads(zf.read(nombre).decode("utf-8"))
            if nombre == "config.json":
                if not isinstance(raw, dict):
                    raw = {"idioma": "es"}
                raw = _config_sin_pin(raw)
                raw.update(pin_actual)
            dest = _DATA_DIR / nombre
            with dest.open("w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)

        if "notificaciones_usuario.json" in zf.namelist():
            raw_n = json.loads(zf.read("notificaciones_usuario.json").decode("utf-8"))
            _NOTIF_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _NOTIF_FILE.open("w", encoding="utf-8") as f:
                json.dump(raw_n, f, ensure_ascii=False, indent=2)

    return {
        "meta": meta,
        "backup": str(backup),
    }
