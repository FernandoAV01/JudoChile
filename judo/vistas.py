"""Páginas del sitio."""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .datos import SEXOS
from .programador import proxima_revision

bp = Blueprint("vistas", __name__)


def _almacen():
    return current_app.extensions["almacen"]


def _ranking():
    r = _almacen().ranking()
    if r is None:
        abort(503)
    return r


@bp.app_context_processor
def contexto_comun():
    cfg = current_app.config
    r = _almacen().ranking()
    return {
        "rk": r,
        "estado": _almacen().estado(),
        "proxima": proxima_revision(cfg["ACTUALIZACION_CRON"], cfg["ZONA_HORARIA"]),
        "grupos_nav": r.grupos() if r else [],
        "SEXOS": SEXOS,
    }


@bp.app_errorhandler(404)
def no_encontrado(_):
    return render_template("error.html", titulo="Página no encontrada",
                           texto="La dirección no existe o cambió con la última actualización del ranking."), 404


@bp.app_errorhandler(503)
def sin_datos(_):
    if _almacen().estado().get("resultado") == "error":
        return render_template("error.html", titulo="No pudimos descargar el ranking",
                               texto="La carpeta de la federación no respondió. El sitio vuelve a intentarlo "
                                     "solo cada 30 minutos.", recargar=60), 503
    return render_template("error.html", titulo="Estamos cargando el ranking",
                           texto="El servidor recién se encendió y está descargando las planillas desde la carpeta "
                                 "de la federación. Tarda menos de un minuto.", recargar=10), 503


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


@bp.get("/categorias")
def categorias_inicio():
    grupos = _ranking().grupos()
    return redirect(url_for("vistas.grupo", grupo=grupos[-1][2]))


@bp.get("/categorias/<grupo>")
def grupo(grupo):
    r = _ranking()
    info = next((g for g in r.grupos() if g[2] == grupo), None)
    if not info:
        abort(404)
    return render_template("grupo.html", seccion="categorias", grupo=info, grupo_slug=grupo,
                           por_sexo=r.categorias_de(grupo))


@bp.get("/categorias/<grupo>/<cat>")
def categoria(grupo, cat):
    r = _ranking()
    info, filas = r.categoria(grupo, cat)
    if not info:
        abort(404)
    maximo = max([f["total"] for f in filas] + [1])
    return render_template("categoria.html", seccion="categorias", grupo_slug=grupo, cat=info, filas=filas,
                           maximo=maximo, por_sexo=r.categorias_de(grupo))


@bp.get("/clubes")
def clubes():
    r = _ranking()
    return render_template("clubes.html", seccion="clubes", clubes=r.lista_clubes())


@bp.get("/clubes/<slug>")
def club(slug):
    info = _ranking().club(slug)
    if not info:
        abort(404)
    return render_template("club.html", seccion="clubes", club=info, n_clubes=len(_ranking().clubes))


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
    return render_template("metodologia.html", seccion="metodologia", res=r.resumen())
