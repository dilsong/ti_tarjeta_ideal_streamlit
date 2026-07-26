"""
Persistencia y lógica de consumos locales en data/consumos.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.fechas import fecha_en_mes, hoy
from app.core.tarjetas import Tarjeta, guardar_tarjeta, obtener_tarjeta

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONSUMOS_FILE = _DATA_DIR / "consumos.json"

CONSUMO_SIN_DETALLE = "CONSUMO"


@dataclass
class Consumo:
    id: str
    id_tarjeta: str
    fecha: str
    monto: float
    tienda_razon: str | None
    ciclo: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Consumo:
        return Consumo(
            id=data["id"],
            id_tarjeta=data["id_tarjeta"],
            fecha=data["fecha"],
            monto=float(data["monto"]),
            tienda_razon=data.get("tienda_razon") or None,
            ciclo=data["ciclo"],
        )


def _read_consumos_raw() -> list[dict[str, Any]]:
    if not _CONSUMOS_FILE.exists():
        return []
    with _CONSUMOS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _write_consumos_raw(data: list[dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _CONSUMOS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def asignar_ciclo(tarjeta: Tarjeta, fecha: date | None = None) -> str:
    """Identifica el ciclo de facturación según la fecha de corte."""
    ref = fecha or hoy()
    corte_mes = fecha_en_mes(ref.year, ref.month, tarjeta.dia_corte)
    if ref <= corte_mes:
        ciclo_fecha = corte_mes
    else:
        mes = ref.month + 1
        anio = ref.year
        if mes > 12:
            mes = 1
            anio += 1
        ciclo_fecha = fecha_en_mes(anio, mes, tarjeta.dia_corte)
    return ciclo_fecha.strftime("%Y-%m")


def guardar_consumo(consumo: Consumo) -> None:
    raw = _read_consumos_raw()
    raw = [item for item in raw if item.get("id") != consumo.id]
    raw.append(consumo.to_dict())
    _write_consumos_raw(raw)


def listar_consumos_por_tarjeta(id_tarjeta: str) -> list[Consumo]:
    return [
        Consumo.from_dict(item)
        for item in _read_consumos_raw()
        if item.get("id_tarjeta") == id_tarjeta
    ]


def actualizar_monto_tarjeta(id_tarjeta: str, monto: float) -> Tarjeta:
    """Suma el monto al adeudado actual y persiste la tarjeta."""
    tarjeta = obtener_tarjeta(id_tarjeta)
    if tarjeta is None:
        raise ValueError(f"Tarjeta no encontrada: {id_tarjeta}")

    tarjeta.adeudado = min(tarjeta.limite, tarjeta.adeudado + monto)
    guardar_tarjeta(tarjeta)
    return tarjeta


def registrar_consumo(
    id_tarjeta: str,
    monto: float,
    tienda_razon: str | None = None,
    fecha: date | None = None,
) -> Consumo:
    """Registra consumo, actualiza adeudado y guarda en consumos.json."""
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    tarjeta = obtener_tarjeta(id_tarjeta)
    if tarjeta is None:
        raise ValueError(f"Tarjeta no encontrada: {id_tarjeta}")

    ref = fecha or hoy()
    detalle = (tienda_razon or "").strip() or None

    consumo = Consumo(
        id=str(uuid4()),
        id_tarjeta=id_tarjeta,
        fecha=ref.isoformat(),
        monto=float(monto),
        tienda_razon=detalle,
        ciclo=asignar_ciclo(tarjeta, ref),
    )

    actualizar_monto_tarjeta(id_tarjeta, monto)
    guardar_consumo(consumo)
    return consumo
