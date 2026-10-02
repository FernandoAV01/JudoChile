"""Pruebas del sitio: páginas, carga de datos y lectura de planillas.

    .venv/bin/python -m pytest -q
"""
import json
import shutil
from pathlib import Path

import pytest

from judo import create_app

RAIZ = Path(__file__).resolve().parent.parent
PLANILLAS = sorted(RAIZ.glob("RANKING*.xlsx")) or sorted((RAIZ / "data" / "versiones").glob("*/RANKING*.xlsx"))


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    if not PLANILLAS:
        pytest.skip("No hay planillas locales; ejecuta primero: python -m judo.actualizar")
    d = tmp_path_factory.mktemp("data")
    v = d / "versiones" / "20260101-000000"
    v.mkdir(parents=True)
    for p in PLANILLAS[:5]:
        shutil.copy(p, v / p.name)
    (d / "estado.json").write_text(json.dumps({
        "version": v.name, "fecha_planillas": "2026-09-04T16:33:27+00:00",
        "ultima_revision": "2026-09-27T02:00:00+00:00", "resultado": "sin cambios",
        "archivos": [{"nombre": p.name, "modificado": "2026-09-04T16:33:27+00:00"} for p in PLANILLAS[:5]],
    }))
    return d


@pytest.fixture(scope="session")
def app(data_dir):
    return create_app({"TESTING": True, "DATA_DIR": data_dir, "PROGRAMADOR": False})


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------- páginas
@pytest.mark.parametrize("ruta,texto", [
    ("/", "Los clubes más fuertes del país"),
    ("/categorias/absoluta", "−81 kg"),
    ("/categorias/absoluta/hombres-81", "Ranking completo"),
    ("/categorias/sub-13/mujeres-mas63", "+63 kg"),
    ("/clubes", "Hiroshima"),
    ("/clubes/hiroshima", "Sus números 1"),
    ("/clubes/sin-club", "NAC"),
    ("/deportistas/maria-camila-valencia-f", "Sus categorías"),
    ("/buscar?q=valencia", "Deportistas"),
    ("/buscar?q=zzzzqq", "No encontramos"),
    ("/metodologia", "Planillas usadas"),
])
def test_paginas_publicas(client, ruta, texto):
    """Cualquier persona con el enlace ve las páginas, sin iniciar sesión."""
    r = client.get(ruta)
    assert r.status_code == 200, ruta
    assert texto in r.get_data(as_text=True)


def test_categorias_lleva_a_absoluta(client):
    assert client.get("/categorias").headers["Location"].endswith("/categorias/absoluta")


@pytest.mark.parametrize("ruta", ["/categorias/sub-99", "/categorias/absoluta/hombres-999", "/clubes/no-existe",
                                  "/deportistas/nadie-f", "/ingresar"])
def test_404(client, ruta):
    assert client.get(ruta).status_code == 404


def test_salud(client):
    assert client.get("/salud").get_json() == {"ok": True, "datos": True}


def test_sin_datos_muestra_carga_con_recarga(tmp_path):
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path, "PROGRAMADOR": False})
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 503 and 'http-equiv="refresh"' in r.get_data(as_text=True)
    assert "Cache-Control" not in r.headers
    assert c.get("/salud").get_json() == {"ok": True, "datos": False}


# ---------------------------------------------------------------- datos
def test_puntajes_cuadran(app):
    r = app.extensions["almacen"].ranking()
    df = r.df
    assert r.anio == 2026 and len(r.cats) == 80
    assert ((df.arrastre + df.torneos - df.total).abs() < 0.05).all()
    assert (df.groupby("cat_id").pos.min() == 1).all()
