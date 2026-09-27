{% load static %}/*
 * Service worker: el que recibe los avisos cuando el sistema está cerrado.
 *
 * Se sirve desde la raíz del sitio a propósito: un service worker solo manda
 * sobre las páginas que cuelgan de su carpeta, y desde /static/ no cubriría
 * nada. No guarda páginas en caché: los datos del colegio cambian todo el
 * tiempo y una copia vieja (una nota, una asistencia) confunde más que ayuda.
 */
'use strict';

const ICONO = '{% static "img/app-192.png" %}';

self.addEventListener('install', function () {
  // Sin espera: la versión nueva manda desde el primer momento.
  self.skipWaiting();
});

self.addEventListener('activate', function (evento) {
  evento.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (evento) {
  let datos = {};
  try {
    datos = evento.data ? evento.data.json() : {};
  } catch (error) {
    datos = {titulo: 'Eduardo Abaroa Tarde', mensaje: evento.data ? evento.data.text() : ''};
  }

  const titulo = datos.titulo || 'Eduardo Abaroa Tarde';
  const opciones = {
    body: datos.mensaje || '',
    icon: ICONO,
    badge: ICONO,
    lang: 'es',
    // Reemplaza al anterior en vez de apilar diez avisos de lo mismo.
    tag: datos.url || 'aviso',
    renotify: true,
    data: {url: datos.url || '/'},
  };
  evento.waitUntil(self.registration.showNotification(titulo, opciones));
});

self.addEventListener('notificationclick', function (evento) {
  evento.notification.close();
  const destino = new URL(evento.notification.data.url || '/', self.location.origin).href;

  evento.waitUntil(
    self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(function (ventanas) {
      // Si el sistema ya está abierto, se usa esa ventana en vez de abrir otra.
      for (const ventana of ventanas) {
        if (ventana.url === destino && 'focus' in ventana) return ventana.focus();
      }
      for (const ventana of ventanas) {
        if ('navigate' in ventana) return ventana.navigate(destino).then(v => v && v.focus());
      }
      return self.clients.openWindow(destino);
    })
  );
});
