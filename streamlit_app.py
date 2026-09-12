"""
Launcher Streamlit — TI App (PWA monousuario / Lab).

Lab en PC con JSON compartido:

    set TI_USE_FILESYSTEM=1
    streamlit run streamlit_app.py

Producción (Render / PWA, dominio fijo):

    streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
    # TI_USE_FILESYSTEM=0  → PIN + datos en localStorage del navegador/PWA
    # TI_USE_FILESYSTEM=1  → app/data/*.json (disco persistente)
    # FECHA_EXPIRACION_LICENCIA=2026-10-08  → bloqueo total tras esa fecha
"""

from app.app import main

main()
