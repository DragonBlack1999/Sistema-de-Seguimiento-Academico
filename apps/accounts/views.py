from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from . import resumenes, tablero
from .forms import LoginForm
from .models import Usuario


class AccountsLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def redirigir_dashboard(request):
    rol = request.user.rol
    if rol == Usuario.Rol.ADMIN:
        return redirect('accounts:dashboard_admin')
    if rol == Usuario.Rol.PROFESOR:
        return redirect('accounts:dashboard_profesor')
    if rol == Usuario.Rol.PADRE:
        return redirect('padres:panel')
    if rol == Usuario.Rol.REGENTE:
        return redirect('accounts:dashboard_regente')
    return redirect('accounts:dashboard_estudiante')


@login_required
def dashboard_admin(request):
    from apps.academico.models import Curso, Estudiante, Matricula
    from apps.asistencia.services import gestion_vigente
    from apps.comunicaciones.models import Citacion

    gestion = gestion_vigente()
    return render(request, 'accounts/dashboard_admin.html', {
        'avisos': resumenes.para_direccion(gestion),
        'hoy': timezone.localdate(),
        'total_estudiantes': Estudiante.objects.count(),
        'total_cursos': Curso.objects.count(),
        'matriculas_activas': Matricula.objects.filter(activa=True).count(),
        'citaciones_pendientes': Citacion.objects.filter(estado=Citacion.Estado.PENDIENTE).count(),
    })


@login_required
def dashboard_profesor(request):
    from apps.academico.models import AsignacionDocente

    from apps.tareas.models import EntregaTarea

    asignaciones = AsignacionDocente.objects.filter(
        profesor=request.user
    ).select_related('curso__gestion', 'materia')

    # Entregas que el estudiante ya hizo y el profesor todavia no califico.
    # "Sin calificar" es no tener nota en la planilla: ahi vive la nota.
    from apps.tareas.notas import sin_calificar

    por_calificar = sin_calificar(EntregaTarea.objects.filter(
        tarea__asignacion__profesor=request.user,
        estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
    )).count()

    return render(request, 'accounts/dashboard_profesor.html', {
        'asignaciones': asignaciones, 'por_calificar': por_calificar,
        # Sus materias salen de lo que dicta, no de una columna en su usuario.
        'materias': sorted({str(a.materia) for a in asignaciones}),
    })


@login_required
def dashboard_estudiante(request):
    from apps.academico.models import Estudiante
    from apps.comunicaciones.models import Citacion

    from apps.asistencia.models import Asistencia
    from apps.calificaciones.services import gestion_actual, notas_de_gestion
    from apps.calificaciones.services import pivotar_notas
    from apps.tareas.models import EntregaTarea, Tarea

    estudiante = (
        Estudiante.objects.filter(usuario=request.user)
        .prefetch_related('matriculas__curso__gestion').first()
    )
    if estudiante is None:
        return render(request, 'accounts/dashboard_estudiante.html', {'estudiante': None})

    _, totales = pivotar_notas(notas_de_gestion(estudiante, gestion_actual(estudiante)))
    promedio = totales['promedio'] if totales and totales['promedio'] != '-' else None

    matricula = estudiante.matriculas.filter(activa=True).select_related('curso__gestion').first()
    pendientes = 0
    if matricula is not None:
        tareas = Tarea.objects.filter(
            asignacion__curso=matricula.curso,
            fecha_entrega__gte=timezone.localdate(),
        )
        entregadas = set(
            EntregaTarea.objects.filter(
                estudiante=estudiante, tarea__in=tareas,
                estado__in=[EntregaTarea.Estado.ENTREGADA, EntregaTarea.Estado.ATRASADA],
            ).values_list('tarea_id', flat=True)
        )
        pendientes = sum(1 for t in tareas if t.pk not in entregadas)

    return render(request, 'accounts/dashboard_estudiante.html', {
        'estudiante': estudiante,
        'avisos': resumenes.para_estudiante(estudiante),
        'promedio': promedio,
        'tareas_pendientes': pendientes,
        'faltas': Asistencia.objects.filter(
            estudiante=estudiante, estado=Asistencia.Estado.FALTA,
        ).count(),
        'citaciones': Citacion.objects.filter(estudiante=estudiante).order_by('-fecha')[:5],
    })


@login_required
def dashboard_regente(request):
    if not (request.user.es_regente() or request.user.es_admin()):
        return HttpResponseForbidden('Esta sección es solo para el regente.')

    from apps.asistencia.models import Asistencia
    from apps.asistencia.services import gestion_vigente, matriculas_del_dia, resumen_por_estado

    hoy = timezone.localdate()
    gestion = gestion_vigente()
    registros = list(Asistencia.objects.filter(fecha=hoy)) if gestion else []

    resumen = resumen_por_estado(registros)
    total = matriculas_del_dia(gestion, hoy).count() if gestion else 0
    resumen['sin_registrar'] = max(0, total - len(registros))

    return render(request, 'accounts/dashboard_regente.html', {
        'hoy': hoy, 'resumen': resumen, 'avisos': resumenes.para_regente(gestion),
    })


@login_required
def tablero_direccion(request):
    """Tablero grande de dirección: lo que hace falta para decidir."""
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo el administrador puede ver el tablero de dirección.')

    from apps.asistencia.services import gestion_vigente

    gestion = gestion_vigente()
    if gestion is None:
        return render(request, 'accounts/tablero.html', {'sin_gestion': True})

    atencion, total_atencion = tablero.necesitan_atencion(gestion)
    return render(request, 'accounts/tablero.html', {
        'gestion': gestion,
        'hoy': timezone.localdate(),
        'cifras': tablero.cifras(gestion),
        'atencion': atencion,
        'total_atencion': total_atencion,
        'materias': tablero.rendimiento_por_materia(gestion),
        'asistencia': tablero.asistencia_por_dia(gestion),
        'pendientes': tablero.pendientes(gestion),
    })
