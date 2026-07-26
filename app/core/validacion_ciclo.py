"""
Validación del ciclo de facturación: separación de deuda, consumos y fechas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from app.core.ciclo import sincronizar_ciclo
from app.core.consumos import CONSUMO_SIN_DETALLE, listar_consumos_por_tarjeta
from app.core.fechas import dias_entre, fecha_en_mes, hoy, proxima_fecha_por_dia
from app.core.tarjetas import EstadoSalud, Tarjeta

if TYPE_CHECKING:
    from app.core.intereses import ProyeccionIntereses


@dataclass
class ConsumoDetalle:
    nombre: str
    monto: float


@dataclass
class EstadoCiclo:
    monto_adeudado_ciclo_anterior: float
    consumos_ciclo_actual: float
    monto_adeudado_actual: float
    disponibilidad: float
    consumos_detalle: list[ConsumoDetalle] = field(default_factory=list)
    dias_hasta_corte: int = 0
    dias_hasta_pago: int = 0
    dias_hasta_pago_siguiente_ciclo: int = 0
    fecha_ultimo_corte: date | None = None
    fecha_corte_proximo: date | None = None
    fecha_pago_proximo: date | None = None
    fecha_pago_siguiente_ciclo: date | None = None
    compra_en_ciclo_actual: bool = True
    pago_minimo: float = 0.0
    saldo_restante: float = 0.0
    interes_estimado: float = 0.0
    total_proximo_ciclo: float = 0.0
    proyeccion_intereses: ProyeccionIntereses | None = None


def ultimo_corte(tarjeta: Tarjeta, referencia: date | None = None) -> date:
    """Fecha de corte más reciente ya aplicada respecto a la referencia."""
    ref = referencia or hoy()
    corte_mes = fecha_en_mes(ref.year, ref.month, tarjeta.dia_corte)
    if ref >= corte_mes:
        return corte_mes
    mes = ref.month - 1
    anio = ref.year
    if mes < 1:
        mes = 12
        anio -= 1
    return fecha_en_mes(anio, mes, tarjeta.dia_corte)


def compra_cae_en_proximo_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> bool:
    """
    True si la compra no aumenta el pago inmediato (después del último corte aplicado).
    Usado por el motor de recomendación.
    """
    ref = referencia or hoy()
    return ref > ultimo_corte(tarjeta, ref)


def compra_en_ciclo_actual(tarjeta: Tarjeta, referencia: date | None = None) -> bool:
    """True si la compra cae antes o en el próximo corte (ciclo abierto actual)."""
    ref = referencia or hoy()
    corte_proximo = proxima_fecha_por_dia(tarjeta.dia_corte, ref)
    return ref <= corte_proximo


def calcular_dias_hasta_pago_siguiente_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> tuple[int, date]:
    """Días y fecha de pago del estado de cuenta que cierra en el próximo corte."""
    ref = referencia or hoy()
    corte_proximo = proxima_fecha_por_dia(tarjeta.dia_corte, ref)
    pago_siguiente = proxima_fecha_por_dia(tarjeta.dia_pago, corte_proximo)
    return max(0, dias_entre(ref, pago_siguiente)), pago_siguiente


def _agrupar_consumos_ciclo_actual(
    tarjeta: Tarjeta,
    desde: date,
) -> tuple[float, list[ConsumoDetalle]]:
    grupos: dict[str, float] = {}
    for consumo in listar_consumos_por_tarjeta(tarjeta.id):
        fecha_consumo = date.fromisoformat(consumo.fecha)
        if fecha_consumo <= desde:
            continue
        clave = (consumo.tienda_razon or "").strip() or CONSUMO_SIN_DETALLE
        grupos[clave] = grupos.get(clave, 0.0) + consumo.monto

    detalle = [
        ConsumoDetalle(nombre=n, monto=m)
        for n, m in sorted(grupos.items(), key=lambda x: -x[1])
    ]
    return sum(grupos.values()), detalle


def validar_ciclo(tarjeta: Tarjeta, referencia: date | None = None) -> EstadoCiclo:
    """Separa deuda congelada, consumos del ciclo actual y calcula fechas clave."""
    ref = referencia or hoy()
    sincronizada = sincronizar_ciclo(tarjeta, ref)

    deuda_ciclo = sincronizada.adeudado_ciclo
    adeudado_actual = sincronizada.adeudado
    ultimo = ultimo_corte(sincronizada, ref)

    consumos_total, consumos_detalle = _agrupar_consumos_ciclo_actual(sincronizada, ultimo)
    consumos_ciclo = consumos_total if consumos_total > 0 else max(0.0, adeudado_actual - deuda_ciclo)

    if consumos_total <= 0 and consumos_ciclo > 0:
        consumos_detalle = [ConsumoDetalle(nombre=CONSUMO_SIN_DETALLE, monto=consumos_ciclo)]

    corte_proximo = proxima_fecha_por_dia(sincronizada.dia_corte, ref)
    pago_proximo = proxima_fecha_por_dia(sincronizada.dia_pago, ref)
    dias_pago_sig, pago_siguiente = calcular_dias_hasta_pago_siguiente_ciclo(sincronizada, ref)

    return EstadoCiclo(
        monto_adeudado_ciclo_anterior=deuda_ciclo,
        consumos_ciclo_actual=consumos_ciclo,
        monto_adeudado_actual=adeudado_actual,
        disponibilidad=max(0.0, sincronizada.limite - adeudado_actual),
        consumos_detalle=consumos_detalle,
        dias_hasta_corte=max(0, dias_entre(ref, corte_proximo)),
        dias_hasta_pago=max(0, dias_entre(ref, pago_proximo)),
        dias_hasta_pago_siguiente_ciclo=dias_pago_sig,
        fecha_ultimo_corte=ultimo,
        fecha_corte_proximo=corte_proximo,
        fecha_pago_proximo=pago_proximo,
        fecha_pago_siguiente_ciclo=pago_siguiente,
        compra_en_ciclo_actual=compra_en_ciclo_actual(sincronizada, ref),
    )


def validar_ciclo_con_intereses(tarjeta: Tarjeta, referencia: date | None = None) -> EstadoCiclo:
    """Validación de ciclo enriquecida con proyección de intereses."""
    from app.core.intereses import enriquecer_estado_ciclo

    estado = validar_ciclo(tarjeta, referencia)
    return enriquecer_estado_ciclo(tarjeta, estado)


def estado_riesgo_pago(tarjeta: Tarjeta, referencia: date | None = None) -> EstadoSalud:
    """
    Semáforo de pago por tarjeta (única fuente de verdad).

    - Verde: sin deuda del ciclo anterior.
    - Amarillo: con deuda y más de 3 días hasta el pago.
    - Rojo: con deuda y 3 días o menos.
    """
    estado = validar_ciclo(tarjeta, referencia)
    if estado.monto_adeudado_ciclo_anterior <= 0:
        return EstadoSalud.POSITIVO
    if estado.dias_hasta_pago <= 3:
        return EstadoSalud.NEGATIVO
    return EstadoSalud.MEDIO


def dias_para_pagar_compra(
    tarjeta: Tarjeta,
    referencia: date | None = None,
) -> int:
    """Días reales para pagar según si la compra cae en el ciclo actual o el siguiente."""
    ref = referencia or hoy()
    estado = validar_ciclo(tarjeta, ref)
    if compra_cae_en_proximo_ciclo(tarjeta, ref):
        return estado.dias_hasta_pago_siguiente_ciclo
    return estado.dias_hasta_pago


def ejecutar_prueba_escenario() -> EstadoCiclo:
    """
    Escenario de prueba:
    Límite 2000, deuda ciclo anterior 500, consumos actuales 403,
    corte 30, pago 20, hoy 13 junio.
    """
    ref = date(2026, 6, 13)
    tarjeta = Tarjeta(
        id="test-ciclo",
        banco="Test",
        nombre="Visa",
        limite=2000.0,
        adeudado=903.0,
        ultimos_digitos="0000",
        color="azul",
        estilo="solido",
        dia_corte=30,
        dia_pago=20,
        adeudado_ciclo=500.0,
        fecha_corte_aplicada=date(2026, 5, 30).isoformat(),
    )
    return validar_ciclo(tarjeta, ref)


def imprimir_prueba_escenario() -> EstadoCiclo:
    estado = ejecutar_prueba_escenario()
    print("=== Prueba validación ciclo ===")
    print(f"Deuda ciclo anterior:  ${estado.monto_adeudado_ciclo_anterior:,.2f}")
    print(f"Consumos ciclo actual: ${estado.consumos_ciclo_actual:,.2f}")
    print(f"Adeudado actual:       ${estado.monto_adeudado_actual:,.2f}")
    print(f"Disponibilidad:        ${estado.disponibilidad:,.2f}")
    print(f"Días hasta corte:      {estado.dias_hasta_corte}")
    print(f"Días hasta pago:       {estado.dias_hasta_pago}")
    print(f"Días pago sig. ciclo:  {estado.dias_hasta_pago_siguiente_ciclo}")
    print(f"Compra en ciclo actual:{estado.compra_en_ciclo_actual}")
    for c in estado.consumos_detalle:
        print(f"  · {c.nombre}: ${c.monto:,.2f}")
    return estado


if __name__ == "__main__":
    imprimir_prueba_escenario()
