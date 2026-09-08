"""
Launcher Streamlit — piloto con data por dispositivo (?ti= en la URL).

Cada piloto guarda su data en un archivo propio ligado al enlace.
Lab en PC con JSON compartido:

    set TI_USE_FILESYSTEM=1
    streamlit run streamlit_app.py

Producción (Render / PWA monousuario):

    streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
    # TI_USE_FILESYSTEM=0  → data en la URL (?ti=&s=), disco efímero OK
    # TI_USE_FILESYSTEM=1  → app/data/*.json (solo con disco persistente)
    # FECHA_EXPIRACION_LICENCIA=2026-10-08  → bloqueo total tras esa fecha
"""

from app.app import main

main()
