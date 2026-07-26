"""
Vista de uso del límite: ciclo pasado (congelado) vs ciclo nuevo (acumulando).
Sin lógica de pagos — solo mapa del límite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.consumos import CONSUMO_SIN_DETALLE
from app.core.intereses import calcular_interes_proximo_ciclo, tasa_vigente
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import EstadoCiclo, validar_ciclo


@dataclass
class LineaConsumo:
    nombre: str
    monto: float


@dataclass
class DesgloseCicloPasado:
    saldo_no_pagado: float
    interes_estimado: float
    costo_total: float
    tasa_aplicada: float
    dias_interes: int


@dataclass
class DesgloseCicloNuevo:
    lineas: list[LineaConsumo] = field(default_factory=list)
    total: float = 0.0


@dataclass
class VistaUso:
    limite: float
    disponible: float
    total_usado: float
    ciclo_pasado_pendiente: float
    ciclo_pasado_costo: float
    ciclo_nuevo_total: float
    mostrar_ciclo_pasado: bool
    desglose_pasado: DesgloseCicloPasado | None
    desglose_nuevo: DesgloseCicloNuevo


def _dias_interes_pasado(estado: EstadoCiclo) -> int:
    if estado.dias_hasta_pago <= 0:
        return max(1, estado.dias_hasta_pago_siguiente_ciclo)
    return max(1, estado.dias_hasta_pago)


def _desglose_pasado(tarjeta: Tarjeta, estado: EstadoCiclo, pendiente: float) -> DesgloseCicloPasado:
    dias = _dias_interes_pasado(estado)
    tasa = tasa_vigente(tarjeta, estado.dias_hasta_pago)
    interes = calcular_interes_proximo_ciclo(pendiente, tasa, dias)
    return DesgloseCicloPasado(
        saldo_no_pagado=pendiente,
        interes_estimado=interes,
        costo_total=pendiente + interes,
        tasa_aplicada=tasa,
        dias_interes=dias,
    )


def _desglose_nuevo(estado: EstadoCiclo) -> DesgloseCicloNuevo:
    lineas: list[LineaConsumo] = []
    for item in estado.consumos_detalle:
        lineas.append(LineaConsumo(nombre=item.nombre, monto=item.monto))
    total = estado.consumos_ciclo_actual
    if not lineas and total > 0:
        lineas.append(LineaConsumo(nombre=CONSUMO_SIN_DETALLE, monto=total))
    return DesgloseCicloNuevo(lineas=lineas, total=total)


def calcular_vista_uso(tarjeta: Tarjeta) -> VistaUso:
    estado = validar_ciclo(tarjeta)
    pendiente = max(0.0, estado.monto_adeudado_ciclo_anterior)
    nuevo = max(0.0, estado.consumos_ciclo_actual)
    limite = max(tarjeta.limite, 0.0)

    total_usado = pendiente + nuevo
    disponible = max(0.0, limite - total_usado)

    desglose_pasado = _desglose_pasado(tarjeta, estado, pendiente) if pendiente > 0 else None
    costo_pasado = desglose_pasado.costo_total if desglose_pasado else 0.0

    return VistaUso(
        limite=limite,
        disponible=disponible,
        total_usado=total_usado,
        ciclo_pasado_pendiente=pendiente,
        ciclo_pasado_costo=costo_pasado,
        ciclo_nuevo_total=nuevo,
        mostrar_ciclo_pasado=pendiente > 0,
        desglose_pasado=desglose_pasado,
        desglose_nuevo=_desglose_nuevo(estado),
    )


def sincronizar_saldo_desde_ciclos(tarjeta: Tarjeta) -> Tarjeta:
    """Alinea adeudado con ciclo anterior + consumos del ciclo nuevo."""
    from app.core.tarjetas import guardar_tarjeta

    estado = validar_ciclo(tarjeta)
    total = max(0.0, estado.monto_adeudado_ciclo_anterior + estado.consumos_ciclo_actual)
    nuevo_adeudado = min(tarjeta.limite, total)
    if abs(tarjeta.adeudado - nuevo_adeudado) > 0.009:
        tarjeta.adeudado = nuevo_adeudado
        guardar_tarjeta(tarjeta)
    return tarjeta
