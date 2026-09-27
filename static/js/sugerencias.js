/*
 * Lista desplegable de sugerencias: la comparten «Nueva citación» y «Mensajes».
 *
 * Abrir y cerrar llevan una animación corta. Por eso cerrar no esconde la lista
 * de golpe: primero la desvanece y recién después la vacía. Si mientras tanto
 * se vuelve a escribir, la lista se reabre sin llegar a esconderse.
 */
window.Sugerencias = (function () {
  'use strict';

  const DURACION_CIERRE = 170;   // igual que la transición de sistema.css
  const DURACION_ENTRADA = 450;  // lo que tardan en entrar todas las opciones
  const temporizadores = new WeakMap();

  function cancelar(lista) {
    const previos = temporizadores.get(lista);
    if (previos) previos.forEach(clearTimeout);
    temporizadores.set(lista, []);
  }

  function programar(lista, funcion, demora) {
    temporizadores.get(lista).push(setTimeout(funcion, demora));
  }

  function abierta(lista) {
    return !lista.hidden && lista.classList.contains('abierta');
  }

  function abrir(lista) {
    const estabaCerrada = !abierta(lista);
    cancelar(lista);
    lista.hidden = false;
    if (!estabaCerrada) return;   // ya abierta: solo cambió el contenido, sin repetir la entrada

    lista.classList.remove('abierta');
    void lista.offsetWidth;       // parte del estado inicial, si no la transición no arranca
    // Las opciones entran escalonadas solo al abrir: repetirlo en cada tecla marearía.
    lista.classList.add('abierta', 'entrando');
    programar(lista, () => lista.classList.remove('entrando'), DURACION_ENTRADA);
  }

  function cerrar(lista) {
    cancelar(lista);
    if (lista.hidden) return;
    lista.classList.remove('abierta', 'entrando');
    programar(lista, function () {
      lista.hidden = true;
      lista.replaceChildren();
    }, DURACION_CIERRE);
  }

  /* Una opción: el nombre y debajo el dato. Van en piezas separadas y con un
     espacio entre ambas, así se leen bien aunque la hoja de estilos no cargue. */
  function opcion(nombre, dato) {
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.setAttribute('role', 'option');
    const principal = document.createElement('span');
    principal.className = 'nombre';
    principal.textContent = nombre;           // textContent: nunca se interpreta como HTML
    const detalle = document.createElement('span');
    detalle.className = 'dato';
    detalle.textContent = dato;
    boton.append(principal, ' ', detalle);
    return boton;
  }

  function vacio(texto) {
    const aviso = document.createElement('div');
    aviso.className = 'buscador-vacio';
    aviso.textContent = texto;
    return aviso;
  }

  return {abrir: abrir, cerrar: cerrar, abierta: abierta, opcion: opcion, vacio: vacio};
})();
