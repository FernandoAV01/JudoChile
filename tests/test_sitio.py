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
    ("/clubes/nac", "Arica"),
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


def test_clubes_ordenados_por_puntos(app, client):
    clubes = app.extensions["almacen"].ranking().lista_clubes()
    puntos = [c["puntos"] for c in clubes]
    assert puntos == sorted(puntos, reverse=True)
    assert [c["lugar"] for c in clubes] == list(range(1, len(clubes) + 1))
    primero, segundo = clubes[0]["club_nombre"], clubes[1]["club_nombre"]
    for ruta in ("/clubes", "/"):  # sección Clubes y portada
        html = client.get(ruta).get_data(as_text=True)
        assert html.index(f">{primero}</a>") < html.index(f">{segundo}</a>")


def test_categoria_con_un_solo_deportista(client):
    html = client.get("/categorias/sub-18/mujeres-40").get_data(as_text=True)
    assert "Sin rivales" in html and "Dominada" not in html


def test_salud(client):
    assert client.get("/salud").get_json() == {"ok": True, "datos": True}


def test_sin_datos_muestra_carga_con_recarga(tmp_path):
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path, "PROGRAMADOR": False})
    c = app.test_client()
    r = c.get("/")
    assert r.status_code == 503 and 'http-equiv="refresh"' in r.get_data(as_text=True)
    assert "Cache-Control" not in r.headers
    assert c.get("/salud").get_json() == {"ok": True, "datos": False}


def test_descarga_fallida_muestra_aviso(tmp_path):
    (tmp_path / "estado.json").write_text(json.dumps({"resultado": "error", "error": "sin conexión"}))
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path, "PROGRAMADOR": False})
    r = app.test_client().get("/")
    assert r.status_code == 503 and "No pudimos descargar" in r.get_data(as_text=True)


# ---------------------------------------------------------------- datos
def test_puntajes_cuadran(app):
    r = app.extensions["almacen"].ranking()
    df = r.df
    assert r.anio == 2026 and len(r.cats) == 80
    assert ((df.arrastre + df.torneos - df.total).abs() < 0.05).all()
    assert (df.groupby("cat_id").pos.min() == 1).all()


# ---------------------------------------------------------------- zonas, ubicación y clubes por categoría
@pytest.mark.parametrize("ruta", ["/", "/clubes", "/categorias/sub-15", "/categorias-por-clubes/absoluta", "/metodologia",
                                  "/clubes/no-existe"])
def test_pie_con_autoria(client, ruta):
    html = client.get(ruta).get_data(as_text=True)
    for texto in ("Fernando Arellano", "https://github.com/FernandoAV01",
                  "https://www.linkedin.com/in/fernando-arellano-v", "arellano.fernando.v@gmail.com"):
        assert texto in html, (ruta, texto)


def test_ficha_de_club_con_ubicacion(client):
    html = client.get("/clubes/hiroshima").get_data(as_text=True)
    assert "Iquique" in html and "Tarapacá" in html and "Norte" in html
    html = client.get("/clubes/nac").get_data(as_text=True)
    assert "North American College" in html and "Arica" in html


def test_club_sin_ubicacion_confirmada(client):
    assert "Sin confirmar" in client.get("/clubes/shijoukou").get_data(as_text=True)


def test_clubes_por_zona(app, client):
    r = app.extensions["almacen"].ranking()
    for zona in ("norte", "centro", "sur"):
        clubes = r.lista_clubes(zona)
        assert clubes and all(c["zona"] == zona for c in clubes)
        assert [c["puesto"] for c in clubes] == list(range(1, len(clubes) + 1))
    html = client.get("/clubes?zona=norte").get_data(as_text=True)
    assert ">Hiroshima</a>" in html and ">Pudahuel</a>" not in html and "Nacional" in html


def test_zona_invalida_se_ignora(client):
    assert client.get("/clubes?zona=marte").get_data(as_text=True) == client.get("/clubes").get_data(as_text=True)


def test_categoria_filtrada_por_zona(app):
    r = app.extensions["almacen"].ranking()
    info, filas = r.categoria("absoluta", "hombres-81", "sur")
    assert filas and all(f["zona"] == "sur" for f in filas)
    assert [f["pos_zona"] for f in filas] == list(range(1, len(filas) + 1))
    assert info["inscritos"] == len(filas) and info["lider"] == filas[0]["deportista"]


def test_clubes_por_categoria(app, client):
    r = app.extensions["almacen"].ranking()
    df = r.df[r.df.con_club]
    for grupo, cat in (("absoluta", "hombres-81"), ("sub-13", ""), ("sub-18", "mujeres-40")):
        clubes = r.clubes_en(grupo, cat)
        sub = df[(df.grupo_slug == grupo) & ((df.cat_slug == cat) if cat else True)]
        assert abs(sum(c["puntos"] for c in clubes) - sub.total.sum()) < 0.01
        assert [c["puntos"] for c in clubes] == sorted((c["puntos"] for c in clubes), reverse=True)
    assert client.get("/categorias-por-clubes").headers["Location"].endswith("/categorias-por-clubes/absoluta")
    assert client.get("/categorias-por-clubes/absoluta/hombres-999").status_code == 404
    html = client.get("/categorias-por-clubes/sub-15?zona=centro").get_data(as_text=True)
    assert "Clubes en Sub 15 · Zona Centro" in html


def test_navegacion_conserva_la_zona(client):
    html = client.get("/categorias/sub-15?zona=sur").get_data(as_text=True)
    assert "/categorias/sub-15/mujeres-52?zona=sur" in html and "/categorias/absoluta?zona=sur" in html


def test_categoria_sin_deportistas_de_la_zona(client):
    # Sub 18 · Mujeres · −40 kg tiene una sola deportista, de un club de Iquique (Zona Norte).
    html = client.get("/categorias/sub-18/mujeres-40?zona=sur").get_data(as_text=True)
    assert "Ningún deportista de la Zona Sur" in html and "Ranking completo" not in html
    html = client.get("/categorias/sub-18?zona=sur").get_data(as_text=True)
    assert "Ningún deportista de la Zona Sur en esta categoría" in html
    html = client.get("/categorias-por-clubes/sub-18/mujeres-40?zona=sur").get_data(as_text=True)
    assert "Ningún club de la Zona Sur" in html
