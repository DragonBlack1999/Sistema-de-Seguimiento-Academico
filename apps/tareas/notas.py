"""El puente entre una tarea y la planilla de notas.

Cada tarea es una columna de **hacer**: su actividad. Lo que el docente califica
en la tarea aparece en la planilla, y lo que escribe en la planilla vuelve a la
entrega. El número vive en un solo lugar y las dos pantallas muestran lo mismo.

No hay señales en el proyecto: estas funciones las llaman las vistas después de
guardar, que es donde se ve quién hizo el cambio.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Exists, OuterRef

from apps.calificaciones.models import MAXIMO, Actividad, Dimension, Nota, Puntaje

# Una tarea se califica sobre lo que vale la dimensión donde entra.
MAXIMO_TAREA = MAXIMO[Dimension.HACER]


def _siguiente_orden(asignacion_id, trimestre):
    ultimo = (
        Actividad.objects
        .filter(asignacion_id=asignacion_id, trimestre=trimestre, dimension=Dimension.HACER)
        .order_by('-orden').values_list('orden', flat=True).first()
    )
    return 0 if ultimo is None else ultimo + 1


def sincronizar_actividad(tarea, usuario=None):
    """Crea la columna de la tarea, o la pone al día si cambió de nombre o trimestre.

    Devuelve los trimestres que hay que recalcular: al mover una tarea de
    trimestre, las notas del viejo y las del nuevo quedan distintas.
    """
    trimestres = {tarea.trimestre}
    actividad = tarea.actividad

    if actividad is None:
        actividad = Actividad.objects.create(
            asignacion_id=tarea.asignacion_id, trimestre=tarea.trimestre,
            dimension=Dimension.HACER,
            orden=_siguiente_orden(tarea.asignacion_id, tarea.trimestre),
            creada_por=usuario,
        )
        Tarea = type(tarea)
        Tarea.objects.filter(pk=tarea.pk).update(actividad=actividad)
        tarea.actividad = actividad
        return trimestres

    # El nombre no se copia: `Actividad.etiqueta` lo toma de la tarea.
    cambios = {}
    if actividad.trimestre != tarea.trimestre:
        trimestres.add(actividad.trimestre)
        cambios['trimestre'] = tarea.trimestre
        cambios['orden'] = _siguiente_orden(tarea.asignacion_id, tarea.trimestre)
    if cambios:
        for campo, valor in cambios.items():
            setattr(actividad, campo, valor)
        actividad.save(update_fields=list(cambios))
    return trimestres


def borrar_actividad(tarea):
    """Se va la tarea, se va su columna. Devuelve a quiénes hay que recalcular."""
    actividad = tarea.actividad
    if actividad is None:
        return set(), tarea.trimestre
    estudiantes = set(actividad.puntajes.values_list('estudiante_id', flat=True))
    trimestre = actividad.trimestre
    actividad.delete()
    return estudiantes, trimestre


def guardar_puntaje(tarea, estudiante_id, valor, usuario=None):
    """Escribe (o borra) la nota de una tarea y rehace el trimestre.

    La nota vive solo aquí, en la columna de la tarea. Vacío significa "sin
    calificar", igual que en el resto de la planilla.
    """
    if tarea.actividad_id is None:
        sincronizar_actividad(tarea, usuario)
    if tarea.actividad_id is None:
        return

    if valor is None:
        Puntaje.objects.filter(
            actividad_id=tarea.actividad_id, estudiante_id=estudiante_id,
        ).delete()
    else:
        Puntaje.objects.update_or_create(
            actividad_id=tarea.actividad_id, estudiante_id=estudiante_id,
            defaults={'valor': valor, 'registrado_por': usuario},
        )
    recalcular(tarea.asignacion_id, tarea.trimestre, [estudiante_id], usuario)


def puntajes_de(tarea):
    """{estudiante: nota} de la columna de la tarea, en una sola consulta."""
    if tarea.actividad_id is None:
        return {}
    return dict(
        Puntaje.objects.filter(actividad_id=tarea.actividad_id)
        .values_list('estudiante_id', 'valor')
    )


def sin_calificar(entregas):
    """Las entregas de ese conjunto que todavía no tienen nota en la planilla."""
    puntaje = Puntaje.objects.filter(
        actividad_id=OuterRef('tarea__actividad_id'), estudiante_id=OuterRef('estudiante_id'),
    )
    return entregas.annotate(_tiene_nota=Exists(puntaje)).filter(_tiene_nota=False)


def recalcular(asignacion_id, trimestre, estudiantes=None, usuario=None):
    """Rehace la nota del trimestre de esos estudiantes (o de todos los que tengan)."""
    notas = Nota.objects.filter(asignacion_id=asignacion_id, trimestre=trimestre)
    if estudiantes is not None:
        notas = notas.filter(estudiante_id__in=list(estudiantes))
    existentes = {n.estudiante_id for n in notas}

    from apps.comunicaciones.alertas import avisar_nota_baja

    for nota in notas:
        if usuario is not None:
            nota.registrado_por = usuario
        nota.recalcular()
        avisar_nota_baja(nota)

    # Quien todavía no tenía nota en esa materia la estrena con esta tarea.
    for estudiante_id in set(estudiantes or []) - existentes:
        nota = Nota(
            asignacion_id=asignacion_id, estudiante_id=estudiante_id,
            trimestre=trimestre, registrado_por=usuario,
        )
        nota.save()
        nota.recalcular()


def entero_valido(texto):
    """Devuelve (valor, error) para una nota escrita a mano: solo enteros, de 0 al máximo."""
    texto = (texto or '').strip().replace(',', '.')
    if texto == '':
        return None, None
    try:
        numero = Decimal(texto)
    except Exception:
        return None, f'"{texto}" no es un número'
    if numero != numero.to_integral_value():
        return None, f'{texto} tiene decimales: las notas se ponen en números enteros'
    numero = numero.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    if numero < 0 or numero > MAXIMO_TAREA:
        return None, f'{numero} está fuera de 0 a {MAXIMO_TAREA:.0f}'
    return numero, None
