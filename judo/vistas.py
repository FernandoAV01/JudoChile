"""Páginas del sitio, en el orden del menú, y al final las páginas de error y los archivos técnicos
(chequeo de salud para Render, robots.txt, sitemap.xml y favicon.ico)."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from markupsafe import escape

from .datos import GRUPOS_MENORES, SEXOS
from .programador import proxima_revision
from .ubicaciones import NOMBRE_ZONA, REGIONES, ZONA_DE_REGION, ZONAS, slug_region

bp = Blueprint("vistas", __name__)


# ---------------------------------------------------------------- ayudas comunes
def _almacen():
    return current_app.extensions["almacen"]


def _ranking():
    """El ranking vigente. Si todavía no hay datos, responde la página "Estamos cargando" (503)."""
    r = _almacen().ranking()
    if r is None:
        abort(503)
    return r


def _zona() -> str:
    """Zona elegida en el filtro (?zona=norte|centro|sur); '' = todo el país."""
    z = request.args.get("zona", "")
    return z if z in NOMBRE_ZONA else ""


def _grupo(r, grupo: str):
    """(etiqueta, orden, slug) del grupo de edad de la dirección; 404 si no existe."""
    info = next((g for g in r.grupos() if g[2] == grupo), None)
    if not info:
        abort(404)
    return info


def _no_indexar(r) -> bool:
    """Páginas que los buscadores no deben indexar: las de menores de edad (sus fichas y los rankings
    de Sub 13, Sub 15 y Sub 18) y los resultados de búsqueda."""
    args = request.view_args or {}
    if request.endpoint == "vistas.buscar" or args.get("grupo") in GRUPOS_MENORES:
        return True
    return request.endpoint == "vistas.deportista" and r is not None and args.get("slug") in r.menores


@bp.app_context_processor
def contexto_comun():
    """Variables que usan todas las plantillas (menú, filtro de zona, pie de página…)."""
    cfg = current_app.config
    r = _almacen().ranking()
    zona = _zona()
    return {
        "rk": r,
        # En las demás páginas, los nombres de menores llevan data-nosnippet (Google no los muestra)
        "menores": r.menores if r else frozenset(),
        "no_indexar": _no_indexar(r),
        "estado": _almacen().estado(),
        "proxima": proxima_revision(cfg["ACTUALIZACION_CRON"], cfg["ZONA_HORARIA"]),
        "grupos_nav": r.grupos() if r else [],
        "SEXOS": SEXOS,
        "ZONAS": ZONAS,
        "zona": zona,
        "zona_nombre": NOMBRE_ZONA.get(zona, ""),
        "NOMBRE_ZONA": NOMBRE_ZONA,
        "regiones_de_zona": {z: [x for x in REGIONES if ZONA_DE_REGION[x] == z] for z, _ in ZONAS},
    }


# ---------------------------------------------------------------- Resumen (portada)
@bp.get("/")
def resumen():
    r = _ranking()
    return render_template(
        "resumen.html", seccion="resumen", res=r.resumen(), clubes=r.lista_clubes()[:10],
        mapa=r.mapa_podios(), mejores=r.mejores_por_grupo(), figuras=r.figuras(),
        pelea=r.pelea_primer_lugar(), multi=r.multi_edad(), participacion=r.participacion())


# ---------------------------------------------------------------- Categorías (ranking de deportistas)
@bp.get("/categorias")
def categorias_inicio():
    grupos = _ranking().grupos()
    return redirect(url_for("vistas.grupo", grupo=grupos[-1][2], zona=_zona() or None))


@bp.get("/categorias/<grupo>")
def grupo(grupo):
    r = _ranking()
    return render_template("grupo.html", seccion="categorias", grupo=_grupo(r, grupo), grupo_slug=grupo,
                           por_sexo=r.categorias_de(grupo, _zona()))


@bp.get("/categorias/<grupo>/<cat>")
def categoria(grupo, cat):
    r = _ranking()
    info, filas = r.categoria(grupo, cat, _zona())
    if not info:
        abort(404)
    maximo = max([f["total"] for f in filas] + [1])
    return render_template("categoria.html", seccion="categorias", grupo_slug=grupo, cat=info, filas=filas,
                           maximo=maximo, por_sexo=r.categorias_de(grupo))


# ---------------------------------------------------------------- Clubes
@bp.get("/clubes")
def clubes():
    return render_template("clubes.html", seccion="clubes", clubes=_ranking().lista_clubes(_zona()))


@bp.get("/clubes/<slug>")
def club(slug):
    r = _ranking()
    info = r.club(slug)
    if not info:
        abort(404)
    zona_club = r.lista_clubes(info["zona"]) if info.get("zona") else []
    puesto_zona = next((c["puesto"] for c in zona_club if c["club_slug"] == slug), None)
    return render_template("club.html", seccion="clubes", club=info, n_clubes=len(r.clubes),
                           puesto_zona=puesto_zona, n_zona=len(zona_club))


# ---------------------------------------------------------------- Categorías por clubes (ranking de clubes)
@bp.get("/categorias-por-clubes")
def por_clubes_inicio():
    grupos = _ranking().grupos()
    return redirect(url_for("vistas.por_clubes_grupo", grupo=grupos[-1][2], zona=_zona() or None))


@bp.get("/categorias-por-clubes/<grupo>")
def por_clubes_grupo(grupo):
    r = _ranking()
    info = _grupo(r, grupo)
    return render_template("por_clubes.html", seccion="por-clubes", grupo=info, grupo_slug=grupo, cat=None,
                           nombre=info[0], clubes=r.clubes_en(grupo, "", _zona()), por_sexo=r.categorias_de(grupo))


@bp.get("/categorias-por-clubes/<grupo>/<cat>")
def por_clubes_categoria(grupo, cat):
    r = _ranking()
    info = _grupo(r, grupo)
    cat_info, _ = r.categoria(grupo, cat)
    if not cat_info:
        abort(404)
    return render_template("por_clubes.html", seccion="por-clubes", grupo=info, grupo_slug=grupo, cat=cat_info,
                           nombre=cat_info["categoria"], clubes=r.clubes_en(grupo, cat, _zona()),
                           por_sexo=r.categorias_de(grupo))


# ---------------------------------------------------------------- Regiones
@bp.get("/regiones")
def regiones():
    r = _ranking()
    zona = _zona()
    return render_template("regiones.html", seccion="regiones", regiones=r.regiones(zona), geo=r.regiones_geo(zona),
                           mapa=r.mapa_regiones(zona), resumen_reg=r.resumen_regiones(zona))


@bp.get("/regiones/<slug>")
def region(slug):
    info = _ranking().region(slug)
    if not info:
        abort(404)
    return render_template("region.html", seccion="regiones", reg=info)


# ---------------------------------------------------------------- Deportistas y búsqueda
@bp.get("/deportistas/<slug>")
def deportista(slug):
    r = _ranking()
    info = r.deportista(slug)
    if not info:
        # Un enlace viejo (compartido antes de una actualización) lleva a la ficha que corresponde hoy.
        vigente = r.ficha_vigente(slug)
        if vigente and vigente[0] == "ficha":
            return redirect(url_for("vistas.deportista", slug=vigente[1]))
        if vigente:
            return redirect(url_for("vistas.buscar", q=vigente[1]))
        abort(404)
    return render_template("deportista.html", seccion="", dep=info)


@bp.get("/buscar")
def buscar():
    q = request.args.get("q", "").strip()[:80]
    return render_template("buscar.html", seccion="", q=q, res=_ranking().buscar(q))


# ---------------------------------------------------------------- Cómo funciona
@bp.get("/metodologia")
def metodologia():
    r = _ranking()
    return render_template("metodologia.html", seccion="metodologia", res=r.resumen(),
                           clubes=r.lista_clubes())


# ---------------------------------------------------------------- páginas de error
@bp.app_errorhandler(404)
def no_encontrado(_):
    return render_template("error.html", titulo="No encontramos esta página",
                           texto="La dirección no existe o cambió con la última actualización del ranking."), 404


@bp.app_errorhandler(503)
def sin_datos(_):
    """Sin datos todavía: "Estamos cargando" mientras se descargan, o el aviso si la descarga falló."""
    if _almacen().estado().get("resultado") == "error":
        return render_template("error.html", titulo="No pudimos descargar el ranking",
                               texto="La carpeta de la federación no respondió. El sitio lo vuelve a intentar "
                                     "solo cada 30 minutos.", recargar=60), 503
    return render_template("error.html", titulo="Estamos cargando el ranking",
                           texto="El servidor se acaba de encender y está descargando las planillas de la "
                                 "federación. Tarda menos de un minuto.", recargar=10), 503


@bp.app_errorhandler(500)
def error_interno(_):
    texto = "Ocurrió un error inesperado al armar esta página. Prueba de nuevo en un momento."
    try:
        return render_template("error.html", titulo="Algo falló de nuestro lado", texto=texto), 500
    except Exception:  # si el error viene de la plantilla base, al menos una página simple
        return f"<!doctype html><title>Error</title><h1>Algo falló de nuestro lado</h1><p>{texto}</p>", 500


# ---------------------------------------------------------------- archivos técnicos
@bp.get("/salud")
def salud():
    """Chequeo de salud de Render: responde siempre, haya datos o no (si no, Render reiniciaría el servidor)."""
    return {"ok": True, "datos": _almacen().hay_datos()}


@bp.get("/robots.txt")
def robots():
    texto = f"User-agent: *\nAllow: /\n\nSitemap: {url_for('vistas.mapa_del_sitio', _external=True)}\n"
    return current_app.response_class(texto, mimetype="text/plain")


@bp.get("/sitemap.xml")
def mapa_del_sitio():
    """Páginas principales para los buscadores. Las fichas de deportistas se encuentran por los enlaces,
    y las edades de menores no se incluyen porque esas páginas no se indexan."""
    r = _ranking()
    urls = [url_for(e, _external=True) for e in ("vistas.resumen", "vistas.clubes", "vistas.regiones", "vistas.metodologia")]
    cats = r.cats[~r.cats.grupo_slug.isin(GRUPOS_MENORES)]
    for c in cats.drop_duplicates("grupo_slug").itertuples():
        urls += [url_for("vistas.grupo", grupo=c.grupo_slug, _external=True),
                 url_for("vistas.por_clubes_grupo", grupo=c.grupo_slug, _external=True)]
    for c in cats.itertuples():
        urls += [url_for("vistas.categoria", grupo=c.grupo_slug, cat=c.cat_slug, _external=True),
                 url_for("vistas.por_clubes_categoria", grupo=c.grupo_slug, cat=c.cat_slug, _external=True)]
    urls += [url_for("vistas.club", slug=s, _external=True) for s in r.clubes.club_slug]
    urls += [url_for("vistas.region", slug=slug_region(x), _external=True) for x in r.regiones_t.region if x]
    xml = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    return current_app.response_class(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml}</urlset>',
        mimetype="application/xml")


@bp.get("/favicon.ico")
def favicon():
    # Algunos navegadores y buscadores piden este archivo aunque la página indique otro ícono.
    return current_app.send_static_file("img/favicon.png")
