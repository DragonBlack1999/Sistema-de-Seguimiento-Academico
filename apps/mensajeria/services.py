"""Quién puede conversar con quién.

Todo el módulo se apoya en una sola función, `usuarios_contactables`. El selector
de contactos, el buscador y el control de acceso de las vistas usan **la misma
consulta**, así que no pueden divergir: si alguien no aparece en la lista, tampoco
se le puede escribir forzando la URL.

Las relaciones son simétricas por construcción (si A puede escribir a B, B puede
responder), porque las cuatro reglas se apoyan en la misma condición de
"el profesor dicta en el curso donde el estudiante tiene matrícula activa".
"""

from django.db.models import Q

from apps.academico.busqueda import buscar_estudiantes, buscar_por_nombre
from apps.academico.models import AsignacionDocente, Estudiante, Matricula
from apps.accounts.models import Usuario

# Cuántos estudiantes y cuántos padres sugiere el buscador. Cada estudiante puede
# arrastrar a su tutor, así que la lista llega a unas veinte filas como mucho.
LIMITE_BUSQUEDA = 8


def _cursos_del_profesor(profesor):
    """Pares (curso, gestión) donde el profesor tiene asignación."""
    return AsignacionDocente.objects.filter(profesor=profesor).values('curso_id')


def _condicion_matricula_en(asignaciones):
    """Q que empareja matrículas activas con cualquiera de esos pares curso/gestión."""
    condicion = Q(pk__in=[])
    for fila in asignaciones:
        condicion |= Q(curso_id=fila['curso_id'])
    return condicion


def _estudiantes_del_profesor(profesor):
    """Matrículas activas de los cursos donde el profesor dicta."""
    asignaciones = list(_cursos_del_profesor(profesor))
    if not asignaciones:
        return Matricula.objects.none()
    return Matricula.objects.filter(_condicion_matricula_en(asignaciones), activa=True)


def _profesores_de_cursos(matriculas):
    """Profesores con asignación en los cursos/gestiones de esas matrículas."""
    pares = list(matriculas.values('curso_id'))
    if not pares:
        return Usuario.objects.none()
    condicion = Q(pk__in=[])
    for par in pares:
        condicion |= Q(asignaciones__curso_id=par['curso_id'])
    return Usuario.objects.filter(condicion, rol=Usuario.Rol.PROFESOR)


def usuarios_contactables(usuario):
    """Queryset de usuarios con los que `usuario` puede conversar."""
    if usuario is None or not usuario.is_authenticated:
        return Usuario.objects.none()

    if usuario.es_admin():
        # La administración atiende a familias, no a su propio equipo docente.
        contactos = Usuario.objects.filter(rol__in=[Usuario.Rol.ESTUDIANTE, Usuario.Rol.PADRE])

    elif usuario.es_profesor():
        matriculas = _estudiantes_del_profesor(usuario)
        ids_estudiantes = matriculas.values_list('estudiante__usuario_id', flat=True)
        ids_tutores = matriculas.exclude(estudiante__tutor__isnull=True).values_list(
            'estudiante__tutor_id', flat=True,
        )
        contactos = Usuario.objects.filter(
            Q(pk__in=list(ids_estudiantes)) | Q(pk__in=list(ids_tutores)),
        )

    elif usuario.es_estudiante():
        estudiante = getattr(usuario, 'estudiante', None)
        if estudiante is None:
            return Usuario.objects.none()
        mis_matriculas = Matricula.objects.filter(estudiante=estudiante, activa=True)
        profesores = _profesores_de_cursos(mis_matriculas)
        contactos = Usuario.objects.filter(
            Q(pk__in=list(profesores.values_list('pk', flat=True)))
            | Q(rol=Usuario.Rol.ADMIN),
        )

    elif usuario.es_padre():
        matriculas_hijos = Matricula.objects.filter(estudiante__tutor_id=usuario.pk, activa=True)
        profesores = _profesores_de_cursos(matriculas_hijos)
        contactos = Usuario.objects.filter(
            Q(pk__in=list(profesores.values_list('pk', flat=True)))
            | Q(rol=Usuario.Rol.ADMIN),
        )

    else:
        return Usuario.objects.none()

    return (
        contactos.filter(is_active=True)
        .exclude(pk=usuario.pk)
        .distinct()
        .order_by('rol', 'last_name', 'first_name')
    )


def puede_conversar(usuario, otro):
    """True si `usuario` tiene permitido escribirle a `otro`."""
    if usuario is None or otro is None:
        return False
    return usuarios_contactables(usuario).filter(pk=otro.pk).exists()


def _curso_corto(estudiante):
    curso = estudiante.curso_actual
    return f'{curso.grado}° {curso.paralelo}' if curso else 'sin curso'


def buscar_contactos(usuario, consulta):
    """Personas a las que `usuario` puede escribir y que coinciden con la búsqueda.

    Busca **dentro** de `usuarios_contactables`: el buscador no puede ofrecer a
    nadie que después la conversación rechace.

    A la administración y a los docentes, cada estudiante encontrado les trae
    debajo a su padre o tutor: muchas veces a quien hay que escribir por un
    estudiante es a su familia, y así no hace falta saber cómo se llama. Si no
    tiene tutor registrado, se dice, para que no parezca que falta en la lista.
    """
    permitidos = set(usuarios_contactables(usuario).values_list('pk', flat=True))
    sugerir_tutor = usuario.es_admin() or usuario.es_profesor()
    resultados, vistos = [], set()

    def agregar(persona, detalle, bajo_su_hijo=False):
        if persona.pk in vistos or persona.pk not in permitidos:
            return
        vistos.add(persona.pk)
        resultados.append({
            'id': persona.pk,
            'nombre': persona.get_full_name() or persona.username,
            'rol': persona.get_rol_display(),
            'detalle': detalle,
            # Solo el tutor que va justo después de su hijo se dibuja corrido
            # bajo él. Uno encontrado por su nombre va suelto: si no, quedaría
            # debajo de un estudiante cualquiera, como si fuera su padre.
            'bajo_su_hijo': bajo_su_hijo,
        })

    estudiantes = (
        buscar_estudiantes(consulta, Estudiante.objects.filter(usuario_id__in=permitidos))
        .select_related('usuario', 'tutor')
        .order_by('usuario__last_name', 'usuario__first_name')[:LIMITE_BUSQUEDA]
    )
    for estudiante in estudiantes:
        detalle = f'Estudiante · {_curso_corto(estudiante)}'
        tiene_tutor = estudiante.tutor_id in permitidos
        if sugerir_tutor and not tiene_tutor:
            detalle += ' · sin padre/tutor registrado'
        agregar(estudiante.usuario, detalle)
        if sugerir_tutor and tiene_tutor:
            nombre = estudiante.usuario.get_full_name()
            agregar(estudiante.tutor, f'Padre/tutor de {nombre} ({_curso_corto(estudiante)})', bajo_su_hijo=True)

    # Los padres también por su propio nombre. Un docente solo ve nombrados a
    # los hijos que tiene en sus cursos: los demás no son asunto suyo.
    padres = buscar_por_nombre(
        consulta, Usuario.objects.filter(pk__in=permitidos, rol=Usuario.Rol.PADRE),
    ).order_by('last_name', 'first_name')[:LIMITE_BUSQUEDA]
    for padre in padres:
        hijos = [
            f'{h.usuario.get_full_name()} ({_curso_corto(h)})'
            for h in padre.hijos.select_related('usuario') if h.usuario_id in permitidos
        ]
        agregar(padre, 'Padre/tutor de ' + ', '.join(hijos) if hijos else 'Padre/tutor')

    # Cualquier otro contacto (un docente o la dirección), solo por nombre.
    otros = buscar_por_nombre(
        consulta,
        Usuario.objects.filter(pk__in=permitidos).exclude(rol__in=[Usuario.Rol.ESTUDIANTE, Usuario.Rol.PADRE]),
    ).order_by('last_name', 'first_name')[:LIMITE_BUSQUEDA]
    for otro in otros:
        agregar(otro, otro.get_rol_display())

    return resultados
