# Piloto Streamlit — data local por dispositivo

## Qué cambió

La app Streamlit guarda **tarjetas, pagos, consumos, PIN e idioma** en el
`localStorage` del navegador de cada usuario.

- No se escribe en `app/data/` del servidor (modo piloto).
- No se sube a GitHub.
- Cada teléfono/PC tiene su propia data (origen del navegador).
- Persiste al cerrar la pestaña o el navegador.

Clave: `ti_tarjeta_ideal_v1`

## Cómo correr el piloto

```powershell
cd c:\ti_tarjeta_ideal
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Comparte la URL (o usa un túnel tipo ngrok / Cloudflare) para que cada piloto
abra TI en **su** navegador (Safari/Chrome del teléfono).

Primera vez en un dispositivo: data en blanco → crear PIN → registrar tarjetas.

## Lab en tu PC (archivos JSON, como antes)

Solo si necesitas `cargar_caso.py` o depurar con JSON en disco:

```powershell
$env:TI_USE_FILESYSTEM="1"
streamlit run streamlit_app.py
```

## Soporte

El ZIP de Ayuda exporta la data del **dispositivo actual** (sin PIN).
En modo navegador, importar el ZIP restaura en ese mismo localStorage.
