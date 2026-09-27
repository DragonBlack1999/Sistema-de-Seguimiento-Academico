from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario

from .forms import MensajeForm
from .models import Conversacion, Mensaje
from .services import buscar_contactos, puede_conversar, usuarios_contactables

MENSAJE_SIN_PERMISO = 'No tienes permiso para conversar con esta persona.'


def _con_buscador(usuario):
    """La administración y los docentes tienen cientos de contactos: buscan en vez de recorrer."""
    return usuario.es_admin() or usuario.es_profesor()


def _contacto_o_none(usuario, otro_id):
    """Resuelve al interlocutor *dentro* de la consulta de contactos permitidos.

    Al filtrar por id sobre `usuarios_contactables`, un usuario no permitido
    simplemente no existe para esta consulta: no hace falta comparar después, y
    "no existe" y "no permitido" devuelven la misma respuesta.
    """
    return usuarios_contactables(usuario).filter(pk=otro_id).first()


@login_required
def bandeja(request):
    """Conversaciones existentes + a quién se puede escribir.

    Un estudiante o un padre tienen pocos contactos y los ven todos. La
    administración y los docentes tienen cientos (la administración, a todo el
    colegio): una lista de botones así no se recorre, así que buscan.
    """
    yo = request.user

    conversaciones = (
        Conversacion.objects
        .filter(Q(usuario_menor=yo) | Q(usuario_mayor=yo), fecha_ultimo_mensaje__isnull=False)
        .select_related('usuario_menor', 'usuario_mayor')
        .annotate(no_leidos=Count('mensajes', filter=Q(mensajes__destinatario=yo, mensajes__leido=False)))
    )

    filas = []
    for conversacion in conversaciones:
        ultimo = conversacion.mensajes.order_by('-fecha_envio').first()
        filas.append({
            'otro': conversacion.otro_participante(yo),
            'ultimo': ultimo,
            'no_leidos': conversacion.no_leidos,
        })

    con_buscador = _con_buscador(yo)
    contactos = []
    if not con_buscador:
        con_conversacion = {fila['otro'].pk for fila in filas}
        contactos = [c for c in usuarios_contactables(yo) if c.pk not in con_conversacion]

    return render(request, 'mensajeria/bandeja.html', {
        'filas': filas, 'contactos': contactos, 'con_buscador': con_buscador,
    })


@login_required
def sugerencias_contactos(request):
    """Sugerencias del buscador de la bandeja, mientras se escribe."""
    yo = request.user
    if not _con_buscador(yo):
        return HttpResponseForbidden('El buscador de contactos es para la administración y los docentes.')

    consulta = request.GET.get('q', '').strip()
    if len(consulta) < 2:
        # Con una sola letra la lista sería medio colegio: no orienta a nadie.
        return JsonResponse({'resultados': []})

    resultados = buscar_contactos(yo, consulta)
    for resultado in resultados:
        resultado['url'] = reverse('mensajeria:conversacion', args=[resultado['id']])
    return JsonResponse({'resultados': resultados})


@login_required
def conversacion(request, usuario_id):
    otro = _contacto_o_none(request.user, usuario_id)
    if otro is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    hilo, _ = Conversacion.entre(request.user, otro)

    if request.method == 'POST':
        form = MensajeForm(request.POST, request.FILES)
        if form.is_valid():
            mensaje = form.save(commit=False)
            mensaje.conversacion = hilo
            mensaje.autor = request.user
            mensaje.destinatario = otro
            if mensaje.archivo:
                mensaje.archivo_nombre = Path(mensaje.archivo.name).name[:255]
            mensaje.save()
            hilo.fecha_ultimo_mensaje = mensaje.fecha_envio
            hilo.save(update_fields=['fecha_ultimo_mensaje'])
            return redirect('mensajeria:conversacion', usuario_id=otro.pk)
    else:
        form = MensajeForm()

    # Abrir la conversación marca como leído lo que mandó el otro.
    hilo.mensajes.filter(destinatario=request.user, leido=False).update(leido=True)

    mensajes = hilo.mensajes.select_related('autor')
    ultimo_id = mensajes.last().pk if mensajes else 0

    return render(request, 'mensajeria/conversacion.html', {
        'otro': otro,
        'mensajes': mensajes,
        'form': form,
        'ultimo_id': ultimo_id,
        'url_nuevos': reverse('mensajeria:nuevos_mensajes', args=[otro.pk]),
    })


@login_required
def nuevos_mensajes(request, usuario_id):
    """JSON con los mensajes posteriores a `desde`, para la actualización automática.

    Repite el control de permiso a propósito: proteger solo la página que llama
    a este endpoint no protegería el endpoint.
    """
    otro = _contacto_o_none(request.user, usuario_id)
    if otro is None:
        return HttpResponseForbidden(MENSAJE_SIN_PERMISO)

    try:
        desde = int(request.GET.get('desde', 0))
    except (TypeError, ValueError):
        desde = 0

    menor_id, mayor_id = sorted((request.user.pk, otro.pk))
    hilo = Conversacion.objects.filter(usuario_menor_id=menor_id, usuario_mayor_id=mayor_id).first()
    if hilo is None:
        return JsonResponse({'mensajes': []})

    nuevos = list(hilo.mensajes.filter(pk__gt=desde).select_related('autor'))
    hilo.mensajes.filter(pk__gt=desde, destinatario=request.user, leido=False).update(leido=True)

    return JsonResponse({'mensajes': [
        {
            'id': m.pk,
            'cuerpo': m.cuerpo,
            'es_mio': m.autor_id == request.user.pk,
            'autor': m.autor.get_full_name(),
            'fecha': timezone.localtime(m.fecha_envio).strftime('%d/%m/%Y %H:%M'),
            'adjunto_nombre': m.archivo_nombre if m.archivo else '',
            'adjunto_url': reverse('mensajeria:descargar_adjunto', args=[m.pk]) if m.archivo else '',
        }
        for m in nuevos
    ]})


@login_required
def descargar_adjunto(request, mensaje_id):
    mensaje = get_object_or_404(Mensaje, pk=mensaje_id)
    if request.user.pk not in (mensaje.autor_id, mensaje.destinatario_id):
        return HttpResponseForbidden('No tienes permiso para descargar este archivo.')
    if not mensaje.archivo:
        raise Http404('El archivo no existe.')
    return FileResponse(
        mensaje.archivo.open('rb'), as_attachment=True,
        filename=mensaje.archivo_nombre or Path(mensaje.archivo.name).name,
    )
