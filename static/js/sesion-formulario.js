// Django rota el token al iniciar sesión, también para las pestañas ya abiertas.
(() => {
  const {sesion, usuario} = document.currentScript.dataset;
  const cookieCSRF = () => document.cookie.split('; ').find(c => c.startsWith('csrftoken='));
  let cookieInicial = cookieCSRF();
  let restaurada = false;
  let renovando = false;
  window.addEventListener('pageshow', evento => {
    restaurada = evento.persisted || performance.getEntriesByType('navigation')[0]?.type === 'back_forward';
  });

  document.addEventListener('submit', async evento => {
    const form = evento.target;
    const boton = evento.submitter;
    const metodo = boton?.getAttribute('formmethod') || form.method;
    const destino = boton?.hasAttribute('formaction') ? boton.formAction : form.action;
    if (metodo.toLowerCase() !== 'post' || new URL(destino).origin !== location.origin) return;
    if (!form.querySelector('input[name="csrfmiddlewaretoken"]')) return;
    if (!restaurada && cookieInicial && cookieInicial === cookieCSRF()) return;

    evento.preventDefault();
    evento.stopImmediatePropagation();
    if (renovando) return;
    renovando = true;
    try {
      const respuesta = await fetch(sesion, {mode: 'same-origin', cache: 'no-store'});
      if (!respuesta.ok) throw new Error();
      const actual = await respuesta.json();
      if (actual.usuario !== usuario) {
        alert('La cuenta abierta cambió. Vuelve a abrir el formulario con la cuenta correcta.');
        location.assign(location.href);
        return;
      }
      if (!cookieCSRF()) {
        alert('Habilita las cookies de este sitio y vuelve a abrir el formulario.');
        return;
      }
      // Todos los formularios de esta página se dibujaron para la misma cuenta.
      document.querySelectorAll('input[name="csrfmiddlewaretoken"]').forEach(campo => {
        if (campo.form && new URL(campo.form.action).origin === location.origin) campo.value = actual.token;
      });
      cookieInicial = cookieCSRF();
      restaurada = false;
      form.requestSubmit(boton || undefined);
    } catch {
      alert('No se pudo comprobar la sesión. Revisa la conexión y vuelve a intentar.');
    } finally {
      renovando = false;
    }
  }, true);
})();
