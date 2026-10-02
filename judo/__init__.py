"""Sitio web del Ranking Nacional de Judo Chile."""
from __future__ import annotations

import datetime as dt
import logging
import secrets
from zoneinfo import ZoneInfo

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .almacen import Almacen
from .config import Config

log = logging.getLogger(__name__)


def fmt_puntos(x) -> str:
    """Formato chileno: punto de miles y coma decimal (1.234,5)."""
    x = float(x or 0)
    s = f"{x:,.1f}" if abs(x - round(x)) > 0.05 else f"{x:,.0f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(v) -> str:
    v = float(v or 0) * 100
    return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + " %"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        log.warning("SECRET_KEY no está definida: se usa una temporal y las sesiones se pierden al reiniciar")
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Detrás de un proxy HTTPS (Render, Railway, Cloud Run, nginx…) las URL de retorno salen con https.
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

    app.jinja_env.filters.update(pts=fmt_puntos, pct=fmt_pct, fecha=fecha)

    from . import auth, vistas
    auth.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(vistas.bp)

    @app.after_request
    def cabeceras(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: https://*.googleusercontent.com; "
            "script-src 'self'; form-action 'self' https://accounts.google.com; frame-ancestors 'none'")
        if request.endpoint != "static":
            resp.headers.setdefault("Cache-Control", "private, no-store")
        return resp

    from . import programador
    programador.iniciar(app)
    return app
