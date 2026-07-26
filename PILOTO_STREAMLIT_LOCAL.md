# Piloto Streamlit — data por dispositivo

## Qué cambió

La app guarda **tarjetas, pagos, consumos, PIN e idioma** por dispositivo.

En Streamlit Cloud el `localStorage` del navegador **no sirve** (queda aislado
en un iframe). En su lugar:

- Cada piloto recibe un ID en la URL: `?ti=...`
- Sus datos se guardan en un archivo propio en el servidor (no en GitHub)
- **Hay que reabrir el mismo enlace** (con `?ti=`) o guardarlo en favoritos

## Cómo correr el piloto

```powershell
cd c:\ti_tarjeta_ideal
pip install -r requirements.txt
streamlit run streamlit_app.py
```

En Cloud: sube el repo; el archivo `packages.txt` instala Tesseract para OCR.

## Importante para pilotos

1. Tras crear el PIN, **guarda la URL completa** (debe verse `?ti=` en la barra).
2. Si abres solo el link corto sin `?ti=`, la app cree que eres un dispositivo nuevo.
3. Usa Ayuda → exportar ZIP como respaldo.

## Lab en tu PC (archivos JSON compartidos)

```powershell
$env:TI_USE_FILESYSTEM="1"
streamlit run streamlit_app.py
```

## Soporte

El ZIP de Ayuda exporta la data del dispositivo actual (sin PIN).
Importar el ZIP restaura en ese mismo dispositivo (`?ti=`).
