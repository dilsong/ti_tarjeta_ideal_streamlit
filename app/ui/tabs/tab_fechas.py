from __future__ import annotations

from app.components.charts import render_grafico_fechas
from app.core.tarjetas import Tarjeta


def render(tarjeta: Tarjeta) -> None:
    render_grafico_fechas(tarjeta)
