"""Accesibilidad básica de cada sección: lo que se puede revisar en el HTML, sin abrir un navegador."""
import re

import pytest

PAGINAS = ["/", "/categorias/absoluta", "/categorias/absoluta/hombres-81?zona=sur", "/clubes", "/clubes/hiroshima",
           "/categorias-por-clubes/sub-15", "/regiones", "/regiones/tarapaca", "/deportistas/maria-camila-valencia-f",
           "/buscar?q=koga", "/metodologia", "/no-existe"]


@pytest.mark.parametrize("ruta", PAGINAS)
def test_estructura_accesible(client, ruta):
    html = client.get(ruta).get_data(as_text=True)
    # Enlace para saltar al contenido y zona principal con ese destino
    assert '<a class="saltar" href="#contenido">' in html and '<main id="contenido"' in html
    # Un solo título principal y sin saltos de nivel (h1 → h3)
    niveles = [int(n) for n in re.findall(r"<h([1-6])\b", html)]
    assert niveles.count(1) == 1, ruta
    assert all(b <= a + 1 for a, b in zip(niveles, niveles[1:])), (ruta, niveles)
    # Cada zona de búsqueda tiene un nombre propio
    nombres = re.findall(r'role="search" aria-label="([^"]+)"', html)
    assert len(nombres) == html.count('role="search"') and len(set(nombres)) == len(nombres)
