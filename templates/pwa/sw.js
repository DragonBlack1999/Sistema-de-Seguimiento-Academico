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

/*
 * Atender `fetch` es lo que convierte esto en una app instalable: Chrome solo
 * ofrece «Instalar aplicación» si el service worker puede responder algo
 * estando sin conexión. No se guarda ninguna página: se va siempre a la red, y
 * si no hay, se muestra un cartel en vez del error del navegador.
 */
const SIN_CONEXION = `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sin conexión</title>
<style>
 body{font-family:system-ui,sans-serif;background:#f1fbf8;color:#12403b;margin:0;
      min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
 div{max-width:22rem;text-align:center}
 h1{font-size:1.25rem;margin:0 0 .5rem}
 p{color:#5b7d78;line-height:1.5;margin:0}
</style></head><body><div>
 <h1>Sin conexión</h1>
 <p>El colegio no está al alcance en este momento. Revisa tus datos o el wifi
 y vuelve a intentarlo; lo que ya estaba guardado no se pierde.</p>
</div></body></html>`;

self.addEventListener('fetch', function (evento) {
  // Solo las navegaciones: las imágenes y los estilos que fallen no necesitan
  // un cartel, y tapar una petición de datos con HTML rompería la pantalla.
  if (evento.request.mode !== 'navigate') return;
  evento.respondWith(
    fetch(evento.request).catch(function () {
      return new Response(SIN_CONEXION, {
        status: 503,
        headers: {'Content-Type': 'text/html; charset=utf-8'},
      });
    })
  );
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
