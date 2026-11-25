/*
 * Lo que antes iba escrito en la página como onclick="…" u onsubmit="…".
 *
 * La política de seguridad (SECURE_CSP en config/settings.py) no deja correr
 * código escrito dentro de los atributos: es justo por donde entraría un
 * script inyectado. Así que las plantillas marcan lo que quieren y aquí se hace:
 *
 *   <form data-confirmar="¿Seguro?">    pregunta antes de enviar
 *   <button data-confirmar="¿Seguro?">  pregunta antes de enviar con ese botón
 *   <select data-autoenvio>             envía su formulario al cambiar
 *   <button data-imprimir>              abre el cuadro de imprimir
 *
 * Se escucha en el documento entero, así también vale para lo que llega
 * después (las tablas que se recargan solas, por ejemplo).
 */
(function () {
  'use strict';

  document.addEventListener('click', function (evento) {
    const objetivo = evento.target instanceof Element ? evento.target : null;
    if (!objetivo) return;

    const boton = objetivo.closest('button[data-confirmar], input[type="submit"][data-confirmar]');
    if (boton && !window.confirm(boton.dataset.confirmar)) {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      return;
    }
    if (objetivo.closest('[data-imprimir]')) {
      evento.preventDefault();
      window.print();
    }
  }, true);

  document.addEventListener('submit', function (evento) {
    const formulario = evento.target;
    if (formulario instanceof HTMLFormElement && formulario.dataset.confirmar
        && !window.confirm(formulario.dataset.confirmar)) {
      evento.preventDefault();
      evento.stopImmediatePropagation();
    }
  }, true);

  document.addEventListener('change', function (evento) {
    const campo = evento.target;
    if (campo instanceof HTMLSelectElement && campo.hasAttribute('data-autoenvio') && campo.form) {
      campo.form.requestSubmit ? campo.form.requestSubmit() : campo.form.submit();
    }
  });
})();
