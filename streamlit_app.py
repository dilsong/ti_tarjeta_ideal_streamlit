"""
Launcher Streamlit — TI App (PWA monousuario / Lab).

Lab en PC con JSON compartido (solo local):

    set TI_USE_FILESYSTEM=1
    streamlit run streamlit_app.py

Producción (Render / PWA):

    streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
    # En Render el disco se ignora: PIN + tarjetas van a localStorage del teléfono
    # (ti_pin_created, ti_app_auth_v1, ti_app_bundle_v1).
    # FECHA_EXPIRACION_LICENCIA=2026-10-08
"""

from app.app import main

main()
