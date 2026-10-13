"""Menores de edad fuera de los buscadores: sus fichas y los rankings de sus edades no se indexan, y en
las demás páginas sus nombres van marcados para que Google no los muestre en sus resultados."""
import pytest

from judo.datos import GRUPOS_MENORES

NOINDEX = '<meta name="robots" content="noindex">'


def test_edades_de_menores():
    assert GRUPOS_MENORES == {"sub-13", "sub-15", "sub-18"}


def test_fichas_de_menores_no_se_indexan(rk, client):
    df = rk.df
    menor = sorted(rk.menores)[0]
    adulto = sorted(set(df[df.grupo_slug.isin(["sub-21", "absoluta"])].dep_slug) - rk.menores)[0]
    html = client.get(f"/deportistas/{menor}").get_data(as_text=True)
    assert NOINDEX in html and 'rel="canonical"' not in html
    html = client.get(f"/deportistas/{adulto}").get_data(as_text=True)
    assert NOINDEX not in html and 'rel="canonical"' in html


@pytest.mark.parametrize("ruta,oculta", [
    ("/categorias/sub-13", True), ("/categorias/sub-15/mujeres-40", True), ("/categorias/sub-18/hombres-60?zona=sur", True),
    ("/categorias-por-clubes/sub-15", True), ("/buscar?q=valencia", True),
    ("/", False), ("/categorias/absoluta/hombres-81", False), ("/categorias/sub-21", False), ("/clubes/hiroshima", False),
    ("/regiones/tarapaca", False), ("/metodologia", False),
])
def test_paginas_fuera_de_los_buscadores(client, ruta, oculta):
    assert (NOINDEX in client.get(ruta).get_data(as_text=True)) == oculta


def test_mapa_del_sitio_sin_edades_de_menores(client):
    mapa = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/categorias/absoluta/hombres-81</loc>" in mapa
    assert not any(f"/{g}" in mapa for g in ("sub-13", "sub-15", "sub-18"))


def test_nombres_de_menores_marcados_en_paginas_indexadas(rk, client):
    club = rk.df[rk.df.club_slug == "hiroshima"]
    menor = club[club.dep_slug.isin(rk.menores)].iloc[0]
    adulto = club[~club.dep_slug.isin(rk.menores)].iloc[0]
    html = client.get("/clubes/hiroshima").get_data(as_text=True)
    assert f"<span data-nosnippet>{menor.deportista}</span>" in html
    assert f">{adulto.deportista}</a>" in html and f"<span data-nosnippet>{adulto.deportista}</span>" not in html
