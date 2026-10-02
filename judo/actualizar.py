"""
Actualización manual desde la línea de comandos (útil para la primera carga o
para un cron externo si el servidor se duerme):

    .venv/bin/python -m judo.actualizar           # descarga solo si algo cambió
    .venv/bin/python -m judo.actualizar --forzar  # descarga igual
"""
from __future__ import annotations

import argparse
import logging
import sys

from .almacen import actualizar
from .config import Config


def main() -> int:
    p = argparse.ArgumentParser(description="Descarga las planillas del ranking desde Google Drive.")
    p.add_argument("--forzar", action="store_true", help="descargar aunque no haya cambios")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        estado = actualizar(Config.DATA_DIR, Config.DRIVE_CARPETA_ID, Config.GOOGLE_API_KEY,
                            forzar=args.forzar, conservar=Config.VERSIONES_A_CONSERVAR)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"{estado['resultado']}: versión {estado['version']} · ranking {estado['anio']} · {estado['filas']} filas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
