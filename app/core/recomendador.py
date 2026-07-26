"""
Motor de recomendación con lógica real de ciclo de facturación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.ciclo import calcular_disponibilidad
from app.core.fechas import hoy
from app.core.tarjetas import Tarjeta
from app.core.validacion_ciclo import (
    compra_cae_en_proximo_ciclo,
    dias_para_pagar_compra,
    validar_ciclo,
)
from app.i18n.translator import t


@dataclass
class EvaluacionInteres:
    genera_interes: bool
    proximo_ciclo: bool
    dias_pago: int
    dias_corte: int
    monto_ciclo: float


@dataclass
class Recomendacion:
    tarjeta: Tarjeta | None
    mensaje: str
    frase_corta: str = ""
    dias_para_pagar: int = 0
    score: float = 0.0


@dataclass
class EvaluacionEleccion:
    """Pros y contras de usar una tarjeta concreta (elección del usuario)."""

    tarjeta: Tarjeta
    pros: list[str]
    contras: list[str]
    resumen: str
    puede_comprar: bool
    score: float
    dias_para_pagar: int = 0


def evaluar_riesgo_intereses(
    tarjeta: Tarjeta,
    monto: float,
    referencia: date | None = None,
) -> EvaluacionInteres:
    ref = referencia or hoy()
    estado = validar_ciclo(tarjeta, ref)
    proximo_ciclo = compra_cae_en_proximo_ciclo(tarjeta, ref)
    dias_pago = dias_para_pagar_compra(tarjeta, ref)
    dias_corte = estado.dias_hasta_corte
    monto_ciclo = estado.monto_adeudado_ciclo_anterior

    if proximo_ciclo:
        genera_interes = False
    else:
        total_a_pagar = monto_ciclo + monto
        genera_interes = total_a_pagar > tarjeta.limite * 0.95 or estado.dias_hasta_pago <= 3

    return EvaluacionInteres(
        genera_interes=genera_interes,
        proximo_ciclo=proximo_ciclo,
        dias_pago=dias_pago,
        dias_corte=dias_corte,
        monto_ciclo=monto_ciclo,
    )


def calcular_score_tarjeta(
    tarjeta: Tarjeta,
    monto: float,
    referencia: date | None = None,
) -> float:
    ref = referencia or hoy()
    disponible = calcular_disponibilidad(tarjeta, ref)

    if monto <= 0 or disponible < monto:
        return -1.0

    eval_int = evaluar_riesgo_intereses(tarjeta, monto, ref)
    disponible_ratio = disponible / tarjeta.limite if tarjeta.limite else 0
    uso_post = (tarjeta.adeudado + monto) / tarjeta.limite if tarjeta.limite else 1

    score = 0.0
    score += min(eval_int.dias_pago, 45) * 2.5
    score += min(eval_int.dias_corte, 30) * 1.0
    score += disponible_ratio * 35.0
    score += (1.0 - uso_post) * 30.0

    if eval_int.proximo_ciclo:
        score += 15.0
    if not eval_int.genera_interes:
        score += 12.0
    else:
        score -= 20.0

    if uso_post > 0.9:
        score -= 25.0
    elif uso_post > 0.75:
        score -= 10.0

    if eval_int.dias_pago <= 5:
        score -= 15.0

    return score


def generar_mensaje_humano(
    tarjeta: Tarjeta,
    monto: float,
    referencia: date | None = None,
) -> str:
    ref = referencia or hoy()
    eval_int = evaluar_riesgo_intereses(tarjeta, monto, ref)
    estado = validar_ciclo(tarjeta, ref)
    disponible = calcular_disponibilidad(tarjeta, ref)
    ratio = disponible / tarjeta.limite if tarjeta.limite else 0

    partes = [
        t("pantalla_recomendacion.mejor_tarjeta", nombre=tarjeta.nombre),
        t("pantalla_recomendacion.dias_pago", dias=eval_int.dias_pago),
    ]

    if eval_int.proximo_ciclo:
        partes.append(
            t(
                "pantalla_recomendacion.dias_pago_siguiente_ciclo",
                dias=estado.dias_hasta_pago_siguiente_ciclo,
            )
        )

    if ratio >= 0.5:
        partes.append(t("pantalla_recomendacion.disponibilidad_buena"))
    elif ratio >= 0.25:
        partes.append(t("pantalla_recomendacion.disponibilidad_media"))
    else:
        partes.append(t("pantalla_recomendacion.disponibilidad_baja"))

    if eval_int.proximo_ciclo:
        partes.append(t("pantalla_recomendacion.compra_proximo_ciclo"))
        partes.append(t("pantalla_recomendacion.sin_intereses_ciclo_actual"))
        partes.append(t("pantalla_recomendacion.conclusion_comoda"))
    elif not eval_int.genera_interes and eval_int.dias_pago >= 10:
        partes.append(t("pantalla_recomendacion.sin_intereses"))
        partes.append(t("pantalla_recomendacion.conclusion_comoda"))
    elif eval_int.genera_interes or eval_int.dias_pago <= 7:
        partes.append(t("pantalla_recomendacion.con_intereses"))
        partes.append(t("pantalla_recomendacion.conclusion_cuidado"))
    else:
        partes.append(t("pantalla_recomendacion.sin_intereses"))
        partes.append(t("pantalla_recomendacion.conclusion_cuidado"))

    return " ".join(partes)


def generar_frase_compra_corta(
    tarjeta: Tarjeta,
    monto: float,
    referencia: date | None = None,
) -> str:
    """Una sola frase humana para el momento de compra."""
    ref = referencia or hoy()
    if monto <= 0:
        return t("tabs.comprar_monto_invalido")

    disponible = calcular_disponibilidad(tarjeta, ref)
    disp_txt = f"${disponible:,.2f}"
    monto_txt = f"${monto:,.2f}"

    if disponible < monto:
        return t(
            "asesor_compra.sin_disponible",
            nombre=tarjeta.nombre,
            disp=disp_txt,
            monto=monto_txt,
        )

    eval_int = evaluar_riesgo_intereses(tarjeta, monto, ref)
    estado = validar_ciclo(tarjeta, ref)

    if eval_int.proximo_ciclo:
        return t(
            "asesor_compra.proximo_ciclo",
            nombre=tarjeta.nombre,
            dias=estado.dias_hasta_pago_siguiente_ciclo,
            disp=disp_txt,
        )
    if eval_int.dias_pago >= 14:
        return t(
            "asesor_compra.comoda",
            nombre=tarjeta.nombre,
            dias=eval_int.dias_pago,
            disp=disp_txt,
        )
    return t(
        "asesor_compra.cuidado",
        nombre=tarjeta.nombre,
        dias=eval_int.dias_pago,
        disp=disp_txt,
    )


def evaluar_tarjeta_abanico(
    tarjeta: Tarjeta,
    monto: float,
    referencia: date | None = None,
) -> EvaluacionEleccion:
    """Evalúa pros y contras de usar la tarjeta que el usuario tiene al frente."""
    ref = referencia or hoy()
    pros: list[str] = []
    contras: list[str] = []

    if monto <= 0:
        return EvaluacionEleccion(
            tarjeta=tarjeta,
            pros=[],
            contras=[t("tabs.comprar_monto_invalido")],
            resumen=t("tabs.comprar_monto_invalido"),
            puede_comprar=False,
            score=-1.0,
        )

    disponible = calcular_disponibilidad(tarjeta, ref)
    puede_comprar = disponible >= monto
    eval_int = evaluar_riesgo_intereses(tarjeta, monto, ref)
    estado = validar_ciclo(tarjeta, ref)
    ratio = disponible / tarjeta.limite if tarjeta.limite else 0
    uso_post = (tarjeta.adeudado + monto) / tarjeta.limite if tarjeta.limite else 1
    score = calcular_score_tarjeta(tarjeta, monto, ref)
    dias = dias_para_pagar_compra(tarjeta, ref)

    if puede_comprar:
        pros.append(t("tabs.comprar_pro_disponible", monto=disponible))
    else:
        contras.append(t("tabs.comprar_contra_sin_disponible", monto=disponible, compra=monto))

    if eval_int.dias_pago >= 14:
        pros.append(t("tabs.comprar_pro_dias_pago", dias=eval_int.dias_pago))
    elif eval_int.dias_pago >= 7:
        pros.append(t("tabs.comprar_pro_dias_pago_moderado", dias=eval_int.dias_pago))
    elif eval_int.dias_pago > 0:
        contras.append(t("tabs.comprar_contra_dias_pago", dias=eval_int.dias_pago))

    if ratio >= 0.5:
        pros.append(t("pantalla_recomendacion.disponibilidad_buena"))
    elif ratio >= 0.25:
        pros.append(t("pantalla_recomendacion.disponibilidad_media"))
    else:
        contras.append(t("pantalla_recomendacion.disponibilidad_baja"))

    if eval_int.proximo_ciclo:
        pros.append(t("pantalla_recomendacion.compra_proximo_ciclo"))
        pros.append(t("pantalla_recomendacion.sin_intereses_ciclo_actual"))
    elif not eval_int.genera_interes:
        pros.append(t("pantalla_recomendacion.sin_intereses"))
    else:
        contras.append(t("pantalla_recomendacion.con_intereses"))

    if uso_post > 0.9:
        contras.append(t("tabs.comprar_contra_limite_alto", pct=uso_post * 100))
    elif uso_post > 0.75:
        contras.append(t("tabs.comprar_contra_limite_medio", pct=uso_post * 100))

    if tarjeta.excluida_de_recomendacion(monto) and puede_comprar:
        contras.append(t("tabs.comprar_contra_umbral"))

    if tarjeta.umbral_uso_pct is not None and tarjeta.uso_porcentaje >= tarjeta.umbral_uso_pct:
        contras.append(t("tabs.umbral_activo_pct", pct=tarjeta.umbral_uso_pct))
    if tarjeta.umbral_disponible_min is not None and tarjeta.disponible < tarjeta.umbral_disponible_min:
        contras.append(t("tabs.umbral_activo_min", monto=tarjeta.umbral_disponible_min))

    if eval_int.proximo_ciclo:
        resumen = t("tabs.comprar_resumen_abanico_comoda", nombre=tarjeta.nombre, dias=estado.dias_hasta_pago_siguiente_ciclo)
    elif not puede_comprar:
        resumen = t("tabs.comprar_resumen_abanico_riesgo", nombre=tarjeta.nombre)
    elif len(contras) == 0 or (len(pros) >= len(contras) and not eval_int.genera_interes):
        resumen = t("tabs.comprar_resumen_abanico_ok", nombre=tarjeta.nombre, dias=dias)
    elif eval_int.genera_interes or eval_int.dias_pago <= 7:
        resumen = t("tabs.comprar_resumen_abanico_cuidado", nombre=tarjeta.nombre, dias=dias)
    else:
        resumen = t("tabs.comprar_resumen_abanico_ok", nombre=tarjeta.nombre, dias=dias)

    return EvaluacionEleccion(
        tarjeta=tarjeta,
        pros=pros,
        contras=contras,
        resumen=resumen,
        puede_comprar=puede_comprar,
        score=score,
        dias_para_pagar=dias,
    )


def recomendar_tarjeta(
    tarjetas: list[Tarjeta],
    monto: float,
    referencia: date | None = None,
) -> Recomendacion:
    if monto <= 0:
        return Recomendacion(tarjeta=None, mensaje=t("pantalla_recomendacion.sin_opcion"))

    ref = referencia or hoy()
    candidatas: list[tuple[Tarjeta, float]] = []

    for tarjeta in tarjetas:
        if tarjeta.excluida_de_recomendacion(monto):
            continue
        score = calcular_score_tarjeta(tarjeta, monto, ref)
        if score >= 0:
            candidatas.append((tarjeta, score))

    if not candidatas:
        return Recomendacion(tarjeta=None, mensaje=t("pantalla_recomendacion.sin_opcion"))

    candidatas.sort(key=lambda x: x[1], reverse=True)
    mejor, score = candidatas[0]
    dias = dias_para_pagar_compra(mejor, ref)

    return Recomendacion(
        tarjeta=mejor,
        mensaje=generar_mensaje_humano(mejor, monto, ref),
        frase_corta=generar_frase_compra_corta(mejor, monto, ref),
        dias_para_pagar=dias,
        score=score,
    )
