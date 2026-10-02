// Mejoras pequeñas: el sitio funciona igual sin JavaScript.
(() => {
  const sinTildes = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  // Filtro de la tabla de clubes.
  const filtro = document.querySelector('[data-filtra]');
  if (filtro) {
    const filas = [...document.querySelectorAll(filtro.dataset.filtra + ' tbody tr')];
    const info = document.getElementById('filtro-info');
    filtro.addEventListener('input', () => {
      const q = sinTildes(filtro.value.trim());
      let visibles = 0;
      for (const f of filas) {
        const ok = !q || sinTildes(f.dataset.nombre || '').includes(q);
        f.hidden = !ok;
        if (ok) visibles++;
      }
      info.textContent = q ? `${visibles} club${visibles === 1 ? '' : 'es'}` : '';
    });
  }

  // En pantallas angostas, deja a la vista la edad y el peso elegidos.
  document.querySelectorAll('.pill-row [aria-current="page"], .mainnav [aria-current="page"]').forEach(el => {
    const fila = el.parentElement;
    if (fila.scrollWidth > fila.clientWidth) {
      fila.scrollLeft = el.offsetLeft - fila.clientWidth / 2 + el.clientWidth / 2;
    }
  });
})();
