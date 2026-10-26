"""Las cifras del panel de dirección.

El panel no repite al Tablero: el Tablero es para sentarse a mirar —tendencias,
rendimiento por materia, quién necesita atención— y el panel es lo primero que
se ve al entrar. Por eso aquí van los números que **cambian hoy** y las cosas
que están trabadas esperando a alguien, con un enlace al Tablero para el resto.

Las tres cifras que había antes (estudiantes, cursos, matrículas activas) no
cambian de un mes al otro: no son noticia, son contexto, y bajan al pie.
"""
from django.db.models import Avg
from django.utils import timezone

from apps.academico.models import Curso, Matricula
from apps.asistencia.models import Asistencia
from apps.calificaciones.models import NOTA_APROBACION, Nota
from apps.comunicaciones.models import Citacion
from apps.tareas.models import EntregaTarea


def cifras_del_dia(gestion):
    """Lo que un director mira al entrar: cómo va hoy y cómo va el año."""
    from apps.asistencia.services import matriculas_del_dia

    hoy = timezone.localdate()
    esperados = matriculas_del_dia(gestion, hoy).count()
    registros = Asistencia.objects.filter(fecha=hoy).values_list('estado', flat=True)
    entraron = sum(1 for e in registros
                   if e in (Asistencia.Estado.PRESENTE, Asistencia.Estado.ATRASO))

    notas = Nota.objects.calificadas().filter(asignacion__curso__gestion=gestion)
    promedio = notas.aggregate(p=Avg('nota'))['p']

    # Reprobando: por promedio del estudiante en todo lo cargado, que es como
    # se decide si alguien está en riesgo, no materia por materia.
    por_estudiante = notas.values('estudiante').annotate(p=Avg('nota'))
    reprobando = sum(1 for fila in por_estudiante
                     if fila['p'] is not None and fila['p'] < NOTA_APROBACION)

    return {
        'esperados': esperados,
        'entraron': entraron,
        'asistencia': round(entraron / esperados * 100) if esperados else None,
        'promedio': round(float(promedio), 1) if promedio is not None else None,
        'reprobando': reprobando,
        'evaluados': por_estudiante.count(),
        'citaciones': Citacion.objects.filter(estado=Citacion.Estado.PENDIENTE).count(),
    }


def contexto(gestion):
    """Lo que no cambia de un mes al otro. Va al pie, como contexto."""
    from apps.accounts.models import Usuario

    return {
        'estudiantes': Matricula.objects.filter(activa=True, curso__gestion=gestion).count(),
        'cursos': Curso.objects.filter(gestion=gestion).count(),
        'docentes': Usuario.objects.filter(rol=Usuario.Rol.PROFESOR, is_active=True).count(),
    }


def trabado(gestion):
    """Lo que está esperando a que alguien lo destrabe, con a dónde ir.

    Es un adelanto del Tablero, no una copia: aquí van solo las cosas que
    tienen un responsable y una pantalla donde resolverse.
    """
    from apps.accounts.claves import pendientes as claves_pendientes
    from apps.accounts.tablero import _dias_de_clase
    from apps.tareas.notas import sin_calificar

    lista = []

    cuantas = claves_pendientes().count()
    if cuantas:
        lista.append({
            'tono': 'urgente',
            'texto': f'{cuantas} persona{"" if cuantas == 1 else "s"} no puede entrar al sistema '
                     f'y pidió que le devuelvan su contraseña.',
            'url_nombre': 'accounts:solicitudes_de_clave',
            'accion': 'Atender',
        })

    # Días de clase de la última semana en los que nadie registró asistencia.
    fechas = _dias_de_clase(timezone.localdate(), 6)
    con_registro = set(Asistencia.objects.filter(fecha__in=fechas)
                       .values_list('fecha', flat=True))
    faltantes = [f for f in fechas if f not in con_registro]
    if faltantes:
        lista.append({
            'tono': 'urgente',
            'texto': 'Sin asistencia registrada: '
                     + ', '.join(f.strftime('%d/%m') for f in faltantes) + '.',
            'url_nombre': 'asistencia:puerta',
            'accion': 'Registrar',
        })

    entregas = sin_calificar(EntregaTarea.objects.filter(
        estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
        tarea__asignacion__curso__gestion=gestion,
    )).count()
    if entregas:
        lista.append({
            'tono': 'atencion',
            'texto': f'{entregas} entrega{"" if entregas == 1 else "s"} de tarea esperan '
                     f'calificación de sus docentes.',
            'url_nombre': 'accounts:tablero',
            'accion': 'Ver quiénes',
        })

    return lista
