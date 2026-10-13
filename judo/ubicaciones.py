"""
Ubicación de los clubes: ciudad, comuna, región y zona.

Los datos viven en judo/clubes.csv (una fila por club, editable a mano). La zona no
se guarda: se deduce de la región con ZONA_DE_REGION, igual que la federación agrupa
los campeonatos zonales.

Zonas de la federación en 2026 (verificado con las noticias de los campeonatos zonales):
  Norte  : Arica y Parinacota a Coquimbo (Coquimbo compitió en el zonal Norte de 2026;
           en 2022 estaba en el Centro).
  Centro : Valparaíso, Metropolitana, O'Higgins y Maule.
  Sur    : Ñuble a Magallanes.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent / "clubes.csv"

# De norte a sur: también es el orden en que se muestran en los filtros.
REGIONES = [
    "Arica y Parinacota", "Tarapacá", "Antofagasta", "Atacama", "Coquimbo",
    "Valparaíso", "Metropolitana", "O'Higgins", "Maule",
    "Ñuble", "Biobío", "La Araucanía", "Los Ríos", "Los Lagos", "Aysén", "Magallanes",
]
ZONAS = [("norte", "Norte"), ("centro", "Centro"), ("sur", "Sur")]
ZONA_DE_REGION = {
    **dict.fromkeys(REGIONES[:5], "norte"),
    **dict.fromkeys(REGIONES[5:9], "centro"),
    **dict.fromkeys(REGIONES[9:], "sur"),
}
NOMBRE_ZONA = dict(ZONAS)


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


# Identificador de cada región en las direcciones web: 'Tarapacá' -> 'tarapaca', "O'Higgins" -> 'o-higgins'.
SLUG_REGION = {r: _slug(r) for r in REGIONES}
REGION_DE_SLUG = {s: r for r, s in SLUG_REGION.items()}

# Columnas de clubes.csv. clave: el club como aparece en las planillas (ya unificado, ver datos.ALIAS_CLUBES);
# nombre: el nombre que muestra el sitio; nombre_registro: como figura en el registro de la federación.
COLUMNAS = ["clave", "nombre", "nombre_registro", "comuna", "ciudad", "region", "confianza", "fuente", "nota"]


def cargar() -> dict[str, dict]:
    """Ficha de cada club, indexada por la clave del club en las planillas (ej. 'HIROSHIMA')."""
    if not ARCHIVO.exists():
        return {}
    with open(ARCHIVO, encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
        if faltan:  # un error al editar el archivo a mano se explica solo
            raise ValueError(f"A {ARCHIVO.name} le faltan las columnas {', '.join(faltan)}")
        filas = {r["clave"].strip(): {k: (v or "").strip() for k, v in r.items()} for r in lector}
    for r in filas.values():
        if r["region"] not in ZONA_DE_REGION:  # región vacía o mal escrita: el club queda "Sin confirmar"
            r["region"] = ""
    return filas


def nombre_largo(region: str) -> str:
    """'Tarapacá' -> 'Región de Tarapacá', 'Metropolitana' -> 'Región Metropolitana'."""
    if not region:
        return ""
    if region == "Metropolitana":
        return "Región Metropolitana"
    return ("Región del " if region in ("Maule", "Biobío") else "Región de ") + region


def slug_region(region: str) -> str:
    """'Tarapacá' -> 'tarapaca' ('' si la región no se conoce)."""
    return SLUG_REGION.get(region, "")


def zona_de(region: str) -> str:
    """Slug de la zona ('norte', 'centro', 'sur') o '' si la región no se conoce."""
    return ZONA_DE_REGION.get(region, "")
