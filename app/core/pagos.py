"""
Registro de pagos manuales en data/pagos.json y actualización de saldos.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.fechas import hoy
from app.core.tarjetas import EstadoSalud, Tarjeta, guardar_tarjeta, obtener_tarjeta
from app.core.validacion_ciclo import estado_riesgo_pago, validar_ciclo_con_intereses

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PAGOS_FILE = _DATA_DIR / "pagos.json"


class EstatusPago(str, Enum):
    TOTAL = "total"
    MINIMO = "minimo"
    PERSONALIZADO = "personalizado"


@dataclass
class RegistroPago:
    id: str
    id_tarjeta: str
    fecha: str
    monto: float
    estatus_pago: str
    deuda_ciclo_antes: float
    adeudado_despues: float
    adeudado_ciclo_despues: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RegistroPago:
        return RegistroPago(**data)


def _read_pagos_raw() -> list[dict[str, Any]]:
    from app.core.browser_store import read_pagos, use_browser_storage

    if use_browser_storage():
        return read_pagos()
    if not _PAGOS_FILE.exists():
        return []
    with _PAGOS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _write_pagos_raw(data: list[dict[str, Any]]) -> None:
    from app.core.browser_store import use_browser_storage, write_pagos

    if use_browser_storage():
        write_pagos(data)
        return
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _PAGOS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def guardar_registro_pago(registro: RegistroPago) -> None:
    raw = _read_pagos_raw()
    raw.append(registro.to_dict())
    _write_pagos_raw(raw)


def listar_pagos_por_tarjeta(id_tarjeta: str) -> list[RegistroPago]:
    return [
        RegistroPago.from_dict(item)
        for item in _read_pagos_raw()
        if item.get("id_tarjeta") == id_tarjeta
    ]


def _crear_registro(
    tarjeta: Tarjeta,
    monto: float,
    estatus: EstatusPago,
    deuda_antes: float,
    fecha: date | None = None,
) -> RegistroPago:
    ref = fecha or hoy()
    return RegistroPago(
        id=str(uuid4()),
        id_tarjeta=tarjeta.id,
        fecha=ref.isoformat(),
        monto=monto,
        estatus_pago=estatus.value,
        deuda_ciclo_antes=deuda_antes,
        adeudado_despues=tarjeta.adeudado,
        adeudado_ciclo_despues=tarjeta.adeudado_ciclo,
    )


def _aplicar_pago(tarjeta: Tarjeta, monto: float, deuda_ciclo: float) -> None:
    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a cero.")
    if monto > tarjeta.adeudado:
        raise ValueError("El monto no puede superar el adeudado actual.")

    tarjeta.adeudado = max(0.0, tarjeta.adeudado - monto)
    reduccion_ciclo = min(monto, deuda_ciclo)
    tarjeta.adeudado_ciclo = max(0.0, tarjeta.adeudado_ciclo - reduccion_ciclo)


def registrar_pago_total(id_tarjeta: str, fecha: date | None = None) -> RegistroPago:
    tarjeta = obtener_tarjeta(id_tarjeta)
    if tarjeta is None:
        raise ValueError(f"Tarjeta no encontrada: {id_tarjeta}")

    estado = validar_ciclo_con_intereses(tarjeta)
    deuda = estado.monto_adeudado_ciclo_anterior
    if deuda <= 0:
        raise ValueError("No hay deuda del ciclo por pagar.")

    monto = deuda
    _aplicar_pago(tarjeta, monto, deuda)
    tarjeta.adeudado_ciclo = 0.0
    guardar_tarjeta(tarjeta)

    registro = _crear_registro(tarjeta, monto, EstatusPago.TOTAL, deuda, fecha)
    guardar_registro_pago(registro)
    return registro


def registrar_pago_minimo(id_tarjeta: str, fecha: date | None = None) -> RegistroPago:
    tarjeta = obtener_tarjeta(id_tarjeta)
    if tarjeta is None:
        raise ValueError(f"Tarjeta no encontrada: {id_tarjeta}")

    estado = validar_ciclo_con_intereses(tarjeta)
    deuda = estado.monto_adeudado_ciclo_anterior
    pago_min = estado.pago_minimo
    if deuda <= 0:
        raise ValueError("No hay deuda del ciclo por pagar.")
    if pago_min <= 0:
        raise ValueError("No se pudo calcular el pago mínimo.")

    _aplicar_pago(tarjeta, pago_min, deuda)
    tarjeta.adeudado_ciclo = max(0.0, deuda - pago_min)
    guardar_tarjeta(tarjeta)

    registro = _crear_registro(tarjeta, pago_min, EstatusPago.MINIMO, deuda, fecha)
    guardar_registro_pago(registro)
    return registro


def registrar_pago_personalizado(
    id_tarjeta: str,
    monto: float,
    fecha: date | None = None,
) -> RegistroPago:
    tarjeta = obtener_tarjeta(id_tarjeta)
    if tarjeta is None:
        raise ValueError(f"Tarjeta no encontrada: {id_tarjeta}")

    estado = validar_ciclo_con_intereses(tarjeta)
    deuda = estado.monto_adeudado_ciclo_anterior
    if tarjeta.adeudado <= 0:
        raise ValueError("No hay saldo adeudado.")

    _aplicar_pago(tarjeta, monto, deuda)
    if monto >= deuda:
        tarjeta.adeudado_ciclo = 0.0
    else:
        tarjeta.adeudado_ciclo = max(0.0, deuda - monto)

    guardar_tarjeta(tarjeta)
    estatus = EstatusPago.TOTAL if monto >= deuda else EstatusPago.PERSONALIZADO
    registro = _crear_registro(tarjeta, monto, estatus, deuda, fecha)
    guardar_registro_pago(registro)
    return registro


@dataclass
class SugerenciaAbono:
    escenario: str  # ciclo_pendiente | ciclo_abierto
    monto: float
    usa_historial: bool
    urgente: bool
    es_pago_total: bool
    deuda_ciclo: float
    consumos_ciclo: float
    dias_restantes: int
    foto_antes: float
    foto_despues: float


def _redondear_practico(monto: float) -> float:
    if monto <= 0:
        return 0.0
    if monto < 100:
        return round(max(10.0, monto) / 5.0) * 5.0
    if monto < 1000:
        return round(monto / 25.0) * 25.0
    return round(monto / 50.0) * 50.0


def _promedio_abonos_tarjeta(id_tarjeta: str) -> float | None:
    pagos = listar_pagos_por_tarjeta(id_tarjeta)
    montos = [p.monto for p in pagos if p.monto > 0]
    if len(montos) < 2:
        return None
    recientes = montos[-6:]
    return sum(recientes) / len(recientes)


def _factor_salud(riesgo: EstadoSalud) -> float:
    if riesgo == EstadoSalud.NEGATIVO:
        return 1.25
    if riesgo == EstadoSalud.MEDIO:
        return 1.1
    return 0.9


def _factor_tiempo(dias: int) -> float:
    if dias <= 3:
        return 1.3
    if dias <= 7:
        return 1.15
    return 1.0


def calcular_sugerencia_abono(tarjeta: Tarjeta) -> SugerenciaAbono | None:
    """Monto y contexto para el banner de abono inteligente."""
    estado = validar_ciclo_con_intereses(tarjeta)
    deuda = estado.monto_adeudado_ciclo_anterior
    consumos = estado.consumos_ciclo_actual
    riesgo = estado_riesgo_pago(tarjeta)

    if deuda > 0:
        escenario = "ciclo_pendiente"
        referencia = deuda
        dias = estado.dias_hasta_pago
        urgente = riesgo == EstadoSalud.NEGATIVO
        foto_antes = deuda
        pago_min = max(estado.pago_minimo, 0.0)

        # Solo deuda congelada → priorizar liquidar el ciclo (no un “abono” parcial pequeño).
        if consumos <= 0:
            monto = deuda
            es_pago_total = True
        elif dias <= 7 or urgente:
            monto = deuda
            es_pago_total = True
        else:
            promedio = _promedio_abonos_tarjeta(tarjeta.id)
            usa_historial = promedio is not None
            if usa_historial and promedio is not None:
                base = max(promedio, pago_min)
            else:
                base = max(pago_min, deuda * 0.5)
            monto = _redondear_practico(
                min(deuda, base * _factor_salud(riesgo) * _factor_tiempo(dias))
            )
            monto = max(pago_min, min(monto, deuda))
            es_pago_total = monto >= deuda - 0.01

        foto_despues = max(0.0, deuda - monto)
    elif consumos > 0 and tarjeta.adeudado > 0:
        escenario = "ciclo_abierto"
        referencia = consumos
        dias = estado.dias_hasta_corte
        urgente = False
        foto_antes = consumos
        foto_despues = consumos
        es_pago_total = False

        promedio = _promedio_abonos_tarjeta(tarjeta.id)
        usa_historial = promedio is not None

        if usa_historial and promedio is not None:
            base = promedio
        else:
            base = consumos * 0.30

        monto = base * _factor_salud(riesgo) * _factor_tiempo(dias)
        monto = _redondear_practico(monto)
        maximo = min(tarjeta.adeudado, tarjeta.adeudado)
        monto = min(monto, maximo)
        if monto <= 0:
            monto = min(maximo, _redondear_practico(maximo * 0.25))
        if monto <= 0:
            return None

        foto_despues = max(0.0, consumos - monto)

        return SugerenciaAbono(
            escenario=escenario,
            monto=monto,
            usa_historial=usa_historial,
            urgente=urgente,
            es_pago_total=es_pago_total,
            deuda_ciclo=deuda,
            consumos_ciclo=consumos,
            dias_restantes=dias,
            foto_antes=foto_antes,
            foto_despues=foto_despues,
        )
    else:
        return None

    usa_historial = _promedio_abonos_tarjeta(tarjeta.id) is not None
    if monto <= 0:
        return None

    return SugerenciaAbono(
        escenario=escenario,
        monto=monto,
        usa_historial=usa_historial,
        urgente=urgente,
        es_pago_total=es_pago_total,
        deuda_ciclo=deuda,
        consumos_ciclo=consumos,
        dias_restantes=dias,
        foto_antes=foto_antes,
        foto_despues=foto_despues,
    )


def registrar_abono_sugerido(id_tarjeta: str, monto: float) -> RegistroPago:
    """Registra el abono sugerido desde el banner (mismo flujo que pago personalizado)."""
    return registrar_pago_personalizado(id_tarjeta, monto)
