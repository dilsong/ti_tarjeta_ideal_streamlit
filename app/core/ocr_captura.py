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
    w, h = img.size
    target = 2200
    if max(w, h) < target:
        scale = target / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    gray = ImageEnhance.Sharpness(gray).enhance(1.3)
    return gray


def texto_desde_imagen(imagen: Image.Image) -> str:
    if not ocr_disponible():
        return ""
    import pytesseract
    from pytesseract import TesseractNotFoundError

    preparada = _preparar_imagen_ocr(imagen)
    intentos: list[tuple[str, str]] = [
        ("eng", "--psm 6"),
        ("spa+eng", "--psm 6"),
        ("eng", "--psm 4"),
        ("spa+eng", "--psm 3"),
        ("eng", "--psm 11"),
    ]
    mejor = ""
    for lang, cfg in intentos:
        try:
            txt = pytesseract.image_to_string(preparada, lang=lang, config=cfg)
        except (TesseractNotFoundError, OSError):
            try:
                txt = pytesseract.image_to_string(preparada, config=cfg)
            except Exception:
                continue
        except Exception:
            continue
        if len((txt or "").strip()) > len(mejor.strip()):
            mejor = txt or ""
    return mejor


_MESES_ES = (
    r"(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|"
    r"jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
)
_MESES_EN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_MONTO = r"([\d]{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)"


def _float_es(m: re.Match[str], group: int = 1) -> float:
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
        if val <= 31 and "$" not in m.group(0) and "." not in m.group(1) and "," not in m.group(1):
            continue
        if val >= 1900 and val <= 2100:
            continue
        return val
    return None


def _dia_desde_fecha(texto_fecha: str) -> int | None:
    """Extrae día del mes. Soporta MM/DD (US) y DD/MM (MX/ES)."""
    t = (texto_fecha or "").strip()
    if not t:
        return None

    m = re.search(
        rf"\b(?:{_MESES_ES}|{_MESES_EN})\.?\s+(\d{{1,2}})(?:[,\s]+\d{{2,4}})?\b",
        t,
        re.IGNORECASE,
    )
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None

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
        # 07/24 → día 24 (MM/DD US — Credit One)
        if 1 <= a <= 12 and b > 12 and b <= 31:
            return b
        # 24/07 → día 24 (DD/MM)
        if a > 12 and a <= 31 and 1 <= b <= 12:
            return a
        # Ambiguo: preferir MM/DD (día = segundo número)
        if 1 <= b <= 31:
            return b
        if 1 <= a <= 31:
            return a

    m = re.search(r"\bd[ií]a\s*[:\s]*(\d{1,2})\b", t, re.IGNORECASE)
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    return None


def _bloque_tras_etiqueta(texto: str, etiqueta_re: str, hasta: int = 120) -> str | None:
    m = re.search(etiqueta_re + rf"[:\s]*([\s\S]{{0,{hasta}}})", texto, re.IGNORECASE)
    return m.group(1) if m else None


def _limpiar_texto_ocr(texto: str) -> str:
    t = texto.replace("\u00a0", " ")
    for pat, rep in (
        (r"cred[i1l]t\s+lim[i1l]t", "Credit Limit"),
        (r"new\s+ba[il]ance", "New Balance"),
        (r"available\s+cred[i1l]t", "Available Credit"),
        (r"payment\s+due\s+date", "Payment Due Date"),
        (r"statement\s+closing\s+date", "Statement Closing Date"),
        (r"minimum\s+payment\s+due", "Minimum Payment Due"),
    ):
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return t


def extraer_datos_captura(texto: str) -> DatosCaptura:
    bruto = texto or ""
    r = DatosCaptura(texto_crudo=bruto)
    if not bruto.strip():
        return r

    texto = _limpiar_texto_ocr(bruto)

    # Fechas numéricas US (Credit One)
    m = re.search(
        r"payment\s+due\s+date\s*[:\s]*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
        texto,
        re.IGNORECASE,
    )
    if m:
        r.dia_pago = _dia_desde_fecha(m.group(1))
    m = re.search(
        r"(?:statement\s+closing\s+date|closing\s+date)\s*[:\s]*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
        texto,
        re.IGNORECASE,
    )
    if m:
        r.dia_corte = _dia_desde_fecha(m.group(1))

    if r.dia_pago is None:
        for etiq in (
            r"fecha\s+de\s+vencimiento\s+del\s+pago",
            r"vencimiento\s+del\s+pago",
            r"fecha\s+l[ií]mite\s+de\s+pago",
            r"payment\s+due\s+date",
            r"payment\s+due",
            r"paga\s+antes\s+del?",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 80)
            if bloque:
                d = _dia_desde_fecha(bloque)
                if d:
                    r.dia_pago = d
                    break
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

    if r.dia_corte is None:
        for etiq in (
            r"fecha\s+de\s+cierre\s+del\s+pr[oó]ximo\s+estado\s+de\s+cuenta",
            r"fecha\s+de\s+cierre(?:\s+del\s+estado\s+de\s+cuenta)?",
            r"fecha\s+de\s+corte",
            r"statement\s+closing\s+date",
            r"closing\s+date",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 80)
            if bloque:
                d = _dia_desde_fecha(bloque)
                if d:
                    r.dia_corte = d
                    break
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
    if r.dia_corte is None:
        m = re.search(
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|a|[-–—])\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = _dia_desde_fecha(m.group(2))
            if d:
                r.dia_corte = d

    # Límite — Credit Limit / Límite de Crédito
    for pat in (
        rf"credit\s+limit\s*[:\s]*\$?\s*{_MONTO}",
        rf"l[ií]mite\s+de\s+cr[eé]dito\s*[:\s]*\$?\s*{_MONTO}",
        rf"l[ií]mite\s+total\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                val = _float_es(m)
            except ValueError:
                continue
            if val >= 50:
                r.limite = val
                break
    if r.limite is None:
        for etiq in (r"credit\s+limit", r"l[ií]mite\s+de\s+cr[eé]dito"):
            bloque = _bloque_tras_etiqueta(texto, etiq, 80)
            if not bloque or re.search(r"adelanto|cash\s*advance", bloque, re.I):
                continue
            val = _primer_monto(bloque)
            if val is not None and val >= 50:
                r.limite = val
                break

    # Saldo — New Balance / Saldo Nuevo
    for pat in (
        rf"new\s+balance\s*[:\s]*\$?\s*{_MONTO}",
        rf"saldo\s+nuevo\s*(?:=\s*)?\$?\s*{_MONTO}",
        rf"current\s+balance\s*[:\s]*\$?\s*{_MONTO}",
        rf"saldo\s+actual\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.saldo = _float_es(m)
                break
            except ValueError:
                continue
    if r.saldo is None:
        for etiq in (r"new\s+balance", r"saldo\s+nuevo", r"current\s+balance", r"saldo\s+actual"):
            bloque = _bloque_tras_etiqueta(texto, etiq, 40)
            if not bloque:
                continue
            primera = bloque.splitlines()[0] if bloque.splitlines() else bloque
            if re.search(r"credit\s+limit|l[ií]mite", primera, re.I):
                continue
            val = _primer_monto(primera)
            if val is not None:
                r.saldo = val
                break

    # Disponible
    for pat in (
        rf"available\s+credit\s*[:\s]*\$?\s*{_MONTO}",
        rf"cr[eé]dito\s+disponible\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.disponible = _float_es(m)
                break
            except ValueError:
                continue
    if r.disponible is None:
        for etiq in (r"available\s+credit", r"cr[eé]dito\s+disponible"):
            bloque = _bloque_tras_etiqueta(texto, etiq, 100)
            if not bloque or re.search(r"adelanto|cash\s*advance", bloque, re.I):
                continue
            val = _primer_monto(bloque)
            if val is not None:
                r.disponible = val
                break

    if r.saldo is None and r.limite is not None and r.disponible is not None:
        r.saldo = max(0.0, round(r.limite - r.disponible, 2))
    if r.disponible is None and r.limite is not None and r.saldo is not None:
        r.disponible = max(0.0, round(r.limite - r.saldo, 2))
    if r.limite is not None and r.saldo is not None and r.saldo > r.limite:
        r.limite, r.saldo = r.saldo, r.limite
        r.disponible = max(0.0, round(r.limite - r.saldo, 2))

    low = texto.lower()
    if re.search(r"american\s*express|\bamax\b", low):
        r.nombre_tarjeta = "American Express"
    elif re.search(r"master\s*card|mastercard", low):
        r.nombre_tarjeta = "Mastercard"
    elif re.search(r"\bvisa\b", low):
        r.nombre_tarjeta = "Visa"
    elif re.search(r"\bdiscover\b", low):
        r.nombre_tarjeta = "Discover"

    for etiq in (
        r"minimum\s+payment\s+due",
        r"pago\s+m[ií]nimo\s+a\s+pagar",
        r"minimum\s+payment",
        r"pago\s+m[ií]nimo",
    ):
        bloque = _bloque_tras_etiqueta(texto, etiq, 80)
        if not bloque:
            continue
        if re.search(r"si\s+usted|each\s+period|cada\s+per[ií]odo|ejemplo|you\s+will\s+pay", bloque, re.I):
            bloque = "\n".join(bloque.splitlines()[:3])
        val = _primer_monto(bloque)
        if val is not None and 0 < val < 5000:
            r.pago_minimo = val
            break

    for pat in (
        r"account\s+number\s*[:\s]*(?:\d{4}[\s-]*){3}(\d{4})\b",
        r"\b(?:\d{4}[\s-]*){3}(\d{4})\b",
        r"termina(?:d[ao])?\s+en\s*(\d{4})\b",
        r"que\s+termina\s+en\s*(\d{4})\b",
        r"cuenta\s+que\s+termina\s+en\s*(\d{4})\b",
        r"(?:\*{2,}|\bend(?:ing)?\s+in\b)[^\d]{0,12}(\d{4})\b",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.ultimos_digitos = m.group(1)
            break

    for pat in (
        r"(?:Purchase\s+)?APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+(?:de\s+)?inter[eé]s\s+(?:ordinari[ao]\s+)?anual[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
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

    # Cargo por atraso ≠ tasa anual
    for pat in (
        r"late\s+fee\s+up\s+to\s+\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Late\s+(?:Payment\s+)?Fee[:\s]*(?:up\s+to\s+)?\$?\s*([\d]+(?:[.,]\d+)?)",
        r"cargo\s+por\s+atraso(?:\s+en\s+el\s+pago)?\s+de\s+hasta\s+\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Comisi[oó]n\s+por\s+pago\s+tard[ií]o[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.late_fee = float(m.group(1).replace(",", "."))
            break

    for pat in (
        r"Annual\s+Fee[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Anualidad[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.annual_fee = float(m.group(1).replace(",", "."))
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
