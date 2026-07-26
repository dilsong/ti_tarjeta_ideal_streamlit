"""
Persistencia local de tarjetas de crédito en data/tarjetas.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_TARJETAS_FILE = _DATA_DIR / "tarjetas.json"


class EstiloTarjeta(str, Enum):
    REALISTA = "realista"
    SOLIDO = "solido"
    PREMIUM = "premium"


class EstadoSalud(str, Enum):
    POSITIVO = "positivo"
    MEDIO = "medio"
    NEGATIVO = "negativo"


@dataclass
class Tarjeta:
    id: str
    banco: str
    nombre: str
    limite: float
    adeudado: float
    ultimos_digitos: str
    color: str
    estilo: str
    dia_corte: int
    dia_pago: int
    adeudado_ciclo: float = 0.0
    fecha_corte_aplicada: str | None = None
    umbral_uso_pct: float | None = None
    umbral_disponible_min: float | None = None
    tasa_interes_anual: float = 45.0
    tasa_interes_mora: float | None = None
    tasa_es_estimada: bool = True
    pago_minimo_pct: float = 5.0
    pago_minimo_piso: float = 200.0
    pago_minimo_manual: float | None = None
    url_app_banco: str | None = None
    preferencia_banco: str = "app"

    @property
    def interes_diario_referencia(self) -> float:
        """Interés diario sobre la deuda del ciclo (calculado, no persistido)."""
        from app.core.intereses import calcular_interes_diario

        return calcular_interes_diario(self.adeudado_ciclo, self.tasa_interes_anual)

    @property
    def monto_adeudado_actual(self) -> float:
        return self.adeudado

    @property
    def monto_adeudado_ciclo(self) -> float:
        return self.adeudado_ciclo

    @staticmethod
    def nueva(
        banco: str,
        nombre: str,
        limite: float,
        adeudado: float,
        ultimos_digitos: str,
        color: str,
        estilo: str,
        dia_corte: int,
        dia_pago: int,
    ) -> Tarjeta:
        return Tarjeta(
            id=str(uuid4()),
            banco=banco,
            nombre=nombre,
            limite=limite,
            adeudado=adeudado,
            adeudado_ciclo=adeudado if adeudado > 0 else 0.0,
            ultimos_digitos=ultimos_digitos,
            color=color,
            estilo=estilo,
            dia_corte=dia_corte,
            dia_pago=dia_pago,
        )

    @property
    def disponible(self) -> float:
        return max(0.0, self.limite - self.adeudado)

    @property
    def uso_porcentaje(self) -> float:
        if self.limite <= 0:
            return 100.0
        return (self.adeudado / self.limite) * 100

    def estado_salud(self) -> EstadoSalud:
        pct = self.uso_porcentaje
        if pct < 50:
            return EstadoSalud.POSITIVO
        if pct < 80:
            return EstadoSalud.MEDIO
        return EstadoSalud.NEGATIVO

    def excluida_de_recomendacion(self, monto: float = 0.0) -> bool:
        """True si la tarjeta no debe entrar en la simulación de compra."""
        if self.umbral_uso_pct is not None and self.uso_porcentaje >= self.umbral_uso_pct:
            return True
        if self.umbral_disponible_min is not None and self.disponible < self.umbral_disponible_min:
            return True
        if monto > 0 and self.disponible < monto:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Tarjeta:
        adeudado = float(data.get("adeudado", 0))
        if "adeudado_ciclo" not in data:
            data = {**data, "adeudado_ciclo": adeudado}
        if "fecha_corte_aplicada" not in data:
            data = {**data, "fecha_corte_aplicada": None}
        if "umbral_uso_pct" not in data:
            data = {**data, "umbral_uso_pct": None}
        if "umbral_disponible_min" not in data:
            data = {**data, "umbral_disponible_min": None}
        if "tasa_interes_anual" not in data:
            data = {**data, "tasa_interes_anual": 45.0, "tasa_es_estimada": True}
        if "tasa_interes_mora" not in data:
            data = {**data, "tasa_interes_mora": None}
        if "tasa_es_estimada" not in data:
            data = {**data, "tasa_es_estimada": False}
        if "pago_minimo_pct" not in data:
            data = {**data, "pago_minimo_pct": 5.0}
        if "pago_minimo_piso" not in data:
            data = {**data, "pago_minimo_piso": 200.0}
        if "pago_minimo_manual" not in data:
            data = {**data, "pago_minimo_manual": None}
        if "url_app_banco" not in data:
            data = {**data, "url_app_banco": None}
        if "preferencia_banco" not in data:
            data = {**data, "preferencia_banco": "app"}
        pref = str(data.get("preferencia_banco", "app")).strip().lower()
        data = {**data, "preferencia_banco": "web" if pref == "web" else "app"}
        return Tarjeta(**{k: data[k] for k in Tarjeta.__dataclass_fields__ if k in data})


def _read_tarjetas_raw() -> list[dict[str, Any]]:
    if not _TARJETAS_FILE.exists():
        return []
    with _TARJETAS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _write_tarjetas_raw(data: list[dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _TARJETAS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def listar_tarjetas() -> list[Tarjeta]:
    from app.core.ciclo import sincronizar_ciclo
    from app.core.vista_uso import sincronizar_saldo_desde_ciclos

    resultado: list[Tarjeta] = []
    for item in _read_tarjetas_raw():
        original = Tarjeta.from_dict(item)
        sincronizada = sincronizar_ciclo(original)
        sincronizada = sincronizar_saldo_desde_ciclos(sincronizada)
        if (
            sincronizada.adeudado_ciclo != original.adeudado_ciclo
            or sincronizada.fecha_corte_aplicada != original.fecha_corte_aplicada
            or sincronizada.adeudado != original.adeudado
        ):
            guardar_tarjeta(sincronizada)
        resultado.append(sincronizada)
    return resultado


def guardar_tarjeta(tarjeta: Tarjeta) -> None:
    raw = _read_tarjetas_raw()
    raw = [item for item in raw if item.get("id") != tarjeta.id]
    raw.append(tarjeta.to_dict())
    _write_tarjetas_raw(raw)


def obtener_tarjeta(id_tarjeta: str) -> Tarjeta | None:
    for tarjeta in listar_tarjetas():
        if tarjeta.id == id_tarjeta:
            return tarjeta
    return None
