"""
Launcher Streamlit — TI App (PWA monousuario / Lab).

Render ejecuta este archivo (Procfile / startCommand).
"""

from __future__ import annotations

import os

# En Render el disco es efímero: nunca usar app/data para el usuario.
if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
    os.environ["TI_USE_FILESYSTEM"] = "0"

from app.app import main

main()
