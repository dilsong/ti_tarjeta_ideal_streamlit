"""Utilidades compartidas entre pantallas Streamlit."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

from app.components.theme import MOBILE_CSS
from app.core.seguridad import crear_pin, get_idioma, pin_configurado, set_idioma, verificar_pin
from app.i18n.translator import get_language, init_translator, set_language, t

TARJETA_SEL_KEY = "tarjeta_sel_idx"
GUIA_BANCO_KEY = "guia_banco_preselect"


def seleccionar_tarjeta_en_abanico(tarjeta_id: str) -> None:
    """Trae la tarjeta al frente del abanico global."""
    from app.core.tarjetas import listar_tarjetas

    tarjetas = listar_tarjetas()
    idx = next(i for i, tj in enumerate(tarjetas) if tj.id == tarjeta_id)
    st.session_state[TARJETA_SEL_KEY] = idx


@contextmanager
def fila_accion(main_ratio: int = 8, btn_ratio: int = 1) -> Iterator[tuple]:
    """Contenido a la izquierda y botón compacto (?, ›) a la derecha, sin apilar en móvil."""
    st.markdown('<span class="ti-inline-row-marker"></span>', unsafe_allow_html=True)
    c_main, c_btn = st.columns(
        [main_ratio, btn_ratio],
        gap="small",
        vertical_alignment="center",
    )
    yield c_main, c_btn


def setup_page(title: str | None = None) -> None:
    """Configura página con estilo móvil."""
    init_i18n()
    st.set_page_config(
        page_title=title or t("app.nombre"),
        page_icon="💳",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)
    st.markdown(
        '<link rel="manifest" href="/static/manifest.webmanifest">'
        '<meta name="theme-color" content="#2563EB">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
        unsafe_allow_html=True,
    )


def init_i18n() -> None:
    init_translator(get_idioma())


def _render_lang_select(key: str = "lang_sel") -> None:
    lang = st.selectbox(
        t("common.idioma"),
        ["es", "en"],
        index=0 if get_language() == "es" else 1,
        format_func=lambda x: t("common.espanol") if x == "es" else t("common.ingles"),
        label_visibility="collapsed",
        key=key,
    )
    if lang != get_language():
        set_language(lang)
        set_idioma(lang)
        st.rerun()


def language_selector(*, aligned: bool = False) -> None:
    """Selector compacto ES/EN."""
    if aligned:
        st.markdown('<div class="ti-lang-slot">', unsafe_allow_html=True)
        _render_lang_select()
        return
    col1, col2 = st.columns([3, 1])
    with col2:
        st.markdown('<div class="ti-lang-slot">', unsafe_allow_html=True)
        _render_lang_select()


def render_page_header(title: str, caption: str | None = None) -> None:
    """Título + selector de idioma alineados en una sola fila."""
    col_title, col_lang = st.columns([4, 1])
    with col_title:
        st.title(title)
        if caption:
            st.caption(caption)
    with col_lang:
        st.markdown('<div class="ti-lang-slot">', unsafe_allow_html=True)
        _render_lang_select(key="lang_sel_main")


def render_tarjeta_visual(tarjeta) -> None:
    """Renderiza una sola tarjeta (compatibilidad)."""
    st.markdown(_card_html_single(tarjeta), unsafe_allow_html=True)


def _card_html_single(tarjeta, layout: dict | None = None) -> str:
    from app.components.theme import gradiente_tarjeta

    grad = gradiente_tarjeta(tarjeta.color)
    if layout:
        cls = "ti-fan-card ti-fan-card-sel" if layout["sel"] else "ti-fan-card"
        style = (
            f"top:{layout['top']}px;z-index:{layout['z']};"
            f"transform:rotate({layout['rot']}deg) scale({layout['scale']});"
            f"opacity:{layout['opacity']};"
            f"background:{grad};"
        )
        return (
            f'<div class="{cls}" style="{style}">'
            f'<div style="display:flex;justify-content:space-between;font-weight:700;font-size:0.95rem;">'
            f"{tarjeta.banco}<span>&#8226;&#8226;&#8226;&#8226; {tarjeta.ultimos_digitos}</span></div>"
            f'<div style="margin-top:1.1rem;font-size:1.05rem;font-weight:600;">{tarjeta.nombre}</div>'
            f'<div style="opacity:0.85;font-size:0.85rem;margin-top:0.25rem;">${tarjeta.disponible:,.2f}</div>'
            f"</div>"
        )

    return (
        f'<div class="ti-fan-wrap"><div class="ti-card ti-card-front" '
        f'style="background:{grad};">'
        f'<div style="display:flex;justify-content:space-between;font-weight:700;">'
        f"{tarjeta.banco}<span>&#8226;&#8226;&#8226;&#8226; {tarjeta.ultimos_digitos}</span></div>"
        f'<div style="margin-top:1.5rem;font-size:1.1rem;font-weight:600;">{tarjeta.nombre}</div>'
        f'<div style="opacity:0.85;font-size:0.85rem;">${tarjeta.disponible:,.2f}</div>'
        f"</div></div>"
    )


def render_resumen_financiero(tarjeta, vista=None) -> None:
    """Muestra Límite, uso del límite (deuda anterior + ciclo nuevo) y Disponibilidad."""
    from app.core.vista_uso import calcular_vista_uso

    if vista is None:
        vista = calcular_vista_uso(tarjeta)

    color_limite = "#F8FAFC"
    color_consumo = "#EF4444"
    color_disp = "#22C55E"
    consumo = vista.total_usado
    disponible = vista.disponible

    if vista.ciclo_pasado_pendiente > 0 and vista.ciclo_nuevo_total <= 0:
        etiqueta_usado = t("estado.etiqueta_deuda_anterior")
    elif vista.ciclo_pasado_pendiente > 0 and vista.ciclo_nuevo_total > 0:
        etiqueta_usado = t("estado.etiqueta_usado_total")
    else:
        etiqueta_usado = t("pantalla_lista_tarjetas.consumo")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div style="background:#1E293B;border-radius:12px;padding:0.65rem 0.75rem;border-left:4px solid {color_limite};">'
            f'<div style="color:#94A3B8;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
            f'{t("pantalla_lista_tarjetas.limite")}</div>'
            f'<div class="ti-money" style="color:{color_limite};font-size:1.1rem;font-weight:700;">${tarjeta.limite:,.2f}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="background:#1E293B;border-radius:12px;padding:0.65rem 0.75rem;border-left:4px solid {color_consumo};">'
            f'<div style="color:#94A3B8;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
            f'{etiqueta_usado}</div>'
            f'<div class="ti-money" style="color:{color_consumo};font-size:1.1rem;font-weight:700;">${consumo:,.2f}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div style="background:#1E293B;border-radius:12px;padding:0.65rem 0.75rem;border-left:4px solid {color_disp};">'
            f'<div style="color:#94A3B8;font-size:0.72rem;font-weight:600;text-transform:uppercase;">'
            f'{t("pantalla_lista_tarjetas.disponible")}</div>'
            f'<div class="ti-money" style="color:{color_disp};font-size:1.1rem;font-weight:700;">${disponible:,.2f}</div></div>',
            unsafe_allow_html=True,
        )


def _card_button_label(tarjeta) -> str:
    return (
        f"{tarjeta.banco}  •••• {tarjeta.ultimos_digitos}\n"
        f"{tarjeta.nombre}\n"
        f"${tarjeta.disponible:,.2f}"
    )


def _fan_stack_css(tarjetas, sel: int, order: list[int], key_prefix: str) -> str:
    from app.components.theme import gradiente_tarjeta

    anchor = f"ti-fan-stack-anchor-{key_prefix}"
    n = len(tarjetas)
    reserve = max(0, (n - 1) * 22)
    overlap = 84
    card_h = 104
    # Solo el contenedor directo del abanico — evita afectar otros botones de la página
    block = (
        f'div[data-testid="stVerticalBlock"]:has('
        f'> div[data-testid="stElementContainer"] .{anchor})'
    )
    btn = f'{block} > div[data-testid="stElementContainer"]:has([data-testid="stButton"])'

    rules = [
        f"""
        {block} {{
            margin-bottom: {reserve}px !important;
            padding-bottom: 0 !important;
            isolation: isolate;
            position: relative;
            z-index: 1;
        }}
        {btn}:not(:last-of-type) {{
            margin-bottom: -{overlap}px !important;
            position: relative !important;
        }}
        {btn}:last-of-type {{
            position: relative !important;
            z-index: 5 !important;
            margin-bottom: 0 !important;
        }}
        {btn} button {{
            min-height: {card_h}px !important;
            height: auto !important;
            width: 100% !important;
            text-align: left !important;
            border: none !important;
            border-radius: 16px !important;
            padding: 1rem 1.2rem !important;
            color: #FFFFFF !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.35) !important;
            transition: transform 0.25s ease, opacity 0.25s ease !important;
        }}
        {btn} button p {{
            text-align: left !important;
            white-space: pre-line !important;
            line-height: 1.45 !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            color: #FFFFFF !important;
        }}
        """
    ]
    for pos, idx in enumerate(order):
        tarjeta = tarjetas[idx]
        grad = gradiente_tarjeta(tarjeta.color)
        dist = 0 if idx == sel else abs(idx - sel)
        rot = 0 if idx == sel else (-4 if idx < sel else 4) * min(dist, 2)
        op = 1.0 if idx == sel else 0.86
        nth = pos + 2
        rules.append(
            f"""
        {block} > div[data-testid="stElementContainer"]:nth-child({nth}) button {{
            background: {grad} !important;
            opacity: {op} !important;
            transform: rotate({rot}deg) !important;
        }}
            """
        )
    rules.append(
        f"""
        {btn}:last-of-type button {{
            transform: rotate(0deg) scale(1.01) !important;
            opacity: 1 !important;
            box-shadow: 0 14px 36px rgba(0,0,0,0.5) !important;
        }}
        """
    )
    return f"<style>{''.join(rules)}</style>"


def render_abanico_tarjetas(tarjetas, sel_key: str, key_prefix: str = "fan") -> int:
    """Abanico: tarjetas apiladas tocables; al pulsar una pasa al frente."""
    n = len(tarjetas)
    if sel_key not in st.session_state:
        st.session_state[sel_key] = 0
    sel = min(st.session_state[sel_key], n - 1)

    if n == 1:
        render_tarjeta_visual(tarjetas[0])
        return 0

    order = [i for i in range(n) if i != sel] + [sel]
    anchor = f"ti-fan-stack-anchor-{key_prefix}"
    st.markdown(_fan_stack_css(tarjetas, sel, order, key_prefix), unsafe_allow_html=True)

    with st.container():
        st.markdown(f'<div class="{anchor}"></div>', unsafe_allow_html=True)
        for i in order:
            if st.button(_card_button_label(tarjetas[i]), key=f"{key_prefix}_card_{i}", use_container_width=True):
                if i != sel:
                    st.session_state[sel_key] = i
                    st.rerun()

    return sel


def render_abanico_global(tarjetas, key_prefix: str = "global") -> int:
    """Abanico con selección global persistente entre solapas."""
    return render_abanico_tarjetas(tarjetas, TARJETA_SEL_KEY, key_prefix=key_prefix)


def render_abanico_compacto(tarjeta) -> None:
    """Chip compacto de la tarjeta activa (tabs sin abanico completo)."""
    from app.components.theme import CARD_COLORS

    color = CARD_COLORS.get(tarjeta.color, CARD_COLORS["azul"])
    st.markdown(
        f'<div style="background:#1E293B;border-radius:10px;padding:0.55rem 0.85rem;'
        f"border-left:4px solid {color};margin:0.35rem 0 0.75rem;"
        f'"><span style="color:#F8FAFC;font-weight:600;">{tarjeta.nombre}</span>'
        f'<span style="color:#94A3B8;font-size:0.82rem;"> · {tarjeta.banco}'
        f" · •••• {tarjeta.ultimos_digitos}</span></div>",
        unsafe_allow_html=True,
    )


def card_html(tarjeta, front: bool = False) -> str:
    """Deprecated: usar render_tarjeta_visual."""
    from app.components.theme import gradiente_tarjeta

    grad = gradiente_tarjeta(tarjeta.color)
    cls = "ti-card ti-card-front" if front else "ti-card ti-card-back"
    return (
        f'<div class="{cls}" style="background:{grad};">'
        f'<div style="display:flex;justify-content:space-between;font-weight:700;">'
        f"{tarjeta.banco}<span>&#8226;&#8226;&#8226;&#8226; {tarjeta.ultimos_digitos}</span></div>"
        f'<div style="margin-top:1.5rem;font-size:1.1rem;font-weight:600;">{tarjeta.nombre}</div>'
        f'<div style="opacity:0.85;font-size:0.85rem;">${tarjeta.disponible:,.2f}</div>'
        f"</div>"
    )


def pin_input(label: str, key: str) -> str:
    """PIN de 4 dígitos con teclado nativo del dispositivo."""
    return st.text_input(
        label,
        key=key,
        max_chars=4,
        type="password",
        help=t("pantalla_pin.pin"),
    )


def render_pin_gate(on_unlock) -> None:
    """Pantalla de crear PIN (primera vez) o desbloquear."""
    c_sp, c_lang = st.columns([4, 1])
    with c_lang:
        language_selector(aligned=True)
    with c_sp:
        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
    if not pin_configurado():
        _render_crear_pin(on_unlock)
    else:
        _render_desbloquear(on_unlock)


def _render_crear_pin(on_unlock) -> None:
    st.title("💳 " + t("pantalla_pin.crear_titulo"))
    st.info(t("pantalla_pin.crear_subtitulo"))

    step = st.session_state.get("pin_step", "pin")
    error = st.empty()

    if step == "pin":
        pin = pin_input(t("pantalla_pin.pin"), "crear_pin")
        if st.button(t("common.continuar"), key="pin_next", type="primary", use_container_width=True):
            if len(pin) != 4 or not pin.isdigit():
                error.error(t("pantalla_pin.error_pin_corto"))
            else:
                st.session_state["pin_temp"] = pin
                st.session_state["pin_step"] = "confirm"
                st.rerun()
    else:
        pin2 = pin_input(t("pantalla_pin.confirmar_pin"), "confirm_pin")
        if st.button(t("pantalla_pin.boton_crear"), key="pin_create", type="primary", use_container_width=True):
            if pin2 != st.session_state.get("pin_temp", ""):
                error.error(t("pantalla_pin.error_pin_no_coincide"))
            elif crear_pin(pin2):
                st.session_state.pop("pin_step", None)
                st.session_state.pop("pin_temp", None)
                st.session_state["ti_pedir_guardar_favorito"] = True
                on_unlock()
            else:
                error.error(t("pantalla_pin.error_pin_corto"))


def _render_desbloquear(on_unlock) -> None:
    st.title("💳 " + t("pantalla_pin.desbloquear_titulo"))
    st.info(t("pantalla_pin.desbloquear_subtitulo"))

    error = st.empty()
    pin = pin_input(t("pantalla_pin.pin"), "unlock_pin")

    if st.button(t("pantalla_pin.boton_desbloquear"), key="unlock", type="primary", use_container_width=True):
        if verificar_pin(pin):
            on_unlock()
        else:
            error.error(t("pantalla_pin.error_pin_incorrecto"))
