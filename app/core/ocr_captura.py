"""
OCR de capturas / estados de cuenta para TI (Streamlit).

Usa pytesseract + Tesseract del sistema (packages.txt en Cloud).
La foto es la vía preferida; pegar texto es respaldo si OCR no está o falla.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageOps


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
    nombre_tarjeta: str | None = None
    pago_minimo: float | None = None
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
                self.nombre_tarjeta,
                self.pago_minimo,
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


def _configurar_tesseract() -> None:
    """En Windows a veces no está en PATH; apunta a la instalación típica."""
    try:
        import pytesseract
    except ImportError:
        return
    if shutil.which("tesseract"):
        return
    for candidato in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ):
        if candidato.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidato)
            return


def ocr_disponible() -> bool:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return False
    _configurar_tesseract()
    try:
        pytesseract.get_tesseract_version()
        return True
    except (TesseractNotFoundError, OSError):
        return False


def _preparar_imagen_ocr(imagen: Image.Image) -> Image.Image:
    """Mejora contraste/tamaño para leer mejor estados de cuenta."""
    img = imagen.convert("RGB")
    # Escalar si es chica (capturas de móvil a veces salen borrosas al OCR)
    w, h = img.size
    if max(w, h) < 1600:
        scale = 1600 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.4)
    gray = ImageEnhance.Sharpness(gray).enhance(1.2)
    return gray


def texto_desde_imagen(imagen: Image.Image) -> str:
    if not ocr_disponible():
        return ""
    import pytesseract
    from pytesseract import TesseractNotFoundError

    preparada = _preparar_imagen_ocr(imagen)
    try:
        return pytesseract.image_to_string(preparada, lang="spa+eng")
    except (TesseractNotFoundError, OSError):
        try:
            return pytesseract.image_to_string(preparada)
        except (TesseractNotFoundError, OSError):
            return ""
    except Exception:
        try:
            return pytesseract.image_to_string(preparada)
        except Exception:
            return ""


_MESES_ES = (
    r"(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|"
    r"jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
)
_MESES_EN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_MONTO = r"([\d]{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)"


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


def _primer_monto(bloque: str) -> float | None:
    """Prefiere montos con $ (evita tomar el día '15' de una fecha)."""
    for pat in (
        rf"\$\s*{_MONTO}",
        rf"{_MONTO}(?=\s*(?:USD|MXN)?\b)",
    ):
        m = re.search(pat, bloque, re.IGNORECASE)
        if not m:
            continue
        try:
            val = _float_es(m)
        except ValueError:
            continue
        # Ignora números que parecen días/años sueltos
        if val <= 31 and "$" not in m.group(0) and "." not in m.group(1) and "," not in m.group(1):
            continue
        if val >= 1900 and val <= 2100:
            continue
        return val
    return None


def _dia_desde_fecha(texto_fecha: str) -> int | None:
    """Extrae día del mes (1–31) de formatos comunes ES/EN."""
    t = (texto_fecha or "").strip()
    if not t:
        return None

    # agosto 15, 2026 | ago 09, 2026 | Aug 9, 2026
    m = re.search(
        rf"\b(?:{_MESES_ES}|{_MESES_EN})\.?\s+(\d{{1,2}})(?:[,\s]+\d{{2,4}})?\b",
        t,
        re.IGNORECASE,
    )
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None

    # 15 de agosto / 15 agosto 2026
    m = re.search(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?(?:{_MESES_ES}|{_MESES_EN})\b",
        t,
        re.IGNORECASE,
    )
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and 1 <= b <= 31:
            return b
        if b > 12 and 1 <= a <= 31:
            return a
        if 1 <= a <= 31:
            return a

    m = re.search(r"\bd[ií]a\s*[:\s]*(\d{1,2})\b", t, re.IGNORECASE)
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    return None


def _bloque_tras_etiqueta(texto: str, etiqueta_re: str, hasta: int = 120) -> str | None:
    """Texto inmediatamente después de una etiqueta (permite salto de línea)."""
    m = re.search(etiqueta_re + rf"[:\s]*([\s\S]{{0,{hasta}}})", texto, re.IGNORECASE)
    return m.group(1) if m else None


def extraer_datos_captura(texto: str) -> DatosCaptura:
    r = DatosCaptura(texto_crudo=texto or "")
    if not (texto or "").strip():
        return r

    # --- Día de pago (vencimiento) ---
    for etiq in (
        r"fecha\s+de\s+vencimiento\s+del\s+pago",
        r"vencimiento\s+del\s+pago",
        r"fecha\s+l[ií]mite\s+de\s+pago",
        r"payment\s+due\s+date",
        r"payment\s+due",
        r"due\s+date",
        r"paga\s+antes\s+del?",
    ):
        bloque = _bloque_tras_etiqueta(texto, etiq, 80)
        if bloque:
            d = _dia_desde_fecha(bloque)
            if d:
                r.dia_pago = d
                break
    # Patrón directo Capital One: "Vencimiento del Pago: ago 09, 2026"
    if r.dia_pago is None:
        m = re.search(
            rf"(?:vencimiento\s+del\s+pago|payment\s+due)[^\n]{{0,40}}"
            rf"((?:{_MESES_ES}|{_MESES_EN})\.?\s+\d{{1,2}}(?:[,\s]+\d{{2,4}})?)",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = _dia_desde_fecha(m.group(1))
            if d:
                r.dia_pago = d

    # --- Día de corte / cierre de estado ---
    for etiq in (
        r"fecha\s+de\s+cierre\s+del\s+pr[oó]ximo\s+estado\s+de\s+cuenta",
        r"fecha\s+de\s+cierre(?:\s+del\s+estado\s+de\s+cuenta)?",
        r"cierre\s+del\s+pr[oó]ximo\s+estado",
        r"fecha\s+de\s+corte",
        r"(?:cut[\s-]?off|closing|statement)\s+date",
        r"cierre\s+del\s+estado\s+de\s+cuenta",
    ):
        bloque = _bloque_tras_etiqueta(texto, etiq, 80)
        if bloque:
            d = _dia_desde_fecha(bloque)
            if d:
                r.dia_corte = d
                break
    if r.dia_corte is None:
        m = re.search(
            rf"(?:cierre|corte)[^\n]{{0,50}}"
            rf"((?:{_MESES_ES}|{_MESES_EN})\.?\s+\d{{1,2}}(?:[,\s]+\d{{2,4}})?)",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = _dia_desde_fecha(m.group(1))
            if d:
                r.dia_corte = d

    # Ciclo "jun 15, 2026 - jul 15, 2026" → corte = fin del ciclo
    if r.dia_corte is None:
        m = re.search(
            rf"(?:{_MESES_ES}|{_MESES_EN})\.?\s+\d{{1,2}}[,\s]+\d{{2,4}}\s*[-–—a]+\s*"
            rf"((?:{_MESES_ES}|{_MESES_EN})\.?\s+\d{{1,2}}(?:[,\s]+\d{{2,4}})?)",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = _dia_desde_fecha(m.group(1))
            if d:
                r.dia_corte = d

    # --- Límite (antes que saldo, con regex estricto) ---
    m = re.search(
        rf"(?:l[ií]mite\s+de\s+cr[eé]dito|credit\s+limit)(?![^\n]{{0,30}}adelanto)"
        rf"\s*[:\s]*\$?\s*{_MONTO}",
        texto,
        re.IGNORECASE,
    )
    if m:
        try:
            r.limite = _float_es(m)
        except ValueError:
            pass
    if r.limite is None:
        for etiq in (
            r"l[ií]mite\s+de\s+cr[eé]dito",
            r"credit\s+limit",
            r"l[ií]mite\s+total",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 60)
            if bloque:
                if re.search(r"adelanto|cash\s*advance", bloque, re.IGNORECASE):
                    continue
                val = _primer_monto(bloque)
                if val is not None and val >= 100:
                    r.limite = val
                    break

    # --- Saldo nuevo / adeudado (NO confundir con límite) ---
    m = re.search(
        rf"(?:saldo\s+nuevo|new\s+balance)\s*(?:=\s*)?\$?\s*{_MONTO}",
        texto,
        re.IGNORECASE,
    )
    if m:
        try:
            r.saldo = _float_es(m)
        except ValueError:
            pass
    if r.saldo is None:
        for etiq in (
            r"saldo\s+nuevo",
            r"new\s+balance",
            r"saldo\s+actual",
            r"saldo\s+deudor",
            r"current\s+balance",
            r"saldo\s+al\s+corte",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 40)
            if bloque:
                if re.search(r"l[ií]mite|limit", bloque, re.IGNORECASE):
                    # Tomar solo la primera línea del bloque
                    bloque = bloque.splitlines()[0] if bloque.splitlines() else bloque
                val = _primer_monto(bloque)
                if val is not None:
                    r.saldo = val
                    break

    # --- Disponible ---
    m = re.search(
        rf"(?:cr[eé]dito\s+disponible|available\s+credit)(?![^\n]{{0,40}}adelanto)"
        rf"[^\n$]{{0,60}}\$\s*{_MONTO}",
        texto,
        re.IGNORECASE,
    )
    if m:
        try:
            r.disponible = _float_es(m)
        except ValueError:
            pass
    if r.disponible is None:
        for etiq in (
            r"cr[eé]dito\s+disponible",
            r"available\s+credit",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 100)
            if bloque:
                if re.search(r"adelanto|cash\s*advance", bloque, re.IGNORECASE):
                    continue
                val = _primer_monto(bloque)
                if val is not None:
                    r.disponible = val
                    break

    if r.saldo is None and r.limite is not None and r.disponible is not None:
        r.saldo = max(0.0, round(r.limite - r.disponible, 2))
    if r.disponible is None and r.limite is not None and r.saldo is not None:
        r.disponible = max(0.0, round(r.limite - r.saldo, 2))

    # Si adeudado > límite, casi seguro están invertidos
    if r.limite is not None and r.saldo is not None and r.saldo > r.limite:
        r.limite, r.saldo = r.saldo, r.limite
        if r.disponible is not None:
            r.disponible = max(0.0, round(r.limite - r.saldo, 2))

    # --- Nombre / red de la tarjeta ---
    low = texto.lower()
    if re.search(r"american\s*express|\bamax\b", low):
        r.nombre_tarjeta = "American Express"
    elif re.search(r"master\s*card|mastercard", low):
        r.nombre_tarjeta = "Mastercard"
    elif re.search(r"\bvisa\b", low):
        r.nombre_tarjeta = "Visa"
    elif re.search(r"\bdiscover\b", low):
        r.nombre_tarjeta = "Discover"
    else:
        m = re.search(
            r"\b(Platinum|Gold|Quicksilver|Signature|World\s+Elite|Infinite)\b",
            texto,
            re.IGNORECASE,
        )
        if m:
            r.nombre_tarjeta = re.sub(r"\s+", " ", m.group(1)).title()

    # --- Pago mínimo ---
    for etiq in (
        r"pago\s+m[ií]nimo\s+a\s+pagar",
        r"minimum\s+payment\s+due",
        r"minimum\s+payment",
        r"pago\s+m[ií]nimo",
    ):
        bloque = _bloque_tras_etiqueta(texto, etiq, 80)
        if bloque:
            # Evitar el párrafo educativo "si solo hace el pago mínimo"
            if re.search(r"si\s+usted|each\s+period|cada\s+per[ií]odo|ejemplo", bloque, re.I):
                # Buscar $ en las primeras líneas del bloque
                primera = "\n".join(bloque.splitlines()[:4])
                val = _primer_monto(primera)
            else:
                val = _primer_monto(bloque)
            if val is not None and 0 < val < 5000:
                r.pago_minimo = val
                break

    # --- Últimos 4 dígitos ---
    for pat in (
        r"termina(?:d[ao])?\s+en\s*(\d{4})\b",
        r"que\s+termina\s+en\s*(\d{4})\b",
        r"cuenta\s+que\s+termina\s+en\s*(\d{4})\b",
        r"(?:\*{2,}|\bX{2,}|\bxxxx\b|\bend(?:ing)?\s+in\b|\búltimos?\s*4\b|\bultimos?\s*4\b)[^\d]{0,12}(\d{4})\b",
        r"(?:tarjeta|card)\s*(?:n[uú]m(?:ero)?\.?)?\s*[:\s]*(?:\*{4}[\s-]*)+(\d{4})\b",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.ultimos_digitos = m.group(1)
            break

    # --- Tasas ---
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
        r"cargo\s+por\s+atraso\s+en\s+el\s+pago\s+de\s+hasta\s+\$?([\d]+(?:[.,]\d+)?)",
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
        r"Intereses\s+(?:del\s+periodo|cargo|cobrados)\s*[:\+]?\s*\$?([\d]+(?:[.,]\d+)?)",
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
