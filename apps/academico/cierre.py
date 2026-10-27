"""Cerrar un año escolar y abrir el siguiente.

Es la operación más grande del sistema: mueve de grado a los 402 estudiantes
del colegio de una sola vez, crea el año nuevo entero y deja sin acceso a los
que egresan. No se deshace sola.

Por eso está partida en dos mitades que no se tocan:

- `propuesta()` **no escribe nada**. Lee el año que termina y arma lo que va a
  pasar, estudiante por estudiante, para que la secretaría lo vea antes.
- `cerrar()` escribe, y escribe todo junto en una transacción: o queda el año
  nuevo entero o no queda nada. A mitad de camino —402 matrículas creadas y
  ningún horario— el colegio se quedaría sin sistema en marzo.

Quién pasa lo decide la secretaría, no el sistema. El sistema propone: marca a
quien aprobó todo y **señala** a quien tiene alguna materia debajo de 51 o no
tiene ninguna nota cargada, que hoy son la mayoría.
"""
from django.db import transaction
from django.db.models import Avg

from apps.calificaciones.models import NOTA_APROBACION, Nota

from .models import (
    AsignacionDocente, CierreDeGestion, Curso, Gestion, Horario, Matricula, Periodo,
)

# Después de 6° de Secundaria no hay 7°: ese grado egresa.
GRADO_FINAL = 6


class NoSePuedeCerrar(Exception):
    """La gestión no está en condiciones de cerrarse."""


def _materias_flojas(gestion):
    """Por estudiante, cuántas materias tiene cargadas y cuántas debajo de 51.

    Una sola consulta para el colegio entero. La nota de una materia es el
    promedio de sus trimestres, que es como la lee el boletín: mirar trimestre
    por trimestre reprobaría a quien levantó en el tercero.
    """
    resumen = {}
    for fila in (Nota.objects.calificadas()
                 .filter(asignacion__curso__gestion=gestion)
                 .values('estudiante_id', 'asignacion__materia_id')
                 .annotate(promedio=Avg('nota'))):
        datos = resumen.setdefault(fila['estudiante_id'], {'materias': 0, 'flojas': 0})
        datos['materias'] += 1
        if fila['promedio'] is not None and fila['promedio'] < NOTA_APROBACION:
            datos['flojas'] += 1
    return resumen


def propuesta(gestion):
    """Qué pasaría al cerrar, curso por curso. No escribe nada.

    Devuelve una lista de cursos, cada uno con sus estudiantes y, por cada uno,
    si se propone que pase y qué habría que mirarle.
    """
    resumen = _materias_flojas(gestion)

    matriculas = (
        Matricula.objects
        .filter(curso__gestion=gestion, activa=True)
        .select_related('estudiante__usuario', 'curso')
        .order_by('curso__nivel', 'curso__grado', 'curso__paralelo',
                  'estudiante__usuario__last_name', 'estudiante__usuario__first_name')
    )

    cursos = []
    for matricula in matriculas:
        if not cursos or cursos[-1]['curso'].pk != matricula.curso_id:
            cursos.append({
                'curso': matricula.curso,
                'egresa': matricula.curso.grado >= GRADO_FINAL,
                'estudiantes': [],
            })

        datos = resumen.get(matricula.estudiante_id, {'materias': 0, 'flojas': 0})
        if datos['materias'] == 0:
            senal = 'sin notas cargadas'
        elif datos['flojas']:
            plural = '' if datos['flojas'] == 1 else 's'
            senal = f'{datos["flojas"]} materia{plural} debajo de {NOTA_APROBACION}'
        else:
            senal = ''

        cursos[-1]['estudiantes'].append({
            'matricula': matricula,
            'estudiante': matricula.estudiante,
            # Se propone que pase, incluso señalado: lo contrario sería hacer
            # repetir a 383 personas porque nadie cargó sus notas todavía.
            'pasa': True,
            'senal': senal,
            'materias': datos['materias'],
        })

    return cursos


def revisar(gestion):
    """Que se pueda cerrar, y qué año abre. Explica el motivo si no se puede."""
    if gestion is None:
        raise NoSePuedeCerrar('No hay ninguna gestión activa que cerrar.')
    if CierreDeGestion.objects.filter(gestion=gestion).exists():
        cierre = gestion.cierre
        raise NoSePuedeCerrar(
            f'La gestión {gestion} ya se cerró el {cierre.fecha:%d/%m/%Y} '
            f'y abrió la {cierre.gestion_nueva}.'
        )
    cursos = list(Curso.objects.filter(gestion=gestion))
    if not cursos:
        raise NoSePuedeCerrar(f'La gestión {gestion} no tiene ningún curso.')

    # Que cada curso tenga a dónde mandar a su gente. Sin esto, un estudiante
    # de 3° «C» cuyo colegio no tiene 4° «C» se quedaría sin curso destino, y
    # la única salida que le quedaría al programa sería darlo de baja como si
    # hubiera egresado: a los catorce años y sin que nadie se entere.
    paralelos = {(c.nivel, c.grado, c.paralelo) for c in cursos}
    huerfanos = [
        c for c in cursos
        if c.grado < GRADO_FINAL
        and (c.nivel, c.grado + 1, c.paralelo) not in paralelos
        and Matricula.objects.filter(curso=c, activa=True).exists()
    ]
    if huerfanos:
        faltan = ', '.join(f'{c.grado + 1}° "{c.paralelo}"' for c in huerfanos)
        raise NoSePuedeCerrar(
            f'Falta crear el curso al que pasarían: {faltan}. '
            f'Créalos en Gestión de datos y vuelve a intentar.'
        )

    return gestion.anio + 1


def _destino(curso, nuevos, pasa):
    """A qué curso del año que viene va un estudiante de este.

    `nuevos` está indexado por (nivel, grado, paralelo). El estudiante conserva
    su paralelo, que es como se arma el colegio; quien repite vuelve al mismo
    grado, no al siguiente.
    """
    grado = curso.grado + 1 if pasa else curso.grado
    return nuevos.get((curso.nivel, grado, curso.paralelo))


@transaction.atomic
def cerrar(gestion, *, promovidos, por, copiar_horario=True, copiar_asignaciones=True):
    """Cierra la gestión y abre la siguiente. Devuelve el `CierreDeGestion`.

    `promovidos` son los ids de estudiante que la secretaría dejó marcados: los
    que no están en ese conjunto repiten su grado, con su mismo paralelo.
    """
    anio_nuevo = revisar(gestion)
    promovidos = set(promovidos or [])

    nueva, _ = Gestion.objects.get_or_create(anio=anio_nuevo)

    # ── 1. Los cursos del año nuevo ──
    nuevos = {}
    for curso in Curso.objects.filter(gestion=gestion):
        destino, _ = Curso.objects.get_or_create(
            gestion=nueva, nivel=curso.nivel, grado=curso.grado, paralelo=curso.paralelo,
        )
        nuevos[(curso.nivel, curso.grado, curso.paralelo)] = destino

    # ── 2. Quién dicta qué, y el horario que cuelga de eso ──
    # El horario apunta a una asignación: copiarlo sin copiarlas dejaría los
    # bloques colgando del docente del año pasado.
    equivalente = {}
    if copiar_asignaciones:
        for asignacion in AsignacionDocente.objects.filter(curso__gestion=gestion):
            curso = asignacion.curso
            copia, _ = AsignacionDocente.objects.get_or_create(
                curso=nuevos[(curso.nivel, curso.grado, curso.paralelo)],
                materia_id=asignacion.materia_id,
                defaults={'profesor_id': asignacion.profesor_id},
            )
            equivalente[asignacion.pk] = copia

    if copiar_horario:
        periodos = {}
        for periodo in Periodo.objects.filter(curso__gestion=gestion):
            curso = periodo.curso
            copia, _ = Periodo.objects.get_or_create(
                curso=nuevos[(curso.nivel, curso.grado, curso.paralelo)],
                orden=periodo.orden,
                defaults={'es_recreo': periodo.es_recreo, 'etiqueta': periodo.etiqueta},
            )
            periodos[periodo.pk] = copia

        for horario in Horario.objects.filter(asignacion__curso__gestion=gestion):
            asignacion = equivalente.get(horario.asignacion_id)
            periodo = periodos.get(horario.periodo_id)
            if asignacion is None or periodo is None:
                # Sin asignación equivalente no hay dónde colgar el bloque: se
                # deja para el constructor, que es quien entiende de choques.
                continue
            Horario.objects.get_or_create(
                asignacion=asignacion, periodo=periodo, dia=horario.dia,
                defaults={'aula': horario.aula},
            )

    # ── 3. Los estudiantes ──
    cuenta = {'promovidos': 0, 'repitentes': 0, 'egresados': 0}
    sin_acceso = []
    por_crear = []

    matriculas = (
        Matricula.objects.filter(curso__gestion=gestion, activa=True)
        .select_related('estudiante', 'curso')
    )
    for matricula in matriculas:
        pasa = matricula.estudiante_id in promovidos

        if pasa and matricula.curso.grado >= GRADO_FINAL:
            # Egresa: no hay 7°. Su historial queda entero; su cuenta deja de
            # entrar, que es lo que se decidió para los egresados.
            cuenta['egresados'] += 1
            sin_acceso.append(matricula.estudiante.usuario_id)
            continue

        destino = _destino(matricula.curso, nuevos, pasa)
        if destino is None:
            # `revisar()` ya lo descartó antes de escribir nada. Si se llegara
            # aquí es que los cursos cambiaron entre la revisión y el guardado:
            # se corta y la transacción deshace todo.
            raise NoSePuedeCerrar(
                f'No existe el curso al que pasaría {matricula.estudiante}: '
                f'{matricula.curso.grado + 1}° "{matricula.curso.paralelo}".'
            )

        cuenta['promovidos' if pasa else 'repitentes'] += 1
        por_crear.append(Matricula(estudiante_id=matricula.estudiante_id, curso=destino))

    # `bulk_create` no llama a `clean()`, así que la regla de «una matrícula por
    # gestión» se cuida con la restricción de la base: se ignora lo repetido.
    Matricula.objects.bulk_create(por_crear, batch_size=500, ignore_conflicts=True)

    # ── 4. Cerrar lo viejo ──
    Matricula.objects.filter(curso__gestion=gestion, activa=True).update(activa=False)

    if sin_acceso:
        from apps.accounts.models import Usuario

        Usuario.objects.filter(pk__in=sin_acceso).update(is_active=False)

    # El orden importa: hay una restricción de una sola gestión activa, así que
    # primero se apaga la vieja y recién después se enciende la nueva.
    Gestion.objects.filter(activa=True).update(activa=False)
    nueva.activa = True
    nueva.save(update_fields=['activa'])

    return CierreDeGestion.objects.create(
        gestion=gestion, gestion_nueva=nueva, cerrada_por=por,
        promovidos=cuenta['promovidos'], repitentes=cuenta['repitentes'],
        egresados=cuenta['egresados'],
    )
