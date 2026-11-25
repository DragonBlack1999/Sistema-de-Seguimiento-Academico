"""Creación de notificaciones (fan-out).

Se crea una fila por destinatario cuando ocurre el evento, en vez de calcular
las notificaciones al vuelo. El contador de la campanita se muestra en todas las
páginas, así que tiene que ser un COUNT sobre un índice y no varias consultas
cruzadas. Además congela la audiencia en el momento del evento, que es la
semántica correcta: un estudiante que cambia de curso no debe recibir
retroactivamente los avisos viejos de su curso nuevo.
"""

import json

from django.db import transaction
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

from . import push
from .models import Notificacion, SuscripcionPush


def crear_notificaciones(destinatarios, *, tipo, titulo, url, mensaje='', excluir=None,
                         nivel=Notificacion.Nivel.INFORMATIVO, estudiante=None):
    """Crea una notificación por destinatario. Devuelve cuántas creó.

    `destinatarios` acepta objetos Usuario o ids, mezclados. Los repetidos se
    colapsan: un padre con dos hijos en el mismo curso recibe un solo aviso.

    `estudiante` es de quién habla el aviso, cuando habla de uno solo. El resumen
    del día se arma con eso: un mensaje por hijo.

    El **nivel** decide cuándo sale al celular:

    - urgente e informativo salen al instante;
    - los de atención se guardan sin avisar, y el resumen diario los junta en un
      solo mensaje por persona. En la campanita aparecen igual, al momento.
    """
    ids = {getattr(d, 'pk', d) for d in destinatarios}
    ids.discard(None)
    if excluir is not None:
        ids.discard(getattr(excluir, 'pk', excluir))
    if not ids:
        return 0

    al_instante = nivel != Notificacion.Nivel.ATENCION
    Notificacion.objects.bulk_create(
        [
            Notificacion(
                usuario_id=uid, estudiante=estudiante, tipo=tipo, nivel=nivel,
                titulo=titulo[:200], mensaje=mensaje[:300], url=url, avisada=al_instante,
            )
            for uid in sorted(ids)
        ],
        batch_size=500,
    )

    # El mismo aviso, también al celular de quien lo tenga activado. Va aquí y no
    # en cada pantalla: por esta función pasan las citaciones, las tareas y las
    # noticias, así que nadie puede olvidarse de avisar.
    if al_instante:
        from .push import enviar as enviar_al_celular

        enviar_al_celular(sorted(ids), titulo=titulo, mensaje=mensaje, url=url)
    return len(ids)


def enviar_resumen_diario():
    """Junta los avisos de atención en un mensaje al celular por persona y por hijo.

    Devuelve cuántos mensajes salieron. Los avisos ya estaban en la campanita
    desde que ocurrieron; esto es solo el golpe al teléfono, una vez al día, para
    no interrumpir quince veces por la misma tarde.

    Se agrupa **por hijo** y no todo junto: un padre con dos hijos recibe dos
    mensajes, cada uno con el nombre adelante, y así sabe de quién le hablan sin
    abrir nada. Al propio estudiante se le habla de lo suyo, sin repetirle su
    nombre.
    """
    if not push.hay_push():
        return 0

    pendientes = Notificacion.objects.filter(avisada=False, nivel=Notificacion.Nivel.ATENCION)
    grupos = list(pendientes.filter(usuario__suscripciones_push__isnull=False).order_by()
                  .values_list('usuario_id', 'estudiante_id').distinct())
    aceptados = 0
    for usuario_id, estudiante_id in grupos:
        avisos = pendientes.filter(usuario_id=usuario_id, estudiante_id=estudiante_id)
        destinos = SuscripcionPush.objects.filter(usuario_id=usuario_id)
        for destino_id in list(destinos.values_list('pk', flat=True)):
            if _enviar_resumen_al_dispositivo(avisos, destinos, destino_id):
                aceptados += 1

        # Un teléfono caducado deja de ser un destino. Si nadie aceptó, los
        # avisos quedan pendientes para cuando el usuario active un dispositivo.
        completos = avisos.annotate(
            dispositivos=Count('usuario__suscripciones_push', distinct=True),
            confirmaciones=Count('resumen_aceptado_por', distinct=True,
                                 filter=Q(resumen_aceptado_por__usuario_id=usuario_id)),
        ).filter(dispositivos__gt=0, confirmaciones=F('dispositivos'))
        Notificacion.objects.filter(pk__in=completos.values('pk')).update(avisada=True)
    return aceptados


def _enviar_resumen_al_dispositivo(avisos, destinos, destino_id):
    """Manda a un teléfono lo que todavía no recibió. Devuelve si lo aceptó.

    La red queda **fuera** de la transacción. Enviando con el bloqueo tomado,
    un teléfono que no responde mantenía bloqueada su fila los diez segundos
    que tarda el envío en rendirse (`ESPERA` en push.py), y quien justo en ese
    momento activara o desactivara sus avisos quedaba esperando.
    """
    destino, faltantes = _apartar_para(avisos, destinos, destino_id)
    if destino is None:
        return False

    codigo = push.enviar_a_suscripcion(destino, json.dumps(_contenido_resumen(faltantes)))
    if push.aceptado(codigo):
        destino.ultimo_envio = timezone.now()
        destino.save(update_fields=['ultimo_envio'])
        return True

    if codigo in (404, 410):
        # El teléfono ya no existe; lo apartado se va con él.
        destino.delete()
    else:
        # No llegó: vuelven al montón para el intento siguiente.
        destino.avisos_aceptados.remove(*faltantes)
    return False


@transaction.atomic
def _apartar_para(avisos, destinos, destino_id):
    """Reserva para ese teléfono los avisos que todavía no recibió.

    Se aparta **antes** de salir a la red, en una transacción corta. Dos
    ejecuciones que coinciden siguen mandando una sola vez: la segunda espera
    el bloqueo y, cuando lo obtiene, ya no le queda nada que apartar.
    """
    destino = destinos.select_for_update().filter(pk=destino_id).first()
    if destino is None:
        return None, []
    faltantes = list(avisos.exclude(resumen_aceptado_por=destino)
                     .select_related('estudiante__usuario').order_by('fecha_creacion', 'pk'))
    if not faltantes:
        return None, []
    destino.avisos_aceptados.add(*faltantes)
    return destino, faltantes


def _contenido_resumen(avisos):
    primero = avisos[0]
    if len(avisos) == 1:
        return {'titulo': primero.titulo, 'mensaje': primero.mensaje, 'url': primero.url}

    titulo = f'{len(avisos)} avisos {_de_quien(primero, primero.usuario_id)}'
    mensaje = ' · '.join(_sin_el_nombre(aviso) for aviso in avisos[:3])
    if len(avisos) > 3:
        mensaje += f' y {len(avisos) - 3} más'
    return {'titulo': titulo, 'mensaje': mensaje[:300], 'url': reverse('notificaciones:lista')}


def _de_quien(aviso, usuario_id):
    """«de Andrés» para el padre, «del colegio» para el propio estudiante."""
    estudiante = aviso.estudiante
    if estudiante is None or estudiante.usuario_id == usuario_id:
        return 'del colegio'
    return f'de {estudiante.usuario.first_name or estudiante.usuario.get_full_name()}' 


def destinatarios_de_estudiante(estudiante):
    """El propio estudiante y su tutor (si tiene cuenta)."""
    return [estudiante.usuario_id, estudiante.tutor_id]


def _sin_el_nombre(aviso):
    """El título del aviso sin el «— Nombre Apellido» que lleva el del tutor."""
    if aviso.estudiante is None:
        return aviso.titulo
    return aviso.titulo.replace(f' — {aviso.estudiante.usuario.get_full_name()}', '')
