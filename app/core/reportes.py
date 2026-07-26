"""
Agregación de datos para el módulo de Reportes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from app.core.consumos import listar_consumos_por_tarjeta
from app.core.fechas import formatear_fecha, hoy, proxima_fecha_por_dia
from app.core.tarjetas import EstadoSalud, Tarjeta, listar_tarjetas
from app.core.validacion_ciclo import estado_riesgo_pago, validar_ciclo
from app.core.vista_uso import VistaUso, calcular_vista_uso


class EstadoCicloReporte(str, Enum):
    BLOQUEADO = "bloqueado"
    ACUMULANDOSE = "acumulando"
    AMBOS = "ambos"
    LIBRE = "libre"


class OrdenReporte(str, Enum):
    URGENCIA = "urgencia"
    CONSUMO = "consumo"
    RIESGO = "riesgo"
    DISPONIBILIDAD = "disponibilidad"
    ALFABETICO = "alfabetico"


@dataclass
class FiltrosReporte:
    banco: str | None = None
    tipo_tarjeta: str | None = None
    estado_ciclo: str | None = None
    compra_desde: date | None = None
    compra_hasta: date | None = None
    consumo_min: float | None = None
    consumo_max: float | None = None


@dataclass
class FilaReporte:
    tarjeta: Tarjeta
    vista: VistaUso
    tipo: str
    limite: float
    consumo: float
    consumo_ciclo_nuevo: float
    disponibilidad: float
    fecha_corte: date | None
    fecha_pago: date | None
    fecha_corte_txt: str
    fecha_pago_txt: str
    ultima_compra: date | None
    ultima_compra_txt: str
    estado_ciclo: EstadoCicloReporte
    estado_ciclo_txt: str
    dias_hasta_pago: int
    riesgo: EstadoSalud
    score_riesgo: float


@dataclass
class ResumenReporte:
    total_limite: float
    total_consumo: float
    total_disponibilidad: float
    tarjeta_mas_cargada: str
    tarjeta_mas_urgente: str
    cantidad: int
    filas: list[FilaReporte] = field(default_factory=list)


def _ultima_compra(id_tarjeta: str) -> date | None:
    fechas = [date.fromisoformat(c.fecha) for c in listar_consumos_por_tarjeta(id_tarjeta)]
    return max(fechas) if fechas else None


def _estado_ciclo_reporte(vista: VistaUso) -> EstadoCicloReporte:
    tiene_pasado = vista.ciclo_pasado_pendiente > 0
    tiene_nuevo = vista.ciclo_nuevo_total > 0
    if tiene_pasado and tiene_nuevo:
        return EstadoCicloReporte.AMBOS
    if tiene_pasado:
        return EstadoCicloReporte.BLOQUEADO
    if tiene_nuevo:
        return EstadoCicloReporte.ACUMULANDOSE
    return EstadoCicloReporte.LIBRE


def _score_riesgo(fila: FilaReporte) -> float:
    if fila.limite <= 0:
        return 0.0
    uso = fila.consumo / fila.limite
    urgencia = 1.0 / max(1, fila.dias_hasta_pago)
    mult = 1.5 if fila.riesgo == EstadoSalud.NEGATIVO else 1.2 if fila.riesgo == EstadoSalud.MEDIO else 1.0
    return (uso * 60.0 + urgencia * 40.0) * mult


def _estado_ciclo_label(estado: EstadoCicloReporte, idioma: str) -> str:
    claves = {
        EstadoCicloReporte.BLOQUEADO: "reportes.estado_bloqueado",
        EstadoCicloReporte.ACUMULANDOSE: "reportes.estado_acumulando",
        EstadoCicloReporte.AMBOS: "reportes.estado_ambos",
        EstadoCicloReporte.LIBRE: "reportes.estado_libre",
    }
    from app.i18n.translator import t

    return t(claves[estado])


def construir_fila(tarjeta: Tarjeta, idioma: str = "es") -> FilaReporte:
    vista = calcular_vista_uso(tarjeta)
    estado = validar_ciclo(tarjeta)
    ref = hoy()
    f_corte = proxima_fecha_por_dia(tarjeta.dia_corte, ref)
    f_pago = proxima_fecha_por_dia(tarjeta.dia_pago, ref)
    ultima = _ultima_compra(tarjeta.id)
    est_ciclo = _estado_ciclo_reporte(vista)
    riesgo = estado_riesgo_pago(tarjeta)

    fila = FilaReporte(
        tarjeta=tarjeta,
        vista=vista,
        tipo=tarjeta.nombre,
        limite=vista.limite,
        consumo=vista.total_usado,
        consumo_ciclo_nuevo=vista.ciclo_nuevo_total,
        disponibilidad=vista.disponible,
        fecha_corte=f_corte,
        fecha_pago=f_pago,
        fecha_corte_txt=formatear_fecha(f_corte, idioma),
        fecha_pago_txt=formatear_fecha(f_pago, idioma),
        ultima_compra=ultima,
        ultima_compra_txt=formatear_fecha(ultima, idioma) if ultima else "—",
        estado_ciclo=est_ciclo,
        estado_ciclo_txt=_estado_ciclo_label(est_ciclo, idioma),
        dias_hasta_pago=estado.dias_hasta_pago,
        riesgo=riesgo,
        score_riesgo=0.0,
    )
    fila.score_riesgo = _score_riesgo(fila)
    return fila


def _pasa_filtro(fila: FilaReporte, filtros: FiltrosReporte) -> bool:
    tj = fila.tarjeta
    if filtros.banco and filtros.banco != tj.banco:
        return False
    if filtros.tipo_tarjeta and filtros.tipo_tarjeta != tj.nombre:
        return False
    if filtros.estado_ciclo:
        if filtros.estado_ciclo == "bloqueado":
            if fila.estado_ciclo not in {EstadoCicloReporte.BLOQUEADO, EstadoCicloReporte.AMBOS}:
                return False
        elif filtros.estado_ciclo == "acumulando":
            if fila.estado_ciclo not in {EstadoCicloReporte.ACUMULANDOSE, EstadoCicloReporte.AMBOS}:
                return False
        elif filtros.estado_ciclo == "libre" and fila.estado_ciclo != EstadoCicloReporte.LIBRE:
            return False
    if filtros.compra_desde and (not fila.ultima_compra or fila.ultima_compra < filtros.compra_desde):
        return False
    if filtros.compra_hasta and (not fila.ultima_compra or fila.ultima_compra > filtros.compra_hasta):
        return False
    if filtros.consumo_min is not None and fila.consumo < filtros.consumo_min:
        return False
    if filtros.consumo_max is not None and fila.consumo > filtros.consumo_max:
        return False
    return True


def ordenar_filas(filas: list[FilaReporte], orden: OrdenReporte) -> list[FilaReporte]:
    if orden == OrdenReporte.URGENCIA:
        return sorted(filas, key=lambda f: (f.dias_hasta_pago, -f.consumo))
    if orden == OrdenReporte.CONSUMO:
        return sorted(filas, key=lambda f: -f.consumo)
    if orden == OrdenReporte.RIESGO:
        return sorted(filas, key=lambda f: -f.score_riesgo)
    if orden == OrdenReporte.DISPONIBILIDAD:
        return sorted(filas, key=lambda f: -f.disponibilidad)
    return sorted(filas, key=lambda f: f.tarjeta.nombre.lower())


def generar_reporte(filtros: FiltrosReporte | None = None, idioma: str = "es") -> ResumenReporte:
    filtros = filtros or FiltrosReporte()
    filas = [f for f in (construir_fila(t, idioma) for t in listar_tarjetas()) if _pasa_filtro(f, filtros)]

    total_limite = sum(f.limite for f in filas)
    total_consumo = sum(f.consumo for f in filas)
    total_disp = sum(f.disponibilidad for f in filas)

    mas_cargada = max(filas, key=lambda f: f.consumo).tarjeta.nombre if filas else "—"
    mas_urgente = min(filas, key=lambda f: (f.dias_hasta_pago, -f.consumo)).tarjeta.nombre if filas else "—"

    return ResumenReporte(
        total_limite=total_limite,
        total_consumo=total_consumo,
        total_disponibilidad=total_disp,
        tarjeta_mas_cargada=mas_cargada,
        tarjeta_mas_urgente=mas_urgente,
        cantidad=len(filas),
        filas=filas,
    )


def opciones_filtro() -> tuple[list[str], list[str], list[str]]:
    tarjetas = listar_tarjetas()
    bancos = sorted({t.banco for t in tarjetas})
    tipos = sorted({t.nombre for t in tarjetas})
    return bancos, tipos, bancos
