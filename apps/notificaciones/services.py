"""Creación de notificaciones (fan-out).

Se crea una fila por destinatario cuando ocurre el evento, en vez de calcular
las notificaciones al vuelo. El contador de la campanita se muestra en todas las
páginas, así que tiene que ser un COUNT sobre un índice y no varias consultas
cruzadas. Además congela la audiencia en el momento del evento, que es la
semántica correcta: un estudiante que cambia de curso no debe recibir
retroactivamente los avisos viejos de su curso nuevo.
"""

from .models import Notificacion


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
    import collections

    from django.urls import reverse

    from .push import enviar as enviar_al_celular

    pendientes = list(
        Notificacion.objects.filter(avisada=False)
        .select_related('estudiante__usuario')
        .order_by('usuario_id', 'fecha_creacion')
    )
    if not pendientes:
        return 0

    grupos = collections.defaultdict(list)
    for aviso in pendientes:
        grupos[(aviso.usuario_id, aviso.estudiante_id)].append(aviso)

    for (usuario_id, _estudiante_id), avisos in grupos.items():
        if len(avisos) == 1:
            titulo, mensaje, url = avisos[0].titulo, avisos[0].mensaje, avisos[0].url
        else:
            titulo = f'{len(avisos)} avisos {_de_quien(avisos[0], usuario_id)}'
            # El nombre ya va en el título: repetirlo en cada línea no deja sitio
            # para lo que de verdad pasó.
            mensaje = ' · '.join(_sin_el_nombre(aviso) for aviso in avisos[:3])
            if len(avisos) > 3:
                mensaje += f' y {len(avisos) - 3} más'
            url = reverse('notificaciones:lista')
        enviar_al_celular(
            [usuario_id], titulo=titulo, mensaje=mensaje[:300], url=url, en_segundo_plano=False,
        )

    Notificacion.objects.filter(pk__in=[aviso.pk for aviso in pendientes]).update(avisada=True)
    return len(grupos)


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
