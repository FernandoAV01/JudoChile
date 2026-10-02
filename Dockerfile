FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 DATA_DIR=/app/data WEB_CONCURRENCY=2
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY judo ./judo
COPY wsgi.py .

RUN useradd --create-home judo && mkdir -p /app/data && chown -R judo /app/data
USER judo
# Las planillas descargadas viven aquí: monta un volumen para no perderlas al redesplegar.
# (Va después del chown: Docker descarta los cambios hechos a un VOLUME ya declarado.)
VOLUME ["/app/data"]

EXPOSE 8000
# WEB_CONCURRENCY = número de procesos (gunicorn lo lee solo). Con varios, la revisión
# semanal de Drive corre solo en uno gracias a un bloqueo de archivo.
CMD gunicorn --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} --access-logfile - wsgi:app
