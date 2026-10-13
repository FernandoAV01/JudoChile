"""Datos y aplicación compartidos por todas las pruebas.

    .venv/bin/python -m pytest -q

Las pruebas usan las planillas de la carpeta planillas/ (las mismas que el sitio usa como respaldo).
"""
import json
import shutil
from pathlib import Path

import pytest

from judo import create_app

RAIZ = Path(__file__).resolve().parent.parent
PLANILLAS = sorted((RAIZ / "planillas").glob("RANKING*.xlsx")) or sorted((RAIZ / "data" / "versiones").glob("*/RANKING*.xlsx"))


@pytest.fixture(scope="session")
def planillas():
    """Las planillas de ranking con que se hacen las pruebas (una por edad)."""
    if not PLANILLAS:
        pytest.skip("No hay planillas locales; ejecuta primero: python -m judo.actualizar")
    return PLANILLAS[:5]


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory, planillas):
    """Una carpeta de datos como la del servidor, con las planillas ya publicadas."""
    d = tmp_path_factory.mktemp("data")
    v = d / "versiones" / "20260101-000000"
    v.mkdir(parents=True)
    for p in planillas:
        shutil.copy(p, v / p.name)
    (d / "estado.json").write_text(json.dumps({
        "version": v.name, "fecha_planillas": "2026-09-04T16:33:27+00:00",
        "ultima_revision": "2026-09-27T02:00:00+00:00", "resultado": "sin cambios",
        "archivos": [{"nombre": p.name, "modificado": "2026-09-04T16:33:27+00:00"} for p in planillas],
    }))
    return d


@pytest.fixture(scope="session")
def app(data_dir):
    return create_app({"TESTING": True, "DATA_DIR": data_dir, "PROGRAMADOR": False})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def rk(app):
    """El ranking cargado: el mismo objeto con que se arman las páginas."""
    return app.extensions["almacen"].ranking()


@pytest.fixture
def semilla(tmp_path, planillas):
    """Una carpeta de respaldo con las planillas, como planillas/ en el servidor."""
    d = tmp_path / "semilla"
    d.mkdir()
    for p in planillas:
        shutil.copy(p, d / p.name)
    return d
