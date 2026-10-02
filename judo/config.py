"""Configuración leída de variables de entorno (o de un archivo .env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _bool(nombre: str, defecto: bool) -> bool:
    v = os.environ.get(nombre)
    return defecto if v is None else v.strip().lower() in ("1", "true", "si", "sí", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    # Dominios de correo autorizados, separados por coma.
    DOMINIOS_PERMITIDOS = [d.strip().lower().lstrip("@")
                           for d in os.environ.get("DOMINIOS_PERMITIDOS", "mail.pucv.cl").split(",") if d.strip()]

    DRIVE_CARPETA_ID = os.environ.get("DRIVE_CARPETA_ID", "1g2ZvhjbvHZ9SJYYw8cqsdCQn5ZY3WESf")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or None
    DATA_DIR = Path(os.environ.get("DATA_DIR", RAIZ / "data"))
    ZONA_HORARIA = os.environ.get("ZONA_HORARIA", "America/Santiago")
    # Formato crontab: minuto hora día mes día-semana. Por defecto, domingos 23:00.
    ACTUALIZACION_CRON = os.environ.get("ACTUALIZACION_CRON", "0 23 * * sun")
    PROGRAMADOR = _bool("PROGRAMADOR", True)
    VERSIONES_A_CONSERVAR = int(os.environ.get("VERSIONES_A_CONSERVAR", "12"))

    SESSION_COOKIE_SECURE = _bool("COOKIE_SEGURA", True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_NAME = "judo_sesion"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7
