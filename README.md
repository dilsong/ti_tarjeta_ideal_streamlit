# Tarjeta Ideal

App de gestión inteligente de tarjetas de crédito — **Streamlit**, datos 100% locales.

## Características

- PIN de 4 dígitos encriptado localmente (PBKDF2-SHA256)
- Sin usuarios, perfiles ni servidores
- Abanico interactivo estilo wallet
- Motor de recomendación con mensajes humanos
- Multi-idioma ES/EN
- Arquitectura preparada para notificaciones futuras

## Estructura

```
app/
├── components/     # Teclados, selectores, segmented control
├── ui/             # Pantallas (cada una con main())
├── core/           # recomendador.py, seguridad.py, tarjetas.py
├── data/           # tarjetas.json, config.json (local)
├── i18n/           # es.json, en.json, translator.py
└── app.py          # Navegación principal
```

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecutar

```bash
streamlit run streamlit_app.py
```

> **Importante:** no uses `streamlit run app/app.py`. Python confunde el archivo
> `app.py` con el paquete `app` y la pantalla queda en blanco.

Pantallas individuales (desarrollo):

```bash
streamlit run app/ui/app_inicio.py
streamlit run app/ui/app_registrar_tarjeta.py
streamlit run app/ui/app_lista_tarjetas.py
```

## i18n

```python
from app.i18n.translator import t
t("pantalla_registrar_tarjeta.boton_guardar")
```

## Datos locales

- `app/data/config.json` — PIN encriptado e idioma
- `app/data/tarjetas.json` — tarjetas registradas

## Lab + app móvil (Fase 2)

- **Lab (PC):** `streamlit run streamlit_app.py` — depuración e import de casos con `python tools/cargar_caso.py …`
- **Móvil:** carpeta [`mobile/`](mobile/README.md) — Expo (Android + iOS), data local, PIN por dispositivo

## Fase futura

- `app/core/notificaciones.py` — stub para alertas de pago, feriados y fines de semana
