from __future__ import annotations

from app.components.uso_panel import render_panel_uso
from app.core.tarjetas import Tarjeta


def render(tarjeta: Tarjeta) -> None:
    render_panel_uso(tarjeta)
