"""
Cargar un paquete de soporte (.zip) en app/data para depurar en el Lab.

Solo para el desarrollador en su PC. No forma parte de la app del usuario.

Uso (desde la raíz del proyecto):

    python tools/cargar_caso.py lab_casos/ana/ti_soporte_20260711.zip
    python tools/cargar_caso.py ruta/al/archivo.zip --piloto ana

Opcional: copia el ZIP a lab_casos/<piloto>/ antes de cargar.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Raíz del repo en sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.soporte import importar_paquete_soporte  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga un ZIP de soporte TI en app/data (Lab Streamlit).",
    )
    parser.add_argument(
        "zip",
        type=Path,
        help="Ruta al archivo ti_soporte_….zip",
    )
    parser.add_argument(
        "--piloto",
        type=str,
        default="",
        help="Nombre del piloto (ana, luis, maria…). Guarda copia en lab_casos/<piloto>/",
    )
    args = parser.parse_args()

    zip_path = args.zip.expanduser().resolve()
    if not zip_path.is_file():
        print(f"No existe el archivo: {zip_path}", file=sys.stderr)
        return 1
    if zip_path.suffix.lower() != ".zip":
        print("El archivo debe ser un .zip", file=sys.stderr)
        return 1

    if args.piloto:
        destino_piloto = _ROOT / "lab_casos" / args.piloto.strip().lower()
        destino_piloto.mkdir(parents=True, exist_ok=True)
        copia = destino_piloto / zip_path.name
        if zip_path != copia.resolve():
            shutil.copy2(zip_path, copia)
            print(f"Copia guardada en: {copia}")

    contenido = zip_path.read_bytes()
    try:
        resultado = importar_paquete_soporte(contenido)
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error al importar: {exc}", file=sys.stderr)
        return 1

    meta = resultado.get("meta") or {}
    print("OK — caso cargado en app/data")
    print(f"  Versión origen: {meta.get('version_ti', '—')}")
    print(f"  Plataforma:     {meta.get('plataforma', '—')}")
    if meta.get("nota"):
        print(f"  Nota:           {meta.get('nota')}")
    print(f"  Backup Lab:     {resultado.get('backup')}")
    print("Abrí Streamlit (streamlit run streamlit_app.py) para revisar el caso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
