# Judo Chile · Ranking nacional

Sitio web que analiza el Ranking Nacional de la Federación de Judo de Chile (FEJUCHILE):
clubes y deportistas más destacados del país, ranking completo por edad y peso, y la ficha
de cada club y deportista.

- **Acceso**: solo cuentas de Google con correo `@mail.pucv.cl` (configurable).
- **Datos**: se leen de la [carpeta pública de Drive](https://drive.google.com/drive/folders/1g2ZvhjbvHZ9SJYYw8cqsdCQn5ZY3WESf)
  donde la federación publica las planillas. El sitio la revisa **todos los domingos a las 23:00 (hora de Chile)**
  y solo descarga cuando alguna planilla cambió.

## Cómo está armado

```
judo/
  datos.py        lee las planillas .xlsx (detecta el año solo; sirve para 2027 en adelante)
  analisis.py     medallero de clubes, figuras, competitividad, búsquedas
  drive.py        lista y descarga la carpeta pública de Drive
  almacen.py      guarda versiones en data/ y recarga los datos cuando hay una nueva
  programador.py  revisión semanal automática
  auth.py         ingreso con Google y restricción de dominio
  vistas.py       páginas del sitio
  templates/      HTML (Jinja); _ui.html tiene los componentes compartidos
  static/         estilos.css (sistema de diseño), app.js
tests/            pruebas (acceso, páginas y datos)
```

Si una descarga falla o la federación sube una planilla con un formato que no se puede leer,
el sitio **mantiene los datos anteriores** y deja el error registrado en `data/estado.json`
y en la página "Cómo funciona".

## 1. Crear las credenciales de Google (una vez)

1. Entra a <https://console.cloud.google.com/> y crea un proyecto (por ejemplo "Judo Chile").
2. **APIs y servicios → Pantalla de consentimiento de OAuth**: tipo *Externo*, nombre de la app,
   correo de soporte. Alcances: `openid`, `email`, `profile`. Publica la app (no necesita verificación
   porque esos alcances son básicos).
3. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: *Aplicación web*.
   - URI de redirección autorizados:
     - `https://TU-DOMINIO/auth/callback` (producción)
     - `http://localhost:8000/auth/callback` (pruebas locales)
4. Copia el *ID de cliente* y el *Secreto* a `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.
5. (Opcional, recomendado) **Crear credenciales → Clave de API**, habilita la *Google Drive API*
   y ponla en `GOOGLE_API_KEY`. Sin clave el sitio igual funciona leyendo la página pública de la
   carpeta, pero la API oficial es más estable si Google cambia esa página.

La restricción a `@mail.pucv.cl` se verifica en el servidor (correo verificado por Google y dominio
exacto); no se puede saltar desde el navegador. Para autorizar otros dominios:
`DOMINIOS_PERMITIDOS=mail.pucv.cl,pucv.cl`.

## 2. Probar en tu computador

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
cp .env.example .env          # completa SECRET_KEY y las credenciales; COOKIE_SEGURA=0
.venv/bin/python -m judo.actualizar           # primera descarga desde Drive
.venv/bin/gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 wsgi:app
```

Abre <http://localhost:8000>. Pruebas: `.venv/bin/python -m pytest -q`.

## 3. Publicar gratis en Render

[Render](https://render.com) tiene un plan gratuito sin tarjeta de crédito. El repositorio ya trae
`render.yaml`, así que Render configura todo solo.

**Qué implica el plan gratuito**

| | |
|---|---|
| Costo | $0, sin tarjeta |
| Dirección | `https://judo-chile.onrender.com` (o similar), con HTTPS |
| Se duerme | tras 15 minutos sin visitas; la primera visita después espera ~1 minuto (la página de carga se recarga sola) |
| Datos | no hay disco permanente: al despertar descarga las planillas vigentes de Drive, así que siempre están al día |
| Límites | 512 MB de RAM (el sitio usa ~110 MB) y 750 horas al mes (alcanza para estar encendido todo el mes) |

**Pasos**

1. Crea una cuenta en <https://github.com> y un repositorio **privado** vacío (por ejemplo `judo-chile`).
2. Sube el proyecto (desde esta carpeta):
   ```bash
   git init -b main
   git add .
   git commit -m "Sitio del ranking de judo"
   git remote add origin https://github.com/TU-USUARIO/judo-chile.git
   git push -u origin main
   ```
   `.env` y `data/` no se suben (están en `.gitignore`).
3. Crea una cuenta en <https://render.com> entrando con GitHub.
4. **New → Blueprint**, elige el repositorio y confirma. Cuando pida `GOOGLE_CLIENT_ID` y
   `GOOGLE_CLIENT_SECRET` puedes dejarlos vacíos por ahora.
5. Espera el primer despliegue (unos minutos) y anota la dirección que te asigna Render.
6. Haz el paso 1 de este README (credenciales de Google) usando
   `https://TU-SERVICIO.onrender.com/auth/callback` como URI de redirección.
7. En Render → tu servicio → **Environment**, completa `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`
   y guarda. El servicio se reinicia solo y el ingreso queda funcionando.

Cada `git push` a `main` vuelve a desplegar el sitio automáticamente.

**Otros servicios**: la imagen Docker funciona en cualquier lugar (Railway, Google Cloud Run, un
servidor propio o de la universidad). Con disco permanente, monta un volumen en `/app/data`:

```bash
docker build -t judo-chile .
docker run -d --name judo -p 8000:8000 --env-file .env -v judo-data:/app/data judo-chile
```

## Tareas habituales

| Qué | Cómo |
|---|---|
| Forzar una actualización ahora | En Render: *Manual Deploy → Restart service* (al reiniciar descarga de nuevo). En otro servidor: `python -m judo.actualizar --forzar` |
| Cambiar el día u hora de la revisión | `ACTUALIZACION_CRON` (ej. `0 22 * * sun`) |
| Unificar un club escrito de otra forma | agrega la variante en `ALIAS_CLUBES` (`judo/datos.py`) |
| Ver el estado de la última revisión | página "Cómo funciona" o `data/estado.json` |
