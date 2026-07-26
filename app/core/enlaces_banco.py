"""Enlaces a banca móvil / web por banco (abrir app o sitio del banco)."""

from __future__ import annotations

from typing import Literal

PreferenciaBanco = Literal["app", "web"]

# Por banco: enlace orientado a app (suele abrir la app instalada) y a banca web.
ENLACES_BANCO: dict[str, dict[str, str]] = {
    "BBVA": {
        "app": "https://www.bbva.mx/personas/productos/cuentas/banca-movil.html",
        "web": "https://www.bbva.mx/personas.html",
    },
    "Banorte": {
        "app": "https://www.banorte.com/wps/portal/banorte/Home/inicio",
        "web": "https://www.banorte.com/",
    },
    "Santander": {
        "app": "https://www.santander.com.mx/personas/santander-movil.html",
        "web": "https://www.santander.com.mx/",
    },
    "HSBC": {
        "app": "https://www.hsbc.com.mx/online-banking/",
        "web": "https://www.hsbc.com.mx/",
    },
    "Scotiabank": {
        "app": "https://www.scotiabank.com.mx/personas/servicios/banca-en-linea.aspx",
        "web": "https://www.scotiabank.com.mx/",
    },
    "Inbursa": {
        "app": "https://www.inbursa.com/portal/",
        "web": "https://www.inbursa.com/",
    },
    "Chase": {
        "app": "https://www.chase.com/digital/mobile-banking",
        "web": "https://www.chase.com/",
    },
    "Capital One": {
        "app": "https://www.capitalone.com/digital/mobile/",
        "web": "https://www.capitalone.com/",
    },
    "Bank of America": {
        "app": "https://www.bankofamerica.com/online-banking/mobile-and-online-banking/",
        "web": "https://www.bankofamerica.com/",
    },
    "Wells Fargo": {
        "app": "https://www.wellsfargo.com/mobile/",
        "web": "https://www.wellsfargo.com/",
    },
    "Citi": {
        "app": "https://online.citi.com/US/ag/mobile-app",
        "web": "https://www.citi.com/",
    },
    "Discover": {
        "app": "https://www.discover.com/online-banking/mobile/",
        "web": "https://www.discover.com/",
    },
    "American Express": {
        "app": "https://www.americanexpress.com/en-us/support/mobile-app/",
        "web": "https://www.americanexpress.com/",
    },
    "Credit One": {
        "app": "https://www.creditonebank.com/mobile-app",
        "web": "https://www.creditonebank.com/",
    },
}

# Compatibilidad con código que aún pide una sola URL (preferencia app).
URLS_BANCA_MOVIL: dict[str, str] = {
    banco: enlaces["app"] for banco, enlaces in ENLACES_BANCO.items()
}


def normalizar_preferencia(valor: str | None) -> PreferenciaBanco:
    return "web" if (valor or "").strip().lower() == "web" else "app"


def url_banca_movil(banco: str) -> str | None:
    """URL de app del catálogo, o None si el banco no está listado."""
    enlaces = ENLACES_BANCO.get(banco.strip())
    return enlaces["app"] if enlaces else None


def url_catalogo(banco: str, preferencia: PreferenciaBanco | str) -> str | None:
    """URL del catálogo según preferencia app/web, con fallback a la otra."""
    enlaces = ENLACES_BANCO.get(banco.strip())
    if not enlaces:
        return None
    pref = normalizar_preferencia(preferencia)
    primaria = enlaces.get(pref)
    if primaria:
        return primaria
    return enlaces.get("app") or enlaces.get("web")


def resolver_url_banco(tarjeta) -> str | None:
    """
    URL a abrir para ir al banco:
    1) override manual en la tarjeta (url_app_banco distinto del catálogo)
    2) catálogo según preferencia_banco
    """
    pref = normalizar_preferencia(getattr(tarjeta, "preferencia_banco", None))
    guardada = getattr(tarjeta, "url_app_banco", None)
    if guardada and str(guardada).strip():
        u = str(guardada).strip()
        del_catalogo = {
            url_catalogo(tarjeta.banco, "app"),
            url_catalogo(tarjeta.banco, "web"),
        }
        if u not in del_catalogo:
            return u
    return url_catalogo(tarjeta.banco, pref)


def url_para_banco(
    banco: str,
    preferencia: PreferenciaBanco | str = "app",
    url_manual: str | None = None,
) -> str | None:
    """Al guardar tarjeta: prioriza URL manual, luego catálogo por preferencia."""
    manual = (url_manual or "").strip()
    if manual:
        return manual
    return url_catalogo(banco, preferencia)
