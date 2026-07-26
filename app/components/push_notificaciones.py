"""Notificaciones del navegador (móvil / PWA) al abrir la app."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from app.i18n.translator import t
from notificaciones.notificador_ciclos import evaluar_notificaciones_del_dia


def _cuerpo_humano(mensaje: str) -> str:
    lineas = [ln.strip() for ln in mensaje.splitlines() if ln.strip()]
    if len(lineas) >= 2 and ("Asesor" in lineas[0] or "Advisor" in lineas[0]):
        return " ".join(lineas[1:])
    return " ".join(lineas)


def listar_alertas_push_hoy() -> list[dict[str, str]]:
    """Alertas del día para todas las tarjetas (prioridad ya resuelta por tarjeta)."""
    alertas: list[dict[str, str]] = []
    for notif in evaluar_notificaciones_del_dia():
        if not notif.mensaje:
            continue
        alertas.append(
            {
                "title": t("push.titulo_tarjeta", nombre=notif.tarjeta_nombre or "TI"),
                "body": _cuerpo_humano(notif.mensaje),
            }
        )
    return alertas


def render_solicitud_permiso(*, compacto: bool = False) -> None:
    """Botón para activar avisos en el teléfono (requiere permiso del navegador)."""
    st.markdown(
        f'<div id="ti-push-perm-anchor"></div>',
        unsafe_allow_html=True,
    )
    if compacto:
        st.caption(t("push.nota_movil"))
    else:
        st.markdown(f"**{t('push.titulo_seccion')}**")
        st.caption(t("push.subtitulo"))

    if st.button(t("push.boton_activar"), key="push_activar_perm", use_container_width=True):
        components.html(
            """
            <script>
            (async function () {
              if (!("Notification" in window)) {
                alert("NOT_SUPPORTED");
                return;
              }
              try {
                const perm = await Notification.requestPermission();
                window.parent.postMessage({type: "streamlit:setComponentValue", value: perm}, "*");
              } catch (e) {
                console.error(e);
              }
            })();
            </script>
            """,
            height=0,
        )
        st.info(t("push.instruccion_permiso"))


def disparar_push_si_permitido(alertas: list[dict[str, str]], clave_dia: str) -> None:
    """Muestra notificaciones nativas una vez por día al abrir la app."""
    if not alertas:
        return
    if st.session_state.get(clave_dia):
        return

    payload = json.dumps(alertas[:3], ensure_ascii=False)
    titulo_app = t("push.titulo_app")
    components.html(
        f"""
        <script>
        (function () {{
          const alertas = {payload};
          const tituloApp = {json.dumps(titulo_app)};
          if (!("Notification" in window)) return;
          if (Notification.permission !== "granted") return;
          alertas.forEach(function (a, i) {{
            setTimeout(function () {{
              try {{
                new Notification(a.title || tituloApp, {{
                  body: a.body,
                  tag: "ti-" + i + "-" + (a.title || ""),
                  renotify: true
                }});
              }} catch (e) {{ console.error(e); }}
            }}, i * 800);
          }});
        }})();
        </script>
        """,
        height=0,
    )
    st.session_state[clave_dia] = True
