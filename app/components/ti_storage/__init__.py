"""Componente Streamlit ↔ localStorage del origen PWA (ventana top)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent
_ls = components.declare_component("ti_local_storage", path=str(_COMPONENT_DIR))

# Bundle completo (tarjetas, pagos, config, …)
STORAGE_KEY_BUNDLE = "ti_app_bundle_v1"
# Auth indestructible (sobrevive aunque el bundle falle al parsear)
STORAGE_KEY_PIN_CREATED = "ti_pin_created"
STORAGE_KEY_AUTH = "ti_app_auth_v1"


def ls_get(storage_key: str, *, widget_key: str) -> Any:
    """Lee un string de localStorage. En el primer tick puede devolver None (pendiente)."""
    return _ls(mode="get", storage_key=storage_key, default=None, key=widget_key)


def ls_set(storage_key: str, value: str, *, widget_key: str) -> Any:
    """Escribe (o borra si value='') en localStorage."""
    return _ls(mode="set", storage_key=storage_key, value=value, default=None, key=widget_key)


def inject_ls_write(storage_key: str, value: str) -> None:
    """
    Escritura de respaldo vía components.html → window.top.localStorage.
    Más fiable en PWA/móvil que solo el custom component.
    """
    import json

    import streamlit as st

    payload = json.dumps(value, ensure_ascii=False)
    key_js = json.dumps(storage_key)
    seq = int(st.session_state.get("ti_ls_html_seq", 0)) + 1
    st.session_state["ti_ls_html_seq"] = seq
    components.html(
        f"""
        <script>
        (function () {{
          try {{
            var ls = null;
            try {{ ls = window.top.localStorage; }} catch (e1) {{
              try {{ ls = window.parent.localStorage; }} catch (e2) {{
                ls = window.localStorage;
              }}
            }}
            if (!ls) return;
            var key = {key_js};
            var val = {payload};
            if (val === null || val === undefined || val === "") {{
              ls.removeItem(key);
            }} else {{
              ls.setItem(key, String(val));
            }}
          }} catch (err) {{
            console.warn("TI inject_ls_write failed", err);
          }}
        }})();
        </script>
        """,
        height=0,
    )
