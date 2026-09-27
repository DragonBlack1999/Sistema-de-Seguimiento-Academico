"""Cuándo avisar a la familia, y con cuánta urgencia.

Tres niveles, y el nivel no es un color: decide cuándo sale el aviso al celular.

- **Informativo**: llegó tarde. Sale al momento, sin insistir.
- **Atención**: faltó, no entregó una tarea, sacó menos de 51. Se guarda y sale
  en el resumen del día, junto con los demás. Un padre con un hijo de trece
  materias que recibe quince avisos sueltos termina por no mirar ninguno.
- **Urgente**: citación, faltas acumuladas, tareas sin entregar una tras otra,
  materia reprobada. Sale sola y al instante.

Cada aviso deja una marca (`AlertaEmitida`) para no repetirse: la revisión
nocturna vuelve a ver la misma tarea vencida todos los días hasta fin de año.
"""
import datetime

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.asistencia.models import Asistencia
from apps.calificaciones.models import NOTA_APROBACION
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import crear_notificaciones

from .emails import enviar_notificacion_citacion
from .models import AlertaEmitida, Citacion


def ya_avisado(estudiante, clave):
    """True si ese hecho ya se avisó. Si es la primera vez, deja la marca puesta."""
    _, creada = AlertaEmitida.objects.get_or_create(estudiante=estudiante, clave=clave[:80])
    return not creada


def olvidar(estudiante, clave):
    """Borra la marca: el hecho dejó de ser cierto y podría volver a ocurrir."""
    AlertaEmitida.objects.filter(estudiante=estudiante, clave=clave[:80]).delete()


def _avisar(estudiante, *, tipo, nivel, titulo, mensaje, url_estudiante, url_tutor,
            tambien_al_estudiante=True):
    """Manda el aviso al estudiante y a su tutor, cada uno a su propia pantalla."""
    if tambien_al_estudiante:
        crear_notificaciones(
            [estudiante.usuario_id], tipo=tipo, nivel=nivel, estudiante=estudiante,
            titulo=titulo, mensaje=mensaje, url=url_estudiante,
        )
    if estudiante.tutor_id:
        crear_notificaciones(
            [estudiante.tutor_id], tipo=tipo, nivel=nivel, estudiante=estudiante,
            titulo=f'{titulo} — {estudiante.usuario.get_full_name()}',
            mensaje=mensaje, url=url_tutor,
        )


# ──────────────────────────────── citaciones ────────────────────────────────

def notificar_citacion(citacion):
    """Avisa al estudiante y a su tutor. Una citación siempre es urgente."""
    estudiante = citacion.estudiante
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.CITACION, nivel=Notificacion.Nivel.URGENTE,
        titulo=f'Citación para el {citacion.fecha:%d/%m/%Y}',
        mensaje=citacion.motivo[:300],
        url_estudiante=reverse('comunicaciones:lista_citaciones'),
        url_tutor=reverse('padres:citaciones_hijo', args=[estudiante.pk]),
    )


def verificar_alerta_faltas(estudiante, gestion, generado_por=None):
    """Genera una citación automática si el estudiante cruzó el umbral de faltas de la gestión.

    Devuelve la Citacion creada, o None si no correspondía generar una.
    """
    total_faltas = Asistencia.objects.filter(
        estudiante=estudiante, estado=Asistencia.Estado.FALTA, fecha__year=gestion.anio,
    ).count()

    if total_faltas < settings.UMBRAL_FALTAS_ALERTA:
        return None

    ya_tiene_pendiente = Citacion.objects.filter(
        estudiante=estudiante, es_automatica=True, estado=Citacion.Estado.PENDIENTE,
    ).exists()
    if ya_tiene_pendiente:
        return None

    citacion = Citacion.objects.create(
        estudiante=estudiante,
        motivo=f'Inasistencias reiteradas: acumula {total_faltas} faltas en la gestión {gestion}.',
        fecha=timezone.localdate() + datetime.timedelta(days=3),
        es_automatica=True,
        generado_por=generado_por,
    )
    enviar_notificacion_citacion(citacion)
    notificar_citacion(citacion)
    return citacion


# ──────────────────────────────── asistencia ────────────────────────────────

def avisar_falta(estudiante, fecha):
    """No vino hoy. Va en el resumen del día, no interrumpe."""
    if ya_avisado(estudiante, f'falta:{fecha}'):
        return False
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.ASISTENCIA, nivel=Notificacion.Nivel.ATENCION,
        titulo='No asistió a clases',
        mensaje=f'Falta registrada el {fecha:%d/%m/%Y}.',
        url_estudiante=reverse('asistencia:mi_asistencia'),
        url_tutor=reverse('padres:asistencia_hijo', args=[estudiante.pk]),
    )
    return True


def avisar_atraso(estudiante, fecha, hora):
    """Llegó tarde. Es un dato, no una alarma."""
    if ya_avisado(estudiante, f'atraso:{fecha}'):
        return False
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.ASISTENCIA, nivel=Notificacion.Nivel.INFORMATIVO,
        titulo='Llegó con atraso',
        mensaje=f'Entró a las {hora:%H:%M} del {fecha:%d/%m/%Y}.',
        url_estudiante=reverse('asistencia:mi_asistencia'),
        url_tutor=reverse('padres:asistencia_hijo', args=[estudiante.pk]),
    )
    return True


# ──────────────────────────────── calificaciones ────────────────────────────

def avisar_nota_baja(nota):
    """La nota de un trimestre quedó bajo lo que se necesita para aprobar.

    Si después sube, se borra la marca: si vuelve a bajar, vuelve a avisar.
    """
    clave = f'nota-baja:{nota.asignacion_id}:{nota.trimestre}'
    if nota.nota is None or nota.nota >= NOTA_APROBACION:
        olvidar(nota.estudiante, clave)
        return False
    if ya_avisado(nota.estudiante, clave):
        return False

    materia = nota.asignacion.materia
    _avisar(
        nota.estudiante,
        tipo=Notificacion.Tipo.NOTA, nivel=Notificacion.Nivel.ATENCION,
        titulo=f'Nota baja en {materia}',
        mensaje=(f'{nota.nota:.0f} en el {nota.get_trimestre_display().lower()}. '
                 f'Se aprueba con {NOTA_APROBACION}.'),
        url_estudiante=reverse('calificaciones:mis_notas'),
        url_tutor=reverse('padres:notas_hijo', args=[nota.estudiante_id]),
    )
    return True


def avisar_materia_reprobada(estudiante, asignacion, promedio):
    """El promedio de la materia ya no alcanza. Esto sí interrumpe."""
    if ya_avisado(estudiante, f'reprobada:{asignacion.pk}'):
        return False
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.NOTA, nivel=Notificacion.Nivel.URGENTE,
        titulo=f'Está reprobando {asignacion.materia}',
        mensaje=(f'Su promedio va en {promedio:.0f} y se aprueba con {NOTA_APROBACION}. '
                 'Conviene hablar con el docente.'),
        url_estudiante=reverse('calificaciones:mis_notas'),
        url_tutor=reverse('padres:notas_hijo', args=[estudiante.pk]),
    )
    return True


# ──────────────────────────────── tareas ────────────────────────────────────

def avisar_tarea_sin_entregar(estudiante, tarea):
    """Venció el plazo y no entregó."""
    if ya_avisado(estudiante, f'tarea:{tarea.pk}'):
        return False
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.TAREA, nivel=Notificacion.Nivel.ATENCION,
        titulo=f'No entregó: {tarea.titulo}',
        mensaje=(f'{tarea.asignacion.materia} · el plazo venció el '
                 f'{tarea.fecha_entrega:%d/%m/%Y}.'),
        url_estudiante=reverse('tareas:mis_tareas'),
        url_tutor=reverse('padres:tareas_hijo', args=[estudiante.pk]),
    )
    return True


def avisar_racha_tareas(estudiante, cuantas):
    """Varias tareas seguidas sin entregar. Deja de ser un descuido.

    Se avisa cada vez que se completa otro grupo del umbral (3, 6, 9…), no en
    cada tarea: si no, el aviso urgente se volvería rutina y perdería su sentido.
    """
    umbral = settings.UMBRAL_TAREAS_SIN_ENTREGAR
    if cuantas < umbral:
        return False
    if ya_avisado(estudiante, f'racha:{cuantas // umbral}'):
        return False
    _avisar(
        estudiante,
        tipo=Notificacion.Tipo.TAREA, nivel=Notificacion.Nivel.URGENTE,
        titulo=f'{cuantas} tareas sin entregar',
        mensaje='Se le acumulan las tareas vencidas. Conviene revisarlo en casa hoy mismo.',
        url_estudiante=reverse('tareas:mis_tareas'),
        url_tutor=reverse('padres:tareas_hijo', args=[estudiante.pk]),
    )
    return True
