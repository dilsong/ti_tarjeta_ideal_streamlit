"""
Salud de la tarjeta: atraso (Past Due) vs. ciclo al día.

Fuente única para bloqueo de compras, banners y prioridad de pago.
"""

from __future__ import annotations

from app.core.tarjetas import Tarjeta
from app.i18n.translator import t


def tiene_atraso(tarjeta: Tarjeta) -> bool:
    """True si el estado de cuenta reporta deuda vencida de meses anteriores."""
    return float(tarjeta.monto_vencido_atrasado or 0) > 0


def listar_tarjetas_con_atraso(tarjetas: list[Tarjeta]) -> list[Tarjeta]:
    return [tj for tj in tarjetas if tiene_atraso(tj)]


def mensaje_alerta_atraso(tarjeta: Tarjeta) -> str:
    """Texto empático para banner 🚨 (sin jerga financiera)."""
    monto = float(tarjeta.monto_vencido_atrasado or 0)
    cargo = float(tarjeta.cargo_atraso or 0)
    pago = float(tarjeta.pago_sin_intereses or tarjeta.adeudado or 0)
    etiqueta = f"{tarjeta.banco} ····{tarjeta.ultimos_digitos}"
    if cargo > 0:
        return t(
            "salud_tarjeta.alerta_atraso_con_cargo",
            tarjeta=etiqueta,
            monto=monto,
            pago=pago,
            cargo=cargo,
        )
    return t(
        "salud_tarjeta.alerta_atraso",
        tarjeta=etiqueta,
        monto=monto,
        pago=pago,
    )


def prioridad_pago(tarjetas: list[Tarjeta]) -> list[Tarjeta]:
    """
    Orden de pago: primero la deuda atrasada más alta, luego mayor cargo por mora.
    """
    def _clave(tj: Tarjeta) -> tuple[float, float, float]:
        return (
            float(tj.monto_vencido_atrasado or 0),
            float(tj.cargo_atraso or 0),
            float(tj.tasa_interes_anual or 0),
        )

    return sorted(tarjetas, key=_clave, reverse=True)
