"""Revisión automática de la carpeta de Drive (por defecto, domingos a las 23:00 de Chile)."""
from __future__ import annotations

import atexit
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .almacen import actualizar, fcntl, leer_estado

log = logging.getLogger(__name__)


def proxima_revision(cron: str, zona: str) -> dt.datetime | None:
    tz = ZoneInfo(zona)
    return CronTrigger.from_crontab(cron, timezone=tz).get_next_fire_time(None, dt.datetime.now(tz))


def _hace_falta_revisar(estado: dict, dias: int = 8) -> bool:
    if not estado.get("version") or not estado.get("ultima_revision"):
        return True
    ultima = dt.datetime.fromisoformat(estado["ultima_revision"])
    return dt.datetime.now(dt.timezone.utc) - ultima > dt.timedelta(days=dias)


def iniciar(app) -> BackgroundScheduler | None:
    cfg = app.config
    if not cfg["PROGRAMADOR"]:
        return None
    data_dir = cfg["DATA_DIR"]
    data_dir.mkdir(parents=True, exist_ok=True)

    # Con varios procesos del servidor, solo uno programa la tarea.
    lock = open(data_dir / ".programador.lock", "w")
    if fcntl is not None:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return None

    def tarea():
        try:
            actualizar(data_dir, cfg["DRIVE_CARPETA_ID"], cfg["GOOGLE_API_KEY"],
                       conservar=cfg["VERSIONES_A_CONSERVAR"])
        except Exception:
            pass  # ya quedó registrado en el log y en estado.json
        # Deja los datos cargados y la portada calculada antes de que llegue una visita.
        app.extensions["almacen"].ranking()

    sched = BackgroundScheduler(timezone=ZoneInfo(cfg["ZONA_HORARIA"]))
    sched.add_job(tarea, CronTrigger.from_crontab(cfg["ACTUALIZACION_CRON"], timezone=ZoneInfo(cfg["ZONA_HORARIA"])),
                  id="drive-semanal", coalesce=True, max_instances=1, misfire_grace_time=6 * 3600)
    if _hace_falta_revisar(leer_estado(data_dir)):
        # Primera carga, o el servidor estuvo apagado/dormido y se saltó la revisión semanal.
        sched.add_job(tarea, id="drive-al-iniciar")
    sched.start()
    app.extensions["programador"] = (sched, lock)
    atexit.register(lambda: sched.shutdown(wait=False))
    log.info("Revisión de Drive programada: '%s' (%s)", cfg["ACTUALIZACION_CRON"], cfg["ZONA_HORARIA"])
    return sched
