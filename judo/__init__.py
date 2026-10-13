"""Sitio web del Ranking Nacional de Judo Chile.

create_app() arma la aplicación: configuración, compresión, caché de archivos estáticos, filtros de las
plantillas, páginas (vistas.py), cabeceras de seguridad y la revisión semanal de Drive (programador.py).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, request
from flask_compress import Compress
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix

from . import programador, ubicaciones, vistas
from .almacen import Almacen
from .config import Config


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
    """Arma la aplicación. `config` reemplaza valores de Config (lo usan las pruebas)."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Detrás del proxy del servicio de hosting, los logs muestran la IP real del visitante.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    # Páginas, estilos y scripts viajan comprimidos (gunicorn no lo hace): un tercio o menos del peso en el celular.
    Compress(app)
    # "/clubes/" lleva a lo mismo que "/clubes" (direcciones escritas a mano o copiadas con la barra final).
    app.url_map.strict_slashes = False
    _huellas_en_estaticos(app)
    _filtros_de_plantillas(app)

    app.extensions["almacen"] = Almacen(app.config["DATA_DIR"], app.config["ZONA_HORARIA"])
    app.register_blueprint(vistas.bp)
    app.after_request(_cabeceras)
    programador.iniciar(app)
    return app


def _huellas_en_estaticos(app: Flask):
    """Estilos, script e imágenes llevan la huella de su contenido en la dirección (?v=…): el navegador
    los guarda un año y los pide de nuevo solo cuando cambian. Las fuentes no cambian nunca y van sin
    huella, igual que en estilos.css, para que la precarga sirva (si se reemplaza una, cambiarle el nombre)."""
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 24 * 3600
    huellas: dict[str, str | None] = {}

    @app.url_defaults
    def agregar_huella(endpoint, values):
        archivo = values.get("filename") if endpoint == "static" else None
        if not archivo or archivo.startswith("fuentes/"):
            return
        if archivo not in huellas:
            ruta = Path(app.static_folder) / archivo
            huellas[archivo] = hashlib.sha1(ruta.read_bytes()).hexdigest()[:10] if ruta.is_file() else None
        if huellas[archivo]:
            values["v"] = huellas[archivo]


def _filtros_de_plantillas(app: Flask):
    """Formatos para las plantillas: {{ x|pts }}, {{ v|pct }}, {{ f|fecha }}, {{ n|pl('club', 'clubes') }}…"""
    zona = ZoneInfo(app.config["ZONA_HORARIA"])

    def fecha(v, con_hora=False):
        """Fecha (y hora, si se pide) en la hora de Chile: 04-09-2026 o 04-09-2026 13:30."""
        if not v:
            return "—"
        if isinstance(v, str):
            v = dt.datetime.fromisoformat(v)
        if isinstance(v, dt.datetime):
            v = v.astimezone(zona)
            texto = v.strftime("%d-%m-%Y %H:%M") if con_hora else v.strftime("%d-%m-%Y")
        else:
            texto = v.strftime("%d-%m-%Y")
        # Sin cortes de línea en los guiones de la fecha ("04-" arriba y "09-2026" abajo)
        return Markup('<span class="nw">%s</span>') % texto

    def enumerar(items) -> str:
        """['A', 'B', 'C'] -> 'A, B y C'"""
        items = list(items)
        return " y ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else "".join(items)

    def pl(n, singular: str, plural: str) -> str:
        """Elige singular o plural según n: {{ n|pl('podio', 'podios') }}"""
        return singular if n == 1 else plural

    app.jinja_env.filters.update(pts=fmt_puntos, pct=fmt_pct, fecha=fecha, enumerar=enumerar, pl=pl,
                                 region_larga=ubicaciones.nombre_largo, region_slug=ubicaciones.slug_region)


def _cabeceras(resp):
    """Cabeceras de seguridad y de caché de todas las respuestas."""
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    # Todo sale del propio sitio. 'unsafe-inline' en estilos: el largo de cada barra va en style="width:…".
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; img-src 'self' data:; script-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'")
    if request.is_secure:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    # Los datos cambian como máximo una vez por semana: 5 minutos de caché bastan.
    if request.endpoint != "static" and resp.status_code == 200:
        resp.headers.setdefault("Cache-Control", "public, max-age=300")
    return resp
