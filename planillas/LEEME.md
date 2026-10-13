# Planillas incluidas en el sitio

Copia de las planillas oficiales del ranking (`RANKING <EDAD> <AÑO>.xlsx`), tal como las publica la
federación en su carpeta de Google Drive. El sitio no las usa en el día a día: siempre descarga las
vigentes desde Drive. Sirven para dos cosas:

- **Respaldo**: si el servidor se enciende sin datos y Drive no responde, el sitio muestra estas planillas
  en vez de quedarse cargando, y vuelve a intentar con Drive cada 30 minutos.
- **Pruebas**: las pruebas automáticas (`tests/`) se hacen con estos datos.

Para actualizarlas, reemplaza los archivos por los vigentes de la carpeta de Drive y haz `git push`.
Si cambian los datos, revisa también las pruebas que usan valores concretos (por ejemplo, la cantidad
de categorías o los clubes que se nombran).
