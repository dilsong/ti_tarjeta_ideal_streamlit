"""
Cargador full-screen personalizado TI (PWA / móvil).

Uso (igual que st.spinner):

    from app.components.ti_loader import ti_spinner

    with ti_spinner("Leyendo estado de cuenta…"):
        datos = procesar_fuentes_captura(...)

Inyecta un overlay en window.top (no solo el iframe de Streamlit)
para bloquear toques en iPhone hasta que termine el bloque.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Iterator

import streamlit.components.v1 as components

_OVERLAY_ID = "ti-loader-overlay"
_BG_DARK = "#0F172A"
_BLUE = "#2563EB"
_BLUE_BRIGHT = "#60A5FA"
_TEXT = "#F8FAFC"


def _show_script(mensaje: str) -> str:
    msg_js = json.dumps(mensaje or "")
    return f"""
<script>
(function () {{
  try {{
    var doc = (window.top && window.top.document)
      || (window.parent && window.parent.document)
      || document;
    var old = doc.getElementById("{_OVERLAY_ID}");
    if (old) old.remove();

    if (!doc.getElementById("ti-loader-style")) {{
      var style = doc.createElement("style");
      style.id = "ti-loader-style";
      style.textContent = `
@keyframes ti-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes ti-pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.72; }}
}}
#{_OVERLAY_ID} {{
  position: fixed;
  inset: 0;
  z-index: 2147483646;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.1rem;
  background: rgba(15, 23, 42, 0.72);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}}
#{_OVERLAY_ID} .ti-ring {{
  width: 88px;
  height: 88px;
  border-radius: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: {_BG_DARK};
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.35), 0 12px 40px rgba(0,0,0,0.45);
}}
#{_OVERLAY_ID} .ti-ring::before {{
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 3px solid transparent;
  border-top-color: {_BLUE_BRIGHT};
  border-right-color: {_BLUE};
  animation: ti-spin 0.85s linear infinite;
}}
#{_OVERLAY_ID} .ti-letters {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-weight: 800;
  font-size: 1.55rem;
  letter-spacing: 0.06em;
  color: {_BLUE_BRIGHT};
  animation: ti-pulse 1.4s ease-in-out infinite;
  z-index: 1;
}}
#{_OVERLAY_ID} .ti-msg {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 0.92rem;
  font-weight: 500;
  color: {_TEXT};
  text-align: center;
  max-width: 80vw;
  padding: 0 1rem;
  line-height: 1.35;
}}`;
      doc.head.appendChild(style);
    }}

    var msg = {msg_js};
    var el = doc.createElement("div");
    el.id = "{_OVERLAY_ID}";
    el.setAttribute("role", "progressbar");
    el.setAttribute("aria-busy", "true");
    var html = '<div class="ti-ring"><span class="ti-letters">TI</span></div>';
    if (msg) {{
      var p = doc.createElement("div");
      p.className = "ti-msg";
      p.textContent = msg;
      el.innerHTML = html;
      el.appendChild(p);
    }} else {{
      el.innerHTML = html;
    }}
    el.addEventListener("touchmove", function (e) {{ e.preventDefault(); }}, {{ passive: false }});
    el.addEventListener("click", function (e) {{ e.preventDefault(); e.stopPropagation(); }});
    doc.body.appendChild(el);
  }} catch (err) {{
    console.warn("TI loader show failed", err);
  }}
}})();
</script>
"""


def _hide_script() -> str:
    return f"""
<script>
(function () {{
  try {{
    var doc = (window.top && window.top.document)
      || (window.parent && window.parent.document)
      || document;
    var el = doc.getElementById("{_OVERLAY_ID}");
    if (el) el.remove();
  }} catch (err) {{
    console.warn("TI loader hide failed", err);
  }}
}})();
</script>
"""


def show_ti_loader(mensaje: str = "") -> None:
    """Muestra el overlay TI (bloqueo de pantalla)."""
    components.html(_show_script(mensaje), height=0, width=0)


def hide_ti_loader() -> None:
    """Oculta / elimina el overlay TI."""
    components.html(_hide_script(), height=0, width=0)


@contextmanager
def ti_spinner(mensaje: str = "Procesando…") -> Iterator[None]:
    """
    Context manager tipo ``with st.spinner()`` con el cargador TI.

    Example::

        with ti_spinner("Leyendo PDF e imágenes…"):
            datos = procesar_fuentes_captura(...)
    """
    show_ti_loader(mensaje)
    time.sleep(0.08)
    try:
        yield
    finally:
        hide_ti_loader()
