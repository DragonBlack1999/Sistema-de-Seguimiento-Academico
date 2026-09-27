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
  const botonInstalar = document.getElementById('botonInstalar');
  const ayuda = document.getElementById('ayudaInstalar');

  /* iPhone y iPad. El iPad moderno se hace pasar por Mac, y se lo reconoce
     porque ningún Mac tiene pantalla táctil. */
  const esApple = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  /* ¿Se abrió desde la pantalla de inicio o dentro del navegador? En iPhone
     esto lo cambia todo: los avisos solo existen si está instalada. */
  const instalada = window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  function explicar(html) {
    if (!ayuda) return;
    ayuda.innerHTML = html;
    ayuda.hidden = false;
  }

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
      if (esApple && !instalada) {
        // No es que el iPhone no pueda: es que todavía no está instalada.
        contar('En iPhone y iPad, los avisos funcionan con la app en la pantalla de inicio.');
        explicar(
          '<strong>Para recibir los avisos en tu iPhone:</strong>' +
          '<ol class="mb-0 mt-2">' +
          '<li>Abre esta página en <strong>Safari</strong>.</li>' +
          '<li>Toca el botón de compartir <strong>(el cuadrito con la flecha hacia arriba)</strong>.</li>' +
          '<li>Elige <strong>«Añadir a pantalla de inicio»</strong>.</li>' +
          '<li>Abre el sistema desde ese ícono y vuelve a esta pantalla.</li>' +
          '</ol>' +
          '<div class="small mt-2">Necesita iPhone con iOS 16.4 o más nuevo (de 2023 en adelante).</div>'
        );
      } else if (esApple) {
        contar('Este iPhone no puede mostrar avisos: necesita iOS 16.4 o más nuevo.');
      } else {
        contar('Este navegador no puede mostrar avisos. En Android funciona con Chrome.');
      }
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

  /* Chrome avisa cuando la app se puede instalar; hay que guardar ese aviso
     para poder ofrecerlo con un botón nuestro, en el momento en que la persona
     está justamente pensando en los avisos. */
  let invitacion = null;
  window.addEventListener('beforeinstallprompt', function (evento) {
    evento.preventDefault();
    invitacion = evento;
    if (botonInstalar) botonInstalar.hidden = false;
  });

  window.addEventListener('appinstalled', function () {
    invitacion = null;
    if (botonInstalar) botonInstalar.hidden = true;
  });

  if (botonInstalar) {
    botonInstalar.addEventListener('click', async function () {
      if (!invitacion) return;
      invitacion.prompt();
      await invitacion.userChoice;
      invitacion = null;
      botonInstalar.hidden = true;
    });
  }

  /* ────────────────── los contadores de la barra ──────────────────
     Una pagina no se entera de nada por su cuenta: el numero de la campanita
     es el que se calculo al abrir la pantalla. Esto lo vuelve a preguntar cada
     tanto, para no tener que recargar.

     Cada 45 segundos y solo con la pestana a la vista: en un colegio de
     cuatrocientas personas, preguntar cada segundo seria mucha carga para algo
     que no lo merece. Lo urgente ya viaja por otro camino, el aviso al celular,
     que llega aunque el sistema este cerrado. */
  const CADA = 45000;

  function pintarContador(elemento, cuantos) {
    if (!elemento) return;
    elemento.hidden = !cuantos;
    if (cuantos) {
      elemento.childNodes[0].nodeValue = String(cuantos);
    }
  }

  async function ponerAlDia() {
    if (document.hidden) return;
    try {
      const respuesta = await fetch('/notificaciones/contador/', {
        headers: {'X-Requested-With': 'XMLHttpRequest'},
      });
      if (!respuesta.ok) return;            // sesion vencida u otra cosa: no insistir
      const datos = await respuesta.json();
      pintarContador(document.getElementById('contadorAvisos'), datos.notificaciones);
      pintarContador(document.getElementById('contadorMensajes'), datos.mensajes);
    } catch (error) {
      /* Sin conexion no pasa nada: se vuelve a intentar en la siguiente vuelta. */
    }
  }

  if (document.getElementById('contadorAvisos')) {
    setInterval(ponerAlDia, CADA);
    // Al volver a la pestana, mirar enseguida en vez de esperar el turno.
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) ponerAlDia();
    });
  }

  window.addEventListener('load', async function () {
    const registro = await registrar();
    await pintar(registro);

    // En iPhone ya instalada, conviene recordar que el permiso se pide una vez.
    if (esApple && instalada && soportado && Notification.permission === 'default') {
      explicar('Ya tienes la app en tu pantalla de inicio. Toca <strong>«Activar los avisos ' +
               'en este dispositivo»</strong> y acepta el permiso que pide el teléfono.');
    }

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
