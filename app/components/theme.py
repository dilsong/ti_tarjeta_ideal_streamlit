"""
Estilos visuales compartidos — diseño tipo app móvil para Streamlit.
"""

from __future__ import annotations

CARD_COLORS = {
    "verde": "#059669",
    "azul": "#2563EB",
    "morado": "#7C3AED",
    "rojo": "#DC2626",
    "naranja": "#EA580C",
    "negro": "#1F2937",
    "dorado": "#CA8A04",
}

COLOR_EMOJI = {
    "verde": "🟢",
    "azul": "🔵",
    "morado": "🟣",
    "rojo": "🔴",
    "naranja": "🟠",
    "dorado": "🟡",
    "negro": "⚫",
}


def emoji_color(color_key: str) -> str:
    return COLOR_EMOJI.get(color_key, "⚪")


def etiqueta_color_nombre(color_key: str, nombre: str) -> str:
    return f"{emoji_color(color_key)} {nombre}"


def gradiente_tarjeta(color_key: str) -> str:
    base = CARD_COLORS.get(color_key, CARD_COLORS["azul"])
    fin = "#4B5563" if color_key == "negro" else "#111827"
    return f"linear-gradient(135deg,{base},{fin})"


def colores_mensaje_tarjeta(color_key: str, severidad: str = "normal") -> dict[str, str]:
    """Fondo/borde/texto para mensajes de Fechas según tarjeta o semáforo."""
    if severidad == "urgente":
        return {"bg": "#450A0A", "border": "#EF4444", "text": "#FECACA"}
    if severidad == "medio":
        return {"bg": "#422006", "border": "#EAB308", "text": "#FEF9C3"}
    base = CARD_COLORS.get(color_key, CARD_COLORS["azul"])
    return {"bg": f"{base}22", "border": base, "text": "#F8FAFC"}

ESTADO_COLORS = {
    "positivo": "#22C55E",
    "medio": "#EAB308",
    "negativo": "#EF4444",
}

MOBILE_CSS = """
<style>
    .block-container { padding-top: 2rem; max-width: 480px; }
    div[data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #0F172A; }
    [data-testid="stAppViewContainer"] { background-color: #0F172A; }
    [data-testid="stHeader"] { background-color: rgba(15, 23, 42, 0.95); }

    /* Tipografía legible en fondo oscuro */
    h1, h2, h3, h4, h5, h6,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stHeadingWithActionElements"] {
        color: #F8FAFC !important;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    .stCaption, p.stCaption {
        color: #CBD5E1 !important;
    }
    [data-testid="stWidgetLabel"] p,
    label[data-testid="stWidgetLabel"],
    .stTextInput label p {
        color: #E2E8F0 !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: #E2E8F0;
    }
    .ti-rep-salud-pagos-hint {
        color: #F97316 !important;
        font-weight: 600 !important;
    }

    /* Solapas principales — azul activo, gris claro inactivo */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.25rem;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        color: #94A3B8 !important;
        background: transparent !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        padding: 0.45rem 0.35rem !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        color: #93C5FD !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #2563EB !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: #2563EB !important;
    }
    div[data-testid="stTabs"] { margin-top: 0 !important; }
    div[data-testid="stTabs"] > div:first-child { margin-bottom: 0.35rem !important; }

    /* Navegación persistente (Configurar) — radio horizontal tipo solapas */
    div[data-testid="stElementContainer"]:has(.ti-persist-tabs-marker)
        + div[data-testid="stElementContainer"] div[data-testid="stRadio"] > div {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 0.25rem !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-persist-tabs-marker)
        + div[data-testid="stElementContainer"] div[data-testid="stRadio"] label {
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        padding: 0.45rem 0.35rem !important;
        margin: 0 !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-persist-tabs-marker)
        + div[data-testid="stElementContainer"] div[data-testid="stRadio"] label:has(input:checked) {
        color: #93C5FD !important;
        font-weight: 700 !important;
        border-bottom-color: #2563EB !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-persist-tabs-marker)
        + div[data-testid="stElementContainer"] div[data-testid="stRadio"] label > div:first-child {
        display: none !important;
    }

    /* Botones */
    div.stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100%;
    }
    div.stButton > button[kind="primary"],
    div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
    }
    div.stButton > button[kind="secondary"],
    div.stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #475569 !important;
    }
    .key-btn button {
        min-height: 2.4rem !important;
        background: #334155 !important;
        color: #F8FAFC !important;
        padding: 0.25rem !important;
    }

    .ti-title { font-size: 1.6rem; font-weight: 700; color: #F8FAFC; margin-bottom: 0.25rem; }
    .ti-subtitle { color: #94A3B8; font-size: 0.95rem; margin-bottom: 1rem; }
    .ti-card {
        border-radius: 16px; padding: 1.2rem; color: white;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35); min-height: 120px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .ti-card-front { transform: scale(1.03); box-shadow: 0 12px 32px rgba(0,0,0,0.45); z-index: 10; }
    .ti-card-back { transform: rotate(-4deg) scale(0.96); opacity: 0.88; }
    .ti-fan-wrap { position: relative; min-height: 200px; margin: 1rem 0; }
    .ti-benefit { background: #1E293B; border-radius: 12px; padding: 0.75rem 1rem; margin: 0.4rem 0; color: #CBD5E1; }
    div[data-testid="stAlert"] { margin-top: 0.75rem !important; margin-bottom: 0.75rem !important; position: relative !important; z-index: 0 !important; }
    div[data-testid="stElementContainer"]:has([data-testid="stButton"]) { position: relative !important; z-index: auto !important; margin-bottom: 0.5rem !important; }
    .ti-msg-ok { background: #14532D; border: 1px solid #22C55E; border-radius: 12px; padding: 1rem; color: #DCFCE7; }
    .ti-msg-warn { background: #422006; border: 1px solid #EAB308; border-radius: 12px; padding: 1rem; color: #FEF9C3; }
    .ti-badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; color: white; }
    .ti-display { background: #1E293B; border-radius: 12px; padding: 1rem; text-align: center; font-size: 1.8rem; font-weight: 700; color: #F8FAFC; }
    .seg-btn button { background: #334155 !important; color: #94A3B8 !important; }
    .seg-btn-active button { background: #2563EB !important; color: white !important; }
    .ti-lang-slot { padding-top: 1.85rem; }

    /* Métricas de ciclo — 3 columnas horizontales también en móvil */
    .ti-metric-row {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.45rem;
        margin-bottom: 0.35rem;
    }
    .ti-metric-cell {
        background: transparent;
        border-radius: 8px;
        padding: 0.35rem 0.2rem;
        text-align: left;
        min-width: 0;
    }
    .ti-metric-cell .ti-metric-label {
        color: #CBD5E1;
        font-size: 0.68rem;
        font-weight: 500;
        line-height: 1.2;
        margin-bottom: 0.15rem;
    }
    .ti-metric-cell .ti-metric-value {
        color: #F8FAFC;
        font-size: 1.45rem;
        font-weight: 700;
        line-height: 1.1;
    }

    /* Fila contenido + botón (?, ›) — misma línea en móvil y desktop */
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"],
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 0.35rem !important;
        margin-bottom: 0.5rem !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 0 !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
        flex: 1 1 auto !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
        flex: 0 0 2.5rem !important;
        max-width: 2.5rem !important;
        width: 2.5rem !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"] div.stButton,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] div.stButton {
        margin-bottom: 0 !important;
    }
    div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
        + div[data-testid="stHorizontalBlock"] div.stButton > button,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
        div[data-testid="stHorizontalBlock"] div.stButton > button {
        width: 2.5rem !important;
        min-width: 2.5rem !important;
        min-height: 2.5rem !important;
        max-height: 2.5rem !important;
        padding: 0 !important;
        font-size: 1rem !important;
        white-space: nowrap !important;
        line-height: 1 !important;
    }
    @media (max-width: 768px) {
        div[data-testid="stElementContainer"]:has(.ti-inline-row-marker)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.ti-inline-row-marker)
            div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
        }
    }
    .ti-detail-caption { color: #CBD5E1; font-size: 0.82rem; margin-top: 0.25rem; }

    /* Montos — evitar que los centavos bajen de línea */
    .ti-money, .ti-rep-metric-value, .ti-metric-value {
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }
    .ti-rep-metric-value {
        font-size: clamp(0.95rem, 3.8vw, 1.35rem) !important;
    }
    .ti-metric-value--text { font-size: 1.1rem !important; }

    /* Diálogos — ancho tipo app móvil */
    div[data-testid="stDialog"] > div {
        max-width: 480px !important;
        width: calc(100vw - 1.5rem) !important;
    }

    /* Banner superior — HTML propio (evita que $ active LaTeX en st.warning) */
    .ti-banner-alerta {
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        line-height: 1.55;
        word-wrap: break-word;
        overflow-wrap: anywhere;
        white-space: normal;
    }
    .ti-banner-alerta--warn {
        background: #422006;
        border: 1px solid #FACC15;
        color: #FDE68A;
    }
    .ti-banner-alerta--info {
        background: #1E3A5F;
        border: 1px solid #3B82F6;
        color: #BFDBFE;
    }
    .ti-banner-alerta--urgente {
        background: #450A0A;
        border: 1px solid #EF4444;
        color: #FECACA;
    }

    /* Asesor diario — voz humana */
    .ti-asesor-hoy {
        background: linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin: 0.5rem 0 0.75rem;
    }
    .ti-asesor-hoy .ti-asesor-saludo {
        color: #93C5FD;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 0.35rem;
    }
    .ti-asesor-hoy .ti-asesor-msg {
        color: #E2E8F0;
        font-size: 0.9rem;
        line-height: 1.55;
        word-wrap: break-word;
        overflow-wrap: anywhere;
    }
    .ti-asesor-hoy--urgente { border-left: 4px solid #EF4444; }
    .ti-asesor-hoy--atencion { border-left: 4px solid #EAB308; }
    .ti-asesor-hoy--info { border-left: 4px solid #3B82F6; }
    .ti-asesor-hoy--tranquilo { border-left: 4px solid #22C55E; }

    /* Disponible rápido bajo el abanico */
    .ti-disp-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin: 0.25rem 0 0.5rem;
    }
    .ti-disp-chip {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 999px;
        padding: 0.3rem 0.65rem;
        font-size: 0.75rem;
        color: #CBD5E1;
        white-space: nowrap;
    }
    .ti-disp-chip strong { color: #F8FAFC; }
    .ti-disp-chip--sel {
        border-color: #2563EB;
        background: #1E3A5F;
        color: #BFDBFE;
    }

    /* Resultado compra — evita LaTeX en st.success */
    .ti-compra-resultado {
        background: #14532D;
        border: 1px solid #22C55E;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin: 0.5rem 0;
        color: #BBF7D0;
        font-size: 0.92rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    .ti-compra-resultado--warn {
        background: #422006;
        border-color: #EAB308;
        color: #FEF9C3;
    }
</style>
"""

BANCOS_MX = ["BBVA", "Banorte", "Santander", "HSBC", "Scotiabank", "Inbursa"]
BANCOS_USA = [
    "Credit One",
    "Capital One",
    "Chase",
    "Discover",
    "Bank of America",
    "Wells Fargo",
    "Citi",
    "American Express",
]
# Lista unificada: crear/editar tarjeta y Guía usan los mismos bancos.
BANCOS_DEFAULT = BANCOS_MX + BANCOS_USA
