"""El servidor en producción: arranque sin datos, respaldo, errores, velocidad y archivos para buscadores."""
import gzip
import json
import re
import time

from judo import almacen, create_app, drive


# ---------------------------------------------------------------- arranque, datos y errores
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


def test_respaldo_publica_las_planillas_incluidas(tmp_path, semilla):
    data = tmp_path / "data"
    estado = almacen.instalar_semilla(data, semilla)
    assert estado["version"] == almacen.SEMILLA and estado["resultado"] == "respaldo"
    assert estado["fecha_planillas"].startswith(str(estado["anio"]))  # fecha guardada dentro de la planilla
    app = create_app({"TESTING": True, "DATA_DIR": data, "PROGRAMADOR": False})
    assert app.test_client().get("/").status_code == 200
    assert almacen.instalar_semilla(data, semilla) is None  # con datos publicados no hace nada


def test_drive_caido_al_encender_publica_el_respaldo(tmp_path, semilla, monkeypatch):
    def caido(*_args, **_kwargs):
        raise drive.ErrorDrive("sin conexión (prueba)")

    monkeypatch.setattr(drive, "listar", caido)
    app = create_app({"TESTING": True, "DATA_DIR": tmp_path / "data", "SEMILLA_DIR": semilla, "PROGRAMADOR": True})
    try:
        for _ in range(300):
            if app.extensions["almacen"].hay_datos():
                break
            time.sleep(0.1)
        assert app.test_client().get("/").status_code == 200
        assert almacen.leer_estado(tmp_path / "data")["resultado"] == "respaldo"
    finally:
        app.extensions["programador"][0].shutdown(wait=False)


def test_error_interno_con_pagina_propia(data_dir):
    app = create_app({"TESTING": False, "DATA_DIR": data_dir, "PROGRAMADOR": False})

    @app.get("/falla")
    def falla():
        raise RuntimeError("error de prueba")

    r = app.test_client().get("/falla")
    assert r.status_code == 500 and "Algo falló de nuestro lado" in r.get_data(as_text=True)


# ---------------------------------------------------------------- velocidad: compresión, fuentes y caché
def test_fuentes_propias_y_paginas_comprimidas(client):
    r = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("Content-Encoding") == "gzip"
    html = gzip.decompress(r.data).decode()
    # Sin Google Fonts: las fuentes vienen del sitio y se precargan
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert 'fuentes/barlow-condensed-700.woff2" as="font"' in html
    assert "font-src 'self'" in r.headers["Content-Security-Policy"]
    for nombre in ("barlow-condensed-700.woff2", "source-sans-3.woff2"):
        f = client.get(f"/static/fuentes/{nombre}")
        assert f.status_code == 200 and f.mimetype == "font/woff2"
        f.close()


def test_estaticos_con_huella_y_cache_larga(client):
    html = client.get("/").get_data(as_text=True)
    css = re.search(r'href="(/static/estilos\.css\?v=[0-9a-f]{10})"', html).group(1)
    r = client.get(css)
    assert r.status_code == 200 and r.cache_control.max_age == 365 * 24 * 3600
    r.close()
    # Las fuentes se precargan con la misma dirección que usa estilos.css (sin huella), o se bajarían dos veces
    assert 'href="/static/fuentes/barlow-condensed-700.woff2" as="font"' in html


# ---------------------------------------------------------------- buscadores, navegadores y redes sociales
def test_archivos_para_buscadores_y_navegadores(client):
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Allow: /" in robots and "Sitemap: http" in robots
    mapa = client.get("/sitemap.xml").get_data(as_text=True)
    assert mapa.count("<url>") > 150 and "/clubes/hiroshima</loc>" in mapa and "/regiones/tarapaca</loc>" in mapa
    icono = client.get("/favicon.ico")
    assert icono.status_code == 200 and icono.mimetype == "image/png"
    icono.close()


def test_vista_previa_al_compartir(client):
    html = client.get("/clubes").get_data(as_text=True)
    assert 'property="og:image" content="http' in html and "img/compartir.png" in html
    assert 'property="og:url" content="http://localhost/clubes"' in html and 'rel="apple-touch-icon"' in html
