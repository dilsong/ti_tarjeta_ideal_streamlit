"""Generación HTML e impresión de reportes."""

from __future__ import annotations

from datetime import datetime

from app.components.theme import etiqueta_color_nombre
from app.core.reportes import FilaReporte, ResumenReporte
from app.i18n.translator import t


def _esc(texto: str) -> str:
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _encabezado_html(titulo: str) -> str:
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"<h1>{_esc(titulo)}</h1>"
        f"<p><strong>{_esc(t('reportes.generado'))}:</strong> {ahora}</p>"
        f"<p><strong>{_esc(t('reportes.usuario'))}:</strong> { _esc(t('app.nombre')) }</p>"
        f"<hr/>"
    )


def _totales_html(resumen: ResumenReporte) -> str:
    return (
        f"<h3>{_esc(t('reportes.totales'))}</h3>"
        f"<ul>"
        f"<li>{_esc(t('reportes.total_limite'))}: ${resumen.total_limite:,.2f}</li>"
        f"<li>{_esc(t('reportes.total_consumo'))}: ${resumen.total_consumo:,.2f}</li>"
        f"<li>{_esc(t('reportes.total_disponibilidad'))}: ${resumen.total_disponibilidad:,.2f}</li>"
        f"<li>{_esc(t('reportes.tarjeta_cargada'))}: {_esc(resumen.tarjeta_mas_cargada)}</li>"
        f"<li>{_esc(t('reportes.tarjeta_urgente'))}: {_esc(resumen.tarjeta_mas_urgente)}</li>"
        f"</ul>"
    )


def html_ficha(fila: FilaReporte) -> str:
    tj = fila.tarjeta
    body = (
        f"<h2>{_esc(tj.banco)} — {_esc(tj.nombre)}</h2>"
        f"<p><strong>{_esc(t('reportes.col_tipo'))}:</strong> {_esc(fila.tipo)} · "
        f"•••• {tj.ultimos_digitos}</p>"
        f"<div class='table-wrap'><table>"
        f"<tr><td>{_esc(t('pantalla_lista_tarjetas.limite'))}</td><td>${fila.limite:,.2f}</td></tr>"
        f"<tr><td>{_esc(t('reportes.consumo_ciclo'))}</td><td>${fila.consumo:,.2f}</td></tr>"
        f"<tr><td>{_esc(t('pantalla_lista_tarjetas.disponible'))}</td><td>${fila.disponibilidad:,.2f}</td></tr>"
        f"<tr><td>{_esc(t('reportes.col_corte'))}</td><td>{_esc(fila.fecha_corte_txt)}</td></tr>"
        f"<tr><td>{_esc(t('reportes.col_pago'))}</td><td>{_esc(fila.fecha_pago_txt)}</td></tr>"
        f"<tr><td>{_esc(t('reportes.col_ultima_compra'))}</td><td>{_esc(fila.ultima_compra_txt)}</td></tr>"
        f"<tr><td>{_esc(t('reportes.col_estado_ciclo'))}</td><td>{_esc(fila.estado_ciclo_txt)}</td></tr>"
        f"</table></div>"
    )
    if fila.vista.desglose_pasado:
        dp = fila.vista.desglose_pasado
        body += (
            f"<h4>{_esc(t('uso.ciclo_pasado_titulo'))}</h4>"
            f"<ul><li>${dp.saldo_no_pagado:,.2f} — {_esc(t('uso.linea_saldo_no_pagado'))}</li>"
            f"<li>${dp.interes_estimado:,.2f} — {_esc(t('uso.linea_interes_arrastre'))}</li></ul>"
        )
    if fila.vista.desglose_nuevo.lineas:
        body += f"<h4>{_esc(t('uso.ciclo_nuevo_titulo'))}</h4><ul>"
        for ln in fila.vista.desglose_nuevo.lineas:
            body += f"<li>${ln.monto:,.2f} — {_esc(ln.nombre)}</li>"
        body += "</ul>"
    return _wrap_html(t("reportes.vista_individual"), body)


def html_tabla(resumen: ResumenReporte) -> str:
    rows = ""
    for f in resumen.filas:
        rows += (
            f"<tr>"
            f"<td>{_esc(etiqueta_color_nombre(f.tarjeta.color, f.tarjeta.nombre))}</td>"
            f"<td>{_esc(f.tarjeta.banco)}</td>"
            f"<td>${f.limite:,.2f}</td>"
            f"<td>${f.consumo:,.2f}</td>"
            f"<td>${f.disponibilidad:,.2f}</td>"
            f"<td>{_esc(f.fecha_corte_txt)}</td>"
            f"<td>{_esc(f.fecha_pago_txt)}</td>"
            f"<td>{_esc(f.ultima_compra_txt)}</td>"
            f"</tr>"
        )
    body = (
        f"<div class='table-wrap'><table>"
        f"<thead><tr>"
        f"<th>{_esc(t('reportes.col_color'))}</th>"
        f"<th>{_esc(t('reportes.col_banco'))}</th>"
        f"<th>{_esc(t('reportes.col_limite'))}</th>"
        f"<th>{_esc(t('reportes.col_consumo'))}</th>"
        f"<th>{_esc(t('reportes.col_disponible'))}</th>"
        f"<th>{_esc(t('reportes.col_corte'))}</th>"
        f"<th>{_esc(t('reportes.col_pago'))}</th>"
        f"<th>{_esc(t('reportes.col_ultima_compra'))}</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
        + _totales_html(resumen)
    )
    return _wrap_html(t("reportes.vista_agrupado"), body)


def html_prioridad(filas: list[FilaReporte], resumen: ResumenReporte) -> str:
    items = ""
    for i, f in enumerate(filas, 1):
        items += (
            f"<li>{i}. {_esc(f.tarjeta.nombre)} — "
            f"{_esc(t('reportes.col_pago'))} { _esc(f.fecha_pago_txt)} — "
            f"{_esc(t('reportes.col_consumo'))} ${f.consumo:,.2f}</li>"
        )
    body = f"<ol>{items}</ol>" + _totales_html(resumen)
    return _wrap_html(t("reportes.vista_prioridad"), body)


def _estilos_reporte() -> str:
    return """
        * { box-sizing: border-box; }
        html {
            color-scheme: light;
            -webkit-text-size-adjust: 100%;
        }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, Arial, sans-serif;
            margin: 0;
            padding: 16px;
            max-width: 720px;
            background: #ffffff !important;
            color: #0f172a !important;
            font-size: 15px;
            line-height: 1.5;
        }
        h1, h2, h3, h4, p, li, td, th, strong {
            color: #0f172a !important;
        }
        h1 { font-size: 1.25rem; margin: 0 0 0.5rem; }
        h2 { font-size: 1.1rem; margin: 1rem 0 0.5rem; }
        h3, h4 { font-size: 1rem; margin: 0.75rem 0 0.35rem; }
        p { margin: 0.35rem 0; }
        hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
        ul, ol { padding-left: 1.25rem; margin: 0.5rem 0; }
        .table-wrap {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 12px 0;
        }
        table {
            width: 100%;
            min-width: 280px;
            border-collapse: collapse;
            background: #ffffff !important;
        }
        th, td {
            border: 1px solid #cbd5e1 !important;
            padding: 10px 8px !important;
            text-align: left;
            vertical-align: top;
            background: #ffffff !important;
            color: #0f172a !important;
        }
        th {
            background: #f1f5f9 !important;
            font-weight: 600;
            font-size: 0.8rem;
        }
        tr:nth-child(even) td {
            background: #f8fafc !important;
        }
        .btn-print {
            display: block;
            width: 100%;
            max-width: 320px;
            margin: 20px auto 8px;
            padding: 12px 16px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            border-radius: 10px;
            background: #2563eb;
            color: #ffffff !important;
        }
        @media (max-width: 480px) {
            body { padding: 12px; font-size: 14px; }
            th, td { padding: 8px 6px !important; font-size: 13px; }
        }
        @media print {
            body { padding: 0; max-width: none; }
            .btn-print { display: none; }
        }
    """


def _wrap_html(titulo: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<meta name='color-scheme' content='light'/>"
        "<title>Tarjeta Ideal — Reporte</title>"
        f"<style>{_estilos_reporte()}</style>"
        "</head><body>"
        + _encabezado_html(titulo)
        + body
        + "</body></html>"
    )
