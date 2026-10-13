"""
Versiones de los datos en disco y carga en memoria.

    DATA_DIR/
      estado.json                  versión vigente y resultado de la última revisión
      versiones/AAAAMMDD-HHMMSS/   planillas descargadas de Drive en una actualización
      versiones/00000000-semilla/  copia de respaldo (carpeta planillas/), si Drive falló al encender sin datos

Cada proceso del servidor revisa estado.json en cada visita (solo la fecha del
archivo) y recarga los datos cuando la actualización semanal publica una versión nueva.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from zoneinfo import ZoneInfo

from . import drive
from .analisis import Ranking
from .datos import cargar_directorio, detectar_grupo, fecha_guardado

log = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # Windows: sin bloqueo entre procesos
    fcntl = None

SEMILLA = "00000000-semilla"  # versión de respaldo: queda primera al ordenar, así que se poda sola

# Planillas que se acaban de leer para validar una descarga: el servidor las usa tal cual en vez de
# volver a leer los .xlsx (en el plan gratuito de Render eso ahorra unos 20 segundos al despertar).
_recien_leida: tuple[str, object, int] | None = None


# ---------------------------------------------------------------- estado.json y bloqueos
@contextlib.contextmanager
def bloqueo(ruta: Path, esperar=True):
    """Bloqueo entre procesos. Entrega True si se obtuvo."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w") as f:
        if fcntl is None:
            yield True
            return
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if esperar else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def leer_estado(data_dir: Path) -> dict:
    """Contenido de estado.json ({} si todavía no hay)."""
    try:
        return json.loads((data_dir / "estado.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _guardar_estado(data_dir: Path, estado: dict):
    """Escribe estado.json de una vez (archivo temporal y luego reemplazo): nadie lo lee a medio escribir."""
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = data_dir / "estado.json.tmp"
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, data_dir / "estado.json")


def _ahora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- actualización desde Drive
def seleccionar(archivos: list[drive.ArchivoDrive]) -> list[drive.ArchivoDrive]:
    """Una planilla por grupo de edad: la modificada más recientemente."""
    por_grupo: dict[str, drive.ArchivoDrive] = {}
    for a in archivos:
        es_excel = a.mime in (drive.MIME_XLSX, drive.MIME_SHEETS) or a.nombre.lower().endswith(".xlsx")
        grupo = detectar_grupo(a.nombre) if es_excel else None
        if not grupo:
            continue
        if grupo not in por_grupo or a.modificado > por_grupo[grupo].modificado:
            por_grupo[grupo] = a
    return sorted(por_grupo.values(), key=lambda a: a.nombre)


def actualizar(data_dir: Path, carpeta_id: str, api_key: str | None = None,
               forzar: bool = False, conservar: int = 12) -> dict:
    """Revisa la carpeta de Drive y descarga una versión nueva si algo cambió."""
    versiones = data_dir / "versiones"
    with bloqueo(data_dir / ".actualizar.lock"):
        estado = leer_estado(data_dir)
        tmp = None
        try:
            elegidos = seleccionar(drive.listar(carpeta_id, api_key))
            if not elegidos:
                raise drive.ErrorDrive("La carpeta no tiene planillas de ranking reconocibles (RANKING SUB13…, ABSOLUTA…).")
            firma = "|".join(a.firma() for a in elegidos)
            vigente = estado.get("version") and (versiones / estado["version"]).is_dir()
            if vigente and not forzar and estado.get("firma") == firma:
                estado.update(ultima_revision=_ahora(), resultado="sin cambios", error=None)
                _guardar_estado(data_dir, estado)
                log.info("Drive: sin cambios desde la versión %s", estado["version"])
                return estado

            nombre = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
            tmp = versiones / f".descarga-{nombre}"
            tmp.mkdir(parents=True)
            for a in elegidos:
                drive.descargar(a, tmp)
            df, anio = cargar_directorio(tmp)  # valida antes de publicar
            tmp.rename(versiones / nombre)
            tmp = None
            global _recien_leida
            _recien_leida = (nombre, df, anio)
            estado.update(
                version=nombre, firma=firma, anio=anio, filas=len(df),
                archivos=[a.como_dict() for a in elegidos],
                fecha_planillas=max(a.modificado for a in elegidos).isoformat(),
                ultima_actualizacion=_ahora(), ultima_revision=_ahora(), resultado="actualizado", error=None,
            )
            _guardar_estado(data_dir, estado)
            log.info("Drive: nueva versión %s (%d filas, ranking %s)", nombre, len(df), anio)
            _podar(versiones, conservar, estado["version"])
            return estado
        except Exception as exc:
            log.exception("Falló la actualización desde Drive")
            estado.update(ultima_revision=_ahora(), resultado="error", error=str(exc))
            _guardar_estado(data_dir, estado)
            raise
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)


def _podar(versiones: Path, conservar: int, vigente: str):
    """Borra las versiones más antiguas y deja las últimas `conservar` (nunca borra la vigente)."""
    viejas = sorted(p for p in versiones.iterdir() if p.is_dir() and not p.name.startswith("."))
    for p in viejas[:-conservar]:
        if p.name != vigente:
            shutil.rmtree(p, ignore_errors=True)


# ---------------------------------------------------------------- respaldo
def instalar_semilla(data_dir: Path, semilla_dir: Path) -> dict | None:
    """Respaldo: si el servidor parte sin datos y Drive no responde (caído, sin conexión o con la página
    cambiada), publica las planillas que vienen con el sitio para no quedar sin ranking. La revisión de
    Drive las reemplaza apenas vuelve a funcionar."""
    archivos = sorted(Path(semilla_dir).glob("RANKING*.xlsx"))
    if not archivos:
        return None
    with bloqueo(data_dir / ".actualizar.lock"):
        estado = leer_estado(data_dir)
        if estado.get("version") and (data_dir / "versiones" / estado["version"]).is_dir():
            return None  # ya hay datos publicados
        destino = data_dir / "versiones" / SEMILLA
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for a in archivos:
            shutil.copy2(a, destino / a.name)
        df, anio = cargar_directorio(destino)
        global _recien_leida
        _recien_leida = (SEMILLA, df, anio)
        # La fecha de cada planilla es la que guardó la federación dentro del archivo (la del disco
        # no sirve: es la de cuando se clonó el repositorio).
        fechas = {a.name: fecha_guardado(a) for a in archivos}
        estado.update(version=SEMILLA, firma=None, anio=anio, filas=len(df),
                      archivos=[{"nombre": n, "modificado": f.isoformat()} for n, f in fechas.items()],
                      fecha_planillas=max(fechas.values()).isoformat(), resultado="respaldo")
        _guardar_estado(data_dir, estado)
        log.warning("Sin datos de Drive: se publican las %d planillas incluidas en el sitio", len(archivos))
        return estado


# ---------------------------------------------------------------- datos en memoria
class Almacen:
    """Entrega el ranking vigente y lo recarga cuando cambia la versión en disco."""

    def __init__(self, data_dir: Path, zona: str):
        self.data_dir = Path(data_dir)
        self.zona = ZoneInfo(zona)
        self._lock = threading.Lock()
        self._mtime = None
        self._estado: dict = {}
        self._version = None
        self._ranking: Ranking | None = None

    def estado(self) -> dict:
        """estado.json vigente (para el pie de página y "Cómo funciona")."""
        self._refrescar()
        return self._estado

    def ranking(self) -> Ranking | None:
        """El ranking de la versión vigente (None mientras no haya datos)."""
        self._refrescar()
        return self._ranking

    def hay_datos(self) -> bool:
        """Sin recargar nada: responde al instante aunque se estén procesando planillas."""
        return self._ranking is not None

    def _refrescar(self):
        """Recarga los datos si estado.json cambió. Lo compara por fecha de modificación, sin leerlo."""
        try:
            mtime = (self.data_dir / "estado.json").stat().st_mtime
        except FileNotFoundError:
            return
        if mtime == self._mtime:
            return
        with self._lock:
            if mtime == self._mtime:
                return
            estado = leer_estado(self.data_dir)
            version = estado.get("version")
            if version and version != self._version:
                try:
                    global _recien_leida
                    if _recien_leida and _recien_leida[0] == version:
                        _, df, anio = _recien_leida
                        _recien_leida = None
                    else:
                        df, anio = cargar_directorio(self.data_dir / "versiones" / version)
                    fecha = dt.datetime.fromisoformat(estado["fecha_planillas"]).astimezone(self.zona).date()
                    self._ranking = Ranking(df, anio, fecha).precalcular()
                    self._version = version
                    log.info("Datos cargados: versión %s", version)
                except Exception:
                    log.exception("No se pudo cargar la versión %s; se mantiene la anterior", version)
            self._estado = estado
            self._mtime = mtime
