"""Pantallas Streamlit de Tarjeta Ideal."""

from app.ui.app_inicio import render as render_inicio
from app.ui.app_lista_tarjetas import render as render_lista
from app.ui.app_registrar_tarjeta import render as render_registrar

__all__ = ["render_inicio", "render_lista", "render_registrar"]
