"""Componentes UI reutilizables para Streamlit."""

from app.components.charts import render_grafico_fechas, render_grafico_limite
from app.components.keyboard_alpha import alpha_input
from app.components.keyboard_numeric import entero_text_input, monto_text_input, parse_monto
from app.components.segmented_control import segmented_control
from app.components.select_with_add import persist_if_new, select_with_add
from app.components.theme import BANCOS_DEFAULT, CARD_COLORS, ESTADO_COLORS, MOBILE_CSS

__all__ = [
    "BANCOS_DEFAULT",
    "CARD_COLORS",
    "ESTADO_COLORS",
    "MOBILE_CSS",
    "alpha_input",
    "entero_text_input",
    "monto_text_input",
    "parse_monto",
    "persist_if_new",
    "render_grafico_fechas",
    "render_grafico_limite",
    "segmented_control",
    "select_with_add",
]
