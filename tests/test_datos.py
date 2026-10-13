"""Lectura de las planillas e integridad de los datos que muestra el sitio."""
import csv
import re
import unicodedata

from judo.ubicaciones import ARCHIVO, REGIONES


def test_puntajes_cuadran(rk):
    df = rk.df
    assert rk.anio == 2026 and len(rk.cats) == 80
    assert ((df.arrastre + df.torneos - df.total).abs() < 0.05).all()
    assert (df.groupby("cat_id").pos.min() == 1).all()


def test_ningun_club_se_llama_solo_como_un_lugar():
    """Un club llamado solo "Valparaíso" u "Osorno" se confunde con la ciudad o la región."""
    def norm(t):
        t = "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")
        return " ".join(re.findall(r"[a-z0-9]+", t))

    with open(ARCHIVO, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    lugares = {norm(f[c]) for f in filas for c in ("ciudad", "comuna") if f[c]} | {norm(r) for r in REGIONES}
    solo_lugar = [f["nombre"] for f in filas if norm(f["nombre"]) in lugares]
    assert solo_lugar == []


def test_homonimos_de_clubes_distintos_tienen_fichas_separadas(rk, client):
    """El mismo nombre en dos clubes son dos fichas que se enlazan entre sí (las planillas no traen RUT)."""
    df = rk.df
    clubes_por_nombre = df.groupby("dep_nombre_slug").club_slug.nunique()
    nombre = clubes_por_nombre[clubes_por_nombre > 1].index[0]
    fichas = sorted(df[df.dep_nombre_slug == nombre].dep_slug.unique())
    assert len(fichas) > 1 and all(f.startswith(nombre + "-") for f in fichas)
    html = client.get(f"/deportistas/{fichas[0]}").get_data(as_text=True)
    assert "con el mismo nombre" in html and f'/deportistas/{fichas[1]}"' in html
    # Un enlace con el nombre solo (anterior a que apareciera el homónimo) lleva a la búsqueda
    r = client.get(f"/deportistas/{nombre}")
    assert r.status_code == 302 and "/buscar?q=" in r.headers["Location"]


def test_enlace_viejo_con_club_lleva_a_la_ficha_actual(client):
    r = client.get("/deportistas/maria-camila-valencia-f-hiroshima")
    assert r.status_code == 302 and r.headers["Location"].endswith("/deportistas/maria-camila-valencia-f")
    assert client.get("/deportistas/nadie-con-este-nombre-m").status_code == 404
