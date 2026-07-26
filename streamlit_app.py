"""
Launcher Streamlit — piloto con data local por dispositivo (localStorage).

Cada usuario guarda su data SOLO en su navegador (teléfono/PC).
No se escribe en el servidor ni en GitHub.

    streamlit run streamlit_app.py

Lab en PC con JSON en disco (cargar_caso / depuración):

    set TI_USE_FILESYSTEM=1
    streamlit run streamlit_app.py
"""

from app.app import main

main()
