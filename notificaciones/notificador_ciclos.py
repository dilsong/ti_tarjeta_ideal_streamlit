"""
Notificador de ciclos de tarjeta — TI Asesor Financiero.

Detecta hitos del ciclo (corte, mitad, pago, atrasos) según la configuración
del usuario y envía mensajes claros y accionables.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.core.fechas import dias_entre, formatear_fecha, hoy, proxima_fecha_por_dia
from app.core.tarjetas import Tarjeta, listar_tarjetas
from app.core.validacion_ciclo import ultimo_corte, validar_ciclo

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_CONFIG_FILE = _CONFIG_DIR / "notificaciones_usuario.json"
_PREFIJO = "TI Asesor Financiero:"

DEFAULT_CONFIG: dict[str, Any] = {
    "notificar_dia_corte": True,
    "notificar_antes_corte": True,
    "dias_antes_corte": 3,
    "notificar_mitad_ciclo": True,
    "dias_mitad_ciclo": 10,
    "notificar_antes_pago": True,
    "dias_antes_pago": 3,
    "notificar_despues_pago": True,
    "notificar_dias_despues_corte": True,
    "notificar_inicio_ciclo": True,
    "ultima_ejecucion": None,
    "historial_enviados": [],
}

# Mayor número = mayor prioridad si coinciden dos eventos el mismo día.
_PRIORIDAD_TIPO: dict[str, int] = {
    "despues_pago": 90,
    "dia_pago": 80,
    "corte": 70,
    "antes_corte": 60,
    "despues_corte": 50,
    "antes_pago": 40,
    "mitad_ciclo": 30,
    "inicio_ciclo": 20,
}


@dataclass
class NotificacionCiclo:
    tipo: str
    mensaje: str
    tarjeta_id: str = ""
    tarjeta_nombre: str = ""
    urgente: bool = False
    ciclo_ref: str = ""
    fecha_evento: str = ""


def _fmt_monto(monto: float) -> str:
    return f"${monto:,.2f}"


def _mensaje(cuerpo: str, tarjeta_nombre: str = "") -> str:
    encabezado = f"{_PREFIJO} {tarjeta_nombre}" if tarjeta_nombre else _PREFIJO
    return f"{encabezado}\n{cuerpo}"


def cargar_config_notificaciones() -> dict[str, Any]:
    if not _CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    with _CONFIG_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def guardar_config_notificaciones(config: dict[str, Any]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_CONFIG)
    merged.update(config)
    if not isinstance(merged.get("historial_enviados"), list):
        merged["historial_enviados"] = []
    with _CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def _clave_envio(notif: NotificacionCiclo) -> str:
    if notif.tipo == "despues_pago":
        return f"{notif.tarjeta_id}:{notif.tipo}:{notif.fecha_evento}"
    return f"{notif.tarjeta_id}:{notif.tipo}:{notif.ciclo_ref}"


def _ya_enviada(notif: NotificacionCiclo, config: dict[str, Any]) -> bool:
    historial = config.get("historial_enviados") or []
    clave = _clave_envio(notif)
    return any(item.get("clave") == clave for item in historial)


def _marcar_enviada(notif: NotificacionCiclo, config: dict[str, Any], fecha: date) -> None:
    historial = list(config.get("historial_enviados") or [])
    clave = _clave_envio(notif)
    if any(item.get("clave") == clave for item in historial):
        return
    historial.append({"clave": clave, "fecha": fecha.isoformat(), "tipo": notif.tipo})
    config["historial_enviados"] = historial[-200:]


def _notif(
    tipo: str,
    cuerpo: str,
    *,
    tarjeta_id: str,
    tarjeta_nombre: str,
    ciclo_ref: str,
    fecha_evento: date,
    urgente: bool = False,
) -> NotificacionCiclo:
    return NotificacionCiclo(
        tipo=tipo,
        mensaje=_mensaje(cuerpo, tarjeta_nombre),
        tarjeta_id=tarjeta_id,
        tarjeta_nombre=tarjeta_nombre,
        urgente=urgente,
        ciclo_ref=ciclo_ref,
        fecha_evento=fecha_evento.isoformat(),
    )


def _elegir_notificacion_del_dia(notificaciones: list[NotificacionCiclo]) -> NotificacionCiclo | None:
    if not notificaciones:
        return None
    return max(notificaciones, key=lambda n: _PRIORIDAD_TIPO.get(n.tipo, 0))


def enviar_notificacion(usuario_id: str, mensaje: str) -> None:
    """Placeholder para integración futura (email, push, SMS)."""
    _ = usuario_id
    print(f"[NOTIFICACIÓN] {mensaje}")


def procesar_notificaciones(
    fecha_actual: date,
    fecha_corte: date,
    fecha_pago: date,
    monto_ciclo_anterior: float,
    monto_ciclo_actual: float,
    usuario_config: dict[str, Any],
    *,
    fecha_ultimo_corte: date | None = None,
    monto_adeudado_total: float = 0.0,
    tarjeta_id: str = "",
    tarjeta_nombre: str = "",
) -> list[NotificacionCiclo]:
    """
    Evalúa qué notificaciones corresponden hoy según fechas y montos del ciclo.

    fecha_corte: próximo corte del ciclo abierto.
    fecha_pago: fecha de vencimiento del pago asociado al ciclo relevante.
    fecha_ultimo_corte: inicio del ciclo actual (requerido para mitad y post-corte).
    """
    inicio = fecha_ultimo_corte or fecha_corte
    total = monto_adeudado_total if monto_adeudado_total > 0 else (monto_ciclo_anterior + monto_ciclo_actual)
    monto_pendiente = monto_ciclo_anterior if monto_ciclo_anterior > 0 else total
    dias_hasta_corte = dias_entre(fecha_actual, fecha_corte)
    dias_hasta_pago = dias_entre(fecha_actual, fecha_pago)
    dias_desde_corte = dias_entre(inicio, fecha_actual)
    dias_despues_pago = dias_entre(fecha_pago, fecha_actual) if fecha_actual > fecha_pago else 0
    resultado: list[NotificacionCiclo] = []

    dias_antes_corte = int(usuario_config.get("dias_antes_corte", 3))
    if (
        usuario_config.get("notificar_antes_corte", True)
        and fecha_actual < fecha_corte
        and dias_hasta_corte == dias_antes_corte
    ):
        corte_txt = formatear_fecha(fecha_corte)
        pago_txt = formatear_fecha(fecha_pago)
        resultado.append(
            _notif(
                "antes_corte",
                f"Tu corte es en {dias_antes_corte} días ({corte_txt}).\n"
                f"Monto actual del ciclo: {_fmt_monto(total)}.\n"
                f"Después del corte tendrás hasta el {pago_txt} para pagar.\n"
                "Compras posteriores al corte entrarán al siguiente periodo.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_corte.isoformat(),
                fecha_evento=fecha_actual,
                urgente=dias_antes_corte <= 3,
            )
        )

    if usuario_config.get("notificar_dia_corte") and fecha_actual == fecha_corte:
        dias_para_pagar = max(0, dias_entre(fecha_actual, fecha_pago))
        resultado.append(
            _notif(
                "corte",
                f"Tu ciclo se ha cerrado.\n"
                f"Monto a pagar: {_fmt_monto(monto_pendiente)}.\n"
                f"Tienes {dias_para_pagar} días para pagarlo.\n"
                "Para más detalles consulta TI Asesor Financiero.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_corte.isoformat(),
                fecha_evento=fecha_actual,
            )
        )

    if (
        usuario_config.get("notificar_mitad_ciclo")
        and fecha_actual < fecha_corte
        and dias_desde_corte == int(usuario_config.get("dias_mitad_ciclo", 10))
    ):
        resultado.append(
            _notif(
                "mitad_ciclo",
                f"Llevas {dias_desde_corte} días del ciclo.\n"
                f"Tu pago vence en {max(0, dias_hasta_pago)} días.\n"
                f"Monto pendiente: {_fmt_monto(monto_pendiente)}.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_corte.isoformat(),
                fecha_evento=fecha_actual,
            )
        )

    dias_antes = int(usuario_config.get("dias_antes_pago", 3))
    if (
        usuario_config.get("notificar_antes_pago")
        and monto_pendiente > 0
        and dias_hasta_pago == dias_antes
        and fecha_actual < fecha_pago
    ):
        resultado.append(
            _notif(
                "antes_pago",
                f"Tu pago vence en {dias_antes} días.\n"
                f"Monto pendiente: {_fmt_monto(monto_pendiente)}.\n"
                "Evita intereses adicionales.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_pago.isoformat(),
                fecha_evento=fecha_actual,
                urgente=dias_antes <= 3,
            )
        )

    if fecha_actual == fecha_pago and monto_pendiente > 0:
        resultado.append(
            _notif(
                "dia_pago",
                f"Hoy vence tu pago.\n"
                f"Monto pendiente: {_fmt_monto(monto_pendiente)}.\n"
                "Pagar a tiempo te mantiene en verde.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_pago.isoformat(),
                fecha_evento=fecha_actual,
                urgente=True,
            )
        )

    if (
        usuario_config.get("notificar_despues_pago")
        and monto_ciclo_anterior > 0
        and dias_despues_pago > 0
    ):
        resultado.append(
            _notif(
                "despues_pago",
                "Tu ciclo entró en días de interés.\n"
                f"Día {dias_despues_pago} después del pago.\n"
                f"Monto pendiente: {_fmt_monto(monto_ciclo_anterior)}.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_pago.isoformat(),
                fecha_evento=fecha_actual,
                urgente=True,
            )
        )

    if (
        usuario_config.get("notificar_dias_despues_corte")
        and monto_ciclo_anterior > 0
        and dias_desde_corte == 1
        and fecha_actual > inicio
    ):
        resultado.append(
            _notif(
                "despues_corte",
                "Tu ciclo anterior sigue pendiente.\n"
                f"Monto a pagar: {_fmt_monto(monto_ciclo_anterior)}.\n"
                "Consulta TI Asesor Financiero para más detalles.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=inicio.isoformat(),
                fecha_evento=fecha_actual,
                urgente=True,
            )
        )

    if (
        usuario_config.get("notificar_inicio_ciclo", True)
        and fecha_actual == inicio + timedelta(days=1)
        and monto_ciclo_anterior <= 0
    ):
        resultado.append(
            _notif(
                "inicio_ciclo",
                "Tu nuevo ciclo comenzó.\n"
                f"El próximo corte es el {fecha_corte.strftime('%d/%m/%Y')}.\n"
                "Las compras de hoy en adelante suman al periodo actual.",
                tarjeta_id=tarjeta_id,
                tarjeta_nombre=tarjeta_nombre,
                ciclo_ref=fecha_corte.isoformat(),
                fecha_evento=fecha_actual,
            )
        )

    return resultado


def _contexto_tarjeta(tarjeta: Tarjeta, referencia: date) -> tuple[date, date, date, float, float, float]:
    estado = validar_ciclo(tarjeta, referencia)
    ultimo = ultimo_corte(tarjeta, referencia)
    corte_proximo = estado.fecha_corte_proximo or proxima_fecha_por_dia(tarjeta.dia_corte, referencia)

    deuda_ciclo = estado.monto_adeudado_ciclo_anterior
    if deuda_ciclo > 0:
        fecha_pago = proxima_fecha_por_dia(tarjeta.dia_pago, ultimo)
    else:
        fecha_pago = proxima_fecha_por_dia(tarjeta.dia_pago, corte_proximo)

    return (
        ultimo,
        corte_proximo,
        fecha_pago,
        deuda_ciclo,
        estado.consumos_ciclo_actual,
        estado.monto_adeudado_actual,
    )


def evaluar_notificaciones_tarjeta(
    tarjeta: Tarjeta,
    referencia: date | None = None,
) -> NotificacionCiclo | None:
    """Una alerta como máximo por tarjeta y por día (la de mayor prioridad)."""
    ref = referencia or hoy()
    config = cargar_config_notificaciones()
    ultimo, corte_proximo, fecha_pago, deuda_ciclo, consumo_actual, adeudado_total = _contexto_tarjeta(
        tarjeta, ref
    )
    candidatas = procesar_notificaciones(
        fecha_actual=ref,
        fecha_corte=corte_proximo,
        fecha_pago=fecha_pago,
        monto_ciclo_anterior=deuda_ciclo,
        monto_ciclo_actual=consumo_actual,
        usuario_config=config,
        fecha_ultimo_corte=ultimo,
        monto_adeudado_total=adeudado_total,
        tarjeta_id=tarjeta.id,
        tarjeta_nombre=tarjeta.nombre,
    )
    return _elegir_notificacion_del_dia(candidatas)


def evaluar_notificaciones_del_dia(referencia: date | None = None) -> list[NotificacionCiclo]:
    """Evalúa alertas del día para todas las tarjetas (una por tarjeta)."""
    ref = referencia or hoy()
    resultado: list[NotificacionCiclo] = []
    for tarjeta in listar_tarjetas():
        notif = evaluar_notificaciones_tarjeta(tarjeta, ref)
        if notif:
            resultado.append(notif)
    return resultado


def ejecutar_notificaciones_diarias(
    usuario_id: str = "default",
    referencia: date | None = None,
    forzar: bool = False,
) -> None:
    """
    Envía alertas del día a consola/canales futuros.
    Cada evento (tarjeta + tipo + ciclo) se envía una sola vez.
    """
    ref = referencia or hoy()
    config = cargar_config_notificaciones()
    for tarjeta in listar_tarjetas():
        notif = evaluar_notificaciones_tarjeta(tarjeta, ref)
        if not notif:
            continue
        if forzar or not _ya_enviada(notif, config):
            enviar_notificacion(usuario_id, notif.mensaje)
            _marcar_enviada(notif, config, ref)
    config["ultima_ejecucion"] = ref.isoformat()
    guardar_config_notificaciones(config)
