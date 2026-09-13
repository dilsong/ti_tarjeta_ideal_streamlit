"""
Extracción de datos de capturas bancarias vía Gemini Vision (Flash).

Stdlib + Pillow. Si no hay API key o falla la red/parseo, el caller cae a OCR/texto.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any

from PIL import Image

from app.core.ocr_captura import DatosCaptura, aplicar_analisis_deuda

_MAX_LADO = 1600
_JPEG_QUALITY = 85
_TIMEOUT_S = 45
_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

_PROMPT = """\
Analyze this bank credit-card screenshot / statement photo (often Capital One
Spanish UI: "Hacer un pago", "Saldo actual", "Último balance de declaración").

IMPORTANT layout: on Capital One "Hacer un pago", the dollar AMOUNT appears ABOVE
its label (e.g. "$730.00" then "Saldo actual"). Do not swap amount and label.

Extract a single JSON object with these keys (use null if not visible):
- banco (string, e.g. "Capital One")
- nombre_tarjeta (string, e.g. "Quicksilver")
- ultimos_digitos (string, exactly 4 digits)
- current_balance (number) — Saldo actual / Current balance
- statement_balance (number) — Último balance de declaración / Statement balance;
  include 0.00 when shown as zero
- statement_balance_detectado (boolean) — true if that field was visible (even if 0)
- ultimo_pago (number) — Último pago registrado / Last payment
- pago_minimo (number) — Minimum payment due
- limite (number) — Credit limit
- dia_corte (integer 1-31) — statement/cut-off day
- dia_pago (integer 1-31) — payment due day
- apr (number) — purchase APR percent
- late_fee (number)
- past_due / monto_vencido_atrasado (number) — past due amount if any

Return ONLY valid JSON, no markdown fences.
"""


def vision_api_key() -> str | None:
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    return key or None


def vision_disponible() -> bool:
    return vision_api_key() is not None


def _modelo() -> str:
    return (os.environ.get("GEMINI_VISION_MODEL") or "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _parse_float(val: Any) -> float | None:
    if val is None or val is False:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "n/a", "-"):
        return None
    s = s.replace("$", "").replace("USD", "").replace("MXN", "").strip()
    s = s.replace(" ", "").replace("'", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        s = s.replace(",", ".") if len(parts[-1]) <= 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:[.,]\d+)?", s)
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", "."))
        except ValueError:
            return None


def _parse_int_dia(val: Any) -> int | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, int):
        d = val
    elif isinstance(val, float):
        d = int(val)
    else:
        m = re.search(r"\d{1,2}", str(val))
        if not m:
            return None
        d = int(m.group(0))
    if 1 <= d <= 31:
        return d
    return None


def _parse_digitos(val: Any) -> str | None:
    if val is None:
        return None
    digits = re.sub(r"\D", "", str(val))
    if len(digits) >= 4:
        return digits[-4:]
    return None


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return val != 0
    return str(val).strip().lower() in ("1", "true", "yes", "si", "sí")


def _str_opt(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _datos_desde_vision_json(data: dict[str, Any]) -> DatosCaptura:
    """Mapea el dict JSON de Gemini → DatosCaptura (sin red)."""
    if not isinstance(data, dict):
        data = {}

    current = _parse_float(data.get("current_balance"))
    statement = _parse_float(data.get("statement_balance"))
    # Si el modelo marca detectado o envió el campo (incluso 0), respetarlo.
    sb_detectado = _parse_bool(data.get("statement_balance_detectado"))
    if "statement_balance" in data and data.get("statement_balance") is not None:
        sb_detectado = True
        if statement is None and str(data.get("statement_balance")).strip() in ("0", "0.0", "0.00"):
            statement = 0.0

    past = _parse_float(data.get("monto_vencido_atrasado"))
    if past is None:
        past = _parse_float(data.get("past_due"))

    r = DatosCaptura(
        banco=_str_opt(data.get("banco")),
        nombre_tarjeta=_str_opt(data.get("nombre_tarjeta")),
        ultimos_digitos=_parse_digitos(data.get("ultimos_digitos")),
        current_balance=current,
        saldo=current,
        statement_balance=statement,
        statement_balance_detectado=sb_detectado,
        ultimo_pago=_parse_float(data.get("ultimo_pago")),
        pago_minimo=_parse_float(data.get("pago_minimo")),
        limite=_parse_float(data.get("limite")),
        dia_corte=_parse_int_dia(data.get("dia_corte")),
        dia_pago=_parse_int_dia(data.get("dia_pago")),
        apr=_parse_float(data.get("apr")),
        late_fee=_parse_float(data.get("late_fee")),
        monto_vencido_atrasado=past,
    )

    partes_resumen: list[str] = ["[vision gemini]"]
    if r.banco:
        partes_resumen.append(f"Banco: {r.banco}")
    if r.nombre_tarjeta:
        partes_resumen.append(f"Tarjeta: {r.nombre_tarjeta}")
    if r.ultimos_digitos:
        partes_resumen.append(f"****{r.ultimos_digitos}")
    if r.current_balance is not None:
        partes_resumen.append(f"Saldo actual: ${r.current_balance:.2f}")
    if r.statement_balance_detectado and r.statement_balance is not None:
        partes_resumen.append(f"Último balance de declaración: ${r.statement_balance:.2f}")
    if r.ultimo_pago is not None:
        partes_resumen.append(f"Último pago: ${r.ultimo_pago:.2f}")
    if r.pago_minimo is not None:
        partes_resumen.append(f"Pago mínimo: ${r.pago_minimo:.2f}")
    if r.limite is not None:
        partes_resumen.append(f"Límite: ${r.limite:.2f}")
    if r.dia_corte is not None:
        partes_resumen.append(f"Día de corte: {r.dia_corte}")
    if r.dia_pago is not None:
        partes_resumen.append(f"Día de pago: {r.dia_pago}")
    if r.apr is not None:
        partes_resumen.append(f"APR: {r.apr}")
    if r.late_fee is not None:
        partes_resumen.append(f"Late fee: ${r.late_fee:.2f}")
    if r.monto_vencido_atrasado is not None:
        partes_resumen.append(f"Past due: ${r.monto_vencido_atrasado:.2f}")
    r.texto_crudo = " | ".join(partes_resumen)

    return aplicar_analisis_deuda(r)


def _imagen_a_jpeg_b64(imagen: Image.Image) -> str:
    img = imagen.convert("RGB")
    w, h = img.size
    lado = max(w, h)
    if lado > _MAX_LADO:
        scale = _MAX_LADO / lado
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _strip_json_fences(texto: str) -> str:
    t = (texto or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _extraer_texto_respuesta(payload: dict[str, Any]) -> str | None:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return None
    chunks: list[str] = []
    for part in parts or []:
        if isinstance(part, dict) and "text" in part:
            chunks.append(str(part["text"]))
    joined = "\n".join(chunks).strip()
    return joined or None


def _dump_textual_para_regex(r: DatosCaptura) -> str:
    """Texto plano para que extraer_datos_captura refuerce campos por regex."""
    lineas = [
        r.texto_crudo or "[vision gemini]",
        f"{r.banco or ''} {r.nombre_tarjeta or ''} {r.ultimos_digitos or ''}".strip(),
    ]
    if r.current_balance is not None:
        lineas.append(f"Saldo actual ${r.current_balance:.2f}")
    if r.statement_balance_detectado and r.statement_balance is not None:
        lineas.append(f"Último balance de declaración ${r.statement_balance:.2f}")
    if r.ultimo_pago is not None:
        lineas.append(f"Último pago registrado ${r.ultimo_pago:.2f}")
    if r.pago_minimo is not None:
        lineas.append(f"Pago mínimo ${r.pago_minimo:.2f}")
    if r.limite is not None:
        lineas.append(f"Límite de crédito ${r.limite:.2f}")
    if r.dia_corte is not None:
        lineas.append(f"Fecha de corte día {r.dia_corte}")
    if r.dia_pago is not None:
        lineas.append(f"Fecha de pago día {r.dia_pago}")
    if r.apr is not None:
        lineas.append(f"APR {r.apr}%")
    if r.late_fee is not None:
        lineas.append(f"Late fee ${r.late_fee:.2f}")
    if r.monto_vencido_atrasado is not None:
        lineas.append(f"Past due ${r.monto_vencido_atrasado:.2f}")
    return "\n".join(lineas)


def extraer_datos_desde_imagen_vision(imagen: Image.Image) -> DatosCaptura | None:
    """Llama a Gemini Vision; None si no hay key o falla HTTP/parseo."""
    key = vision_api_key()
    if not key:
        return None

    try:
        b64 = _imagen_a_jpeg_b64(imagen)
    except Exception:
        return None

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _PROMPT},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    url = _ENDPOINT.format(model=_modelo(), key=key)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    texto = _extraer_texto_respuesta(payload)
    if not texto:
        return None

    try:
        data = json.loads(_strip_json_fences(texto))
    except json.JSONDecodeError:
        # A veces viene texto extra alrededor del objeto.
        m = re.search(r"\{[\s\S]*\}", texto)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    return _datos_desde_vision_json(data)
