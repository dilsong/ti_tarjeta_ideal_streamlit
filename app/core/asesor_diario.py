"""Mensaje diario del asesor — lenguaje humano, sin tecnicismos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.consumos import listar_consumos_por_tarjeta
from app.core.fechas import formatear_fecha, hoy
from app.core.pagos import listar_pagos_por_tarjeta
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import estado_riesgo_pago, validar_ciclo
from app.i18n.translator import get_language, t
from notificaciones.notificador_ciclos import evaluar_notificaciones_tarjeta


@dataclass
class BriefAsesor:
    saludo: str
    mensaje: str
    tono: str  # tranquilo | atencion | urgente
    datos_desactualizados: bool = False


def _ultima_actividad(tarjeta_id: str) -> date | None:
    fechas: list[date] = []
    for c in listar_consumos_por_tarjeta(tarjeta_id):
        fechas.append(date.fromisoformat(c.fecha))
    for p in listar_pagos_por_tarjeta(tarjeta_id):
        fechas.append(date.fromisoformat(p.fecha))
    return max(fechas) if fechas else None


def generar_brief_tarjeta(tarjeta: Tarjeta, referencia: date | None = None) -> BriefAsesor:
    """Un mensaje claro para la tarjeta seleccionada en el abanico."""
    ref = referencia or hoy()
    idioma = get_language()
    estado = validar_ciclo(tarjeta, ref)
    riesgo = estado_riesgo_pago(tarjeta, ref)
    deuda = estado.monto_adeudado_ciclo_anterior
    consumos = estado.consumos_ciclo_actual
    disp = estado.disponibilidad
    pago_txt = (
        formatear_fecha(estado.fecha_pago_proximo, idioma)
        if estado.fecha_pago_proximo
        else "—"
    )

    ultima = _ultima_actividad(tarjeta.id)
    dias_sin_mov = (ref - ultima).days if ultima else 999
    datos_viejos = dias_sin_mov > 14

    saludo = t("asesor_diario.saludo", nombre=tarjeta.nombre)

    if deuda > 0 and riesgo.value == "negativo":
        mensaje = t(
            "asesor_diario.pago_urgente",
            monto=f"${deuda:,.2f}",
            dias=estado.dias_hasta_pago,
            pago=pago_txt,
        )
        tono = "urgente"
    elif deuda > 0:
        mensaje = t(
            "asesor_diario.pago_pendiente",
            monto=f"${deuda:,.2f}",
            dias=estado.dias_hasta_pago,
            pago=pago_txt,
        )
        tono = "atencion"
    elif consumos > 0:
        corte_txt = (
            formatear_fecha(estado.fecha_corte_proximo, idioma)
            if estado.fecha_corte_proximo
            else "—"
        )
        mensaje = t(
            "asesor_diario.ciclo_abierto",
            monto=f"${consumos:,.2f}",
            corte=corte_txt,
            disp=f"${disp:,.2f}",
        )
        tono = "info"
    else:
        mensaje = t(
            "asesor_diario.tranquilo",
            disp=f"${disp:,.2f}",
        )
        tono = "tranquilo"

    notif = evaluar_notificaciones_tarjeta(tarjeta, ref)
    if notif and deuda <= 0 and consumos <= 0:
        cuerpo = notif.mensaje.split("\n", 1)[-1].strip()
        if "TI Asesor" in cuerpo or cuerpo.startswith("Financiero"):
            partes = notif.mensaje.split("\n", 1)
            cuerpo = partes[1].strip() if len(partes) > 1 else notif.mensaje
        mensaje = f"{mensaje} {cuerpo}"
        if notif.urgente:
            tono = "urgente"
        elif tono == "tranquilo":
            tono = "atencion"

    if datos_viejos:
        mensaje = f"{mensaje} {t('asesor_diario.datos_viejos', dias=dias_sin_mov)}"

    return BriefAsesor(
        saludo=saludo,
        mensaje=mensaje.strip(),
        tono=tono,
        datos_desactualizados=datos_viejos,
    )
