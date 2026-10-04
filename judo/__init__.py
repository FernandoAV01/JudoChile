"""Sitio web del Ranking Nacional de Judo Chile."""
from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from . import ubicaciones
from .almacen import Almacen
from .config import Config

log = logging.getLogger(__name__)


def fmt_puntos(x) -> str:
    """Formato chileno: punto de miles y coma decimal (1.234,5)."""
    x = float(x or 0)
    s = f"{x:,.1f}" if abs(x - round(x)) > 0.05 else f"{x:,.0f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(v) -> str:
    """0,3 % · 3 % · 45 %: decimales solo bajo 10 % y cuando aportan."""
    v = float(v or 0) * 100
    texto = f"{v:.1f}" if v < 10 else f"{v:.0f}"
    return texto.removesuffix(".0").replace(".", ",") + " %"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Detrás del proxy del servicio de hosting, los logs muestran la IP real del visitante.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    zona = ZoneInfo(app.config["ZONA_HORARIA"])
    app.extensions["almacen"] = Almacen(app.config["DATA_DIR"], app.config["ZONA_HORARIA"])

    def fecha(v, con_hora=False):
        if not v:
            return "—"
        if isinstance(v, str):
            v = dt.datetime.fromisoformat(v)
        if isinstance(v, dt.datetime):
            v = v.astimezone(zona)
            return v.strftime("%d-%m-%Y %H:%M") if con_hora else v.strftime("%d-%m-%Y")
        return v.strftime("%d-%m-%Y")

    def enumerar(items) -> str:
        """['A', 'B', 'C'] -> 'A, B y C'"""
        items = list(items)
        return " y ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else "".join(items)

    def pl(n, singular: str, plural: str) -> str:
        """Elige singular o plural según n: {{ n|pl('podio', 'podios') }}"""
        return singular if n == 1 else plural

    app.jinja_env.filters.update(pts=fmt_puntos, pct=fmt_pct, fecha=fecha, enumerar=enumerar, pl=pl,
                                 region_larga=ubicaciones.nombre_largo)

    from . import vistas
    app.register_blueprint(vistas.bp)

    @app.after_request
    def cabeceras(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'")
        # Los datos cambian como máximo una vez por semana: 5 minutos de caché bastan.
        if request.endpoint != "static" and resp.status_code == 200:
            resp.headers.setdefault("Cache-Control", "public, max-age=300")
        return resp

    from . import programador
    programador.iniciar(app)
    return app
