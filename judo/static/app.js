// Mejoras pequeñas: el sitio funciona igual sin JavaScript.
(() => {
  // 'Río Cruces' -> 'rio cruces' (para buscar sin importar tildes ni mayúsculas)
  const sinTildes = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  // ---- Filtro de la tabla de clubes, con aviso cuando ningún club coincide
  const filtro = document.querySelector('[data-filtra]');
  if (filtro) {
    const tabla = document.querySelector(filtro.dataset.filtra);
    const filas = [...tabla.querySelectorAll('tbody tr')];
    const info = document.getElementById('filtro-info');
    const vacio = document.createElement('tr');
    const celda = document.createElement('td');
    celda.colSpan = tabla.querySelectorAll('thead th').length;
    celda.className = 'vacio';
    vacio.appendChild(celda);
    vacio.hidden = true;
    tabla.querySelector('tbody').appendChild(vacio);
    filtro.addEventListener('input', () => {
      const texto = filtro.value.trim();
      const q = sinTildes(texto);
      let visibles = 0;
      for (const f of filas) {
        const coincide = !q || sinTildes(f.dataset.nombre || '').includes(q);
        f.hidden = !coincide;
        if (coincide) visibles++;
      }
      info.textContent = q ? `${visibles} club${visibles === 1 ? '' : 'es'}` : '';
      celda.textContent = `Ningún club coincide con “${texto}”. Prueba con otra parte del nombre.`;
      vacio.hidden = visibles > 0;
    });
  }

  // ---- Tablas
  // El encabezado de la columna del nombre también queda fijo al deslizar la tabla.
  for (const tabla of document.querySelectorAll('table.t')) {
    const nombre = tabla.querySelector('tbody th[scope="row"]');
    if (!nombre) continue;
    for (const fila of tabla.querySelectorAll('thead tr')) {
      fila.cells[nombre.cellIndex]?.classList.add('col-fija');
    }
  }

  // Tablas más anchas que la pantalla: se pueden enfocar y desplazar con el teclado.
  const ajustarTablas = () => {
    for (const t of document.querySelectorAll('.table-wrap')) {
      if (t.scrollWidth > t.clientWidth + 1) {
        // Nombre para lectores de pantalla: el título de su sección o, si no tiene, el de la página
        const titulo = (t.closest('section, .card')?.querySelector('h2, h3') || document.querySelector('h1'))?.textContent.trim() || 'Tabla';
        t.tabIndex = 0;
        t.setAttribute('role', 'region');
        t.setAttribute('aria-label', `${titulo} (tabla desplazable hacia el lado)`);
      } else {
        t.removeAttribute('tabindex');
        t.removeAttribute('role');
        t.removeAttribute('aria-label');
      }
    }
  };
  ajustarTablas();

  // ---- Filas que se deslizan hacia el lado (menú en celular y botones de edad, peso y zona)
  const filasDeslizables = [...document.querySelectorAll('.mainnav, .pill-row')];

  // En pantallas angostas, deja a la vista la sección, la edad y el peso elegidos.
  for (const actual of document.querySelectorAll('.pill-row [aria-current="page"], .mainnav [aria-current="page"]')) {
    const fila = actual.parentElement;
    if (fila.scrollWidth > fila.clientWidth) {
      fila.scrollLeft = actual.offsetLeft - fila.clientWidth / 2 + actual.clientWidth / 2;
    }
  }

  // El borde se difumina hacia donde quedan más opciones (clases desliza-izq y desliza-der de estilos.css).
  const BORDE = 40;  // ancho del degradado, el mismo de estilos.css
  const marcar = fila => {
    fila.classList.toggle('desliza-izq', fila.scrollLeft > 1);
    fila.classList.toggle('desliza-der', fila.scrollWidth - fila.clientWidth - fila.scrollLeft > 1);
  };
  for (const fila of filasDeslizables) {
    fila.tabIndex = -1;  // Firefox agrega cada fila deslizable al recorrido con Tab; sus enlaces ya bastan
    marcar(fila);
    fila.addEventListener('scroll', () => marcar(fila), {passive: true});
    // Al recorrer la fila con Tab, el enlace enfocado queda a la vista (no bajo la etiqueta ni el degradado).
    // Solo con teclado: mover la fila al hacer clic podría dejar el clic fuera del botón.
    fila.addEventListener('focusin', e => {
      if (fila.scrollWidth <= fila.clientWidth + 1 || !e.target.matches(':focus-visible')) return;
      const caja = fila.getBoundingClientRect();
      const enlace = e.target.getBoundingClientRect();
      const etiqueta = fila.querySelector('.pill-label');
      const desde = etiqueta ? etiqueta.getBoundingClientRect().right : caja.left + (fila.scrollLeft > 1 ? BORDE : 0);
      const hasta = caja.right - (fila.scrollWidth - fila.clientWidth - fila.scrollLeft > 1 ? BORDE : 0);
      if (enlace.left < desde || enlace.right > hasta) {
        fila.scrollLeft += enlace.left + enlace.width / 2 - (desde + hasta) / 2;  // lo centra en el espacio libre
      }
    });
  }

  // ---- Al cambiar el tamaño de la ventana (o girar el celular) se recalcula lo anterior
  let espera;
  addEventListener('resize', () => {
    clearTimeout(espera);
    espera = setTimeout(() => { ajustarTablas(); filasDeslizables.forEach(marcar); }, 150);
  });
})();
