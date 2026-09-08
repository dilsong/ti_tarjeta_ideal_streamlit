"""Notificaciones del navegador (móvil / PWA) al abrir la app."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from app.core.salud_tarjeta import listar_tarjetas_con_atraso, mensaje_alerta_atraso
from app.core.tarjetas import listar_tarjetas
from app.i18n.translator import t
from notificaciones.notificador_ciclos import evaluar_notificaciones_del_dia

_SW_URL = "/app/static/sw.js"


def _cuerpo_humano(mensaje: str) -> str:
    """Quita la primera línea si es encabezado (Tarjeta Ideal · …)."""
    lineas = [ln.strip() for ln in mensaje.splitlines() if ln.strip()]
    if len(lineas) >= 2:
        primera = lineas[0]
        if "·" in primera or "Ideal" in primera or "Tarjeta" in primera:
            return " ".join(lineas[1:])
    return " ".join(lineas)


def listar_alertas_push_hoy() -> list[dict[str, str]]:
    """Alertas del día: Past Due primero, luego hitos de ciclo."""
    alertas: list[dict[str, str]] = []
    tarjetas_vistas: set[str] = set()

    for tarjeta in listar_tarjetas_con_atraso(listar_tarjetas()):
        tarjetas_vistas.add(tarjeta.id)
        alertas.append(
            {
                "title": t("push.past_due_titulo", tarjeta=tarjeta.nombre),
                "body": _cuerpo_humano(mensaje_alerta_atraso(tarjeta)),
            }
        )

    for notif in evaluar_notificaciones_del_dia():
        if notif.tarjeta_id in tarjetas_vistas:
            continue
        if not notif.mensaje:
            continue
        alertas.append(
            {
                "title": t("push.titulo_tarjeta", nombre=notif.tarjeta_nombre or "TI"),
                "body": _cuerpo_humano(notif.mensaje),
            }
        )
    return alertas


def registrar_pwa() -> None:
    """Registra el service worker una vez por sesión."""
    if st.session_state.get("ti_pwa_registrada"):
        return
    components.html(
        f"""
        <script>
        (async function () {{
          try {{
            const root = window.parent;
            if (!root || !("serviceWorker" in root.navigator)) return;
            await root.navigator.serviceWorker.register("{_SW_URL}");
          }} catch (e) {{
            console.warn("TI SW register failed", e);
          }}
        }})();
        </script>
        """,
        height=0,
    )
    st.session_state["ti_pwa_registrada"] = True


def render_solicitud_permiso(*, compacto: bool = False) -> None:
    """Botón para activar avisos (laptop o teléfono)."""
    if compacto:
        st.caption(t("push.nota_movil"))
    else:
        st.markdown(f"**{t('push.titulo_seccion')}**")
        st.caption(t("push.subtitulo"))

    perm_guardado = st.session_state.get("ti_push_perm")
    if perm_guardado == "granted":
        st.success(t("push.estado_permitido"))
    elif perm_guardado == "denied":
        st.warning(t("push.estado_denegado"))
    elif perm_guardado == "unsupported":
        st.info(t("push.no_soportado"))

    if st.button(t("push.boton_activar"), key="push_activar_perm", use_container_width=True):
        st.session_state["ti_push_pedir_permiso"] = True

    # Pedir permiso en un iframe visible (gesto de usuario) — height=0 bloquea el diálogo.
    if st.session_state.pop("ti_push_pedir_permiso", False):
        st.info(t("push.instruccion_permiso"))
        msgs = {
            "solicitando": t("push.perm_solicitando"),
            "espera": t("push.perm_espera"),
            "no_soportado": t("push.perm_no_soportado"),
            "listo": t("push.perm_listo"),
            "bloqueado": t("push.perm_bloqueado"),
            "pendiente": t("push.perm_pendiente"),
            "prueba_titulo": t("push.perm_prueba_titulo"),
            "prueba_cuerpo": t("push.perm_prueba_cuerpo"),
        }
        msgs_js = json.dumps(msgs, ensure_ascii=False)
        resultado = components.html(
            f"""
            <div style="font-family:system-ui,sans-serif;padding:0.5rem;color:#E2E8F0;
                        background:#1E293B;border-radius:10px;border:1px solid #334155;">
              <p style="margin:0 0 0.5rem;font-size:0.9rem;">{msgs["solicitando"]}</p>
              <p id="ti-push-status" style="margin:0;font-size:0.85rem;color:#94A3B8;">{msgs["espera"]}</p>
            </div>
            <script>
            (async function () {{
              const msgs = {msgs_js};
              const status = document.getElementById("ti-push-status");
              const root = window.parent;
              function setVal(v) {{
                try {{
                  window.parent.postMessage({{type: "streamlit:setComponentValue", value: v}}, "*");
                }} catch (e) {{}}
              }}
              if (!root || !("Notification" in root)) {{
                status.textContent = msgs.no_soportado;
                setVal("unsupported");
                return;
              }}
              try {{
                let perm = root.Notification.permission;
                if (perm === "default") {{
                  perm = await root.Notification.requestPermission();
                }}
                if (perm === "granted") {{
                  status.textContent = msgs.listo;
                  status.style.color = "#22C55E";
                  try {{
                    new root.Notification(msgs.prueba_titulo, {{
                      body: msgs.prueba_cuerpo,
                      tag: "ti-test-perm"
                    }});
                  }} catch (e) {{}}
                }} else if (perm === "denied") {{
                  status.textContent = msgs.bloqueado;
                  status.style.color = "#F87171";
                }} else {{
                  status.textContent = msgs.pendiente;
                }}
                setVal(perm);
              }} catch (e) {{
                status.textContent = "Error: " + (e && e.message ? e.message : e);
                setVal("default");
              }}
            }})();
            </script>
            """,
            height=90,
        )
        if resultado in ("granted", "denied", "unsupported", "default"):
            st.session_state["ti_push_perm"] = resultado
            if resultado == "granted":
                st.rerun()

    if not compacto:
        st.markdown(f"**{t('push.instalar_titulo')}**")
        st.caption(f"{t('push.instalar_android')}\n\n{t('push.instalar_ios')}")


def disparar_push_si_permitido(alertas: list[dict[str, str]], clave_dia: str) -> None:
    """Muestra notificaciones nativas una vez por día al abrir la app."""
    if not alertas:
        return
    if st.session_state.get(clave_dia):
        return

    payload = json.dumps(alertas[:3], ensure_ascii=False)
    titulo_app = t("push.titulo_app")
    sw_url = _SW_URL

    components.html(
        f"""
        <script>
        (async function () {{
          const root = window.parent;
          const alertas = {payload};
          const tituloApp = {json.dumps(titulo_app)};
          const icon = "/app/static/icon.png";
          if (!root) return;

          async function viaServiceWorker() {{
            if (!("serviceWorker" in root.navigator)) return false;
            try {{
              const reg = await root.navigator.serviceWorker.register("{sw_url}");
              const sw = reg.active || reg.waiting || reg.installing;
              if (sw) {{
                sw.postMessage({{ type: "TI_SHOW_NOTIFICATIONS", alertas: alertas, tituloApp: tituloApp }});
                return true;
              }}
            }} catch (e) {{ console.warn(e); }}
            return false;
          }}

          function viaNotificationApi() {{
            if (!("Notification" in root)) return;
            if (root.Notification.permission !== "granted") return;
            alertas.forEach(function (a, i) {{
              setTimeout(function () {{
                try {{
                  new root.Notification(a.title || tituloApp, {{
                    body: a.body,
                    tag: "ti-" + i + "-" + (a.title || ""),
                    renotify: true,
                    icon: icon
                  }});
                }} catch (e) {{ console.error(e); }}
              }}, i * 800);
            }});
          }}

          const ok = await viaServiceWorker();
          if (!ok) viaNotificationApi();
        }})();
        </script>
        """,
        height=0,
    )
    st.session_state[clave_dia] = True
