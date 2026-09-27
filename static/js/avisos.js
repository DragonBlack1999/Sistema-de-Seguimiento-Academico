/*
 * Avisos al celular: registra el service worker y maneja el botón de activar.
 *
 * El botón vive en la pantalla de notificaciones; este archivo se carga en todas
 * porque el service worker conviene registrarlo apenas entran, no solo si pasan
 * por esa pantalla.
 */
'use strict';

(function () {
  const soportado = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const boton = document.getElementById('botonAvisos');
  const estado = document.getElementById('estadoAvisos');

  function contar(texto) {
    if (estado) estado.textContent = texto;
  }

  function galleta(nombre) {
    const partes = ('; ' + document.cookie).split('; ' + nombre + '=');
    return partes.length === 2 ? partes.pop().split(';').shift() : '';
  }

  /* La llave del servidor viaja en base64 para la URL; el navegador la pide en bytes. */
  function aBytes(base64) {
    const relleno = '='.repeat((4 - (base64.length % 4)) % 4);
    const limpio = (base64 + relleno).replace(/-/g, '+').replace(/_/g, '/');
    const crudo = window.atob(limpio);
    return Uint8Array.from([...crudo].map(c => c.charCodeAt(0)));
  }

  async function avisarAlServidor(ruta, cuerpo) {
    const respuesta = await fetch(ruta, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': galleta('csrftoken')},
      body: JSON.stringify(cuerpo),
    });
    if (!respuesta.ok) throw new Error('El servidor no aceptó la suscripción');
    return respuesta.json();
  }

  async function registrar() {
    if (!soportado) return null;
    try {
      return await navigator.serviceWorker.register('/sw.js');
    } catch (error) {
      return null;
    }
  }

  async function pintar(registro) {
    if (!boton) return;
    if (!soportado) {
      boton.disabled = true;
      contar('Este navegador no puede mostrar avisos. Prueba con Chrome en Android.');
      return;
    }
    if (Notification.permission === 'denied') {
      boton.disabled = true;
      contar('Bloqueaste los avisos para este sitio. Se activan desde los ajustes del navegador.');
      return;
    }
    const suscripcion = registro ? await registro.pushManager.getSubscription() : null;
    boton.disabled = false;
    boton.dataset.activo = suscripcion ? 'si' : 'no';
    boton.textContent = suscripcion ? 'Desactivar los avisos en este dispositivo'
                                    : 'Activar los avisos en este dispositivo';
    boton.classList.toggle('btn-outline-secondary', Boolean(suscripcion));
    boton.classList.toggle('btn-primary', !suscripcion);
    contar(suscripcion
      ? 'Este dispositivo recibirá los avisos aunque el sistema esté cerrado.'
      : 'Actívalos para enterarte de citaciones, tareas y noticias sin entrar a mirar.');
  }

  async function activar(registro) {
    const permiso = await Notification.requestPermission();
    if (permiso !== 'granted') {
      contar('No diste permiso, así que los avisos seguirán solo dentro del sistema.');
      return;
    }
    const llave = document.querySelector('meta[name="llave-avisos"]');
    if (!llave || !llave.content) {
      contar('Este servidor todavía no tiene configurados los avisos al celular.');
      return;
    }
    const suscripcion = await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: aBytes(llave.content),
    });
    const datos = suscripcion.toJSON();
    await avisarAlServidor('/notificaciones/avisos/activar/', {
      endpoint: datos.endpoint,
      keys: datos.keys,
      dispositivo: navigator.userAgent.slice(0, 120),
    });
  }

  async function desactivar(registro) {
    const suscripcion = await registro.pushManager.getSubscription();
    if (!suscripcion) return;
    await avisarAlServidor('/notificaciones/avisos/desactivar/', {endpoint: suscripcion.endpoint});
    await suscripcion.unsubscribe();
  }

  window.addEventListener('load', async function () {
    const registro = await registrar();
    await pintar(registro);
    if (!boton || !registro) return;

    boton.addEventListener('click', async function () {
      boton.disabled = true;
      contar('Un momento…');
      try {
        if (boton.dataset.activo === 'si') {
          await desactivar(registro);
        } else {
          await activar(registro);
        }
      } catch (error) {
        contar('No se pudo cambiar el aviso. Revisa tu conexión e inténtalo de nuevo.');
      }
      await pintar(registro);
    });
  });
})();
