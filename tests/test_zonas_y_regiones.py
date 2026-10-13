"""Filtro por zona (Norte, Centro y Sur) y sección de regiones."""


# ---------------------------------------------------------------- zonas
def test_clubes_por_zona(rk, client):
    for zona in ("norte", "centro", "sur"):
        clubes = rk.lista_clubes(zona)
        assert clubes and all(c["zona"] == zona for c in clubes)
        assert [c["puesto"] for c in clubes] == list(range(1, len(clubes) + 1))
    html = client.get("/clubes?zona=norte").get_data(as_text=True)
    assert ">Hiroshima</a>" in html and ">Club de Judo Pudahuel</a>" not in html and "Nacional" in html


def test_zona_invalida_se_ignora(client):
    assert client.get("/clubes?zona=marte").get_data(as_text=True) == client.get("/clubes").get_data(as_text=True)


def test_categoria_filtrada_por_zona(rk):
    info, filas = rk.categoria("absoluta", "hombres-81", "sur")
    assert filas and all(f["zona"] == "sur" for f in filas)
    assert [f["pos_zona"] for f in filas] == list(range(1, len(filas) + 1))
    assert info["inscritos"] == len(filas) and info["lider"] == filas[0]["deportista"]


def test_navegacion_conserva_la_zona(client):
    html = client.get("/categorias/sub-15?zona=sur").get_data(as_text=True)
    assert "/categorias/sub-15/mujeres-52?zona=sur" in html and "/categorias/absoluta?zona=sur" in html


def test_categoria_sin_deportistas_de_la_zona(client):
    # Sub 18 · Mujeres · −40 kg tiene una sola deportista, de un club de Iquique (Zona Norte).
    html = client.get("/categorias/sub-18/mujeres-40?zona=sur").get_data(as_text=True)
    assert "Ningún deportista de la Zona Sur aparece en esta categoría." in html
    assert 'class="stats"' not in html and "Ranking completo" not in html  # solo el aviso, sin la fila de ceros
    html = client.get("/categorias/sub-18?zona=sur").get_data(as_text=True)
    assert "Ningún deportista de la Zona Sur en esta categoría" in html
    html = client.get("/categorias-por-clubes/sub-18/mujeres-40?zona=sur").get_data(as_text=True)
    assert "Ningún club de la Zona Sur" in html


# ---------------------------------------------------------------- regiones
def test_ranking_de_regiones(rk, client):
    regiones = rk.regiones()
    assert len(regiones) == 16
    puntos = [f["puntos"] for f in regiones]
    assert puntos == sorted(puntos, reverse=True)
    assert [f["puesto"] for f in regiones] == list(range(1, 17))
    # Todo el puntaje de clubes con ubicación queda repartido entre las regiones
    con = rk.df[rk.df.con_club]
    assert abs(sum(puntos) - con[con.region != ""].total.sum()) < 0.01
    html = client.get("/regiones").get_data(as_text=True)
    assert "Chile de norte a sur" in html and "/regiones/tarapaca" in html and "Por deportista" in html


def test_regiones_por_zona(rk, client):
    sur = rk.regiones("sur")
    assert sur and all(f["zona"] == "sur" for f in sur)
    html = client.get("/regiones?zona=norte").get_data(as_text=True)
    assert "Regiones de la Zona Norte" in html and "/regiones/tarapaca" in html
    assert "/regiones/metropolitana" not in html.split("<main")[1]  # la RM no aparece en el contenido


def test_ficha_de_region(client):
    html = client.get("/regiones/tarapaca").get_data(as_text=True)
    assert "Región de Tarapacá" in html and "Hiroshima" in html and "Iquique" in html and "Sus números 1" in html
    html = client.get("/regiones/metropolitana").get_data(as_text=True)
    assert "<td>Pudahuel</td>" in html and "<td>San Bernardo</td>" in html  # comuna, no solo "Santiago"
    assert client.get("/regiones/o-higgins").status_code == 200
    assert client.get("/regiones/no-existe").status_code == 404


def test_enlaces_a_regiones(client):
    assert "/regiones/tarapaca" in client.get("/clubes/hiroshima").get_data(as_text=True)
    assert "/regiones/arica-y-parinacota" in client.get("/clubes?zona=norte").get_data(as_text=True)
    assert 'href="/regiones"' in client.get("/").get_data(as_text=True)
