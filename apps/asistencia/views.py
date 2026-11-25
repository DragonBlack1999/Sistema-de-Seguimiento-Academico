import calendar
import datetime
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.academico.busqueda import buscar_estudiantes
from apps.academico.models import Curso, Estudiante, Matricula
from apps.comunicaciones.alertas import avisar_atraso, avisar_falta, verificar_alerta_faltas

from .models import Asistencia
from .services import (
    RegistroNoValido,
    cerrar_dia,
    cursos_en_capacitacion,
    error_de_fecha,
    gestion_vigente,
    hora_limite,
    matriculas_del_dia,
    registrar_entrada,
    resumen_por_estado,
)

MENSAJE_SOLO_REGENTE = 'Solo el regente o un administrador pueden registrar la asistencia.'
MARCA_CAPACITACION = 'Clase de capacitación'

# Valor del botón que pide la lista entera del día. Tiene que ser un texto y no
# una cadena vacía: el buscador en vivo descarta los parámetros vacíos, y sin
# valor «Todos» se confundiría con «todavía no elegí nada».
TODOS = 'todos'


def _puede_registrar(user):
    return user.es_regente() or user.es_admin()


def _fecha_pedida(request):
    texto = request.POST.get('fecha', request.GET.get('fecha'))
    if texto is not None:
        try:
            return datetime.date.fromisoformat(texto)
        except ValueError:
            if request.method == 'POST':
                raise RegistroNoValido('Escribe una fecha válida para registrar la asistencia.')
    return timezone.localdate()


# --------------------------------------------------------------- puerta (regente)

def _botones_de_curso(matriculas, registros):
    """Los cursos del día agrupados por grado, con lo que le falta a cada uno.

    El número del botón es lo que convierte la fila de cursos en un tablero: el
    regente ve de un vistazo qué cursos ya entraron enteros y a cuáles les
    falta gente, sin abrir ninguna lista.
    """
    por_curso = {}
    for matricula in matriculas:
        datos = por_curso.setdefault(str(matricula.curso_id), {
            'curso': matricula.curso, 'total': 0, 'pendientes': 0,
        })
        datos['total'] += 1
        if matricula.estudiante_id not in registros:
            datos['pendientes'] += 1

    # El nivel solo se nombra si ese día hay más de uno: en un colegio de puro
    # secundario, repetirlo dieciocho veces es ruido.
    varios = len({d['curso'].nivel for d in por_curso.values()}) > 1

    grupos = []
    for datos in por_curso.values():
        curso = datos['curso']
        rotulo = (f'{curso.grado}° de {curso.get_nivel_display()}'
                  if varios else f'{curso.grado}°')
        # Las matrículas vienen ordenadas por nivel, grado y paralelo, así que
        # los de un mismo grado llegan seguidos y basta con mirar el anterior.
        if not grupos or grupos[-1]['rotulo'] != rotulo:
            grupos.append({'rotulo': rotulo, 'cursos': []})
        grupos[-1]['cursos'].append(datos)

    return grupos, por_curso


@login_required
def puerta(request):
    """Pantalla de la puerta: se elige el curso y entra su lista.

    No se abre con los cuatrocientos estudiantes del día encima: el regente
    toca el curso del que está entrando y ve sus veintitantos. El buscador, que
    mira en todos los cursos, es para cuando el estudiante no aparece ahí.
    """
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    if gestion is None:
        return render(request, 'asistencia/puerta.html', {'sin_gestion': True})

    fecha = _fecha_pedida(request)
    consulta = request.GET.get('q', '').strip()
    pedido = request.GET.get('curso', '').strip()

    matriculas = list(matriculas_del_dia(gestion, fecha))
    registros = {
        a.estudiante_id: a
        for a in Asistencia.objects.filter(fecha=fecha, estudiante_id__in=[m.estudiante_id for m in matriculas])
    }

    grupos, por_curso = _botones_de_curso(matriculas, registros)
    # Un curso que no existe (una dirección vieja, un curso que hoy está en
    # capacitación) se trata como si no se hubiera elegido nada.
    elegido = pedido if pedido == TODOS or pedido in por_curso else ''

    if consulta:
        # Buscar gana sobre el curso elegido: se busca justamente cuando el
        # estudiante no está donde se lo esperaba, así que mirar solo dentro de
        # un curso no encontraría nunca lo que se está buscando.
        permitidos = set(
            buscar_estudiantes(consulta).values_list('pk', flat=True)
        )
        mostradas = [m for m in matriculas if m.estudiante_id in permitidos]
    elif elegido == TODOS:
        mostradas = matriculas
    elif elegido:
        mostradas = [m for m in matriculas if str(m.curso_id) == elegido]
    else:
        mostradas = []

    filas = [
        {'matricula': m, 'asistencia': registros.get(m.estudiante_id)}
        for m in mostradas
    ]

    total = len(matriculas)
    presentes = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.PRESENTE)
    atrasos = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.ATRASO)
    faltas = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.FALTA)
    licencias = sum(1 for a in registros.values() if a.estado == Asistencia.Estado.LICENCIA)

    # Mientras se escribe en el buscador, el navegador pide solo la tabla.
    plantilla = ('asistencia/_tabla_puerta.html'
                 if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                 else 'asistencia/puerta.html')

    return render(request, plantilla, {
        'gestion': gestion,
        'fecha': fecha,
        'consulta': consulta,
        'filas': filas,
        'grupos': grupos,
        'cursos_para_excel': Curso.objects.select_related('gestion').order_by('-gestion__anio', 'nivel', 'grado', 'paralelo'),
        'meses': MONTHS.items(),
        'elegido': elegido,
        'sin_eleccion': not consulta and not elegido,
        'error_fecha': error_de_fecha(gestion, fecha),
        'estados': Asistencia.Estado.choices,
        'hora_limite': hora_limite(),
        'en_capacitacion': list(cursos_en_capacitacion(fecha)),
        'resumen': {
            'total': total,
            'presentes': presentes,
            'atrasos': atrasos,
            'faltas': faltas,
            'licencias': licencias,
            'sin_registrar': total - len(registros),
        },
    })


@login_required
@require_POST
def marcar(request, estudiante_id):
    """Registra la entrada de un estudiante. Responde JSON para no recargar la puerta."""
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    estudiante = get_object_or_404(Estudiante.objects.select_related('usuario'), pk=estudiante_id)
    estado_pedido = request.POST.get('estado', '')
    if estado_pedido and estado_pedido not in Asistencia.Estado.values:
        return JsonResponse({'error': 'El estado de asistencia no es válido.'}, status=400)
    try:
        fecha = _fecha_pedida(request)
        asistencia, _ = registrar_entrada(
            estudiante, gestion, fecha, request.user, estado=estado_pedido,
        )
    except RegistroNoValido as error:
        return JsonResponse({'error': str(error)}, status=400)

    aviso = ''
    if asistencia.estado == Asistencia.Estado.FALTA:
        # A la familia se le avisa siempre; la citación solo si acumula faltas.
        avisar_falta(estudiante, fecha)
        try:
            citacion = verificar_alerta_faltas(estudiante, gestion, generado_por=request.user)
            if citacion:
                aviso = f'Se generó una citación automática para {estudiante} por inasistencias reiteradas.'
        except Exception as error:
            aviso = f'Asistencia guardada, pero la alerta automática falló: {error}'
    elif asistencia.estado == Asistencia.Estado.ATRASO and asistencia.hora_llegada:
        avisar_atraso(estudiante, fecha, asistencia.hora_llegada)

    return JsonResponse({
        'estado': asistencia.estado,
        'estado_texto': asistencia.get_estado_display(),
        'hora': asistencia.hora_llegada.strftime('%H:%M') if asistencia.hora_llegada else '',
        'aviso': aviso,
    })


@login_required
@require_POST
def cerrar(request):
    """Marca como falta a todos los que no pasaron por la puerta ese día."""
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)

    gestion = gestion_vigente()
    try:
        fecha = _fecha_pedida(request)
        marcados = cerrar_dia(gestion, fecha, request.user)
    except RegistroNoValido as error:
        messages.error(request, str(error))
        return redirect('asistencia:puerta')

    citaciones = 0
    for estudiante in marcados:
        try:
            if verificar_alerta_faltas(estudiante, gestion, generado_por=request.user):
                citaciones += 1
        except Exception as error:
            messages.warning(request, f'La alerta automática de {estudiante} falló: {error}')

    if marcados:
        texto = f'Día cerrado: {len(marcados)} estudiante(s) quedaron como falta.'
        if citaciones:
            texto += f' Se generaron {citaciones} citación(es) automática(s).'
        messages.success(request, texto)
    else:
        messages.info(request, 'Todos los estudiantes ya tenían su asistencia registrada.')

    return redirect(f"{reverse('asistencia:puerta')}?fecha={fecha.isoformat()}")


# --------------------------------------------------------------- capacitación (admin)

MENSAJE_SOLO_ADMIN = 'Solo el administrador puede registrar la asistencia de capacitación.'

# En capacitación el curso entra en grupo y a otra hora: solo interesa si vino o
# no. Por eso la pantalla ofrece dos botones y no guarda hora de llegada.
ESTADOS_CAPACITACION = (Asistencia.Estado.PRESENTE, Asistencia.Estado.FALTA)


def _cursos_con_capacitacion(gestion):
    """Cursos de la gestión que tienen días de capacitación asignados."""
    return list(
        Curso.objects.filter(gestion=gestion, dias_capacitacion__isnull=False)
        .distinct().order_by('nivel', 'grado', 'paralelo')
    )


@login_required
def capacitacion(request):
    """Asistencia de los cursos que ese día están en capacitación, curso por curso.

    Se guarda la lista entera de una vez (patrón de formulario masivo del
    proyecto), porque estos cursos llegan en grupo y a otra hora, no de uno en
    uno como en la puerta.
    """
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    gestion = gestion_vigente()
    if gestion is None:
        return render(request, 'asistencia/capacitacion.html', {'sin_gestion': True})

    try:
        fecha = _fecha_pedida(request)
        if request.method == 'POST':
            error = error_de_fecha(gestion, fecha, puerta=False)
            if error:
                raise RegistroNoValido(error)
    except RegistroNoValido as error:
        messages.error(request, str(error))
        return redirect('asistencia:capacitacion')
    del_dia = list(cursos_en_capacitacion(fecha).filter(gestion=gestion))
    todos = _cursos_con_capacitacion(gestion)

    # Por defecto se propone el curso que toca ese día; si no toca ninguno, el
    # administrador puede elegir igual (una recuperación, un día repuesto).
    curso = None
    pedido = request.GET.get('curso') or request.POST.get('curso')
    if pedido:
        curso = next((c for c in todos if str(c.pk) == str(pedido)), None)
    elif del_dia:
        curso = del_dia[0]

    matriculas = []
    if curso is not None:
        matriculas = list(
            Matricula.objects.filter(curso=curso, activa=True, estudiante__usuario__is_active=True,
                                     fecha_matricula__lte=fecha)
            .select_related('estudiante__usuario')
            .order_by('estudiante__usuario__last_name', 'estudiante__usuario__first_name')
        )

    if request.method == 'POST' and curso is not None:
        guardados, citaciones = 0, 0
        for matricula in matriculas:
            estado = request.POST.get(f'estado_{matricula.estudiante_id}', '')
            if estado not in ESTADOS_CAPACITACION:
                # Sin botón elegido (o con un estado que esta pantalla ya no
                # ofrece) se deja el registro como estaba, sin pisarlo.
                continue

            Asistencia.objects.update_or_create(
                estudiante=matricula.estudiante, fecha=fecha,
                defaults={
                    'estado': estado, 'hora_llegada': None,
                    'observacion': MARCA_CAPACITACION,
                    'registrado_por': request.user,
                },
            )
            guardados += 1

            if estado == Asistencia.Estado.FALTA:
                avisar_falta(matricula.estudiante, fecha)
                try:
                    if verificar_alerta_faltas(matricula.estudiante, gestion, generado_por=request.user):
                        citaciones += 1
                except Exception as error:
                    messages.warning(request, f'La alerta automática de {matricula.estudiante} falló: {error}')

        texto = f'Asistencia de capacitación guardada: {guardados} estudiante(s).'
        if citaciones:
            texto += f' Se generaron {citaciones} citación(es) automática(s).'
        messages.success(request, texto)
        return redirect(f"{reverse('asistencia:capacitacion')}?fecha={fecha.isoformat()}&curso={curso.pk}")

    registros = {
        a.estudiante_id: a for a in Asistencia.objects.filter(
            fecha=fecha, estudiante__in=[m.estudiante_id for m in matriculas],
        )
    } if matriculas else {}

    filas = []
    for m in matriculas:
        registro = registros.get(m.estudiante_id)
        # Sin registro previo se propone Presente: así solo hay que marcar a los
        # que faltaron, que son los menos.
        estado = registro.estado if registro else Asistencia.Estado.PRESENTE
        filas.append({
            'matricula': m,
            'asistencia': registro,
            'estado': estado,
            # Un estado que esta pantalla ya no ofrece (una licencia cargada
            # desde el panel de datos): se muestra, y ningún botón sale marcado.
            'otro_estado': (
                registro.get_estado_display()
                if registro and estado not in ESTADOS_CAPACITACION else ''
            ),
        })

    return render(request, 'asistencia/capacitacion.html', {
        'gestion': gestion,
        'fecha': fecha,
        'curso': curso,
        'cursos': todos,
        'del_dia': del_dia,
        'filas': filas,
    })


# --------------------------------------------------- planilla del curso en Excel

@login_required
def capacitacion_excel(request):
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)
    return _excel_curso(request, capacitacion=True)


@login_required
def puerta_excel(request):
    if not _puede_registrar(request.user):
        return HttpResponseForbidden(MENSAJE_SOLO_REGENTE)
    return _excel_curso(request, capacitacion=False)


def _excel_curso(request, *, capacitacion):
    cursos = Curso.objects.select_related('gestion')
    if capacitacion:
        cursos = cursos.filter(gestion=gestion_vigente(), dias_capacitacion__isnull=False).distinct()
    pedido = request.GET.get('curso', '')
    if not pedido.isascii() or not pedido.isdecimal():
        raise Http404('Elige un curso de la gestión.')
    curso = get_object_or_404(cursos, pk=pedido)

    periodo = None
    matriculas = Matricula.objects.filter(curso=curso)
    registros = Asistencia.objects.order_by()
    if capacitacion:
        matriculas = matriculas.filter(activa=True)
        registros = registros.filter(fecha__year=curso.gestion.anio)
    else:
        try:
            periodo, fin = _limites_del_mes(
                request.GET.get('anio', curso.gestion.anio),
                request.GET.get('mes', timezone.localdate().month),
            )
        except (ValueError, OverflowError):
            return HttpResponse('Elige un mes y un año válidos.', status=400)
        if periodo.year != curso.gestion.anio:
            return HttpResponse('Elige un curso de la gestión seleccionada.', status=400)
        registros = registros.filter(fecha__range=(periodo, fin)).exclude(observacion=MARCA_CAPACITACION)
        # El cierre anual desactiva las matrículas. Para el histórico, se usa
        # el curso en la fecha de entrada incluso si el alumno cambió de paralelo.
        inscripciones = Matricula.objects.filter(estudiante_id=OuterRef('estudiante_id'), curso__gestion=curso.gestion)
        vigentes_al_dia = inscripciones.filter(fecha_matricula__lte=OuterRef('fecha')).order_by('-fecha_matricula', '-pk')
        primera = inscripciones.order_by('fecha_matricula', 'pk')
        registros = registros.alias(curso_del_dia=Coalesce(
            Subquery(vigentes_al_dia.values('curso_id')[:1]), Subquery(primera.values('curso_id')[:1]),
        )).filter(curso_del_dia=curso.pk)

    matriculas = list(matriculas.select_related('estudiante__usuario')
                      .order_by('estudiante__usuario__last_name', 'estudiante__usuario__first_name'))
    registros = list(registros.filter(estudiante_id__in=[m.estudiante_id for m in matriculas]))
    if not capacitacion and curso.gestion.activa:
        con_entrada = {r.estudiante_id for r in registros}
        matriculas = [m for m in matriculas if m.activa or m.estudiante_id in con_entrada]

    # La importación es local: openpyxl solo se carga si alguien descarga.
    from .planillas import planilla_por_fechas

    libro = planilla_por_fechas(curso, matriculas, registros, capacitacion=capacitacion, periodo=periodo)

    memoria = io.BytesIO()
    libro.save(memoria)
    memoria.seek(0)

    tipo = 'capacitacion' if capacitacion else 'entrada'
    sufijo = f'-{periodo:%Y-%m}' if periodo else ''
    nombre = f'asistencia-{tipo}-{slugify(str(curso))}{sufijo}.xlsx'
    respuesta = HttpResponse(
        memoria.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return respuesta


# --------------------------------------------------------------- consulta

@login_required
def mi_asistencia(request):
    estudiante = getattr(request.user, 'estudiante', None)
    if estudiante is None:
        return HttpResponseForbidden('Tu usuario no tiene un perfil de estudiante asociado.')
    return mostrar_asistencia_mensual(request, estudiante, 'asistencia/mi_asistencia.html')


def _limites_del_mes(anio, mes):
    inicio = datetime.date(int(anio), int(mes), 1)
    return inicio, inicio.replace(day=calendar.monthrange(inicio.year, inicio.month)[1])


def mostrar_asistencia_mensual(request, estudiante, plantilla):
    """Muestra el mes del estudiante al que la vista ya autorizó el acceso."""
    hoy = timezone.localdate()
    try:
        inicio, fin = _limites_del_mes(request.GET.get('anio', hoy.year), request.GET.get('mes', hoy.month))
    except (ValueError, OverflowError):
        messages.warning(request, 'Elige un mes y un año válidos.')
        return redirect(request.path)

    registros = list(Asistencia.objects.filter(
        estudiante=estudiante, fecha__range=(inicio, fin),
    ).only('fecha', 'hora_llegada', 'estado').order_by('-fecha'))
    return render(request, plantilla, {
        'registros': registros, 'estudiante': estudiante, 'resumen': resumen_por_estado(registros),
        'periodo': inicio, 'meses': MONTHS.items(),
    })
