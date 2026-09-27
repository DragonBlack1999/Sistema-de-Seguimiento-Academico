from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.utils.text import slugify
from django.shortcuts import get_object_or_404, redirect, render

from apps.academico.models import AsignacionDocente, Matricula

from .models import (
    MAXIMO, MAXIMO_AUTOEVALUACION, MAXIMO_EXTRACURRICULAR,
    Actividad, Dimension, Nota, Puntaje, Trimestre,
)
from .services import gestion_actual, notas_de_gestion, pivotar_notas

SIN_PERMISO_MATERIA = 'No tienes permiso para registrar notas de esta materia.'


def _puede_calificar(usuario, asignacion):
    return usuario.es_admin() or (usuario.es_profesor() and asignacion.profesor_id == usuario.id)


def _trimestre_valido(trimestre):
    trimestre = int(trimestre)
    if trimestre not in Trimestre.values:
        raise Http404('Ese trimestre no existe.')
    return trimestre


def _numero(valor, maximo):
    """Devuelve (numero, error). Vacío es válido: significa "sin calificar".

    Las notas se ponen en números enteros, así que un decimal se rechaza en vez
    de guardarse redondeado a espaldas del docente.
    """
    valor = (valor or '').strip().replace(',', '.')
    if valor == '':
        return None, None
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        return None, f'"{valor}" no es un número'
    if numero != numero.to_integral_value():
        return None, f'{valor} tiene decimales: las notas se ponen en números enteros'
    numero = numero.quantize(Decimal('1'))
    if numero < 0 or numero > maximo:
        return None, f'{numero} está fuera de 0 a {maximo:.0f}'
    return numero, None


def _matriculas(asignacion):
    return (
        Matricula.objects.filter(curso=asignacion.curso, activa=True)
        .select_related('estudiante__usuario')
        .order_by('estudiante__usuario__last_name', 'estudiante__usuario__first_name')
    )


# --------------------------------------------------------------- docente

@login_required
def registrar_notas(request, asignacion_id, trimestre):
    """La planilla del docente: actividades por dimensión, autoevaluación y extra.

    La nota del trimestre no se escribe: la calcula `Nota.recalcular()` con lo
    que se carga aquí.
    """
    asignacion = get_object_or_404(
        AsignacionDocente.objects.select_related('materia', 'curso', 'profesor'), pk=asignacion_id,
    )
    if not _puede_calificar(request.user, asignacion):
        return HttpResponseForbidden(SIN_PERMISO_MATERIA)
    trimestre = _trimestre_valido(trimestre)

    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')
        if accion == 'agregar_actividad':
            _agregar_actividad(request, asignacion, trimestre)
        elif accion == 'borrar_actividad':
            _borrar_actividad(request, asignacion, trimestre)
        else:
            _guardar_planilla(request, asignacion, trimestre)
        return redirect('calificaciones:registrar_notas', asignacion_id=asignacion.id, trimestre=trimestre)

    matriculas = list(_matriculas(asignacion))
    actividades = list(Actividad.objects.filter(asignacion=asignacion, trimestre=trimestre))
    puntajes = {
        (p.actividad_id, p.estudiante_id): p.valor
        for p in Puntaje.objects.filter(actividad__in=actividades)
    }
    notas = {
        n.estudiante_id: n
        for n in Nota.objects.filter(asignacion=asignacion, trimestre=trimestre)
        .select_related('autoevaluacion_por')
    }

    # Las columnas que vienen de una tarea llevan su enlace y no se pueden
    # borrar desde aquí: se borran borrando la tarea.
    tareas = _tareas_por_actividad(actividades)
    for actividad in actividades:
        actividad.tarea_asociada = tareas.get(actividad.id)

    dimensiones = [
        {
            'codigo': codigo,
            'nombre': etiqueta,
            'maximo': MAXIMO[codigo],
            'actividades': [a for a in actividades if a.dimension == codigo],
        }
        for codigo, etiqueta in Dimension.choices
    ]
    borrables = [a for a in actividades if a.id not in tareas]

    filas = []
    for matricula in matriculas:
        nota = notas.get(matricula.estudiante_id)
        filas.append({
            'matricula': matricula,
            # Un grupo por dimensión, en el mismo orden que la cabecera: sus
            # actividades y, al final, el promedio de la dimensión.
            'grupos': [
                {
                    'codigo': dimension['codigo'],
                    'celdas': [
                        {
                            'actividad': actividad,
                            'valor': puntajes.get((actividad.id, matricula.estudiante_id), ''),
                        }
                        for actividad in dimension['actividades']
                    ],
                    'promedio': getattr(nota, dimension['codigo'].lower(), None) if nota else None,
                }
                for dimension in dimensiones
            ],
            'nota': nota,
            'autoevaluacion': nota.autoevaluacion if nota and nota.autoevaluacion is not None else '',
            # Para que el docente sepa si el estudiante ya se evaluó y no la pise sin querer.
            'autoevaluacion_del_estudiante': bool(
                nota and nota.autoevaluacion_por_id == matricula.estudiante.usuario_id
            ),
            'extracurricular': nota.extracurricular if nota and nota.extracurricular else '',
        })

    return render(request, 'calificaciones/registrar_notas.html', {
        'asignacion': asignacion,
        'trimestre': trimestre,
        'trimestres': Trimestre.choices,
        'dimensiones': dimensiones,
        'borrables': borrables,
        'cuantas_de_tareas': len(tareas),
        'cuantas_actividades': len(actividades),
        'filas': filas,
        'maximo_autoevaluacion': MAXIMO_AUTOEVALUACION,
        'maximo_extracurricular': MAXIMO_EXTRACURRICULAR,
    })


def _tareas_por_actividad(actividades):
    """{id de actividad: tarea} para las columnas que nacieron de una tarea."""
    from apps.tareas.models import Tarea

    return {
        t.actividad_id: t
        for t in Tarea.objects.filter(actividad__in=actividades)
    }


def _agregar_actividad(request, asignacion, trimestre):
    dimension = request.POST.get('dimension', '')
    if dimension not in Dimension.values:
        messages.error(request, 'Esa dimensión no existe.')
        return
    nombre = (request.POST.get('nombre', '') or '').strip()
    if not nombre:
        messages.error(request, 'Ponle un nombre a la actividad, por ejemplo "Práctico 1".')
        return

    ultimas = Actividad.objects.filter(
        asignacion=asignacion, trimestre=trimestre, dimension=dimension,
    ).order_by('-orden').values_list('orden', flat=True)
    Actividad.objects.create(
        asignacion=asignacion, trimestre=trimestre, dimension=dimension,
        nombre=nombre[:60], orden=(ultimas[0] + 1) if ultimas else 0,
        creada_por=request.user,
    )
    messages.success(request, f'Se agregó "{nombre}" a {Dimension(dimension).label}.')


def _borrar_actividad(request, asignacion, trimestre):
    actividad = Actividad.objects.filter(
        pk=request.POST.get('actividad_id', 0) or 0, asignacion=asignacion, trimestre=trimestre,
    ).first()
    if actividad is None:
        messages.error(request, 'Esa actividad ya no existe.')
        return
    tarea = _tareas_por_actividad([actividad]).get(actividad.id)
    if tarea is not None:
        messages.error(
            request,
            f'«{actividad.etiqueta}» es una tarea. Para quitarla de la planilla, borra la tarea.',
        )
        return

    nombre = actividad.nombre
    with transaction.atomic():
        actividad.delete()
        _recalcular_curso(asignacion, trimestre)
    messages.success(request, f'Se borró "{nombre}" y se recalcularon las notas.')


def _guardar_planilla(request, asignacion, trimestre):
    from apps.comunicaciones.alertas import avisar_nota_baja

    matriculas = list(_matriculas(asignacion))
    actividades = {
        a.id: a for a in Actividad.objects.filter(asignacion=asignacion, trimestre=trimestre)
    }
    problemas = []

    with transaction.atomic():
        for matricula in matriculas:
            estudiante = matricula.estudiante
            quien = str(estudiante)

            for actividad in actividades.values():
                campo = f'p_{actividad.id}_{estudiante.id}'
                # Si el campo no vino en el formulario, esa casilla no se tocó.
                # Solo un campo enviado **en blanco** borra lo que hubiera: de lo
                # contrario un envío parcial arrasaría con la planilla entera.
                if campo not in request.POST:
                    continue
                valor, error = _numero(request.POST[campo], actividad.maximo)
                if error:
                    problemas.append(f'{quien}, {actividad.nombre}: {error}')
                    continue
                if valor is None:
                    # Vacío: la actividad queda sin calificar y no entra al promedio.
                    Puntaje.objects.filter(actividad=actividad, estudiante=estudiante).delete()
                else:
                    Puntaje.objects.update_or_create(
                        actividad=actividad, estudiante=estudiante,
                        defaults={'valor': valor, 'registrado_por': request.user},
                    )

            nota, _ = Nota.objects.get_or_create(
                asignacion=asignacion, estudiante=estudiante, trimestre=trimestre,
                defaults={'registrado_por': request.user},
            )

            campo_auto = f'auto_{estudiante.id}'
            if campo_auto in request.POST:
                auto, error = _numero(request.POST[campo_auto], MAXIMO_AUTOEVALUACION)
                if error:
                    problemas.append(f'{quien}, autoevaluación: {error}')
                elif auto != nota.autoevaluacion:
                    # Queda a nombre de quien la cambió: así el docente ve si se
                    # la puso el propio estudiante.
                    nota.autoevaluacion = auto
                    nota.autoevaluacion_por = request.user

            campo_extra = f'extra_{estudiante.id}'
            if campo_extra in request.POST:
                extra, error = _numero(request.POST[campo_extra], MAXIMO_EXTRACURRICULAR)
                if error:
                    problemas.append(f'{quien}, extracurricular: {error}')
                else:
                    nota.extracurricular = extra or Decimal('0')

            nota.registrado_por = request.user
            nota.recalcular()
            avisar_nota_baja(nota)

    if problemas:
        messages.warning(request, 'No se guardaron estos datos: ' + ' · '.join(problemas[:5])
                         + (f' y {len(problemas) - 5} más' if len(problemas) > 5 else ''))
    messages.success(request, 'Planilla guardada. Las notas del trimestre se recalcularon.')


@login_required
def planilla_excel(request, asignacion_id, trimestre):
    """La misma planilla, en Excel: para archivar o llevarla impresa."""
    asignacion = get_object_or_404(
        AsignacionDocente.objects.select_related('materia', 'curso__gestion', 'profesor'),
        pk=asignacion_id,
    )
    if not _puede_calificar(request.user, asignacion):
        return HttpResponseForbidden(SIN_PERMISO_MATERIA)
    trimestre = _trimestre_valido(trimestre)

    # Importación local: openpyxl solo se carga si alguien descarga.
    from apps.comunicaciones.planilla_notas import libro_de_planilla

    matriculas = list(_matriculas(asignacion))
    actividades = list(Actividad.objects.filter(asignacion=asignacion, trimestre=trimestre))
    puntajes = {
        (p.actividad_id, p.estudiante_id): p.valor
        for p in Puntaje.objects.filter(actividad__in=actividades)
    }
    notas = {
        n.estudiante_id: n
        for n in Nota.objects.filter(asignacion=asignacion, trimestre=trimestre)
    }

    respuesta = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    nombre = slugify(f'{asignacion.materia} {asignacion.curso.grado}{asignacion.curso.paralelo}')
    respuesta['Content-Disposition'] = f'attachment; filename="planilla-{nombre}-t{trimestre}.xlsx"'
    libro_de_planilla(
        asignacion, trimestre, matriculas, actividades, puntajes, notas,
    ).save(respuesta)
    return respuesta


def _recalcular_curso(asignacion, trimestre):
    for nota in Nota.objects.filter(asignacion=asignacion, trimestre=trimestre):
        nota.recalcular()


# --------------------------------------------------------------- estudiante

@login_required
def mi_autoevaluacion(request, trimestre):
    """El estudiante se pone su autoevaluación, de 0 a 5, en cada materia."""
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')
    trimestre = _trimestre_valido(trimestre)

    matricula = (
        estudiante.matriculas.filter(activa=True).select_related('curso__gestion')
        .order_by('-curso__gestion__anio').first()
    )
    asignaciones = list(
        AsignacionDocente.objects.filter(curso=matricula.curso).select_related('materia', 'profesor')
        if matricula else []
    )

    if request.method == 'POST':
        if not asignaciones:
            return HttpResponseNotAllowed(['GET'])
        problemas = 0
        with transaction.atomic():
            # Solo sus materias: el id que llegue de otra no encuentra asignación.
            for asignacion in asignaciones:
                valor, error = _numero(
                    request.POST.get(f'auto_{asignacion.id}'), MAXIMO_AUTOEVALUACION,
                )
                if error:
                    problemas += 1
                    continue
                nota, _ = Nota.objects.get_or_create(
                    asignacion=asignacion, estudiante=estudiante, trimestre=trimestre,
                )
                nota.autoevaluacion = valor
                nota.autoevaluacion_por = request.user
                nota.recalcular()
        if problemas:
            messages.warning(request, f'{problemas} valor(es) quedaron sin guardar: deben ir de 0 a 5.')
        messages.success(request, 'Tu autoevaluación quedó guardada.')
        return redirect('calificaciones:mi_autoevaluacion', trimestre=trimestre)

    notas = {
        n.asignacion_id: n
        for n in Nota.objects.filter(
            estudiante=estudiante, trimestre=trimestre, asignacion__in=asignaciones,
        ).select_related('autoevaluacion_por')
    }
    filas = []
    for asignacion in asignaciones:
        nota = notas.get(asignacion.id)
        filas.append({
            'asignacion': asignacion,
            'valor': nota.autoevaluacion if nota and nota.autoevaluacion is not None else '',
            # Solo si consta quién la puso, y no fue él: si no, diría "la puso tu
            # docente" ante una nota que no puso nadie en particular.
            'la_puso_el_docente': bool(
                nota and nota.autoevaluacion is not None
                and nota.autoevaluacion_por_id
                and nota.autoevaluacion_por_id != request.user.id
            ),
        })

    return render(request, 'calificaciones/mi_autoevaluacion.html', {
        'estudiante': estudiante,
        'curso': matricula.curso if matricula else None,
        'trimestre': trimestre,
        'trimestres': Trimestre.choices,
        'filas': filas,
        'maximo': MAXIMO_AUTOEVALUACION,
    })


@login_required
def mis_notas(request):
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')
    gestion = gestion_actual(estudiante)
    filas, totales = pivotar_notas(notas_de_gestion(estudiante, gestion))

    return render(request, 'calificaciones/mis_notas.html', {
        'estudiante': estudiante, 'filas': filas, 'totales': totales, 'gestion': gestion,
    })


@login_required
def historial_academico(request):
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')

    matriculas = Matricula.objects.filter(estudiante=estudiante).select_related('curso__gestion').order_by('-curso__gestion__anio')

    gestiones = []
    for matricula in matriculas:
        notas = Nota.objects.calificadas().filter(
            estudiante=estudiante, asignacion__curso__gestion=matricula.gestion
        ).select_related('asignacion__materia')
        filas, totales = pivotar_notas(notas)
        gestiones.append({
            'gestion': matricula.gestion,
            'curso': matricula.curso,
            'filas': filas,
            'totales': totales,
        })

    return render(request, 'calificaciones/historial_academico.html', {
        'estudiante': estudiante, 'gestiones': gestiones,
    })
