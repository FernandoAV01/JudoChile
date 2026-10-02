"""Pruebas del sitio: acceso restringido, páginas y lectura de planillas.

    .venv/bin/python -m pytest -q
"""
import json
import shutil
from pathlib import Path

import pytest

from judo import create_app
from judo import auth as auth_mod
from judo.auth import correo_permitido

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
    return create_app({"TESTING": True, "DATA_DIR": data_dir, "PROGRAMADOR": False, "SECRET_KEY": "prueba",
                       "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secreto",
                       "DOMINIOS_PERMITIDOS": ["mail.pucv.cl"], "SESSION_COOKIE_SECURE": False})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logueado(client):
    with client.session_transaction() as s:
        s["usuario"] = {"email": "ana.perez@mail.pucv.cl", "nombre": "Ana", "foto": None}
    return client


# ---------------------------------------------------------------- acceso
@pytest.mark.parametrize("email,verificado,esperado", [
    ("ana@mail.pucv.cl", True, True),
    ("ANA@MAIL.PUCV.CL", True, True),
    ("ana@mail.pucv.cl", False, False),
    ("ana@mail.pucv.cl", None, False),
    ("ana@gmail.com", True, False),
    ("ana@pucv.cl", True, False),
    ("ana@mail.pucv.cl.evil.com", True, False),
    ("ana@evilmail.pucv.cl", True, False),
    ("ana@x@mail.pucv.cl", True, False),
    ("", True, False),
    (None, True, False),
])
def test_correo_permitido(email, verificado, esperado):
    assert correo_permitido(email, verificado, ["mail.pucv.cl"]) is esperado


@pytest.mark.parametrize("ruta", ["/", "/clubes", "/clubes/hiroshima", "/categorias/absoluta", "/buscar?q=a", "/metodologia"])
def test_sin_ingreso_redirige_al_login(client, ruta):
    r = client.get(ruta)
    assert r.status_code == 302 and "/ingresar" in r.headers["Location"]


def test_login_y_salud_son_publicos(client):
    assert client.get("/ingresar").status_code == 200
    assert client.get("/salud").get_json()["datos"] is True


def test_redireccion_externa_bloqueada(client):
    client.get("/ingresar?next=//evil.com")
    with client.session_transaction() as s:
        assert "siguiente" not in s


def _callback(client, monkeypatch, userinfo):
    monkeypatch.setattr(auth_mod.oauth.google, "authorize_access_token", lambda: {"userinfo": userinfo})
    return client.get("/auth/callback")


def test_callback_acepta_dominio_pucv(client, monkeypatch):
    r = _callback(client, monkeypatch, {"email": "ana@mail.pucv.cl", "email_verified": True, "given_name": "Ana"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    with client.session_transaction() as s:
        assert s["usuario"]["email"] == "ana@mail.pucv.cl"
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("info", [
    {"email": "ana@gmail.com", "email_verified": True},
    {"email": "ana@mail.pucv.cl", "email_verified": False},
    {},
])
def test_callback_rechaza_otros_correos(client, monkeypatch, info):
    r = _callback(client, monkeypatch, info)
    assert "error=dominio" in r.headers["Location"]
    with client.session_transaction() as s:
        assert "usuario" not in s
    assert client.get("/").status_code == 302


def test_sesion_con_dominio_no_permitido_se_cierra(client):
    with client.session_transaction() as s:
        s["usuario"] = {"email": "ana@gmail.com", "nombre": "Ana"}
    assert client.get("/").status_code == 302


def test_salir(logueado):
    logueado.post("/salir")
    assert logueado.get("/").status_code == 302


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
def test_paginas(logueado, ruta, texto):
    r = logueado.get(ruta)
    assert r.status_code == 200, ruta
    assert texto in r.get_data(as_text=True)


def test_categorias_lleva_a_absoluta(logueado):
    assert logueado.get("/categorias").headers["Location"].endswith("/categorias/absoluta")


@pytest.mark.parametrize("ruta", ["/categorias/sub-99", "/categorias/absoluta/hombres-999", "/clubes/no-existe", "/deportistas/nadie-f"])
def test_404(logueado, ruta):
    assert logueado.get(ruta).status_code == 404


# ---------------------------------------------------------------- datos
def test_puntajes_cuadran(app):
    r = app.extensions["almacen"].ranking()
    df = r.df
    assert r.anio == 2026 and len(r.cats) == 80
    assert ((df.arrastre + df.torneos - df.total).abs() < 0.05).all()
    assert (df.groupby("cat_id").pos.min() == 1).all()


def test_sin_datos_muestra_carga_con_recarga(tmp_path):
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path, "PROGRAMADOR": False, "SECRET_KEY": "prueba",
                      "SESSION_COOKIE_SECURE": False})
    c = app.test_client()
    with c.session_transaction() as s:
        s["usuario"] = {"email": "ana@mail.pucv.cl", "nombre": "Ana"}
    r = c.get("/")
    assert r.status_code == 503 and 'http-equiv="refresh"' in r.get_data(as_text=True)
    assert c.get("/salud").get_json() == {"ok": True, "datos": False}
