"""
Ingreso con cuentas de Google, limitado a los dominios de DOMINIOS_PERMITIDOS
(por defecto, mail.pucv.cl).

La restricción se aplica en el servidor: Google confirma el correo y aquí se
revisa que esté verificado y que su dominio esté autorizado. El parámetro "hd"
que se envía a Google solo sugiere la cuenta correcta en la pantalla de Google;
no es la barrera de seguridad.
"""
from __future__ import annotations

import logging

from authlib.integrations.flask_client import OAuth, OAuthError
from flask import (Blueprint, current_app, redirect, render_template, request,
                   session, url_for)

log = logging.getLogger(__name__)
bp = Blueprint("auth", __name__)
oauth = OAuth()

# Páginas que se pueden ver sin haber ingresado.
PUBLICAS = {"auth.login", "auth.login_google", "auth.callback", "auth.logout", "static", "vistas.salud"}


def correo_permitido(email: str | None, verificado, dominios: list[str]) -> bool:
    if not email or verificado is not True or email.count("@") != 1:
        return False
    return email.rsplit("@", 1)[1].strip().lower() in dominios


def _destino_seguro(url: str | None) -> str | None:
    """Solo rutas internas, para no redirigir a otros sitios tras el ingreso."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


def init_app(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        client_kwargs={"scope": "openid email profile"},
    )

    @app.before_request
    def exigir_ingreso():
        if request.endpoint in PUBLICAS:
            return None
        usuario = session.get("usuario")
        # Se revisa en cada visita por si cambian los dominios autorizados.
        if usuario and correo_permitido(usuario.get("email"), True, app.config["DOMINIOS_PERMITIDOS"]):
            return None
        session.pop("usuario", None)
        siguiente = request.full_path.rstrip("?") if request.method == "GET" and request.path != "/" else None
        return redirect(url_for("auth.login", next=siguiente))

    @app.context_processor
    def usuario_actual():
        return {"usuario": session.get("usuario")}


@bp.get("/ingresar")
def login():
    if session.get("usuario"):
        return redirect(url_for("vistas.resumen"))
    destino = _destino_seguro(request.args.get("next"))
    if destino:
        session["siguiente"] = destino
    cfg = current_app.config
    return render_template(
        "login.html",
        error=request.args.get("error"),
        intento=session.pop("intento", None),
        dominios=cfg["DOMINIOS_PERMITIDOS"],
        configurado=bool(cfg["GOOGLE_CLIENT_ID"] and cfg["GOOGLE_CLIENT_SECRET"]),
    )


@bp.get("/ingresar/google")
def login_google():
    cfg = current_app.config
    if not (cfg["GOOGLE_CLIENT_ID"] and cfg["GOOGLE_CLIENT_SECRET"]):
        return redirect(url_for("auth.login"))
    extra = {"prompt": "select_account"}
    if len(cfg["DOMINIOS_PERMITIDOS"]) == 1:
        extra["hd"] = cfg["DOMINIOS_PERMITIDOS"][0]
    return oauth.google.authorize_redirect(url_for("auth.callback", _external=True), **extra)


@bp.get("/auth/callback")
def callback():
    try:
        token = oauth.google.authorize_access_token()
    except OAuthError as exc:
        log.info("Ingreso cancelado o inválido: %s", exc)
        return redirect(url_for("auth.login", error="cancelado"))
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    siguiente = session.pop("siguiente", None)
    session.clear()
    if not correo_permitido(email, info.get("email_verified"), current_app.config["DOMINIOS_PERMITIDOS"]):
        log.info("Ingreso rechazado para %s", email or "(sin correo)")
        session["intento"] = email
        return redirect(url_for("auth.login", error="dominio"))
    session.permanent = True
    session["usuario"] = {"email": email, "nombre": info.get("given_name") or info.get("name") or email,
                          "foto": info.get("picture")}
    log.info("Ingreso de %s", email)
    return redirect(_destino_seguro(siguiente) or url_for("vistas.resumen"))


@bp.post("/salir")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
