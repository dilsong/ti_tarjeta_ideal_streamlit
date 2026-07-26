"""
Lógica del ciclo de facturación: adeudado actual vs adeudado del ciclo.
"""

from __future__ import annotations

from datetime import date

from app.core.fechas import dias_entre, fecha_en_mes, hoy, proxima_fecha_por_dia
from app.core.tarjetas import Tarjeta


def calcular_monto_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> float:
    """Monto congelado en el corte — obligación para evitar intereses."""
    t = sincronizar_ciclo(tarjeta, referencia)
    return t.adeudado_ciclo


def calcular_disponibilidad(tarjeta: Tarjeta, referencia: date | None = None) -> float:
    """Disponibilidad real = límite − adeudado actual."""
    _ = referencia
    return max(0.0, tarjeta.limite - tarjeta.adeudado)


def calcular_dias_para_pagar(tarjeta: Tarjeta, referencia: date | None = None) -> int:
    ref = referencia or hoy()
    pago = proxima_fecha_por_dia(tarjeta.dia_pago, ref)
    return max(0, dias_entre(ref, pago))


def calcular_dias_para_corte(tarjeta: Tarjeta, referencia: date | None = None) -> int:
    ref = referencia or hoy()
    corte = proxima_fecha_por_dia(tarjeta.dia_corte, ref)
    return max(0, dias_entre(ref, corte))


def compra_cae_en_proximo_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> bool:
    """True si la compra entra al siguiente ciclo (después del corte)."""
    from app.core.validacion_ciclo import compra_cae_en_proximo_ciclo as _compra_proximo

    return _compra_proximo(tarjeta, referencia)


def sincronizar_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> Tarjeta:
    """Congela adeudado_ciclo al pasar la fecha de corte del mes."""
    ref = referencia or hoy()
    corte_mes = fecha_en_mes(ref.year, ref.month, tarjeta.dia_corte)

    if tarjeta.fecha_corte_aplicada is None:
        if ref >= corte_mes:
            tarjeta.adeudado_ciclo = tarjeta.adeudado
            tarjeta.fecha_corte_aplicada = corte_mes.isoformat()
        else:
            tarjeta.adeudado_ciclo = 0.0
        return tarjeta

    ultima = date.fromisoformat(tarjeta.fecha_corte_aplicada)
    if ref >= corte_mes and ultima < corte_mes:
        tarjeta.adeudado_ciclo = tarjeta.adeudado
        tarjeta.fecha_corte_aplicada = corte_mes.isoformat()

    return tarjeta
