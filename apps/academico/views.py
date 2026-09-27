from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.models import Usuario

from .forms import AsignacionDocenteForm, PerfilEstudianteForm
from .models import AsignacionDocente, Curso, Horario, Materia, Periodo


def _construir_grilla(horarios, periodos):
    """Arma la grilla semanal: las filas son los períodos del día.

    Las celdas se buscan por el **orden** del período, no por su identificador.
    Cada curso tiene sus propios períodos, así que el profesor que dicta en
    varios cursos tiene varios "período 1": si se buscara por identificador,
    solo aparecerían las clases del curso cuyo período quedó en la fila y el
    resto desaparecería sin aviso.
    """
    celdas = {}
    for horario in horarios:
        celdas.setdefault((horario.periodo.orden, horario.dia), []).append(horario)

    filas = []
    for periodo in periodos:
        filas.append({
            'nombre': periodo.nombre,
            'es_recreo': periodo.es_recreo,
            'celdas': [
                {'dia': codigo, 'clases': celdas.get((periodo.orden, codigo), [])}
                for codigo, _ in Horario.Dia.choices
            ],
        })
    return filas


def _periodos_sin_repetir(periodos):
    """Ordena los períodos y descarta los que ocupan el mismo lugar del día.

    Un profesor dicta en varios cursos, y el período 1 de uno es la misma fila
    que el período 1 de otro: se muestra una sola vez.
    """
    vistos, unicos = set(), []
    for periodo in sorted(periodos, key=lambda p: p.orden):
        if periodo.orden not in vistos:
            vistos.add(periodo.orden)
            unicos.append(periodo)
    return unicos


def _colorear_por_materia(horarios):
    """Asigna a cada clase un color estable según su materia.

    Se enumeran las materias presentes en vez de usar el id con módulo: así dos
    materias distintas nunca comparten color mientras quepan en la paleta.
    """
    TOTAL_COLORES = 8
    colores = {}
    for horario in horarios:
        materia_id = horario.asignacion.materia_id
        if materia_id not in colores:
            colores[materia_id] = len(colores) % TOTAL_COLORES
        horario.color = colores[materia_id]


@login_required
def mi_horario(request):
    if not (request.user.es_admin() or request.user.es_profesor() or request.user.es_estudiante()):
        return HttpResponseForbidden('Tu usuario no tiene un horario de clases asignado.')

    todos = list(
        Horario.objects.select_related(
            'asignacion__curso', 'asignacion__materia', 'asignacion__profesor', 'periodo',
        ).order_by('periodo__orden')
    )

    # Ya no se calcula la "primera hora": servía para saber qué profesor tomaba
    # la asistencia, y ahora la registra el regente en la puerta.
    _colorear_por_materia(todos)

    tableros = []
    if request.user.es_profesor():
        mios = [h for h in todos if h.asignacion.profesor_id == request.user.id]
        # Un profesor dicta en varios cursos: se muestran los períodos de todos
        # ellos, sin repetir el mismo lugar del día. El recreo se agrega aparte
        # porque no tiene clases y si no, su fila no saldría.
        descansos = Periodo.objects.filter(
            curso_id__in={h.asignacion.curso_id for h in mios}, es_recreo=True,
        )
        periodos = _periodos_sin_repetir([h.periodo for h in mios] + list(descansos))
        # Sus materias salen de las clases que realmente tiene: `Usuario.materia`
        # guarda solo una y aquí hay quien dicta tres.
        suyas = sorted({str(h.asignacion.materia) for h in mios})
        tableros.append({
            'titulo': 'Mis clases',
            'subtitulo': ' · '.join(suyas),
            'mostrar_curso': True,
            'filas': _construir_grilla(mios, periodos),
        })

    elif request.user.es_estudiante():
        estudiante = getattr(request.user, 'estudiante', None)
        curso = estudiante.curso_actual if estudiante else None
        if curso is not None:
            tableros.append({
                'titulo': str(curso),
                'subtitulo': '',
                'mostrar_curso': False,
                'filas': _construir_grilla(
                    [h for h in todos if h.asignacion.curso_id == curso.pk],
                    Periodo.objects.filter(curso=curso).order_by('orden'),
                ),
            })

    elif request.user.es_admin():
        # El admin ve un tablero por curso: una sola grilla mezclaría cursos
        # distintos en la misma franja.
        for curso in Curso.objects.select_related('gestion').order_by('-gestion__anio', 'nivel', 'grado', 'paralelo'):
            del_curso = [h for h in todos if h.asignacion.curso_id == curso.pk]
            if not del_curso:
                continue
            tableros.append({
                'titulo': str(curso),
                'subtitulo': '',
                'mostrar_curso': False,
                'filas': _construir_grilla(
                    del_curso,
                    Periodo.objects.filter(curso=curso).order_by('orden'),
                ),
            })

    return render(request, 'academico/mi_horario.html', {
        'tableros': tableros,
        'dias': Horario.Dia.choices,
    })


@login_required
def mi_perfil(request):
    if not request.user.es_estudiante():
        return HttpResponseForbidden('Solo los estudiantes tienen esta sección.')

    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')

    if request.method == 'POST':
        form = PerfilEstudianteForm(request.POST, request.FILES, instance=estudiante)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tus datos se actualizaron correctamente.')
            return redirect('academico:mi_perfil')
    else:
        form = PerfilEstudianteForm(instance=estudiante)

    return render(request, 'academico/mi_perfil.html', {'estudiante': estudiante, 'form': form})


def _url_constructor(curso_id):
    return f"{reverse('academico:horario_constructor')}?curso={curso_id}"


@login_required
def horario_constructor(request):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')

    cursos = Curso.objects.select_related('gestion').order_by('-gestion__anio', 'nivel', 'grado', 'paralelo')

    curso_id = request.GET.get('curso')
    curso = None
    if curso_id:
        curso = Curso.objects.filter(pk=curso_id).first()
    if curso is None:
        curso = cursos.first()

    dias = Horario.Dia.choices
    periodos = []
    materias_curso = []
    celdas = {}

    if curso is not None:
        periodos = list(Periodo.objects.filter(curso=curso).order_by('orden'))
        materias_curso = list(
            AsignacionDocente.objects.filter(curso=curso)
            .select_related('materia', 'profesor')
        )
        horarios = Horario.objects.filter(asignacion__curso=curso) \
            .select_related('asignacion__materia', 'asignacion__profesor')
        for h in horarios:
            celdas[(h.periodo_id, h.dia)] = h

    filas = []
    for periodo in periodos:
        fila = {'periodo': periodo, 'celdas': []}
        for codigo_dia, _ in dias:
            fila['celdas'].append({
                'dia': codigo_dia,
                'horario': celdas.get((periodo.pk, codigo_dia)),
            })
        filas.append(fila)

    otros_cursos = cursos.exclude(pk=curso.pk) if curso else cursos

    return render(request, 'academico/horario_constructor.html', {
        'cursos': cursos,
        'curso': curso,
        'dias': dias,
        'filas': filas,
        'materias_curso': materias_curso,
        'otros_cursos': otros_cursos,
        'profesores': Usuario.objects.filter(rol=Usuario.Rol.PROFESOR).order_by('last_name', 'first_name'),
        'materias': Materia.objects.order_by('nombre'),
    })


@login_required
def agregar_periodo(request):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')
    if request.method != 'POST':
        return redirect('academico:horario_constructor')

    curso = get_object_or_404(Curso, pk=request.POST.get('curso_id'))
    es_recreo = request.POST.get('es_recreo') == 'on'
    ultimo_orden = Periodo.objects.filter(curso=curso).count()

    periodo = Periodo(
        curso=curso,
        orden=ultimo_orden,
        es_recreo=es_recreo,
        etiqueta=request.POST.get('etiqueta', '').strip(),
    )
    try:
        periodo.full_clean()
        periodo.save()
        messages.success(request, 'Período agregado.')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))

    return redirect(_url_constructor(curso.id))


@login_required
def eliminar_periodo(request, periodo_id):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')

    periodo = get_object_or_404(Periodo, pk=periodo_id)
    curso_id = periodo.curso_id

    if request.method == 'POST':
        tiene_clases = Horario.objects.filter(
            asignacion__curso=periodo.curso,
            dia__in=[d for d, _ in Horario.Dia.choices],
            periodo=periodo,
        ).exists()
        if tiene_clases:
            messages.error(request, 'No puedes eliminar este período: todavía tiene materias colocadas en algún día. Quítalas primero.')
        else:
            periodo.delete()
            messages.success(request, 'Período eliminado.')

    return redirect(_url_constructor(curso_id))


@login_required
def copiar_periodos(request):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')
    if request.method != 'POST':
        return redirect('academico:horario_constructor')

    curso_destino = get_object_or_404(Curso, pk=request.POST.get('curso_destino_id'))
    curso_origen = get_object_or_404(Curso, pk=request.POST.get('curso_origen_id'))

    if Periodo.objects.filter(curso=curso_destino).exists():
        messages.error(request, 'Este curso ya tiene períodos definidos. Elimínalos primero si quieres copiar otros.')
    else:
        nuevos = [
            Periodo(
                curso=curso_destino, orden=p.orden,
                es_recreo=p.es_recreo, etiqueta=p.etiqueta,
            )
            for p in Periodo.objects.filter(curso=curso_origen)
        ]
        Periodo.objects.bulk_create(nuevos)
        messages.success(request, f'Se copiaron los períodos de "{curso_origen}".')

    return redirect(_url_constructor(curso_destino.id))


@login_required
def agregar_materia_curso(request):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')
    if request.method != 'POST':
        return redirect('academico:horario_constructor')

    curso = get_object_or_404(Curso, pk=request.POST.get('curso_id'))
    form = AsignacionDocenteForm(data={
        'profesor': request.POST.get('profesor_id'),
        'curso': curso.id,
        'materia': request.POST.get('materia_id'),
    })
    if form.is_valid():
        form.save()
        messages.success(request, 'Materia agregada al curso.')
    else:
        # Los errores de campo (un profesor o una materia sin elegir) no salen en
        # non_field_errors y el formulario no se vuelve a mostrar: van al aviso.
        for campo, errores in form.errors.items():
            for error in errores:
                messages.error(request, error)

    return redirect(_url_constructor(curso.id))


@login_required
def colocar_horario(request):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')
    if request.method != 'POST':
        return redirect('academico:horario_constructor')

    asignacion = get_object_or_404(AsignacionDocente, pk=request.POST.get('asignacion_id'))
    periodo = get_object_or_404(Periodo, pk=request.POST.get('periodo_id'))
    dia = request.POST.get('dia')

    if asignacion.curso_id != periodo.curso_id:
        messages.error(request, 'Esa materia no pertenece a este curso.')
        return redirect(_url_constructor(periodo.curso_id))

    horario = Horario(asignacion=asignacion, dia=dia, periodo=periodo)
    try:
        horario.full_clean()
        horario.save()
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))

    return redirect(_url_constructor(periodo.curso_id))


@login_required
def quitar_horario(request, horario_id):
    if not request.user.es_admin():
        return HttpResponseForbidden('Solo un administrador puede armar horarios.')

    horario = get_object_or_404(Horario, pk=horario_id)
    curso_id = horario.asignacion.curso_id
    if request.method == 'POST':
        horario.delete()
        messages.success(request, 'Clase quitada del horario.')

    return redirect(_url_constructor(curso_id))
