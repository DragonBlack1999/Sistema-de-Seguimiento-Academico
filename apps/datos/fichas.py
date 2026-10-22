"""Qué se puede administrar, y cómo se ve cada cosa.

Son nueve entidades. Escribir una lista, un alta, una edición y un borrado para
cada una serían treinta y seis vistas cuyo cuerpo es idéntico salvo tres líneas:
qué columnas se muestran, por qué se busca y qué se puede borrar. Eso no son
treinta y seis vistas, son **una tabla de configuración**.

Aquí está esa tabla. Cada `Ficha` describe una entidad; las vistas de
`views.py` son genéricas y leen de aquí. Agregar algo administrable nuevo es
añadir una ficha, no un archivo.

Lo que NO entra aquí: los periodos y los horarios, que ya tienen el constructor
de horarios —una pantalla hecha a medida que entiende de recreos y de choques, y
que un CRUD genérico solo empeoraría—, y las noticias y citaciones, que ya
tienen su propia pantalla. El índice las enlaza.
"""
from dataclasses import dataclass, field
from typing import Callable

from django.db.models import Count, Prefetch, Q

from apps.academico.busqueda import buscar_estudiantes, buscar_por_nombre
from apps.academico.models import (
    AsignacionDocente, Curso, Estudiante, Gestion, Materia, Matricula,
)
from apps.accounts.models import Usuario


# ──────────────────────────── las piezas ────────────────────────────

@dataclass(frozen=True)
class Columna:
    """Una columna de la lista. `valor` recibe el objeto y devuelve texto."""

    rotulo: str
    valor: Callable
    principal: bool = False        # la que hace de título en el celular


@dataclass(frozen=True)
class Filtro:
    """Un desplegable sobre la lista.

    `opciones` se evalúa al pintar (devuelve pares valor/texto) y `aplicar`
    recibe el queryset y el valor elegido.
    """

    clave: str
    rotulo: str
    opciones: Callable
    aplicar: Callable


@dataclass(frozen=True)
class Ficha:
    clave: str                     # 'estudiantes' → /datos/estudiantes/
    grupo: str                     # el bloque del índice
    titulo: str                    # 'Estudiantes'
    singular: str                  # 'estudiante' → «Nuevo estudiante»
    descripcion: str               # la bajada bajo el título
    modelo: type
    columnas: tuple
    orden: tuple = ()
    base: Callable | None = None           # el queryset de partida
    precarga: Callable | None = None       # select_related/prefetch: obligatorio de facto
    buscador: Callable | None = None       # (consulta, queryset) → queryset
    ayuda_busqueda: str = ''
    filtros: tuple = ()
    esta_de_baja: Callable | None = None   # para pintar la insignia
    por_pagina: int = 25
    icono: str = 'verde'                   # color de la tarjeta del índice

    # Las plantillas de Django LLAMAN a lo que encuentran si es invocable, y
    # `buscador` y `esta_de_baja` son funciones que esperan argumentos: un
    # `{% if ficha.buscador %}` las ejecuta, falla en silencio y da falso. Por
    # eso la plantilla pregunta por estas dos, que devuelven un sí o un no.
    @property
    def tiene_buscador(self):
        return self.buscador is not None

    @property
    def tiene_estado(self):
        return self.esta_de_baja is not None

    def consulta(self):
        """El queryset completo de la ficha, listo para contar o paginar."""
        qs = self.base() if self.base else self.modelo.objects.all()
        if self.precarga:
            qs = self.precarga(qs)
        if self.orden:
            qs = qs.order_by(*self.orden)
        return qs

    def cuantos(self):
        base = self.base() if self.base else self.modelo.objects.all()
        return base.count()


# ─────────────────────── ayudantes de columnas ───────────────────────

def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


def curso_de(estudiante):
    """El curso de este año, leído de la precarga y no de la propiedad.

    `Estudiante.curso_actual` hace su propia consulta y eso esquiva el
    `prefetch_related`: en una página de veinticinco filas serían veinticinco
    consultas de más. Aquí se lee lo que ya vino cargado.
    """
    activas = getattr(estudiante, 'matriculas_activas', None)
    if activas:
        return str(activas[0].curso)
    return 'Sin curso este año'


def _buscar_personas(consulta, queryset):
    """Por nombre (tolerante a tildes), y también por usuario o carnet."""
    por_nombre = buscar_por_nombre(consulta, queryset)
    termino = consulta.strip()
    return (por_nombre | queryset.filter(
        Q(username__icontains=termino) | Q(ci__icontains=termino),
    )).distinct()


def _buscar_matriculas(consulta, queryset):
    estudiantes = buscar_estudiantes(consulta, Estudiante.objects.all())
    return queryset.filter(estudiante__in=estudiantes)


# ──────────────────────────── los filtros ────────────────────────────

def _gestiones():
    return [(g.pk, f'Gestión {g.anio}') for g in Gestion.objects.all()]


def _cursos():
    return [
        (c.pk, str(c))
        for c in Curso.objects.select_related('gestion').order_by(
            '-gestion__anio', 'nivel', 'grado', 'paralelo',
        )
    ]


def _materias():
    return [(m.pk, m.nombre) for m in Materia.objects.all()]


def _profesores():
    return [
        (u.pk, _nombre(u))
        for u in Usuario.objects.filter(rol=Usuario.Rol.PROFESOR).order_by('last_name', 'first_name')
    ]


ESTADOS = [('activos', 'Solo los activos'), ('baja', 'Solo los dados de baja')]


def _filtro_estado(campo='is_active'):
    def aplicar(queryset, valor):
        return queryset.filter(**{campo: valor == 'activos'})

    return Filtro('estado', 'Estado', lambda: ESTADOS, aplicar)


FILTRO_CURSO = Filtro(
    'curso', 'Curso', _cursos,
    lambda qs, valor: qs.filter(matriculas__curso_id=valor, matriculas__activa=True),
)
FILTRO_GESTION_CURSO = Filtro(
    'gestion', 'Gestión', _gestiones, lambda qs, valor: qs.filter(gestion_id=valor),
)


# ──────────────────────────── el registro ────────────────────────────

GRUPOS = ('Las personas', 'El colegio', 'Inscripciones')

REGISTRO = {}


def _registrar(ficha):
    REGISTRO[ficha.clave] = ficha
    return ficha


_registrar(Ficha(
    clave='estudiantes', grupo='Las personas', titulo='Estudiantes',
    singular='estudiante', icono='verde',
    descripcion='Los datos de cada alumno, su curso de este año y su familia.',
    modelo=Estudiante,
    precarga=lambda qs: qs.select_related('usuario', 'tutor').prefetch_related(
        Prefetch(
            'matriculas',
            queryset=Matricula.objects.filter(activa=True).select_related('curso__gestion'),
            to_attr='matriculas_activas',
        ),
    ),
    orden=('usuario__last_name', 'usuario__first_name'),
    columnas=(
        Columna('Estudiante', lambda e: _nombre(e.usuario), principal=True),
        Columna('RUDE', lambda e: e.rude),
        Columna('Curso', curso_de),
        Columna('Padre/tutor', lambda e: e.nombre_tutor or 'Sin registrar'),
        Columna('Celular', lambda e: e.celular or '—'),
    ),
    buscador=lambda consulta, qs: buscar_estudiantes(consulta, qs),
    ayuda_busqueda='Por nombre, apellido, RUDE o curso. Las tildes no importan.',
    filtros=(FILTRO_CURSO, _filtro_estado('usuario__is_active')),
    esta_de_baja=lambda e: not e.usuario.is_active,
))

_registrar(Ficha(
    clave='docentes', grupo='Las personas', titulo='Docentes',
    singular='docente', icono='azul',
    descripcion='Quiénes enseñan en el colegio y cómo entran al sistema.',
    modelo=Usuario,
    base=lambda: Usuario.objects.filter(rol=Usuario.Rol.PROFESOR),
    precarga=lambda qs: qs.annotate(cuantas_materias=Count('asignaciones', distinct=True)),
    orden=('last_name', 'first_name'),
    columnas=(
        Columna('Docente', _nombre, principal=True),
        Columna('Usuario de acceso', lambda u: u.username),
        Columna('Carnet', lambda u: u.ci or '—'),
        Columna('Teléfono', lambda u: u.telefono or '—'),
        Columna('Materias a su cargo', lambda u: u.cuantas_materias),
    ),
    buscador=_buscar_personas,
    ayuda_busqueda='Por nombre, apellido, usuario o carnet.',
    filtros=(_filtro_estado(),),
    esta_de_baja=lambda u: not u.is_active,
))

_registrar(Ficha(
    clave='personal', grupo='Las personas', titulo='Dirección y regencia',
    singular='miembro del personal', icono='naranja',
    descripcion='Las cuentas de dirección, secretaría y regencia.',
    modelo=Usuario,
    base=lambda: Usuario.objects.filter(rol__in=[Usuario.Rol.ADMIN, Usuario.Rol.REGENTE]),
    orden=('rol', 'last_name', 'first_name'),
    columnas=(
        Columna('Nombre', _nombre, principal=True),
        Columna('Usuario de acceso', lambda u: u.username),
        Columna('Función', lambda u: u.get_rol_display()),
        Columna('Carnet', lambda u: u.ci or '—'),
        Columna('Teléfono', lambda u: u.telefono or '—'),
    ),
    buscador=_buscar_personas,
    ayuda_busqueda='Por nombre, apellido, usuario o carnet.',
    filtros=(_filtro_estado(),),
    esta_de_baja=lambda u: not u.is_active,
))

_registrar(Ficha(
    clave='familias', grupo='Las personas', titulo='Padres y tutores',
    singular='padre o tutor', icono='rosa',
    descripcion='Las cuentas de las familias. Entran con su carnet de identidad.',
    modelo=Usuario,
    base=lambda: Usuario.objects.filter(rol=Usuario.Rol.PADRE),
    precarga=lambda qs: qs.prefetch_related('hijos__usuario').annotate(
        cuantos_hijos=Count('hijos', distinct=True),
    ),
    orden=('last_name', 'first_name'),
    columnas=(
        Columna('Padre/tutor', _nombre, principal=True),
        Columna('Carnet', lambda u: u.ci or '—'),
        Columna('Teléfono', lambda u: u.telefono or '—'),
        Columna('Hijos en el colegio', lambda u: u.cuantos_hijos),
    ),
    buscador=_buscar_personas,
    ayuda_busqueda='Por nombre, apellido o carnet.',
    filtros=(_filtro_estado(),),
    esta_de_baja=lambda u: not u.is_active,
))

_registrar(Ficha(
    clave='gestiones', grupo='El colegio', titulo='Años escolares',
    singular='año escolar', icono='verde',
    descripcion='Cada gestión del colegio. Solo una puede estar en curso.',
    modelo=Gestion,
    precarga=lambda qs: qs.annotate(cuantos_cursos=Count('cursos', distinct=True)),
    orden=('-anio',),
    columnas=(
        Columna('Año', lambda g: str(g.anio), principal=True),
        Columna('En curso', lambda g: 'Sí' if g.activa else 'No'),
        Columna('Desde', lambda g: g.fecha_inicio or '—'),
        Columna('Hasta', lambda g: g.fecha_fin or '—'),
        Columna('Cursos', lambda g: g.cuantos_cursos),
    ),
    por_pagina=50,
))

_registrar(Ficha(
    clave='cursos', grupo='El colegio', titulo='Cursos',
    singular='curso', icono='azul',
    descripcion='Los cursos de cada gestión, con sus días de capacitación.',
    modelo=Curso,
    precarga=lambda qs: qs.select_related('gestion').annotate(
        cuantos_estudiantes=Count('matriculas', filter=Q(matriculas__activa=True), distinct=True),
        cuantas_materias=Count('asignaciones', distinct=True),
    ),
    orden=('-gestion__anio', 'nivel', 'grado', 'paralelo'),
    columnas=(
        Columna('Curso', lambda c: str(c), principal=True),
        Columna('Gestión', lambda c: c.gestion.anio),
        Columna('Estudiantes', lambda c: c.cuantos_estudiantes),
        Columna('Materias', lambda c: c.cuantas_materias),
    ),
    filtros=(FILTRO_GESTION_CURSO,),
    por_pagina=50,
))

_registrar(Ficha(
    clave='materias', grupo='El colegio', titulo='Materias',
    singular='materia', icono='naranja',
    descripcion='Las materias que se dictan en el colegio.',
    modelo=Materia,
    precarga=lambda qs: qs.annotate(cuantos_cursos=Count('asignaciones', distinct=True)),
    orden=('nombre',),
    columnas=(
        Columna('Materia', lambda m: m.nombre, principal=True),
        Columna('Se dicta en', lambda m: f'{m.cuantos_cursos} curso(s)'),
    ),
    buscador=lambda consulta, qs: qs.filter(nombre__icontains=consulta.strip()),
    ayuda_busqueda='Por nombre de la materia.',
    por_pagina=50,
))

_registrar(Ficha(
    clave='asignaciones', grupo='El colegio', titulo='Quién dicta qué',
    singular='asignación', icono='rosa',
    descripcion='Qué profesor tiene a su cargo cada materia en cada curso.',
    modelo=AsignacionDocente,
    precarga=lambda qs: qs.select_related('profesor', 'curso__gestion', 'materia'),
    orden=('-curso__gestion__anio', 'curso', 'materia'),
    columnas=(
        Columna('Curso', lambda a: str(a.curso), principal=True),
        Columna('Materia', lambda a: a.materia.nombre),
        Columna('Profesor', lambda a: _nombre(a.profesor)),
    ),
    buscador=lambda consulta, qs: qs.filter(
        Q(materia__nombre__icontains=consulta.strip())
        | Q(profesor__first_name__icontains=consulta.strip())
        | Q(profesor__last_name__icontains=consulta.strip()),
    ),
    ayuda_busqueda='Por materia o por el nombre del profesor.',
    filtros=(
        Filtro('gestion', 'Gestión', _gestiones,
               lambda qs, valor: qs.filter(curso__gestion_id=valor)),
        Filtro('curso', 'Curso', _cursos, lambda qs, valor: qs.filter(curso_id=valor)),
        Filtro('materia', 'Materia', _materias, lambda qs, valor: qs.filter(materia_id=valor)),
        Filtro('profesor', 'Profesor', _profesores,
               lambda qs, valor: qs.filter(profesor_id=valor)),
    ),
))

_registrar(Ficha(
    clave='matriculas', grupo='Inscripciones', titulo='Matrículas',
    singular='matrícula', icono='verde',
    descripcion='En qué curso está inscrito cada estudiante, año por año.',
    modelo=Matricula,
    precarga=lambda qs: qs.select_related('estudiante__usuario', 'curso__gestion'),
    orden=('-curso__gestion__anio', 'curso', 'estudiante__usuario__last_name'),
    columnas=(
        Columna('Estudiante', lambda m: _nombre(m.estudiante.usuario), principal=True),
        Columna('Curso', lambda m: str(m.curso)),
        Columna('Gestión', lambda m: m.curso.gestion.anio),
        Columna('Inscrito el', lambda m: m.fecha_matricula),
    ),
    buscador=_buscar_matriculas,
    ayuda_busqueda='Por nombre, apellido o RUDE del estudiante.',
    filtros=(
        Filtro('gestion', 'Gestión', _gestiones,
               lambda qs, valor: qs.filter(curso__gestion_id=valor)),
        Filtro('curso', 'Curso', _cursos, lambda qs, valor: qs.filter(curso_id=valor)),
        Filtro('estado', 'Estado', lambda: [('activos', 'Vigentes'), ('baja', 'Dadas de baja')],
               lambda qs, valor: qs.filter(activa=(valor == 'activos'))),
    ),
    esta_de_baja=lambda m: not m.activa,
))


def obtener(clave):
    """La ficha de esa clave, o None si no existe."""
    return REGISTRO.get(clave)


def por_grupos():
    """El registro agrupado como se muestra en el índice."""
    salida = []
    for grupo in GRUPOS:
        fichas = [f for f in REGISTRO.values() if f.grupo == grupo]
        if fichas:
            salida.append((grupo, fichas))
    return salida
