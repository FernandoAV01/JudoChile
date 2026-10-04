# Judo Chile · Ranking nacional

Sitio web que analiza el **Ranking Nacional de la Federación de Judo de Chile (FEJUCHILE)** y lo
explica para cualquier persona: qué clubes y deportistas destacan en el país y en cada zona, el ranking
completo de cada edad y peso, qué clubes suman más puntos en cada categoría, y una ficha por club
(con su ciudad, región y zona) y por deportista.

Creado por **Fernando Arellano** · [GitHub](https://github.com/FernandoAV01) ·
[LinkedIn](https://www.linkedin.com/in/fernando-arellano-v) · contacto: arellano.fernando.v@gmail.com.
Es un proyecto independiente, no un sitio oficial de la federación.

Los datos salen de la [carpeta pública de Google Drive](https://drive.google.com/drive/folders/1g2ZvhjbvHZ9SJYYw8cqsdCQn5ZY3WESf)
donde la federación publica las planillas. El sitio la revisa solo **todos los domingos a las 23:00
(hora de Chile)** y descarga las planillas únicamente cuando alguna cambió.

El sitio es público: cualquier persona con el enlace puede verlo.

## Qué muestra

| Página | Contenido |
|---|---|
| **Resumen** | Cifras del país, clubes con más puntos, dónde gana cada club por edad, figuras (más puntos, mejor temporada, ranking internacional), categorías más dominadas y más reñidas |
| **Categorías** | Se elige la edad (Sub 13 a Absoluta) y luego el peso. Muestra el podio y el ranking completo de deportistas, con el origen de los puntos de cada uno |
| **Clubes** | Todos los clubes ordenados por puntos totales (suma de los puntos de sus deportistas), con su región. La ficha de cada club muestra su ciudad, región y zona, sus números 1, su presencia por edad y todos sus deportistas |
| **Categorías por clubes** | Se elige la edad y el peso, y se ve el ranking de clubes de esa categoría: cuántos puntos suman sus deportistas y quién es su mejor ubicado |
| **Deportistas** | Ficha con todas sus categorías, lugar, puntaje y puntos internacionales |
| **Cómo funciona** | Cómo se calcula el puntaje, qué regiones forman cada zona, de dónde sale la ubicación de los clubes y advertencias sobre los datos |

Las secciones Categorías, Clubes y Categorías por clubes se pueden **filtrar por zona** (Norte, Centro
o Sur). Al filtrar, los lugares se calculan dentro de la zona y también se muestra el lugar nacional.

### Zonas y ubicación de los clubes

La zona sale de la región del club, con la división que usa la federación para sus campeonatos zonales
en 2026:

| Zona | Regiones |
|---|---|
| Norte | Arica y Parinacota, Tarapacá, Antofagasta, Atacama y Coquimbo |
| Centro | Valparaíso, Metropolitana, O'Higgins y Maule |
| Sur | Ñuble, Biobío, La Araucanía, Los Ríos, Los Lagos, Aysén y Magallanes |

La ciudad y la región de cada club están en [`judo/clubes.csv`](judo/clubes.csv) y vienen del
[registro de clubes de la federación](https://app.fejuchile.cl/show/clubs). Se verificaron cruzando a
los deportistas del ranking con el registro de judokas de la federación (octubre de 2026).

### Cómo se calcula el puntaje

Verificado con las planillas: el total de cada año es el **50 % de los puntos ganados en torneos del
año anterior** (arrastre) más los **puntos de torneos del año en curso**. Ese total ordena cada
categoría. Absoluta, Sub 21 y Sub 18 traen además un ranking internacional que funciona igual.

## Estructura

```
judo/
  datos.py        lee las planillas .xlsx (detecta el año solo; sirve para 2027 en adelante)
  analisis.py     clasificación de clubes, figuras, competitividad, zonas y búsquedas
  ubicaciones.py  regiones, zonas y lectura de clubes.csv
  clubes.csv      ficha de cada club: nombre visible, ciudad, comuna, región y fuente
  drive.py        lista y descarga la carpeta pública de Drive
  almacen.py      guarda cada versión descargada en data/ y recarga los datos cuando hay una nueva
  programador.py  revisión semanal automática
  actualizar.py   actualización manual desde la línea de comandos
  vistas.py       páginas del sitio
  templates/      HTML (Jinja); _ui.html reúne los componentes compartidos
  static/         estilos.css (sistema de diseño) y app.js
tests/            pruebas automáticas
wsgi.py           punto de entrada para gunicorn
render.yaml       configuración para publicar en Render
Dockerfile        imagen para publicar en cualquier servicio con Docker
```

Si una descarga falla, o la federación sube una planilla con un formato que no se puede leer, el
sitio **mantiene los datos anteriores**. El error queda registrado en el log, en `data/estado.json`
y en la página "Cómo funciona".

## Usarlo en tu computador

Requiere Python 3.12 o superior.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m judo.actualizar            # primera descarga desde Drive
.venv/bin/gunicorn --threads 4 --bind 127.0.0.1:8000 wsgi:app
```

Abre <http://localhost:8000>.

Pruebas: `.venv/bin/python -m pytest -q`. Usan las planillas `RANKING … .xlsx` de la raíz del repositorio.

## Publicar gratis en Render

[Render](https://render.com) tiene un plan gratuito sin tarjeta de crédito, y `render.yaml` deja
todo configurado.

1. Crea una cuenta en Render entrando con GitHub.
2. **New → Blueprint**, elige este repositorio y confirma.
3. Espera el primer despliegue (unos minutos). Render te da una dirección como
   `https://judo-chile.onrender.com`; esa es la que compartes.

Cada `git push` a `main` vuelve a publicar el sitio automáticamente.

**Qué implica el plan gratuito**

| | |
|---|---|
| Costo | $0, sin tarjeta |
| Se duerme | Tras 15 minutos sin visitas. La primera visita después espera alrededor de un minuto; mientras tanto ve una página de carga que se recarga sola |
| Datos | No hay disco permanente: al despertar, el sitio descarga las planillas vigentes de Drive, así que siempre están al día |
| Límites | 512 MB de RAM (el sitio usa ~110 MB) y 750 horas al mes, suficientes para todo el mes |

**Otros servicios**: la imagen Docker funciona en cualquier lugar (Railway, Google Cloud Run, un
servidor propio). Con disco permanente, monta un volumen en `/app/data`:

```bash
docker build -t judo-chile .
docker run -d --name judo -p 8000:8000 -v judo-data:/app/data judo-chile
```

## Configuración

Todo es opcional; los valores por defecto ya apuntan a la carpeta de la federación. Se definen como
variables de entorno o en un archivo `.env` (ver [.env.example](.env.example)).

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `DRIVE_CARPETA_ID` | carpeta de FEJUCHILE | Carpeta de Drive a revisar |
| `GOOGLE_API_KEY` | vacía | Clave de API de Google para listar la carpeta con la API oficial de Drive. Sin clave se lee la página pública de la carpeta, que funciona, pero depende de cómo Google arme esa página |
| `ACTUALIZACION_CRON` | `0 23 * * sun` | Día y hora de la revisión (formato crontab) |
| `ZONA_HORARIA` | `America/Santiago` | Zona horaria de la revisión y de las fechas |
| `DATA_DIR` | `./data` | Dónde se guardan las planillas descargadas |
| `VERSIONES_A_CONSERVAR` | `12` | Cuántas versiones anteriores se guardan |
| `WEB_CONCURRENCY` | `2` en Docker | Procesos del servidor (en Render gratis: `1`) |

## Tareas habituales

| Qué | Cómo |
|---|---|
| Forzar una actualización ahora | En Render: *Manual Deploy → Restart service* (al reiniciar descarga de nuevo). En otro servidor: `python -m judo.actualizar --forzar` |
| Cambiar el día u hora de la revisión | Variable `ACTUALIZACION_CRON`, por ejemplo `0 22 * * sun` |
| Unificar un club escrito de otra forma | Agrega la variante en `ALIAS_CLUBES` (`judo/datos.py`) |
| Agregar o corregir la ubicación de un club | Edita su fila en `judo/clubes.csv` (la columna `clave` es el nombre del club en las planillas, ya unificado). La zona se calcula sola a partir de la región. Un club nuevo sin fila aparece como "Sin confirmar" |
| Ver el estado de la última revisión | Página "Cómo funciona", o `data/estado.json` |

## Advertencias sobre los datos

- La temporada está en curso: quien aún no compite este año solo tiene su arrastre.
- Un mismo club aparece escrito de varias formas en las planillas; el sitio unifica las variantes conocidas.
- "NAC" en las planillas es el club del colegio North American College de Arica.
- Algunos clubes cambiaron de nombre (por ejemplo, Ozanam hoy es Chuseikan) y el sitio los muestra unidos.
- Las planillas no traen RUT: se considera la misma persona a quien tiene el mismo nombre completo y sexo.
- El lugar se recalcula ordenando por puntaje, porque algunas planillas traen errores de numeración.
