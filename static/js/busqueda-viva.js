/*
 * Buscar mientras se escribe, sin recargar la página.
 *
 * Hasta ahora el sistema tenía dos maneras de buscar: en citaciones y mensajes
 * se desplegaban sugerencias al escribir, y en las listas había que apretar
 * «Buscar» y esperar a que la página entera volviera a cargarse. Esto último se
 * nota sobre todo donde más se usa —cuatrocientos estudiantes, uno por uno—.
 *
 * Cómo se usa: el formulario lleva `data-busqueda-viva="#selector"`, donde el
 * selector apunta al contenedor que hay que reemplazar. El servidor devuelve
 * solo ese pedazo cuando la petición trae la cabecera X-Requested-With.
 *
 * Sin JavaScript sigue funcionando: el botón «Buscar» envía el formulario como
 * toda la vida. Esto solo le ahorra el viaje a quien sí lo tiene.
 */
'use strict';

(function () {
  const ESPERA = 250;          // lo que se deja de escribir antes de preguntar

  document.querySelectorAll('form[data-busqueda-viva]').forEach(preparar);

  function preparar(formulario) {
    const destino = document.querySelector(formulario.dataset.busquedaViva);
    if (!destino || !window.fetch) return;

    let temporizador = null;
    let numero = 0;            // para descartar respuestas que llegan tarde

    async function pedir() {
      const parametros = new URLSearchParams(new FormData(formulario));
      // Al cambiar la búsqueda se vuelve a la primera página: quedarse en la
      // página 7 de un resultado de tres filas no le sirve a nadie.
      parametros.delete('page');
      for (const [clave, valor] of [...parametros]) {
        if (!valor) parametros.delete(clave);      // la URL, sin basura
      }
      const consulta = parametros.toString();
      const direccion = location.pathname + (consulta ? '?' + consulta : '');

      const mio = ++numero;
      destino.setAttribute('aria-busy', 'true');
      try {
        const respuesta = await fetch(direccion, {
          headers: {'X-Requested-With': 'XMLHttpRequest'},
        });
        if (!respuesta.ok) return;
        const html = await respuesta.text();
        if (mio !== numero) return;                // llegó una más nueva primero
        // El pedazo lo arma el servidor con sus propias plantillas, que ya
        // escapan todo: aquí no se interpreta nada escrito por nadie.
        destino.innerHTML = html;
        enganchar();
        avisar();
        history.replaceState(null, '', direccion);
      } catch (error) {
        /* Sin conexión se queda lo que había; el botón «Buscar» sigue estando. */
      } finally {
        destino.removeAttribute('aria-busy');
      }
    }

    function programar() {
      clearTimeout(temporizador);
      temporizador = setTimeout(pedir, ESPERA);
    }

    /* Algunas pantallas rehacen lo suyo sobre las filas nuevas (la puerta y
       sus desplegables de estado). Se les avisa por aquí. */
    function avisar() {
      document.dispatchEvent(new CustomEvent('tabla-renovada', {detail: {destino}}));
    }

    /* Los enlaces de paginación del pedazo recién traído también van por aquí. */
    function enganchar() {
      destino.querySelectorAll('a[data-pagina]').forEach(function (enlace) {
        enlace.addEventListener('click', function (evento) {
          evento.preventDefault();
          ir(enlace.getAttribute('href'));
        });
      });
    }

    async function ir(direccion) {
      const mio = ++numero;
      destino.setAttribute('aria-busy', 'true');
      try {
        const respuesta = await fetch(direccion, {
          headers: {'X-Requested-With': 'XMLHttpRequest'},
        });
        if (!respuesta.ok || mio !== numero) return;
        destino.innerHTML = await respuesta.text();
        enganchar();
        avisar();
        history.replaceState(null, '', direccion);
        destino.scrollIntoView({block: 'start', behavior: 'smooth'});
      } finally {
        destino.removeAttribute('aria-busy');
      }
    }

    formulario.addEventListener('submit', function (evento) {
      evento.preventDefault();
      clearTimeout(temporizador);
      pedir();
    });

    formulario.querySelectorAll('input[type="search"]').forEach(function (campo) {
      campo.addEventListener('input', programar);
    });
    formulario.querySelectorAll('select').forEach(function (campo) {
      // Los desplegables ya no necesitan recargar la página entera.
      campo.removeAttribute('onchange');
      campo.addEventListener('change', pedir);
    });
    /* Los botones de opción (los cursos de la puerta) son una elección, no algo
       que se escriba: se piden al instante, sin la espera del tecleo. */
    formulario.querySelectorAll('input[type="radio"], input[type="checkbox"]')
      .forEach(function (campo) {
        campo.addEventListener('change', pedir);
      });

    enganchar();
  }
})();
