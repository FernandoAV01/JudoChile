"""Páginas del sitio: que respondan, qué muestran y cómo se enlazan entre sí."""
import pytest


# ---------------------------------------------------------------- todas las secciones
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


@pytest.mark.parametrize("ruta", ["/categorias/sub-99", "/categorias/absoluta/hombres-999", "/clubes/no-existe",
                                  "/deportistas/nadie-f", "/ingresar"])
def test_404(client, ruta):
    assert client.get(ruta).status_code == 404


def test_direccion_con_barra_final(client):
    assert client.get("/clubes/").status_code == 200
    assert client.get("/regiones/tarapaca/").status_code == 200


@pytest.mark.parametrize("ruta", ["/", "/clubes", "/categorias/sub-15", "/categorias-por-clubes/absoluta", "/metodologia", "/regiones",
                                  "/clubes/no-existe"])
def test_pie_con_autoria(client, ruta):
    html = client.get(ruta).get_data(as_text=True)
    for texto in ("Fernando Arellano", "https://github.com/FernandoAV01",
                  "https://www.linkedin.com/in/fernando-arellano-v", "arellano.fernando.v@gmail.com"):
        assert texto in html, (ruta, texto)


def test_fechas_sin_corte_de_linea(client):
    html = client.get("/").get_data(as_text=True)
    assert 'publicadas el <span class="nw">04-09-2026</span>' in html


# ---------------------------------------------------------------- categorías y clubes
def test_categorias_lleva_a_absoluta(client):
    assert client.get("/categorias").headers["Location"].endswith("/categorias/absoluta")


def test_categoria_con_un_solo_deportista(client):
    html = client.get("/categorias/sub-18/mujeres-40").get_data(as_text=True)
    assert "Sin rivales" in html and "Dominada" not in html


def test_clubes_ordenados_por_puntos(rk, client):
    clubes = rk.lista_clubes()
    puntos = [c["puntos"] for c in clubes]
    assert puntos == sorted(puntos, reverse=True)
    assert [c["lugar"] for c in clubes] == list(range(1, len(clubes) + 1))
    primero, segundo = clubes[0]["club_nombre"], clubes[1]["club_nombre"]
    for ruta in ("/clubes", "/"):  # sección Clubes y portada
        html = client.get(ruta).get_data(as_text=True)
        assert html.index(f">{primero}</a>") < html.index(f">{segundo}</a>")


def test_clubes_por_categoria(rk, client):
    df = rk.df[rk.df.con_club]
    for grupo, cat in (("absoluta", "hombres-81"), ("sub-13", ""), ("sub-18", "mujeres-40")):
        clubes = rk.clubes_en(grupo, cat)
        sub = df[(df.grupo_slug == grupo) & ((df.cat_slug == cat) if cat else True)]
        assert abs(sum(c["puntos"] for c in clubes) - sub.total.sum()) < 0.01
        assert [c["puntos"] for c in clubes] == sorted((c["puntos"] for c in clubes), reverse=True)
    assert client.get("/categorias-por-clubes").headers["Location"].endswith("/categorias-por-clubes/absoluta")
    assert client.get("/categorias-por-clubes/absoluta/hombres-999").status_code == 404
    html = client.get("/categorias-por-clubes/sub-15?zona=centro").get_data(as_text=True)
    assert "Clubes en Sub 15 · Zona Centro" in html


def test_ficha_de_club_con_ubicacion(client):
    html = client.get("/clubes/hiroshima").get_data(as_text=True)
    assert "Iquique" in html and "Tarapacá" in html and "Norte" in html
    html = client.get("/clubes/nac").get_data(as_text=True)
    assert "North American College" in html and "Arica" in html


def test_club_sin_ubicacion_confirmada(client):
    assert "Sin confirmar" in client.get("/clubes/shijoukou").get_data(as_text=True)


def test_nombre_del_club_de_valparaiso(client):
    html = client.get("/clubes/valparaiso").get_data(as_text=True)
    assert "<h1>Club de Judo Valparaíso</h1>" in html


# ---------------------------------------------------------------- búsqueda
def test_titulo_de_la_busqueda(client):
    html = client.get("/buscar?q=valencia").get_data(as_text=True)
    assert "<title>Resultados para “valencia” · Judo Chile" in html
