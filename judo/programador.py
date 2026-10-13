"""Revisión automática de la carpeta de Drive (por defecto, domingos a las 23:00 de Chile)."""
from __future__ import annotations

import atexit
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .almacen import actualizar, fcntl, instalar_semilla, leer_estado

log = logging.getLogger(__name__)
REINTENTO_MINUTOS = 30


def proxima_revision(cron: str, zona: str) -> dt.datetime | None:
    """Cuándo toca la próxima revisión automática (se muestra en el pie de página)."""
    tz = ZoneInfo(zona)
    return CronTrigger.from_crontab(cron, timezone=tz).get_next_fire_time(None, dt.datetime.now(tz))


def _hace_falta_revisar(estado: dict, dias: int = 8) -> bool:
    """Al encender: hay que revisar Drive si no hay datos o si la última revisión tiene más de `dias` días."""
    if not estado.get("version") or not estado.get("ultima_revision"):
        return True
    ultima = dt.datetime.fromisoformat(estado["ultima_revision"])
    return dt.datetime.now(dt.timezone.utc) - ultima > dt.timedelta(days=dias)


def iniciar(app) -> BackgroundScheduler | None:
    """Programa la revisión semanal de Drive (y una al encender, si hace falta). Devuelve None si está
    desactivada (PROGRAMADOR=0) o si otro proceso del servidor ya la programó."""
    cfg = app.config
    if not cfg["PROGRAMADOR"]:
        return None
    data_dir = cfg["DATA_DIR"]
    data_dir.mkdir(parents=True, exist_ok=True)

    # Con varios procesos del servidor, solo uno programa la tarea: el que obtiene este bloqueo. El archivo
    # queda abierto mientras viva el proceso (cerrarlo soltaría el bloqueo), por eso no va en un "with".
    lock = open(data_dir / ".programador.lock", "w")  # noqa: SIM115
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
            # Si el servidor partió sin datos, se publican las planillas incluidas en el sitio.
            try:
                instalar_semilla(data_dir, cfg["SEMILLA_DIR"])
            except Exception:
                log.exception("Tampoco se pudieron leer las planillas incluidas en el sitio")
            # Ya quedó registrado en el log y en estado.json. Se reintenta más tarde
            # (un solo reintento pendiente a la vez) en vez de esperar al próximo domingo.
            reintento = dt.datetime.now(ZoneInfo(cfg["ZONA_HORARIA"])) + dt.timedelta(minutes=REINTENTO_MINUTOS)
            sched.add_job(tarea, "date", run_date=reintento, id="drive-reintento", replace_existing=True)
            log.info("Se reintentará la descarga desde Drive a las %s", reintento.strftime("%H:%M"))
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
    atexit.register(lambda: sched.running and sched.shutdown(wait=False))
    log.info("Revisión de Drive programada: '%s' (%s)", cfg["ACTUALIZACION_CRON"], cfg["ZONA_HORARIA"])
    return sched
