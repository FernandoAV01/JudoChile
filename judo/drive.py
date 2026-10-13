"""
Lectura de la carpeta pública de Google Drive donde la federación publica las planillas.

Hay dos formas de listar la carpeta:
  * Con GOOGLE_API_KEY: la API oficial de Drive (v3). Es la opción estable.
  * Sin clave: se lee la página pública de la carpeta, que trae la lista de
    archivos incrustada. Funciona sin configuración, pero depende de cómo Google
    arma esa página; si cambia, el error lo indica y basta con definir la clave.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) JudoChileRanking/1.0"}
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_SHEETS = "application/vnd.google-apps.spreadsheet"


class ErrorDrive(RuntimeError):
    """No se pudo listar o descargar la carpeta; el mensaje explica qué revisar."""


@dataclass(frozen=True)
class ArchivoDrive:
    id: str
    nombre: str
    mime: str
    modificado: dt.datetime  # UTC
    tamano: int | None = None

    def firma(self) -> str:
        """Identifica esta versión del archivo: cambia si la federación lo reemplaza o lo edita."""
        return f"{self.id}:{self.modificado.isoformat()}:{self.tamano}"

    def como_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "mime": self.mime,
                "modificado": self.modificado.isoformat(), "tamano": self.tamano}


def listar(carpeta_id: str, api_key: str | None = None) -> list[ArchivoDrive]:
    """Archivos de la carpeta: con la API si hay clave; si no, desde la página pública."""
    archivos = _listar_api(carpeta_id, api_key) if api_key else _listar_pagina(carpeta_id)
    log.info("Drive: %d archivos en la carpeta", len(archivos))
    return archivos


def _listar_api(carpeta_id: str, api_key: str) -> list[ArchivoDrive]:
    params = {
        "q": f"'{carpeta_id}' in parents and trashed = false",
        "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)",
        "pageSize": 1000, "key": api_key,
    }
    salida, token = [], None
    while True:
        if token:
            params["pageToken"] = token
        r = requests.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            raise ErrorDrive(f"La API de Drive respondió {r.status_code}: {r.text[:300]}")
        data = r.json()
        for f in data.get("files", []):
            salida.append(ArchivoDrive(
                id=f["id"], nombre=f["name"], mime=f["mimeType"],
                modificado=dt.datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00")),
                tamano=int(f["size"]) if f.get("size") else None))
        token = data.get("nextPageToken")
        if not token:
            return salida


def _listar_pagina(carpeta_id: str) -> list[ArchivoDrive]:
    url = f"https://drive.google.com/drive/folders/{carpeta_id}"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise ErrorDrive(f"No se pudo abrir la carpeta de Drive ({r.status_code}). ¿Sigue siendo pública?")
    m = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'(.*?)';", r.text, re.S)
    if not m:
        raise ErrorDrive("La página de la carpeta cambió de formato. Define GOOGLE_API_KEY para usar la API oficial.")
    crudo = re.sub(r"\\x([0-9a-fA-F]{2})", lambda x: chr(int(x.group(1), 16)), m.group(1)).replace("\\/", "/")
    # Cada archivo es una lista: [0] id, [1] carpetas que lo contienen, [2] nombre, [3] tipo (MIME),
    # [9] fecha de modificación en milisegundos, [13] tamaño en bytes.
    try:
        filas = json.loads(crudo)[0] or []
        salida = []
        for f in filas:
            if carpeta_id not in (f[1] or []):
                continue
            salida.append(ArchivoDrive(
                id=f[0], nombre=f[2], mime=f[3],
                modificado=dt.datetime.fromtimestamp(f[9] / 1000, tz=dt.timezone.utc),
                tamano=int(f[13]) if isinstance(f[13], int) else None))
        return salida
    except (ValueError, IndexError, TypeError) as exc:
        raise ErrorDrive(f"No se pudo interpretar la lista de archivos de Drive ({exc}). "
                         "Define GOOGLE_API_KEY para usar la API oficial.") from None


def descargar(archivo: ArchivoDrive, destino: Path) -> Path:
    """Descarga el archivo como .xlsx (las hojas de cálculo de Google se exportan)."""
    if archivo.mime == MIME_SHEETS:
        url = f"https://docs.google.com/spreadsheets/d/{archivo.id}/export?format=xlsx"
    else:
        url = f"https://drive.usercontent.google.com/download?id={archivo.id}&export=download&confirm=t"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        raise ErrorDrive(f"No se pudo descargar '{archivo.nombre}' ({r.status_code}); no llegó un archivo Excel.")
    nombre = archivo.nombre if archivo.nombre.lower().endswith(".xlsx") else archivo.nombre + ".xlsx"
    ruta = destino / nombre.replace("/", "_")
    ruta.write_bytes(r.content)
    return ruta
