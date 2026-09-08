"""
Salud de la tarjeta: atraso (Past Due) vs. pago del estado de cuenta.

Past Due = deuda ya vencida (meses anteriores) → prioridad HOY.
Pago sin intereses = obligación del ciclo recién cerrado → vencimiento futuro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.fechas import dias_entre, hoy, proxima_fecha_por_dia
from app.core.tarjetas import Tarjeta
from app.i18n.translator import t


def fmt_dinero(valor: float) -> str:
    """Monto con símbolo $ — usar en UI (no dentro de st.warning con LaTeX)."""
    return f"${valor:,.2f}"


def tiene_atraso(tarjeta: Tarjeta) -> bool:
    """True si el estado de cuenta reporta deuda vencida de meses anteriores."""
    return float(tarjeta.monto_vencido_atrasado or 0) > 0


def listar_tarjetas_con_atraso(tarjetas: list[Tarjeta]) -> list[Tarjeta]:
    return [tj for tj in tarjetas if tiene_atraso(tj)]


def monto_past_due(tarjeta: Tarjeta) -> float:
    """Solo el Past Due del extracto — no mezclar con pago_sin_intereses."""
    return max(0.0, float(tarjeta.monto_vencido_atrasado or 0))


def pago_estado_cuenta(tarjeta: Tarjeta) -> float:
    """Pago para no generar intereses / saldo del ciclo cerrado."""
    if tarjeta.pago_sin_intereses is not None and tarjeta.pago_sin_intereses > 0:
        return float(tarjeta.pago_sin_intereses)
    return max(0.0, float(tarjeta.adeudado_ciclo or 0))


def deuda_ciclo_estado(tarjeta: Tarjeta) -> float:
    """Deuda del ciclo cerrado (estado de cuenta), separada del Past Due."""
    return pago_estado_cuenta(tarjeta)


def dias_atraso_mora(tarjeta: Tarjeta, referencia: date | None = None) -> int:
    """
    Días desde que venció el pago del ciclo cerrado.
    Si hay Past Due en el extracto, siempre hay mora activa (mínimo 1 día).
    """
    if not tiene_atraso(tarjeta):
        return 0
    from app.core.validacion_ciclo import ultimo_corte

    ref = referencia or hoy()
    corte_cerrado = ultimo_corte(tarjeta, ref)
    pago_vencido = proxima_fecha_por_dia(tarjeta.dia_pago, corte_cerrado)
    if ref > pago_vencido:
        return max(1, dias_entre(pago_vencido, ref))
    return 1


@dataclass
class PrioridadPagoUI:
    fase: str  # past_due | ciclo | al_dia
    monto_urgente: float
    monto_ciclo: float
    dias_hasta_pago_ciclo: int
    dias_atraso_mora: int
    urgente: bool


def evaluar_prioridad_pago(tarjeta: Tarjeta, referencia: date | None = None) -> PrioridadPagoUI:
    """Qué cobrar primero y con qué urgencia mostrarlo en la UI."""
    from app.core.validacion_ciclo import validar_ciclo

    ref = referencia or hoy()
    estado = validar_ciclo(tarjeta, ref)
    past = monto_past_due(tarjeta)
    ciclo = deuda_ciclo_estado(tarjeta)

    if past > 0:
        return PrioridadPagoUI(
            fase="past_due",
            monto_urgente=past,
            monto_ciclo=ciclo,
            dias_hasta_pago_ciclo=estado.dias_hasta_pago,
            dias_atraso_mora=dias_atraso_mora(tarjeta, ref),
            urgente=True,
        )
    if ciclo > 0:
        return PrioridadPagoUI(
            fase="ciclo",
            monto_urgente=ciclo,
            monto_ciclo=ciclo,
            dias_hasta_pago_ciclo=estado.dias_hasta_pago,
            dias_atraso_mora=0,
            urgente=estado.dias_hasta_pago <= 3,
        )
    return PrioridadPagoUI(
        fase="al_dia",
        monto_urgente=0.0,
        monto_ciclo=0.0,
        dias_hasta_pago_ciclo=estado.dias_hasta_pago,
        dias_atraso_mora=0,
        urgente=False,
    )


def mensaje_alerta_atraso(tarjeta: Tarjeta) -> str:
    """Banner 🚨: solo el Past Due, sin mezclar con el pago del ciclo."""
    monto_txt = fmt_dinero(monto_past_due(tarjeta))
    cargo = float(tarjeta.cargo_atraso or 0)
    etiqueta = f"{tarjeta.banco} ····{tarjeta.ultimos_digitos}"
    dias = dias_atraso_mora(tarjeta)
    if cargo > 0:
        return t(
            "salud_tarjeta.alerta_atraso_con_cargo",
            tarjeta=etiqueta,
            monto=monto_txt,
            cargo=fmt_dinero(cargo),
            dias=dias,
        )
    return t(
        "salud_tarjeta.alerta_atraso",
        tarjeta=etiqueta,
        monto=monto_txt,
        dias=dias,
    )


def mensaje_past_due_hoy(tarjeta: Tarjeta, referencia: date | None = None) -> str:
    """Texto multilínea para asesor cuando hay mora."""
    prio = evaluar_prioridad_pago(tarjeta, referencia)
    return t(
        "salud_tarjeta.prioridad_past_due",
        vencido=fmt_dinero(prio.monto_urgente),
        ciclo=fmt_dinero(prio.monto_ciclo),
        dias=prio.dias_atraso_mora,
        dias_ciclo=prio.dias_hasta_pago_ciclo,
    )


def prioridad_pago(tarjetas: list[Tarjeta]) -> list[Tarjeta]:
    """Orden de pago: primero Past Due más alto, luego mayor cargo por mora."""

    def _clave(tj: Tarjeta) -> tuple[float, float, float]:
        return (
            monto_past_due(tj),
            float(tj.cargo_atraso or 0),
            float(tj.tasa_interes_anual or 0),
        )

    return sorted(tarjetas, key=_clave, reverse=True)
