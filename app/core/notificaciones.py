"""
Notificaciones inteligentes de pago — fase futura.

Arquitectura preparada para alertas basadas en ciclo de facturación,
fines de semana y feriados. Sin implementación activa en esta fase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.ciclo import calcular_dias_para_pagar, calcular_monto_ciclo
from app.core.tarjetas import Tarjeta


@dataclass
class AlertaPago:
    """Modelo de alerta de pago ideal (fase futura)."""

    tarjeta_id: str
    tarjeta_nombre: str
    fecha_pago_oficial: date
    fecha_pago_ideal: date
    monto_ciclo: float
    monto_actual: float
    dias_restantes: int
    mensaje: str
    urgente: bool = False
    ajustado_fin_semana: bool = False
    ajustado_feriado: bool = False


def calcular_fecha_pago_ideal(fecha_pago: date, referencia: date | None = None) -> date:
    """
    Ajusta la fecha de pago si cae en fin de semana o feriado.

    Fase futura: mover al siguiente día hábil.
    """
    _ = referencia
    return fecha_pago


def generar_alerta_pago(tarjeta: Tarjeta, referencia: date | None = None) -> AlertaPago:
    """
    Genera alerta de pago ideal usando monto del ciclo y fechas.

    Fase futura — retorna estructura base sin mensaje final.
    """
    from app.core.fechas import hoy, proxima_fecha_por_dia

    ref = referencia or hoy()
    pago = proxima_fecha_por_dia(tarjeta.dia_pago, ref)
    return AlertaPago(
        tarjeta_id=tarjeta.id,
        tarjeta_nombre=tarjeta.nombre,
        fecha_pago_oficial=pago,
        fecha_pago_ideal=calcular_fecha_pago_ideal(pago, ref),
        monto_ciclo=calcular_monto_ciclo(tarjeta, ref),
        monto_actual=tarjeta.adeudado,
        dias_restantes=calcular_dias_para_pagar(tarjeta, ref),
        mensaje="",
    )


def generar_alertas(tarjetas: list[Tarjeta], referencia: date | None = None) -> list[AlertaPago]:
    """Genera alertas para todas las tarjetas. Fase futura."""
    return [generar_alerta_pago(t, referencia) for t in tarjetas]
