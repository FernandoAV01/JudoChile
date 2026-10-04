"""Páginas del sitio."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .datos import SEXOS
from .programador import proxima_revision
from .ubicaciones import NOMBRE_ZONA, REGIONES, ZONA_DE_REGION, ZONAS

bp = Blueprint("vistas", __name__)


def _almacen():
    return current_app.extensions["almacen"]


def _ranking():
    r = _almacen().ranking()
    if r is None:
        abort(503)
    return r


def _zona() -> str:
    """Zona elegida en el filtro (?zona=norte|centro|sur); '' = todo el país."""
    z = request.args.get("zona", "")
    return z if z in NOMBRE_ZONA else ""


def _grupo(r, grupo: str):
    info = next((g for g in r.grupos() if g[2] == grupo), None)
    if not info:
        abort(404)
    return info


@bp.app_context_processor
def contexto_comun():
    cfg = current_app.config
    r = _almacen().ranking()
    zona = _zona()
    return {
        "rk": r,
        "estado": _almacen().estado(),
        "proxima": proxima_revision(cfg["ACTUALIZACION_CRON"], cfg["ZONA_HORARIA"]),
        "grupos_nav": r.grupos() if r else [],
        "SEXOS": SEXOS,
        "ZONAS": ZONAS,
        "zona": zona,
        "zona_nombre": NOMBRE_ZONA.get(zona, ""),
        "regiones_de_zona": {z: [x for x in REGIONES if ZONA_DE_REGION[x] == z] for z, _ in ZONAS},
    }


@bp.app_errorhandler(404)
def no_encontrado(_):
    return render_template("error.html", titulo="No encontramos esta página",
                           texto="La dirección no existe o cambió con la última actualización del ranking."), 404


@bp.app_errorhandler(503)
def sin_datos(_):
    if _almacen().estado().get("resultado") == "error":
        return render_template("error.html", titulo="No pudimos descargar el ranking",
                               texto="La carpeta de la federación no respondió. El sitio lo vuelve a intentar "
                                     "solo cada 30 minutos.", recargar=60), 503
    return render_template("error.html", titulo="Estamos cargando el ranking",
                           texto="El servidor se acaba de encender y está descargando las planillas de la "
                                 "federación. Tarda menos de un minuto.", recargar=10), 503


@bp.get("/salud")
def salud():
    return {"ok": True, "datos": _almacen().hay_datos()}


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


# ---------------------------------------------------------------- Deportistas, búsqueda y metodología
@bp.get("/deportistas/<slug>")
def deportista(slug):
    info = _ranking().deportista(slug)
    if not info:
        abort(404)
    return render_template("deportista.html", seccion="", dep=info)


@bp.get("/buscar")
def buscar():
    q = request.args.get("q", "").strip()[:80]
    return render_template("buscar.html", seccion="", q=q, res=_ranking().buscar(q))


@bp.get("/metodologia")
def metodologia():
    r = _ranking()
    return render_template("metodologia.html", seccion="metodologia", res=r.resumen(),
                           clubes=r.lista_clubes())
