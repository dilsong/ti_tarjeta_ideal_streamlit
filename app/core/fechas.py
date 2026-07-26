"""
Utilidades de fechas para el recomendador.

Reservado también para notificaciones futuras (fines de semana / feriados).
"""

from __future__ import annotations

import calendar
from datetime import date


def hoy() -> date:
    return date.today()


def fecha_en_mes(anio: int, mes: int, dia: int) -> date:
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(dia, ultimo))


def proxima_fecha_por_dia(dia: int, referencia: date | None = None) -> date:
    ref = referencia or hoy()
    candidato = fecha_en_mes(ref.year, ref.month, dia)
    if candidato < ref:
        mes = ref.month + 1
        anio = ref.year
        if mes > 12:
            mes = 1
            anio += 1
        candidato = fecha_en_mes(anio, mes, dia)
    return candidato


def dias_entre(desde: date, hasta: date) -> int:
    return (hasta - desde).days


def formatear_fecha(fecha: date, idioma: str = "es") -> str:
    """Fecha corta legible según idioma."""
    if idioma == "en":
        return fecha.strftime("%b %d")
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    return f"{fecha.day} {meses[fecha.month - 1]}"
