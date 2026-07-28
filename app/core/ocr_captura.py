"""
OCR de capturas / estados de cuenta para TI (Streamlit).

Usa pytesseract + Tesseract del sistema (packages.txt en Cloud).
No depende del OCR del teléfono del usuario.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, fields
from typing import Any

from PIL import Image


@dataclass
class DatosCaptura:
    """Campos interpretados desde texto OCR o pegado a mano."""

    texto_crudo: str = ""
    dia_corte: int | None = None
    dia_pago: int | None = None
    saldo: float | None = None
    limite: float | None = None
    disponible: float | None = None
    ultimos_digitos: str | None = None
    apr: float | None = None
    penalty_apr: float | None = None
    late_fee: float | None = None
    annual_fee: float | None = None
    daily_rate: float | None = None
    finance_charge: float | None = None

    def tiene_datos_tarjeta(self) -> bool:
        return any(
            v is not None
            for v in (
                self.dia_corte,
                self.dia_pago,
                self.saldo,
                self.limite,
                self.disponible,
                self.ultimos_digitos,
            )
        )

    def tiene_tasas(self) -> bool:
        return self.apr is not None or self.penalty_apr is not None

    def tiene_algo(self) -> bool:
        return bool(self.texto_crudo.strip()) or self.tiene_datos_tarjeta() or self.tiene_tasas()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DatosCaptura":
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def ocr_disponible() -> bool:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except (TesseractNotFoundError, OSError):
        return False


def texto_desde_imagen(imagen: Image.Image) -> str:
    if not ocr_disponible():
        return ""
    import pytesseract
    from pytesseract import TesseractNotFoundError

    try:
        # spa+eng mejora estados de cuenta MX/US
        return pytesseract.image_to_string(imagen, lang="spa+eng")
    except (TesseractNotFoundError, OSError):
        try:
            return pytesseract.image_to_string(imagen)
        except (TesseractNotFoundError, OSError):
            return ""
    except Exception:
        try:
            return pytesseract.image_to_string(imagen)
        except Exception:
            return ""


def _float_es(m: re.Match[str], group: int = 1) -> float:
    """Montos con miles . y decimal , o al revés."""
    raw = m.group(group).strip().replace(" ", "").replace("'", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        raw = raw.replace(",", ".") if len(parts[-1]) <= 2 else raw.replace(",", "")
    return float(raw)


def _dia_desde_fecha(texto_fecha: str) -> int | None:
    """Extrae día del mes (1–31) de formatos comunes."""
    t = texto_fecha.strip()
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # dd/mm o mm/dd: si a>12 es día; si b>12 es día; si ambos <=12 preferimos a como día (MX)
        if a > 12 and 1 <= b <= 31:
            return b
        if b > 12 and 1 <= a <= 31:
            return a
        if 1 <= a <= 31:
            return a
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
        t,
        re.IGNORECASE,
    )
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    m = re.search(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\b",
        t,
        re.IGNORECASE,
    )
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    m = re.search(r"\bd[ií]a\s*[:\s]*(\d{1,2})\b", t, re.IGNORECASE)
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    return None


def extraer_datos_captura(texto: str) -> DatosCaptura:
    r = DatosCaptura(texto_crudo=texto or "")
    if not (texto or "").strip():
        return r

    # --- Fechas de ciclo (día del mes) ---
    for pat in (
        r"(?:fecha\s+de\s+)?corte\s*(?:del\s+periodo)?\s*[:\s]+([^\n|;]+)",
        r"(?:cut[\s-]?off|closing|statement)\s+date\s*[:\s]+([^\n|;]+)",
        r"payment\s+due\s+date",  # skip, handled below
    ):
        if "payment" in pat:
            continue
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            d = _dia_desde_fecha(m.group(1))
            if d:
                r.dia_corte = d
                break
    if r.dia_corte is None:
        m = re.search(r"\bcorte\b[^\d]{0,20}(\d{1,2})\b", texto, re.IGNORECASE)
        if m:
            d = int(m.group(1))
            if 1 <= d <= 31:
                r.dia_corte = d

    for pat in (
        r"(?:fecha\s+)?(?:l[ií]mite\s+de\s+)?pago\s*[:\s]+([^\n|;]+)",
        r"(?:payment\s+due|due\s+date)\s*[:\s]+([^\n|;]+)",
        r"paga\s+antes\s+del?\s*[:\s]*([^\n|;]+)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            d = _dia_desde_fecha(m.group(1))
            if d:
                r.dia_pago = d
                break
    if r.dia_pago is None:
        m = re.search(r"\bpago\b[^\d]{0,20}(\d{1,2})\b", texto, re.IGNORECASE)
        if m and r.dia_corte != int(m.group(1)):
            d = int(m.group(1))
            if 1 <= d <= 31:
                r.dia_pago = d

    # --- Montos ---
    monto = r"([\d]{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)"

    for pat in (
        rf"(?:l[ií]mite\s+de\s+cr[eé]dito|credit\s+limit|l[ií]mite\s+total)\s*[:\s]*\$?\s*{monto}",
        rf"(?:l[ií]mite)\s*[:\s]*\$?\s*{monto}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.limite = _float_es(m)
                break
            except ValueError:
                pass

    for pat in (
        rf"(?:saldo\s+actual|saldo\s+deudor|new\s+balance|current\s+balance|saldo\s+al\s+corte)\s*[:\s]*\$?\s*{monto}",
        rf"(?:total\s+amount\s+due|monto\s+a\s+pagar|saldo)\s*[:\s]*\$?\s*{monto}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.saldo = _float_es(m)
                break
            except ValueError:
                pass

    for pat in (
        rf"(?:cr[eé]dito\s+disponible|available\s+credit|disponible)\s*[:\s]*\$?\s*{monto}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.disponible = _float_es(m)
                break
            except ValueError:
                pass

    if r.saldo is None and r.limite is not None and r.disponible is not None:
        r.saldo = max(0.0, round(r.limite - r.disponible, 2))
    if r.disponible is None and r.limite is not None and r.saldo is not None:
        r.disponible = max(0.0, round(r.limite - r.saldo, 2))

    # --- Últimos 4 dígitos ---
    for pat in (
        r"(?:\*{2,}|\bX{2,}|\bxxxx\b|\bend(?:ing)?\s+in\b|\bterminad[ao]\s+en\b|\búltimos?\s*4\b|\bultimos?\s*4\b)[^\d]{0,12}(\d{4})\b",
        r"(?:tarjeta|card)\s*(?:n[uú]m(?:ero)?\.?)?\s*[:\s]*(?:\*{4}[\s-]*)+(\d{4})\b",
        r"\b(?:\d{4}[\s-]*){3}(\d{4})\b",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.ultimos_digitos = m.group(1)
            break

    # --- Tasas (reutilizable por Guía) ---
    for pat in (
        r"(?:Purchase\s+)?APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+(?:de\s+)?inter[eé]s\s+(?:ordinari[ao]\s+)?anual[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+anual\s+ordinari[ao][:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"(?:Annual\s+Percentage\s+Rate|APR)\s*(?:for\s+Purchases)?[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.apr = float(m.group(1).replace(",", "."))
            break

    m = re.search(r"Penalty\s+APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
    if m:
        r.penalty_apr = float(m.group(1).replace(",", "."))
    if r.penalty_apr is None:
        m = re.search(r"Tasa\s+moratoria[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
        if m:
            r.penalty_apr = float(m.group(1).replace(",", "."))

    for pat in (
        r"Late\s+(?:Payment\s+)?Fee[:\s]*(?:up\s+to\s+)?\$?([\d]+(?:[.,]\d+)?)",
        r"Comisi[oó]n\s+por\s+pago\s+tard[ií]o[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.late_fee = float(m.group(1).replace(",", "."))
            break

    for pat in (
        r"Annual\s+Fee[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Anualidad[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.annual_fee = float(m.group(1).replace(",", "."))
            break

    m = re.search(r"Daily\s+Periodic\s+Rate[:\s]*([\d]+(?:[.,]\d+)?)\s*%", texto, re.IGNORECASE)
    if m:
        r.daily_rate = float(m.group(1).replace(",", "."))

    for pat in (
        r"Finance\s+Charge[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Interest\s+Charged[:\s]*\$?([\d]+(?:[.,]\d+)?)",
        r"Intereses\s+(?:del\s+periodo|cargo)[:\s]*\$?([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.finance_charge = float(m.group(1).replace(",", "."))
            break

    return r


def procesar_imagen_y_texto(imagen: Image.Image | None, texto_manual: str = "") -> DatosCaptura:
    partes: list[str] = []
    if imagen is not None:
        ocr = texto_desde_imagen(imagen)
        if ocr.strip():
            partes.append(ocr)
    if (texto_manual or "").strip():
        partes.append(texto_manual.strip())
    return extraer_datos_captura("\n".join(partes))
