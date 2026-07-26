"""
Launcher Streamlit — piloto con data por dispositivo (?ti= en la URL).

Cada piloto guarda su data en un archivo propio ligado al enlace.
Lab en PC con JSON compartido:

    set TI_USE_FILESYSTEM=1
    streamlit run streamlit_app.py
"""

from app.app import main

main()
