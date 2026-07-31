"""
Cálculo de intereses con base 360 días y simulación de pago mínimo vs total.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import EstadoCiclo

TASA_INTERES_DEFAULT = 45.0
BASE_DIAS_ANIO = 360
DIAS_PERIODO_DEFAULT = 30
PAGO_MINIMO_PCT_DEFAULT = 5.0
PAGO_MINIMO_PISO_DEFAULT = 200.0


@dataclass
class SimulacionPago:
    pago_aplicado: float
    saldo_restante: float
    interes_estimado: float
    total_proximo_ciclo: float
    dias_interes: int


@dataclass
class ProyeccionIntereses:
    monto_pagar_ciclo: float
    monto_acumulado_proximo_min: float
    pago_minimo: float
    saldo_arrastrado: float
    interes_estimado: float
    total_proximo_ciclo: float
    interes_diario: float
    tasa_aplicada: float
    dias_interes: int
    tasa_es_estimada: bool
    escenario_total: SimulacionPago
    escenario_minimo: SimulacionPago


@dataclass
class DesgloseProximoCiclo:
    saldo_arrastrado: float
    consumos_ciclo: float
    interes_estimado: float
    interes_mora: float
    total: float
    escenario: str
    cargo_atraso: float = 0.0


def tasa_vigente(tarjeta: Tarjeta, dias_hasta_pago: int = 0) -> float:
    """Usa tasa moratoria si el pago ya venció y está configurada."""
    if dias_hasta_pago <= 0 and tarjeta.tasa_interes_mora is not None:
        return tarjeta.tasa_interes_mora
    return tarjeta.tasa_interes_anual


def calcular_interes_diario(saldo: float, tasa_anual: float) -> float:
    if saldo <= 0 or tasa_anual <= 0:
        return 0.0
    return saldo * (tasa_anual / 100.0) / BASE_DIAS_ANIO


def calcular_interes_periodo(saldo: float, tasa_anual: float, dias: int) -> float:
    if dias <= 0 or saldo <= 0:
        return 0.0
    return calcular_interes_diario(saldo, tasa_anual) * dias


def calcular_interes_mensual(saldo: float, tasa_anual: float) -> float:
    """Estimación mensual: interés diario × 30 días."""
    return calcular_interes_periodo(saldo, tasa_anual, DIAS_PERIODO_DEFAULT)


def calcular_interes_proximo_ciclo(
    saldo_restante: float,
    tasa_anual: float,
    dias: int = DIAS_PERIODO_DEFAULT,
) -> float:
    return calcular_interes_periodo(saldo_restante, tasa_anual, dias)


def calcular_pago_minimo(tarjeta: Tarjeta, deuda_ciclo: float) -> float:
    """Híbrido: override manual, o max(% de deuda, piso). Piso 0 = sin mínimo fijo."""
    if deuda_ciclo <= 0:
        return 0.0
    if tarjeta.pago_minimo_manual is not None and tarjeta.pago_minimo_manual > 0:
        return min(tarjeta.pago_minimo_manual, deuda_ciclo)
    pct = tarjeta.pago_minimo_pct if tarjeta.pago_minimo_pct > 0 else PAGO_MINIMO_PCT_DEFAULT
    calculado = deuda_ciclo * pct / 100.0
    piso = tarjeta.pago_minimo_piso
    if piso > 0:
        calculado = max(calculado, piso)
    return min(calculado, deuda_ciclo)


def simular_pago(
    deuda_ciclo: float,
    pago: float,
    tasa_anual: float,
    consumos_ciclo_actual: float,
    dias_interes: int = DIAS_PERIODO_DEFAULT,
) -> SimulacionPago:
    pago_aplicado = min(max(0.0, pago), deuda_ciclo)
    saldo_restante = max(0.0, deuda_ciclo - pago_aplicado)
    interes = calcular_interes_proximo_ciclo(saldo_restante, tasa_anual, dias_interes)
    total = consumos_ciclo_actual + saldo_restante + interes
    return SimulacionPago(
        pago_aplicado=pago_aplicado,
        saldo_restante=saldo_restante,
        interes_estimado=interes,
        total_proximo_ciclo=total,
        dias_interes=dias_interes,
    )


def simular_pago_minimo(
    deuda_ciclo: float,
    pago_minimo: float,
    tasa_anual: float,
    consumos_ciclo_actual: float = 0.0,
    dias_interes: int = DIAS_PERIODO_DEFAULT,
) -> SimulacionPago:
    return simular_pago(deuda_ciclo, pago_minimo, tasa_anual, consumos_ciclo_actual, dias_interes)


def _dias_interes_periodo(estado: EstadoCiclo) -> int:
    if estado.dias_hasta_pago_siguiente_ciclo > 0:
        return estado.dias_hasta_pago_siguiente_ciclo
    if estado.dias_hasta_pago > 0:
        return estado.dias_hasta_pago
    return DIAS_PERIODO_DEFAULT


def proyectar_intereses(tarjeta: Tarjeta, estado: EstadoCiclo) -> ProyeccionIntereses:
    deuda = estado.monto_adeudado_ciclo_anterior
    consumos = estado.consumos_ciclo_actual
    dias = _dias_interes_periodo(estado)
    tasa = tasa_vigente(tarjeta, estado.dias_hasta_pago)
    pago_min = calcular_pago_minimo(tarjeta, deuda)

    escenario_total = simular_pago(deuda, deuda, tasa, consumos, dias)
    escenario_minimo = simular_pago_minimo(deuda, pago_min, tasa, consumos, dias)

    saldo_ref = escenario_minimo.saldo_restante
    return ProyeccionIntereses(
        monto_pagar_ciclo=deuda,
        monto_acumulado_proximo_min=escenario_minimo.total_proximo_ciclo,
        pago_minimo=pago_min,
        saldo_arrastrado=escenario_minimo.saldo_restante,
        interes_estimado=escenario_minimo.interes_estimado,
        total_proximo_ciclo=escenario_minimo.total_proximo_ciclo,
        interes_diario=calcular_interes_diario(saldo_ref, tasa) if saldo_ref > 0 else 0.0,
        tasa_aplicada=tasa,
        dias_interes=dias,
        tasa_es_estimada=tarjeta.tasa_es_estimada,
        escenario_total=escenario_total,
        escenario_minimo=escenario_minimo,
    )


def enriquecer_estado_ciclo(tarjeta: Tarjeta, estado: EstadoCiclo) -> EstadoCiclo:
    proy = proyectar_intereses(tarjeta, estado)
    estado.pago_minimo = proy.pago_minimo
    estado.saldo_restante = proy.saldo_arrastrado
    estado.interes_estimado = proy.interes_estimado
    estado.total_proximo_ciclo = proy.total_proximo_ciclo
    estado.proyeccion_intereses = proy
    return estado


def generar_desglose_proximo_ciclo(
    tarjeta: Tarjeta,
    estado: EstadoCiclo,
    proy: ProyeccionIntereses,
) -> DesgloseProximoCiclo:
    """
    Desglose del acumulado próximo ciclo (escenario pago mínimo):
    arrastre + compras actuales + interés + mora = total.
    """
    sim = proy.escenario_minimo

    interes_mora = 0.0
    cargo_atraso = 0.0
    if estado.dias_hasta_pago <= 0:
        tasa_mora = tarjeta.tasa_interes_mora or tasa_vigente(tarjeta, 0)
        interes_mora = calcular_interes_proximo_ciclo(
            proy.monto_pagar_ciclo,
            tasa_mora,
            proy.dias_interes,
        )
        # Cargo fijo del banco por pagar tarde: no depende de la tasa ni del saldo.
        if tarjeta.cargo_atraso and proy.monto_pagar_ciclo > 0:
            cargo_atraso = float(tarjeta.cargo_atraso)

    total = (
        sim.saldo_restante
        + estado.consumos_ciclo_actual
        + sim.interes_estimado
        + interes_mora
        + cargo_atraso
    )

    return DesgloseProximoCiclo(
        saldo_arrastrado=sim.saldo_restante,
        consumos_ciclo=estado.consumos_ciclo_actual,
        interes_estimado=sim.interes_estimado,
        interes_mora=interes_mora,
        total=total,
        escenario="minimo",
        cargo_atraso=cargo_atraso,
    )


def clave_mensaje_escenario(escenario: str) -> str:
    if escenario == "total":
        return "intereses.mensaje_pago_total"
    if escenario == "mora":
        return "intereses.mensaje_no_pago"
    return "intereses.mensaje_pago_minimo"
