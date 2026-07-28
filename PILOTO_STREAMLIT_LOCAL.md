# Piloto Streamlit — data en el enlace

## Cómo funciona (Cloud)

Streamlit Cloud **borra** los archivos temporales entre visitas.
Por eso tus datos (PIN, tarjetas, etc.) van **dentro del enlace**:

`https://….streamlit.app/?ti=….&s=….`

- `ti` = id del dispositivo  
- `s` = tus datos comprimidos  

## Pasos para el piloto

1. Abre el link de la app.
2. Crea el PIN.
3. Mira la barra: debe aparecer **`&s=`** (el link se alarga).
4. **Guarda ese favorito de nuevo** (no el link corto solo con `?ti=`).
5. Para volver, abre **ese** favorito → te pedirá desbloquear, no crear PIN.

Si abres el link corto sin `&s=`, la app cree que eres nuevo.

## Lab en PC

```powershell
$env:TI_USE_FILESYSTEM="1"
streamlit run streamlit_app.py
```

## Soporte

Exporta ZIP desde Ayuda como respaldo extra.
