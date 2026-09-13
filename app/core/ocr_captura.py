"""
OCR de capturas / estados de cuenta para TI (Streamlit).

Usa pytesseract + Tesseract del sistema (Dockerfile en Render; packages.txt en Streamlit Cloud).
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
    statement_balance: float | None = None
    current_balance: float | None = None
    ultimos_digitos: str | None = None
    nombre_tarjeta: str | None = None
    banco: str | None = None
    pago_minimo: float | None = None
    pago_sin_intereses: float | None = None
    monto_vencido_atrasado: float | None = None
    apr: float | None = None
    penalty_apr: float | None = None
    late_fee: float | None = None
    annual_fee: float | None = None
    daily_rate: float | None = None
    finance_charge: float | None = None
    ultimo_pago: float | None = None
    abonos_no_reflejados: float | None = None
    deuda_real_activa: float | None = None
    consumos_ciclo_actual: float | None = None
    ciclo_anterior_saldado: bool = False
    statement_balance_detectado: bool = False

    def tiene_datos_tarjeta(self) -> bool:
        return any(
            v is not None
            for v in (
                self.dia_corte,
                self.dia_pago,
                self.saldo,
                self.limite,
                self.disponible,
                self.statement_balance,
                self.current_balance,
                self.ultimos_digitos,
                self.nombre_tarjeta,
                self.banco,
                self.pago_minimo,
                self.monto_vencido_atrasado,
            )
        )

    def tiene_reglas_banco(self) -> bool:
        return any(
            v is not None
            for v in (
                self.limite,
                self.dia_corte,
                self.dia_pago,
                self.apr,
                self.late_fee,
                self.pago_minimo,
            )
        )

    def tiene_saldos_hoy(self) -> bool:
        return any(
            v is not None
            for v in (
                self.statement_balance,
                self.current_balance,
                self.saldo,
                self.pago_minimo,
                self.monto_vencido_atrasado,
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


def _texto_por_filas(imagen: Image.Image) -> str:
    """
    Reconstruye las filas reales usando las coordenadas de cada palabra.

    En estados de cuenta a dos columnas Tesseract suele devolver la columna de
    etiquetas y la de montos por separado ("Pago Mínimo a Pagar" queda a varias
    líneas de "$25.00"). Agrupando por altura, etiqueta y monto vuelven a quedar
    en la misma línea.
    """
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return ""

    data = None
    for lang in ("spa+eng", None):
        try:
            kwargs = {"config": "--psm 6", "output_type": Output.DICT}
            if lang:
                kwargs["lang"] = lang
            data = pytesseract.image_to_data(imagen, **kwargs)
            break
        except Exception:
            continue
    if not data:
        return ""

    palabras: list[tuple[float, int, str]] = []
    alturas: list[int] = []
    for i in range(len(data.get("text", []))):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        try:
            if float(data["conf"][i]) < 30:
                continue
        except (TypeError, ValueError):
            pass
        try:
            top = int(data["top"][i])
            alto = int(data["height"][i])
            izq = int(data["left"][i])
        except (TypeError, ValueError, KeyError):
            continue
        palabras.append((top + alto / 2.0, izq, txt))
        alturas.append(alto)
    if not palabras:
        return ""

    alturas.sort()
    tolerancia = max(6.0, alturas[len(alturas) // 2] * 0.6)
    palabras.sort(key=lambda p: (p[0], p[1]))

    filas: list[list[tuple[float, int, str]]] = []
    for palabra in palabras:
        if filas and abs(palabra[0] - filas[-1][0][0]) <= tolerancia:
            filas[-1].append(palabra)
        else:
            filas.append([palabra])

    lineas = []
    for fila in filas:
        fila.sort(key=lambda p: p[1])
        lineas.append(" ".join(p[2] for p in fila))
    return "\n".join(lineas)


def texto_desde_imagen(imagen: Image.Image) -> str:
    if not ocr_disponible():
        return ""
    import pytesseract
    from pytesseract import TesseractNotFoundError

    preparada = _preparar_imagen_ocr(imagen)
    # spa+eng primero: statements US en inglés con UI en español (y viceversa).
    intentos: list[tuple[str, str]] = [
        ("spa+eng", "--psm 6"),
        ("eng", "--psm 6"),
        ("spa+eng", "--psm 4"),
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


def texto_por_filas_desde_imagen(imagen: Image.Image) -> str:
    """Lectura alternativa con las columnas reagrupadas en su fila real."""
    if not ocr_disponible():
        return ""
    try:
        return _texto_por_filas(_preparar_imagen_ocr(imagen))
    except Exception:
        return ""


_MESES_ES = (
    r"(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|"
    r"jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
)
_MESES_EN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_MONTO = r"(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2}|\d+)"
# "mínimo" tolerante a acentos perdidos y confusiones típicas del OCR (í→i/1/l/f).
_MINIMO = r"m[íi1lf]n[íi1lf]mo"


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
        # Acepta 0.00 / $0.00 (statement balance saldado); evita días sueltos (1–31).
        tiene_decimal = "." in m.group(1) or "," in m.group(1)
        if val == 0 and ("$" in m.group(0) or tiene_decimal):
            return 0.0
        if val <= 31 and "$" not in m.group(0) and not tiene_decimal:
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

    m = re.search(r"^\s*(\d{1,2})\s*$", t)
    if m:
        d = int(m.group(1))
        return d if 1 <= d <= 31 else None
    return None


def _bloque_tras_etiqueta(texto: str, etiqueta_re: str, hasta: int = 120) -> str | None:
    m = re.search(etiqueta_re + rf"[:\s]*([\s\S]{{0,{hasta}}})", texto, re.IGNORECASE)
    return m.group(1) if m else None


_SOLO_MONTO = re.compile(r"^[=+\-\s]*\$?\s*[\d][\d.,]*$")


def _monto_huerfano_tras_etiqueta(
    texto: str,
    etiqueta_re: str,
    excluir: tuple[float | None, ...] = (),
    maximo_lineas: int = 12,
    tope: float | None = None,
) -> float | None:
    """
    Para tablas que el OCR partió en dos bloques: primero todas las etiquetas y
    después todos los montos. Toma el primer monto suelto plausible.
    """
    valores_excluidos = [v for v in excluir if v is not None]
    for m in re.finditer(etiqueta_re, texto, re.IGNORECASE):
        vistas = 0
        for linea in texto[m.end() :].splitlines():
            limpia = linea.strip()
            if not limpia:
                continue
            vistas += 1
            if vistas > maximo_lineas:
                break
            if not _SOLO_MONTO.match(limpia):
                continue
            val = _primer_monto(limpia)
            if val is None or val <= 0:
                continue
            if tope is not None and val > tope:
                continue
            if any(abs(val - v) < 0.01 for v in valores_excluidos):
                continue
            return val
    return None


def _monto_en_lineas(
    texto: str,
    etiqueta_re: str,
    lineas: int = 3,
    excluir: str | None = None,
) -> float | None:
    """
    Monto en la misma línea de la etiqueta o, si el OCR partió la tabla en
    columnas, en las líneas siguientes.
    """
    for m in re.finditer(etiqueta_re, texto, re.IGNORECASE):
        resto = texto[m.end() :]
        for linea in resto.splitlines()[: lineas + 1]:
            if excluir:
                # Corta la línea antes del texto ruidoso (avisos, "8 Mes(es)", etc.)
                corte = re.search(excluir, linea, re.IGNORECASE)
                if corte:
                    linea = linea[: corte.start()]
            val = _primer_monto(linea)
            if val is not None:
                return val
    return None


def _monto_antes_de_etiqueta(texto: str, etiqueta_re: str) -> float | None:
    """
    Capital One (y similares): el monto aparece ENCIMA de la etiqueta.

    Ej. ``$730.00\\nSaldo actual`` o ``$291.33 Saldo actual``.
    """
    if not texto or not etiqueta_re:
        return None
    # Monto en línea previa (o separado por espacios) + etiqueta
    pat_bloque = rf"\$?\s*{_MONTO}\s*(?:\n|\r\n|\s)+{etiqueta_re}\b"
    # Misma línea: $X.XX … etiqueta
    pat_misma = rf"\$?\s*{_MONTO}\s+{etiqueta_re}\b"
    for pat in (pat_bloque, pat_misma):
        m = re.search(pat, texto, re.IGNORECASE)
        if not m:
            continue
        try:
            val = _float_es(m)
        except ValueError:
            continue
        tiene_decimal = "." in m.group(1) or "," in m.group(1)
        if val == 0 and ("$" in m.group(0) or tiene_decimal):
            return 0.0
        if val <= 31 and "$" not in m.group(0) and not tiene_decimal:
            continue
        if val >= 1900 and val <= 2100:
            continue
        return val
    return None


def _limpiar_texto_ocr(texto: str) -> str:
    """Normaliza errores típicos de OCR en inglés y español (independiente del idioma de la UI)."""
    t = texto.replace("\u00a0", " ")
    for pat, rep in (
        # Inglés
        (r"cred[i1l]t\s+lim[i1l]t", "Credit Limit"),
        (r"new\s+ba[il]ance", "New Balance"),
        (r"available\s+cred[i1l]t", "Available Credit"),
        (r"payment\s+due\s+date", "Payment Due Date"),
        (r"statement\s+closing\s+date", "Statement Closing Date"),
        (r"minimum\s+payment\s+due", "Minimum Payment Due"),
        (r"past\s+due", "Past Due"),
        (r"payment\s+to\s+avoid\s+interest", "Payment to avoid interest"),
        (r"closing\s+date", "Closing Date"),
        # Español
        (r"l[ií]mite\s+de\s+cr[eé]dito", "Límite de crédito"),
        (r"saldo\s+nuevo", "Saldo nuevo"),
        (r"cr[eé]dito\s+disponible", "Crédito disponible"),
        (r"fecha\s+l[ií]mite\s+de\s+pago", "Fecha límite de pago"),
        (r"fecha\s+de\s+vencimiento(?:\s+del\s+pago)?", "Fecha de vencimiento del pago"),
        (r"fecha\s+de\s+corte", "Fecha de corte"),
        (r"monto\s+vencido(?:\s+atrasado)?", "Monto vencido"),
        (r"saldo\s+vencido", "Saldo vencido"),
        (r"pago\s+m[ií]nimo", "Pago mínimo"),
        (r"pago\s+(?:para\s+)?sin\s+intereses", "Pago sin intereses"),
        (r"pago\s+para\s+no\s+generar\s+intereses", "Pago para no generar intereses"),
    ):
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return t


# Orden: más específico primero (Credit One antes que Capital One).
_BANCOS_DETECT: tuple[tuple[str, str], ...] = (
    ("credit one", "Credit One"),
    ("capital one", "Capital One"),
    ("bank of america", "Bank of America"),
    ("wells fargo", "Wells Fargo"),
    ("american express", "American Express"),
    ("scotiabank", "Scotiabank"),
    ("santander", "Santander"),
    ("banorte", "Banorte"),
    ("inbursa", "Inbursa"),
    ("discover", "Discover"),
    ("chase", "Chase"),
    ("bbva", "BBVA"),
    ("citi", "Citi"),
    ("hsbc", "HSBC"),
)

# Productos / marcas de tarjeta (antes que Visa/Mastercard genéricos).
_PRODUCTOS_TARJETA: tuple[tuple[str, str], ...] = (
    (r"\bquicksilver\b", "Quicksilver"),
    (r"\bventure\s*x\b", "Venture X"),
    (r"\bventure\s*one\b", "VentureOne"),
    (r"\bventure\b", "Venture"),
    (r"\bsavor\s*(?:one)?\b", "Savor"),
    (r"\bfreedom\s+unlimited\b", "Freedom Unlimited"),
    (r"\bfreedom\s+flex\b", "Freedom Flex"),
    (r"\bsapphire\s+preferred\b", "Sapphire Preferred"),
    (r"\bsapphire\s+reserve\b", "Sapphire Reserve"),
    (r"\bdouble\s+cash\b", "Double Cash"),
    (r"\bcustom\s+cash\b", "Custom Cash"),
    (r"\bsimplicity\b", "Simplicity"),
    (r"\bwalmart\s+rewards?\b", "Walmart Rewards"),
    (r"\bworld\s+elite\b", "World Elite"),
    (r"\bplatinum\b", "Platinum"),
    (r"\bgold\b", "Gold"),
)

_REDES_TARJETA: tuple[tuple[str, str], ...] = (
    (r"american\s*express|\bamax\b", "American Express"),
    (r"master\s*card|mastercard", "Mastercard"),
    (r"\bvisa\b", "Visa"),
    (r"\bdiscover\b", "Discover"),
)


def detectar_banco(texto: str) -> str | None:
    """Detecta el emisor (Capital One, BBVA, Chase, …) en texto de estado de cuenta."""
    low = (texto or "").lower()
    for needle, banco in _BANCOS_DETECT:
        if needle in low:
            return banco
    return None


def detectar_nombre_tarjeta(texto: str) -> str | None:
    """Producto (Quicksilver, …) o, si no hay, red (Visa / Mastercard / …)."""
    low = (texto or "").lower()
    for pat, nombre in _PRODUCTOS_TARJETA:
        if re.search(pat, low, re.IGNORECASE):
            return nombre
    for pat, nombre in _REDES_TARJETA:
        if re.search(pat, low, re.IGNORECASE):
            return nombre
    return None


def detectar_ultimos_digitos(texto: str) -> str | None:
    """Últimos 4: 'termina en XXXX', '#XXXX', 'ending in', xxxx-6771, etc."""
    if not texto:
        return None
    for pat in (
        r"(?:n[uú]mero\s+de\s+)?cuenta\s+que\s+termina(?:d[ao])?\s+en\s*[:#\s]*(?:\*+|x+|X+|•+|xxxx)?\s*(\d{4})\b",
        r"termina(?:d[ao])?\s+en\s*[:#\s]*(?:\*+|x+|X+|•+|xxxx)?\s*(\d{4})\b",
        r"que\s+termina\s+en\s*[:#\s]*(?:\*+|x+|X+|•+|xxxx)?\s*(\d{4})\b",
        r"(?:account\s+(?:number\s+)?)?(?:that\s+)?(?:ends?|ending)\s+in\s*[:#\s]*(?:\*+|x+|X+|•+|xxxx)?\s*(\d{4})\b",
        r"end(?:ing)?\s+in\s*[:#\s]*(?:\*+|x+|X+|•+|xxxx)?\s*(\d{4})\b",
        r"account\s+number\s*[:\s]*(?:\d{4}[\s-]*){3}(\d{4})\b",
        r"(?:#{1}|x{4}|\*{4}|•{4}|xxxx)[-\s]*(\d{4})\b",
        r"#\s*(\d{4})\b",
        r"\b(?:\d{4}[\s-]*){3}(\d{4})\b",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# Separadores tipicos de encabezado mobile: Quicksilver...6771 / ···· / — /
_SEP_PRODUCTO_DIGITOS = (
    r"(?:\s*(?:\.{2,}|·{2,}|•{2,}|…+|\*{2,}|x{2,}|X{2,}|-{2,}|–+|—+)\s*|\s+)"
)


def detectar_encabezado_producto_digitos(texto: str) -> tuple[str | None, str | None]:
    """Detecta 'Quicksilver...6771', 'Quicksilver ···· 6771', 'Venture X 1234'."""
    if not texto:
        return None, None
    # Capital One pay screen: "Pagar a Quicksilver...6771" / "Pay Quicksilver...6771"
    for pat in (
        r"pagar\s+a\s+(.+?)[\.…\-–—·•*\s]+(\d{4})\b",
        r"pay\s+(?:to\s+)?(.+?)[\.…\-–—·•*\s]+(\d{4})\b",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nombre_raw = re.sub(r"[\.…\-–—·•*]+", " ", m.group(1)).strip()
            if nombre_raw:
                return nombre_raw, m.group(2)
    for pat, nombre in _PRODUCTOS_TARJETA:
        m = re.search(pat + _SEP_PRODUCTO_DIGITOS + r"(\d{4})\b", texto, re.IGNORECASE)
        if m:
            return nombre, m.group(1)
    m = re.search(
        r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})"
        + _SEP_PRODUCTO_DIGITOS
        + r"(\d{4})\b",
        texto,
    )
    if m:
        return m.group(1).strip(), m.group(2)
    return None, None


def aplicar_analisis_deuda(r: DatosCaptura) -> DatosCaptura:
    """Deriva deuda real activa y consumos del ciclo abierto desde saldo / statement."""
    abonos = float(r.abonos_no_reflejados or 0.0)
    saldo = r.current_balance if r.current_balance is not None else r.saldo
    if saldo is not None:
        r.deuda_real_activa = max(0.0, round(float(saldo) - abonos, 2))
    if r.statement_balance_detectado and r.statement_balance is not None and float(r.statement_balance) <= 0.005:
        r.ciclo_anterior_saldado = True
        r.statement_balance = 0.0
        if r.deuda_real_activa is not None:
            r.consumos_ciclo_actual = r.deuda_real_activa
        # pago_sin_intereses stays None / 0 — prior cycle paid
        r.pago_sin_intereses = None
    elif r.statement_balance is not None and r.statement_balance > 0:
        r.ciclo_anterior_saldado = False
        r.pago_sin_intereses = r.statement_balance
    return r


def encontrar_tarjeta_por_captura(datos: DatosCaptura):
    """Match listar_tarjetas() by ultimos_digitos then nombre."""
    from app.core.tarjetas import listar_tarjetas

    digitos = (datos.ultimos_digitos or "").strip()
    if not digitos or len(digitos) != 4:
        return None
    candidatas = [t for t in listar_tarjetas() if (t.ultimos_digitos or "").strip() == digitos]
    if not candidatas:
        return None
    if len(candidatas) == 1:
        return candidatas[0]
    nombre = (datos.nombre_tarjeta or "").strip().lower()
    if not nombre:
        return None
    por_nombre = [
        t
        for t in candidatas
        if (t.nombre or "").strip().lower() == nombre
        or nombre in (t.nombre or "").lower()
        or (t.nombre or "").lower() in nombre
    ]
    if len(por_nombre) == 1:
        return por_nombre[0]
    return None


def extraer_datos_captura(texto: str) -> DatosCaptura:
    bruto = texto or ""
    r = DatosCaptura(texto_crudo=bruto)
    if not bruto.strip():
        return r

    texto = _limpiar_texto_ocr(bruto)

    # Fechas numéricas US (Credit One) y ES
    m = re.search(
        r"(?:payment\s+due\s+date|due\s+date|pay\s+by|payment\s+date|"
        r"fecha\s+l[ií]mite\s+de\s+pago|fecha\s+de\s+vencimiento(?:\s+del\s+pago)?|"
        r"fecha\s+de\s+pago|vence\s+el)\s*[:\s]*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
        texto,
        re.IGNORECASE,
    )
    if m:
        r.dia_pago = _dia_desde_fecha(m.group(1))
    m = re.search(
        r"(?:statement\s+closing\s+date|closing\s+date|billing\s+date|"
        r"fecha\s+de\s+cierre(?:\s+del\s+estado\s+de\s+cuenta)?|fecha\s+de\s+corte|"
        r"fecha\s+de\s+facturaci[oó]n)\s*[:\s]*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
        texto,
        re.IGNORECASE,
    )
    if m:
        r.dia_corte = _dia_desde_fecha(m.group(1))

    if r.dia_pago is None:
        m = re.search(
            r"(?:payment\s+due\s+date|due\s+date|pay\s+by|payment\s+date|"
            r"fecha\s+l[ií]mite\s+de\s+pago|fecha\s+de\s+pago|vence\s+el)\s*[:\s]*(\d{1,2})\b",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = int(m.group(1))
            if 1 <= d <= 31:
                r.dia_pago = d
    if r.dia_corte is None:
        m = re.search(
            r"(?:statement\s+closing\s+date|closing\s+date|billing\s+date|"
            r"fecha\s+de\s+cierre|fecha\s+de\s+corte|fecha\s+de\s+facturaci[oó]n)\s*[:\s]*(\d{1,2})\b",
            texto,
            re.IGNORECASE,
        )
        if m:
            d = int(m.group(1))
            if 1 <= d <= 31:
                r.dia_corte = d

    if r.dia_pago is None:
        for etiq in (
            r"fecha\s+de\s+vencimiento\s+del\s+pago",
            r"vencimiento\s+del\s+pago",
            r"fecha\s+l[ií]mite\s+de\s+pago",
            r"fecha\s+de\s+pago",
            r"vence\s+el",
            r"payment\s+due\s+date",
            r"payment\s+due",
            r"due\s+date",
            r"pay\s+by",
            r"payment\s+date",
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
            rf"(?:vencimiento\s+del\s+pago|fecha\s+de\s+pago|payment\s+due|due\s+date|pay\s+by)[^\n]{{0,40}}"
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
            r"fecha\s+de\s+facturaci[oó]n",
            r"statement\s+closing\s+date",
            r"closing\s+date",
            r"billing\s+date",
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
        rf"credit\s+line\s*[:\s]*\$?\s*{_MONTO}",
        rf"l[ií]mite\s+de\s+cr[eé]dito\s*[:\s]*\$?\s*{_MONTO}",
        rf"l[ií]nea\s+de\s+cr[eé]dito\s*[:\s]*\$?\s*{_MONTO}",
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
        for etiq in (r"credit\s+limit", r"credit\s+line", r"l[ií]mite\s+de\s+cr[eé]dito", r"l[ií]nea\s+de\s+cr[eé]dito"):
            bloque = _bloque_tras_etiqueta(texto, etiq, 80)
            if not bloque or re.search(r"adelanto|cash\s*advance", bloque, re.I):
                continue
            val = _primer_monto(bloque)
            if val is not None and val >= 50:
                r.limite = val
                break

    # Saldo en tiempo real — Current Balance (app del banco / Hacer un pago)
    # Capital One: monto ENCIMA de la etiqueta ("$730.00\\nSaldo actual")
    _ETIQ_CURRENT = (
        r"current\s+balance",
        r"saldo\s+actual",
        r"balance\s+actual",
        r"outstanding\s+balance",
        r"total\s+balance",
    )
    for etiq in _ETIQ_CURRENT:
        val = _monto_antes_de_etiqueta(texto, etiq)
        if val is not None:
            r.current_balance = val
            break
    if r.current_balance is None:
        for pat in (
            rf"current\s+balance\s*[:\s]*\$?\s*{_MONTO}",
            rf"saldo\s+actual\s*[:\s]*\$?\s*{_MONTO}",
            rf"balance\s+actual\s*[:\s]*\$?\s*{_MONTO}",
            rf"outstanding\s+balance\s*[:\s]*\$?\s*{_MONTO}",
            rf"total\s+balance\s*[:\s]*\$?\s*{_MONTO}",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                try:
                    r.current_balance = _float_es(m)
                    break
                except ValueError:
                    continue
    if r.current_balance is None:
        for etiq in (
            r"current\s+balance",
            r"saldo\s+actual",
            r"balance\s+actual",
            r"outstanding\s+balance",
            r"hacer\s+un\s+pago",
            r"make\s+a\s+payment",
        ):
            val = _monto_en_lineas(texto, etiq, lineas=4)
            if val is not None:
                r.current_balance = val
                break
            bloque = _bloque_tras_etiqueta(texto, etiq, 60)
            if not bloque:
                continue
            val = _primer_monto(bloque.splitlines()[0] if bloque.splitlines() else bloque)
            if val is not None:
                r.current_balance = val
                break

    # Saldo al corte — Statement Balance / Last statement / Último balance de declaración
    _ETIQ_STATEMENT = (
        r"last\s+statement\s+balance",
        r"statement\s+balance",
        r"[uú]ltimo\s+balance\s+de\s+(?:la\s+)?declaraci[oó]n",
        r"balance\s+de\s+(?:la\s+)?declaraci[oó]n",
        r"saldo\s+del\s+(?:[uú]ltimo\s+)?estado\s+de\s+cuenta",
        r"new\s+balance",
        r"saldo\s+nuevo",
        r"saldo\s+al\s+corte",
        r"saldo\s+del\s+estado\s+de\s+cuenta",
    )
    for etiq in _ETIQ_STATEMENT:
        val = _monto_antes_de_etiqueta(texto, etiq)
        if val is not None:
            r.statement_balance = val
            r.statement_balance_detectado = True
            break
    if not r.statement_balance_detectado:
        for pat in (
            rf"last\s+statement\s+balance\s*[:\s]*\$?\s*{_MONTO}",
            rf"statement\s+balance\s*[:\s]*\$?\s*{_MONTO}",
            rf"[uú]ltimo\s+balance\s+de\s+(?:la\s+)?declaraci[oó]n\s*[:\s]*\$?\s*{_MONTO}",
            rf"balance\s+de\s+(?:la\s+)?declaraci[oó]n\s*[:\s]*\$?\s*{_MONTO}",
            rf"saldo\s+del\s+(?:[uú]ltimo\s+)?estado\s+de\s+cuenta\s*[:\s]*\$?\s*{_MONTO}",
            rf"new\s+balance\s*[:\s]*\$?\s*{_MONTO}",
            rf"saldo\s+nuevo\s*(?:=\s*)?\$?\s*{_MONTO}",
            rf"saldo\s+al\s+corte\s*[:\s]*\$?\s*{_MONTO}",
            rf"saldo\s+del\s+estado\s+de\s+cuenta\s*[:\s]*\$?\s*{_MONTO}",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                try:
                    r.statement_balance = _float_es(m)
                    r.statement_balance_detectado = True
                    break
                except ValueError:
                    continue
    if not r.statement_balance_detectado:
        for etiq in _ETIQ_STATEMENT:
            val = _monto_en_lineas(texto, etiq, lineas=3)
            if val is not None:
                r.statement_balance = val
                r.statement_balance_detectado = True
                break
            bloque = _bloque_tras_etiqueta(texto, etiq, 40)
            if not bloque:
                continue
            primera = bloque.splitlines()[0] if bloque.splitlines() else bloque
            if re.search(r"credit\s+limit|l[ií]mite", primera, re.I):
                continue
            val = _primer_monto(primera)
            if val is not None:
                r.statement_balance = val
                r.statement_balance_detectado = True
                break

    # Último pago / Last payment / Último pago registrado (Capital One ES)
    _ETIQ_ULTIMO_PAGO = (
        r"[uú]ltimo\s+pago\s+registrado",
        r"ultimo\s+pago\s+registrado",
        r"last\s+registered\s+payment",
        r"last\s+payment(?:\s+amount)?",
        r"[uú]ltimo\s+pago",
        r"ultimo\s+pago",
    )
    for etiq in _ETIQ_ULTIMO_PAGO:
        val = _monto_antes_de_etiqueta(texto, etiq)
        if val is not None:
            r.ultimo_pago = val
            break
    if r.ultimo_pago is None:
        for pat in (
            rf"[uú]ltimo\s+pago\s+registrado\s*[:\s]*\$?\s*{_MONTO}",
            rf"ultimo\s+pago\s+registrado\s*[:\s]*\$?\s*{_MONTO}",
            rf"last\s+registered\s+payment\s*[:\s]*\$?\s*{_MONTO}",
            rf"[uú]ltimo\s+pago\s*[:\s]*\$?\s*{_MONTO}",
            rf"ultimo\s+pago\s*[:\s]*\$?\s*{_MONTO}",
            rf"last\s+payment(?:\s+amount)?\s*[:\s]*\$?\s*{_MONTO}",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                try:
                    r.ultimo_pago = _float_es(m)
                    break
                except ValueError:
                    continue
    if r.ultimo_pago is None:
        for etiq in _ETIQ_ULTIMO_PAGO:
            val = _monto_en_lineas(texto, etiq, lineas=3)
            if val is not None:
                r.ultimo_pago = val
                break

    # Abonos pendientes / no reflejados
    for pat in (
        rf"pending\s+payment(?:\s+amount)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"pago\s+pendiente\s*[:\s]*\$?\s*{_MONTO}",
        rf"(?:abono|pago)\s+(?:no\s+reflejado|en\s+proceso|processing)\s*[:\s]*\$?\s*{_MONTO}",
        rf"payment\s+(?:processing|pending)\s*[:\s]*\$?\s*{_MONTO}",
        rf"unposted\s+payment\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.abonos_no_reflejados = _float_es(m)
                break
            except ValueError:
                continue
    if r.abonos_no_reflejados is None:
        for etiq in (
            r"pending\s+payment",
            r"pago\s+pendiente",
            r"no\s+reflejado",
            r"payment\s+processing",
            r"unposted\s+payment",
        ):
            val = _monto_en_lineas(texto, etiq, lineas=3)
            if val is not None and val > 0:
                r.abonos_no_reflejados = val
                break

    # Compatibilidad: saldo genérico si no hay desglose
    if r.current_balance is None and r.statement_balance is None:
        for pat in (
            rf"saldo\s+total\s*[:\s]*\$?\s*{_MONTO}",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                try:
                    r.saldo = _float_es(m)
                    break
                except ValueError:
                    continue
    if r.saldo is None:
        r.saldo = r.current_balance if r.current_balance is not None else r.statement_balance
    elif r.current_balance is None and r.statement_balance is None:
        r.current_balance = r.saldo

    # Disponible
    for pat in (
        rf"available\s+credit\s*[:\s]*\$?\s*{_MONTO}",
        rf"available\s+(?:for\s+purchases\s+)?(?:credit\s+)?[:\s]*\$?\s*{_MONTO}",
        rf"cr[eé]dito\s+disponible\s*(?:para\s+compras)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"disponible\s+para\s+compras\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                r.disponible = _float_es(m)
                break
            except ValueError:
                continue
    if r.disponible is None:
        for etiq in (
            r"available\s+credit",
            r"available\s+for\s+purchases",
            r"cr[eé]dito\s+disponible",
            r"disponible\s+para\s+compras",
        ):
            bloque = _bloque_tras_etiqueta(texto, etiq, 100)
            if not bloque or re.search(r"adelanto|cash\s*advance", bloque, re.I):
                continue
            val = _primer_monto(bloque)
            if val is not None:
                r.disponible = val
                break

    if r.disponible is None and r.limite is not None:
        uso = r.current_balance if r.current_balance is not None else r.saldo
        if uso is not None:
            r.disponible = max(0.0, round(r.limite - uso, 2))
    if r.disponible is None and r.limite is not None and r.saldo is not None:
        r.disponible = max(0.0, round(r.limite - r.saldo, 2))

    r.banco = detectar_banco(texto)
    r.nombre_tarjeta = detectar_nombre_tarjeta(texto)

    # Pago mínimo: Capital One monto-antes; luego misma línea; luego columnas.
    _ETIQ_PAGO_MIN = (
        rf"pago\s+{_MINIMO}\s+a\s+pagar",
        r"minimum\s+payment\s+(?:due|amount)",
        rf"{_MINIMO}\s+a\s+pagar",
        rf"pago\s+{_MINIMO}",
        r"minimum\s+payment",
        r"min(?:imum)?\s+payment",
        r"importe\s+m[íi]nimo",
        r"amount\s+due",
    )
    for etiq in _ETIQ_PAGO_MIN:
        val = _monto_antes_de_etiqueta(texto, etiq)
        if val is not None and 0 <= val < 5000:
            r.pago_minimo = val
            break
    if r.pago_minimo is None:
        for pat in (
            rf"pago\s+{_MINIMO}\s+a\s+pagar\s*[:\s]*\$?\s*{_MONTO}",
            rf"minimum\s+payment\s+(?:due|amount)\s*[:\s]*\$?\s*{_MONTO}",
            rf"pago\s+{_MINIMO}\s+requerido\s*[:\s]*\$?\s*{_MONTO}",
            rf"minimum\s+payment\s*[:\s]*\$?\s*{_MONTO}",
            rf"min(?:imum)?\s+payment\s+due\s*[:\s]*\$?\s*{_MONTO}",
            rf"importe\s+{_MINIMO}\s*[:\s]*\$?\s*{_MONTO}",
            rf"amount\s+due\s*[:\s]*\$?\s*{_MONTO}",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                try:
                    val = _float_es(m)
                except ValueError:
                    continue
                if 0 < val < 5000:
                    r.pago_minimo = val
                    break
    if r.pago_minimo is None:
        # "Mes(es)" descarta el aviso "Pago Mínimo — 8 Mes(es) — $176".
        ruido = (
            r"mes\(es\)|meses|si\s+usted|cada\s+per[ií]odo|each\s+period|you\s+will\s+pay"
            r"|warning|aviso|atraso|tardar|late\s+fee|no\s+recibimos|if\s+we\s+do\s+not"
        )
        for etiq in _ETIQ_PAGO_MIN:
            val = _monto_en_lineas(texto, etiq, lineas=3, excluir=ruido)
            if val is not None and 0 < val < 5000:
                r.pago_minimo = val
                break
        if r.pago_minimo is None:
            # Columnas partidas: el monto queda suelto varias líneas después.
            for etiq in _ETIQ_PAGO_MIN:
                val = _monto_huerfano_tras_etiqueta(
                    texto,
                    etiq,
                    excluir=(r.saldo, r.limite, r.disponible),
                    tope=r.saldo if r.saldo else None,
                )
                if val is not None and 0 < val < 5000:
                    r.pago_minimo = val
                    break

    r.ultimos_digitos = detectar_ultimos_digitos(texto)

    nombre_hdr, digitos_hdr = detectar_encabezado_producto_digitos(texto)
    if nombre_hdr and not r.nombre_tarjeta:
        r.nombre_tarjeta = nombre_hdr
    if digitos_hdr and not r.ultimos_digitos:
        r.ultimos_digitos = digitos_hdr
    # Productos Capital One en encabezado de "Hacer un pago" sin logo textual.
    if not r.banco and (r.nombre_tarjeta or "").strip().lower() in {
        "quicksilver",
        "venture",
        "venture x",
        "ventureone",
        "savor",
    }:
        r.banco = "Capital One"

    for pat in (
        r"(?:Purchase\s+)?APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Variable\s+APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+(?:de\s+)?inter[eé]s\s+(?:ordinari[ao]\s+)?anual[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+ordinaria[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
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
        for pat in (
            r"Tasa\s+moratoria[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
            r"Tasa\s+de\s+mora[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
            r"Default\s+APR[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        ):
            m = re.search(pat, texto, re.IGNORECASE)
            if m:
                r.penalty_apr = float(m.group(1).replace(",", "."))
                break

    # Cargo por atraso ≠ tasa anual ni tasa moratoria
    for pat in (
        r"late\s+fee\s+up\s+to\s+\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Late\s+(?:Payment\s+)?Fee[:\s]*(?:up\s+to\s+)?\$?\s*([\d]+(?:[.,]\d+)?)",
        r"cargo\s+por\s+atraso(?:\s+en\s+el\s+pago)?(?:[^\d$]{0,40})(?:de\s+)?hasta\s+\$?\s*([\d]+(?:[.,]\d+)?)",
        r"cargo\s+por\s+atraso(?:\s+en\s+el\s+pago)?\s*[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Comisi[oó]n\s+por\s+pago\s+tard[ií]o[:\s]*(?:de\s+hasta\s+)?\$?\s*([\d]+(?:[.,]\d+)?)",
        r"hasta\s+\$?\s*([\d]+(?:[.,]\d+)?)\s*(?:por\s+)?(?:atraso|pago\s+tard[ií]o|late\s+fee)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.late_fee = float(m.group(1).replace(",", "."))
            break

    for pat in (
        r"Annual\s+Fee[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Anualidad[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Membership\s+Fee[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Cuota\s+anual[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.annual_fee = float(m.group(1).replace(",", "."))
            break

    for pat in (
        r"Finance\s+Charge[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Interest\s+Charged[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Intereses\s+(?:del\s+periodo|del\s+ciclo|facturados)[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
        r"Cargos?\s+por\s+inter[eé]s[:\s]*\$?\s*([\d]+(?:[.,]\d+)?)",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.finance_charge = float(m.group(1).replace(",", "."))
            break

    for pat in (
        r"Daily\s+Periodic\s+Rate[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Tasa\s+diaria[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
        r"Daily\s+Rate[:\s]*([\d]+(?:[.,]\d+)?)\s*%",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            r.daily_rate = float(m.group(1).replace(",", "."))
            break

    # Past Due / monto vencido (antes de inferir pago del ciclo)
    for pat in (
        rf"past\s+due\s+(?:amount|balance|payment)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"amount\s+past\s+due\s*[:\s]*\$?\s*{_MONTO}",
        rf"overdue\s+(?:amount|balance|payment)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"monto\s+vencido\s*(?:atrasado)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"importe\s+vencido\s*[:\s]*\$?\s*{_MONTO}",
        rf"saldo\s+vencido\s*[:\s]*\$?\s*{_MONTO}",
        rf"saldo\s+en\s+mora\s*[:\s]*\$?\s*{_MONTO}",
        rf"monto\s+atrasado\s*[:\s]*\$?\s*{_MONTO}",
        rf"deuda\s+vencida\s*[:\s]*\$?\s*{_MONTO}",
        rf"pago\s+vencido\s*[:\s]*\$?\s*{_MONTO}",
        rf"past\s+due\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                val = _float_es(m)
            except ValueError:
                continue
            if val > 0:
                r.monto_vencido_atrasado = val
                break
    if r.monto_vencido_atrasado is None:
        etiquetas_past_due = (
            r"past\s+due",
            r"amount\s+past\s+due",
            r"monto\s+vencido",
            r"importe\s+vencido",
            r"saldo\s+vencido",
            r"saldo\s+en\s+mora",
            r"monto\s+atrasado",
            r"overdue",
            r"deuda\s+vencida",
        )
        for etiq in etiquetas_past_due:
            val = _monto_en_lineas(texto, etiq, lineas=2)
            if val is not None and val > 0:
                if r.saldo is None or abs(val - r.saldo) > 0.01:
                    r.monto_vencido_atrasado = val
                    break
        if r.monto_vencido_atrasado is None:
            for etiq in etiquetas_past_due:
                val = _monto_huerfano_tras_etiqueta(
                    texto,
                    etiq,
                    excluir=(r.saldo, r.limite, r.disponible, r.pago_minimo),
                )
                if val is not None and val > 0:
                    if r.saldo is None or abs(val - r.saldo) > 0.01:
                        r.monto_vencido_atrasado = val
                        break

    # Pago para no generar intereses (= saldo nuevo / pay in full)
    for pat in (
        rf"pago\s+(?:para\s+)?(?:no\s+generar\s+intereses|sin\s+intereses)\s*[:\s]*\$?\s*{_MONTO}",
        rf"payment\s+to\s+avoid\s+interest\s*[:\s]*\$?\s*{_MONTO}",
        rf"pay\s+(?:in\s+)?full\s*(?:amount)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"new\s+balance\s+payment\s*[:\s]*\$?\s*{_MONTO}",
        rf"pago\s+del\s+saldo\s+(?:total|nuevo)\s*[:\s]*\$?\s*{_MONTO}",
        rf"pago\s+total\s*[:\s]*\$?\s*{_MONTO}",
        rf"total\s+payment\s+(?:due|amount)?\s*[:\s]*\$?\s*{_MONTO}",
        rf"statement\s+balance\s*[:\s]*\$?\s*{_MONTO}",
        rf"amount\s+to\s+pay\s*[:\s]*\$?\s*{_MONTO}",
    ):
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            try:
                val = _float_es(m)
            except ValueError:
                continue
            if val > 0:
                r.pago_sin_intereses = val
                break
    if r.pago_sin_intereses is None:
        etiquetas_pago_ciclo = (
            r"payment\s+to\s+avoid\s+interest",
            r"pay\s+in\s+full",
            r"pago\s+sin\s+intereses",
            r"pago\s+para\s+no\s+generar\s+intereses",
            r"pago\s+total",
            r"total\s+payment",
            r"amount\s+to\s+pay",
        )
        for etiq in etiquetas_pago_ciclo:
            val = _monto_en_lineas(texto, etiq, lineas=3)
            if val is not None and val > 0:
                r.pago_sin_intereses = val
                break
        if r.pago_sin_intereses is None:
            for etiq in etiquetas_pago_ciclo:
                val = _monto_huerfano_tras_etiqueta(
                    texto,
                    etiq,
                    excluir=(r.monto_vencido_atrasado, r.pago_minimo),
                )
                if val is not None and val > 0:
                    r.pago_sin_intereses = val
                    break
    if r.pago_sin_intereses is None and r.statement_balance is not None and r.statement_balance > 0:
        r.pago_sin_intereses = r.statement_balance
    if r.pago_sin_intereses is None and r.saldo is not None and r.saldo > 0:
        # En la mayoría de bancos, pagar el saldo nuevo evita recargos del ciclo.
        # Si el ciclo anterior está saldado, aplicar_analisis_deuda lo anula.
        if not (r.statement_balance_detectado and r.statement_balance is not None and float(r.statement_balance) <= 0.005):
            r.pago_sin_intereses = r.saldo

    return aplicar_analisis_deuda(r)


def procesar_ocr_reglas(imagen: Image.Image | None, texto_manual: str = "") -> DatosCaptura:
    """Paso 1: reglas del banco (límite, fechas, tasas, comisiones)."""
    return procesar_imagen_y_texto(imagen, texto_manual)


def procesar_ocr_saldos(imagen: Image.Image | None, texto_manual: str = "") -> DatosCaptura:
    """Paso 2: saldos en tiempo real (app del banco)."""
    return procesar_imagen_y_texto(imagen, texto_manual)


def pdf_disponible() -> bool:
    try:
        import pypdf  # noqa: F401

        return True
    except ImportError:
        return False


def texto_desde_pdf(data: bytes) -> str:
    """Extrae texto de todas las páginas de un PDF (capa de texto)."""
    from io import BytesIO

    if not data:
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(BytesIO(data))
    except Exception:
        return ""

    partes: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            texto = page.extract_text() or ""
        except Exception:
            texto = ""
        if texto.strip():
            partes.append(f"--- page {i} ---\n{texto.strip()}")
    return "\n\n".join(partes)


def _completar_vacios(destino: DatosCaptura, extra: DatosCaptura) -> DatosCaptura:
    """Rellena solo los campos que la lectura principal no logró interpretar."""
    for campo in fields(DatosCaptura):
        if campo.name == "texto_crudo":
            continue
        if campo.name in ("statement_balance_detectado", "ciclo_anterior_saldado"):
            if getattr(extra, campo.name):
                setattr(destino, campo.name, True)
            continue
        if getattr(destino, campo.name) is None:
            valor = getattr(extra, campo.name)
            if valor is not None:
                setattr(destino, campo.name, valor)
    return destino


def procesar_fuentes_captura(
    *,
    imagenes: list[Image.Image] | None = None,
    pdfs_bytes: list[bytes] | None = None,
    texto_manual: str = "",
    nombres_archivo: list[str] | None = None,
) -> DatosCaptura:
    """
    Unifica varias fuentes (PDF multi-página + N imágenes + texto pegado)
    en un solo DatosCaptura antes del Paso 2.
    """
    imagenes = list(imagenes or [])
    pdfs_bytes = list(pdfs_bytes or [])
    nombres = [n.strip() for n in (nombres_archivo or []) if n and str(n).strip()]
    partes: list[str] = []
    extras: list[DatosCaptura] = []

    for raw in pdfs_bytes:
        texto_pdf = texto_desde_pdf(raw)
        if texto_pdf.strip():
            partes.append(texto_pdf.strip())
            extras.append(extraer_datos_captura(texto_pdf))

    for imagen in imagenes:
        ocr = texto_desde_imagen(imagen)
        if ocr.strip():
            partes.append(ocr.strip())
        filas = texto_por_filas_desde_imagen(imagen)
        if filas.strip():
            extras.append(extraer_datos_captura(filas))

    manual = (texto_manual or "").strip()
    if manual:
        partes.append(manual)

    if nombres:
        partes.append("\n".join(nombres))

    resultado = extraer_datos_captura("\n\n".join(partes))
    for extra in extras:
        resultado = _completar_vacios(resultado, extra)

    if nombres and (
        resultado.banco is None
        or resultado.nombre_tarjeta is None
        or resultado.ultimos_digitos is None
    ):
        nombres_join = "\n".join(nombres)
        if resultado.banco is None:
            resultado.banco = detectar_banco(nombres_join)
        if resultado.nombre_tarjeta is None:
            resultado.nombre_tarjeta = detectar_nombre_tarjeta(nombres_join)
        if resultado.ultimos_digitos is None:
            resultado.ultimos_digitos = detectar_ultimos_digitos(nombres_join)

    return aplicar_analisis_deuda(resultado)


def procesar_imagen_y_texto(imagen: Image.Image | None, texto_manual: str = "") -> DatosCaptura:
    return procesar_fuentes_captura(
        imagenes=[imagen] if imagen is not None else [],
        texto_manual=texto_manual,
    )
