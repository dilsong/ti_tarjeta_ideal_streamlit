"""
Licencia de prueba (PWA monousuario).

FECHA_EXPIRACION_LICENCIA — ISO YYYY-MM-DD (env o valor por defecto).
Si hoy > esa fecha, la app se bloquea por completo.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from app.core.fechas import hoy

# Prueba por defecto: 1 año desde hoy.
_DEFAULT_EXPIRACION = "2027-10-08"
_ENV_KEY = "FECHA_EXPIRACION_LICENCIA"


def fecha_expiracion_licencia() -> date:
    """Lee la fecha de caducidad desde env; si falta o es inválida, usa el default."""
    raw = (os.environ.get(_ENV_KEY) or "").strip()
    if not raw:
        raw = _DEFAULT_EXPIRACION
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return date.fromisoformat(_DEFAULT_EXPIRACION)


def licencia_vigente(referencia: date | None = None) -> bool:
    """True si la versión de prueba sigue activa (hoy <= fecha de expiración)."""
    ref = referencia or hoy()
    return ref <= fecha_expiracion_licencia()


def licencia_expirada(referencia: date | None = None) -> bool:
    return not licencia_vigente(referencia)


def dias_restantes_licencia(referencia: date | None = None) -> int:
    """Días inclusive hasta la expiración; negativo si ya venció."""
    ref = referencia or hoy()
    return (fecha_expiracion_licencia() - ref).days


def sugerir_fecha_prueba(dias: int = 30, desde: date | None = None) -> str:
    """Utilidad: ISO de (desde + dias) para configurar el env en Render."""
    base = desde or hoy()
    return (base + timedelta(days=dias)).isoformat()
