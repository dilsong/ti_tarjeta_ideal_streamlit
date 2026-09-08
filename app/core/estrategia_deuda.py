"""
Estrategia de pago multi-tarjeta (Avalancha interna, lenguaje simple).

El usuario no ve jerga — solo: "Si tienes $X extra, ponlo en esta tarjeta."
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.salud_tarjeta import (
    deuda_ciclo_estado,
    fmt_dinero,
    monto_past_due,
    tiene_atraso,
)
from app.core.tarjetas import Tarjeta
from app.i18n.translator import t

MONTO_EXTRA_DEFAULT = 50.0


@dataclass
class SugerenciaAbonoExtra:
    tarjeta: Tarjeta
    monto_extra: float
    mensaje: str
    urgente: bool


def _etiqueta_tarjeta(tarjeta: Tarjeta) -> str:
    return f"{tarjeta.banco} ····{tarjeta.ultimos_digitos}"


def _score_pago(tarjeta: Tarjeta) -> float:
    """Mayor = pagar primero (Past Due > cargo mora > APR > deuda ciclo)."""
    past = monto_past_due(tarjeta)
    if past > 0:
        return (
            past * 10_000
            + float(tarjeta.cargo_atraso or 0) * 100
            + float(tarjeta.tasa_interes_anual or 0)
        )
    ciclo = deuda_ciclo_estado(tarjeta)
    if ciclo > 0:
        return ciclo * 10 + float(tarjeta.tasa_interes_anual or 0)
    return 0.0


def ranking_pago_extra(tarjetas: list[Tarjeta]) -> list[Tarjeta]:
    """Orden Avalancha: la que más te cuesta si te atrasas, primero."""
    candidatas = [tj for tj in tarjetas if _score_pago(tj) > 0]
    return sorted(candidatas, key=_score_pago, reverse=True)


def tarjeta_prioritaria_pago(tarjetas: list[Tarjeta]) -> Tarjeta | None:
    orden = ranking_pago_extra(tarjetas)
    return orden[0] if orden else None


def recomendar_abono_extra(
    tarjetas: list[Tarjeta],
    monto_extra: float | None = None,
) -> SugerenciaAbonoExtra | None:
    """
    Una frase accionable si el usuario puede abonar algo extra hoy.
    """
    extra = float(monto_extra if monto_extra is not None else MONTO_EXTRA_DEFAULT)
    if extra <= 0:
        return None

    tarjeta = tarjeta_prioritaria_pago(tarjetas)
    if tarjeta is None:
        return None

    etiqueta = _etiqueta_tarjeta(tarjeta)
    monto_txt = fmt_dinero(extra)

    if tiene_atraso(tarjeta):
        mensaje = t(
            "estrategia.abono_extra_past_due",
            monto=monto_txt,
            tarjeta=etiqueta,
            vencido=fmt_dinero(monto_past_due(tarjeta)),
        )
        urgente = True
    else:
        mensaje = t(
            "estrategia.abono_extra_ciclo",
            monto=monto_txt,
            tarjeta=etiqueta,
            deuda=fmt_dinero(deuda_ciclo_estado(tarjeta)),
        )
        urgente = deuda_ciclo_estado(tarjeta) > 0

    return SugerenciaAbonoExtra(
        tarjeta=tarjeta,
        monto_extra=extra,
        mensaje=mensaje,
        urgente=urgente,
    )
