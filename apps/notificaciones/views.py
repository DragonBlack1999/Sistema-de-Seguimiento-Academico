import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notificacion, SuscripcionPush


def _destino_seguro(request, destino, por_defecto):
    """Evita un open redirect si alguna vez la URL viniera de datos editables."""
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return por_defecto


@login_required
def contador(request):
    """Cuántos avisos y mensajes sin leer tiene quien pregunta.

    Existe para que la barra de arriba se ponga al día sin recargar la página.
    Son dos COUNT sobre índices: tiene que ser barato, porque lo llama cada
    pestaña abierta del colegio.
    """
    from apps.mensajeria.models import Mensaje

    return JsonResponse({
        'notificaciones': Notificacion.objects.filter(
            usuario_id=request.user.pk, leida=False).count(),
        'mensajes': Mensaje.objects.filter(
            destinatario_id=request.user.pk, leido=False).count(),
    })


@login_required
def abrir(request, pk):
    notificacion = Notificacion.objects.filter(pk=pk, usuario=request.user).first()
    if notificacion is None:
        return HttpResponseForbidden('Esa notificación no existe o no es tuya.')

    if not notificacion.leida:
        Notificacion.objects.filter(pk=notificacion.pk).update(leida=True)

    return redirect(_destino_seguro(request, notificacion.url, reverse('notificaciones:lista')))


@login_required
@require_POST
def activar_avisos(request):
    """Guarda el teléfono que acaba de aceptar recibir avisos.

    El navegador da una dirección única por dispositivo. Si esa dirección ya
    estaba (el mismo teléfono, otra cuenta, o la misma persona reinstalando),
    se reasigna a quien está entrando: es suya ahora.
    """
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles.'}, status=400)

    endpoint = (datos.get('endpoint') or '').strip()
    claves = datos.get('keys') or {}
    if not endpoint or not claves.get('p256dh') or not claves.get('auth'):
        return JsonResponse({'ok': False, 'error': 'Faltan datos de la suscripción.'}, status=400)

    SuscripcionPush.objects.update_or_create(
        endpoint=endpoint[:500],
        defaults={
            'usuario': request.user,
            'p256dh': claves['p256dh'][:120],
            'auth': claves['auth'][:60],
            'dispositivo': (datos.get('dispositivo') or '')[:120],
        },
    )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def desactivar_avisos(request):
    """Quita este teléfono. Solo puede quitar los suyos."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles.'}, status=400)

    borradas, _ = SuscripcionPush.objects.filter(
        usuario=request.user, endpoint=(datos.get('endpoint') or '').strip(),
    ).delete()
    return JsonResponse({'ok': True, 'borradas': borradas})


@login_required
def lista(request):
    notificaciones = Notificacion.objects.filter(usuario=request.user)[:100]
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': notificaciones,
        'dispositivos': SuscripcionPush.objects.filter(usuario=request.user),
    })


@login_required
@require_POST
def marcar_todas(request):
    marcadas = Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    if marcadas:
        messages.success(request, f'Se marcaron {marcadas} notificación(es) como leídas.')
    volver = request.POST.get('volver') or request.META.get('HTTP_REFERER', '')
    return redirect(_destino_seguro(request, volver, reverse('accounts:redirigir_dashboard')))
