"""Visibilidad de noticias y aviso a los destinatarios."""

from django.db.models import Q
from django.urls import reverse

from apps.academico.models import AsignacionDocente, Matricula
from apps.accounts.models import Usuario
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import crear_notificaciones

from .models import Noticia


def cursos_del_usuario(user):
    """Ids de curso que le tocan al usuario, para filtrar noticias dirigidas."""
    if user.es_estudiante():
        estudiante = getattr(user, 'estudiante', None)
        if estudiante is None:
            return []
        return list(
            Matricula.objects.filter(estudiante=estudiante, activa=True)
            .values_list('curso_id', flat=True)
        )
    if user.es_padre():
        return list(
            Matricula.objects.filter(estudiante__tutor_id=user.id, activa=True)
            .values_list('curso_id', flat=True)
        )
    return []


def noticias_visibles(user):
    """Queryset de noticias que este usuario puede ver.

    El mismo filtro protege la lista y el detalle, así que no pueden divergir.
    """
    qs = Noticia.objects.select_related('curso', 'publicado_por')
    if user.es_admin():
        return qs                      # el admin ve también los borradores
    qs = qs.filter(publicada=True)
    if user.es_profesor():
        return qs
    return qs.filter(Q(curso__isnull=True) | Q(curso_id__in=cursos_del_usuario(user)))


def destinatarios_de_noticia(noticia):
    """Usuarios que deben recibir el aviso de esta noticia."""
    if noticia.curso_id is None:
        return list(
            Usuario.objects.filter(
                is_active=True,
                rol__in=[Usuario.Rol.ESTUDIANTE, Usuario.Rol.PROFESOR, Usuario.Rol.PADRE],
            ).values_list('pk', flat=True)
        )

    matriculas = Matricula.objects.filter(curso_id=noticia.curso_id, activa=True).select_related('estudiante')
    ids = []
    for matricula in matriculas:
        ids.append(matricula.estudiante.usuario_id)
        ids.append(matricula.estudiante.tutor_id)
    ids.extend(
        AsignacionDocente.objects.filter(curso_id=noticia.curso_id)
        .values_list('profesor_id', flat=True)
    )
    return ids


def notificar_noticia(noticia, excluir=None):
    """Avisa a los destinatarios de una noticia recién publicada."""
    if not noticia.publicada:
        return 0
    return crear_notificaciones(
        destinatarios_de_noticia(noticia),
        tipo=Notificacion.Tipo.NOTICIA,
        titulo=noticia.titulo,
        mensaje=noticia.get_tipo_display(),
        url=reverse('noticias:detalle', args=[noticia.pk]),
        excluir=excluir,
    )
