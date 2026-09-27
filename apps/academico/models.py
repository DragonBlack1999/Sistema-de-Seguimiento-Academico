from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Gestion(models.Model):
    """Año escolar (gestión educativa)."""
    anio = models.PositiveIntegerField('Año', unique=True)
    activa = models.BooleanField(default=False)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-anio']
        verbose_name = 'Gestión'
        verbose_name_plural = 'Gestiones'
        constraints = [
            # Media docena de consultas preguntan "la gestión activa" y toman la
            # primera: si hubiera dos, cada pantalla podría elegir una distinta.
            models.UniqueConstraint(
                fields=['activa'], condition=models.Q(activa=True),
                name='una_sola_gestion_activa',
            ),
        ]

    def __str__(self):
        return str(self.anio)


class Curso(models.Model):
    class Nivel(models.TextChoices):
        INICIAL = 'INICIAL', 'Inicial'
        PRIMARIA = 'PRIMARIA', 'Primaria'
        SECUNDARIA = 'SECUNDARIA', 'Secundaria'

    gestion = models.ForeignKey(Gestion, on_delete=models.CASCADE, related_name='cursos')
    nivel = models.CharField(max_length=12, choices=Nivel.choices)
    grado = models.PositiveSmallIntegerField('Grado', help_text='Ej: 1 para 1ro')
    paralelo = models.CharField(max_length=2, default='A')

    class Meta:
        ordering = ['gestion', 'nivel', 'grado', 'paralelo']
        unique_together = ('gestion', 'nivel', 'grado', 'paralelo')
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'

    def __str__(self):
        return f'{self.grado}° de {self.get_nivel_display()} "{self.paralelo}" ({self.gestion})'


class Materia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return self.nombre


class Estudiante(models.Model):
    class Genero(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO = 'F', 'Femenino'
        OTRO = 'O', 'Otro'

    class Departamento(models.TextChoices):
        LA_PAZ = 'LA_PAZ', 'La Paz'
        COCHABAMBA = 'COCHABAMBA', 'Cochabamba'
        SANTA_CRUZ = 'SANTA_CRUZ', 'Santa Cruz'
        ORURO = 'ORURO', 'Oruro'
        POTOSI = 'POTOSI', 'Potosí'
        CHUQUISACA = 'CHUQUISACA', 'Chuquisaca'
        TARIJA = 'TARIJA', 'Tarija'
        BENI = 'BENI', 'Beni'
        PANDO = 'PANDO', 'Pando'

    class GrupoSanguineo(models.TextChoices):
        A_POS = 'A+', 'A+'
        A_NEG = 'A-', 'A-'
        B_POS = 'B+', 'B+'
        B_NEG = 'B-', 'B-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'
        O_POS = 'O+', 'O+'
        O_NEG = 'O-', 'O-'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='estudiante'
    )
    rude = models.CharField('RUDE', max_length=20, unique=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    genero = models.CharField(max_length=1, choices=Genero.choices, blank=True)
    nacionalidad = models.CharField(max_length=50, blank=True, default='Boliviana')
    departamento = models.CharField(max_length=15, choices=Departamento.choices, blank=True)

    direccion = models.CharField(max_length=255, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    grupo_sanguineo = models.CharField(max_length=3, choices=GrupoSanguineo.choices, blank=True)
    foto_perfil = models.ImageField(upload_to='estudiantes/fotos/', null=True, blank=True)

    # El curso NO se guarda aquí: lo determina la matrícula activa (ver `curso_actual`).
    # Los datos del tutor tampoco: viven en su Usuario, al que apunta `tutor`.
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hijos', limit_choices_to={'rol': 'PADRE'},
        verbose_name='Padre/tutor',
        help_text='Se crea y se vincula sola a partir del CI que se escriba en el formulario.',
    )

    class Meta:
        ordering = ['usuario__last_name', 'usuario__first_name']
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'

    @property
    def email_estudiante(self):
        return self.usuario.email

    @property
    def matricula_actual(self):
        """Matrícula activa más reciente. Es la fuente del curso del estudiante."""
        return (
            self.matriculas.filter(activa=True)
            .select_related('curso__gestion').order_by('-curso__gestion__anio').first()
        )

    @property
    def curso_actual(self):
        """Curso vigente, derivado de la matrícula activa.

        Antes era una columna propia que podía contradecir a la matrícula; de
        hecho llegó a hacerlo (un estudiante con curso pero sin matrícula no
        aparecía en tareas ni podía escribir a sus profesores).
        """
        matricula = self.matricula_actual
        return matricula.curso if matricula else None

    # --- datos del padre/tutor: se leen de su Usuario, no se copian aquí ---

    @property
    def nombre_tutor(self):
        return self.tutor.get_full_name() if self.tutor else ''

    @property
    def ci_tutor(self):
        return self.tutor.ci if self.tutor else ''

    @property
    def telefono_tutor(self):
        return self.tutor.telefono if self.tutor else ''

    @property
    def email_tutor(self):
        return self.tutor.email if self.tutor else ''

    def __str__(self):
        return f'{self.usuario.get_full_name()} ({self.rude})'


class Matricula(models.Model):
    """Inscripción de un estudiante en un curso.

    La gestión no se guarda: la determina el curso. Antes estaba repetida, y
    nada impedía una matrícula cuyo curso fuera de 2026 y cuya gestión dijera
    2025. La regla de "una matrícula por año" se valida en `clean`, porque una
    restricción de base de datos no puede mirar la gestión a través del curso.
    """

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='matriculas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='matriculas')
    fecha_matricula = models.DateField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'curso'], name='una_matricula_por_curso'),
        ]
        ordering = ['-curso__gestion__anio', 'curso']
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'

    @property
    def gestion(self):
        return self.curso.gestion

    def clean(self):
        if self.estudiante_id and self.curso_id:
            otras = Matricula.objects.filter(
                estudiante_id=self.estudiante_id, curso__gestion_id=self.curso.gestion_id,
            ).exclude(pk=self.pk)
            if otras.exists():
                raise ValidationError(
                    f'{self.estudiante} ya tiene una matrícula en la gestión {self.curso.gestion}.'
                )

    def __str__(self):
        return f'{self.estudiante} - {self.curso}'


class Periodo(models.Model):
    """Una fila de la grilla de horario, propia de un curso.

    No guarda horas: el colegio organiza el día por períodos ("1°", "2°", el
    recreo), y cada curso puede empezar a una hora distinta. Guardar horas
    obligaba a repetirlas en cada curso y a mantenerlas al día sin que
    aportaran nada a la grilla, que se lee por orden.
    """
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='periodos')
    orden = models.PositiveSmallIntegerField(default=0)
    es_recreo = models.BooleanField('Es recreo', default=False)
    etiqueta = models.CharField(
        max_length=50, blank=True,
        help_text='Cómo se llama en el colegio. Ej: "1°", "Recreo". Opcional.',
    )

    class Meta:
        ordering = ['curso', 'orden']
        verbose_name = 'Período'
        verbose_name_plural = 'Períodos'

    @property
    def nombre(self):
        """Cómo se llama la fila en pantalla."""
        if self.etiqueta:
            return self.etiqueta
        if self.es_recreo:
            return 'Recreo'
        return f'Período {self.orden + 1}'

    def __str__(self):
        return f'{self.curso} - {self.nombre}'


class AsignacionDocente(models.Model):
    """Qué profesor dicta qué materia en qué curso.

    La gestión no se guarda: la determina el curso. La restricción de unicidad
    pasa de (curso, materia, gestión) a (curso, materia) sin perder nada,
    porque el curso ya identifica su año.

    Un profesor puede dictar varias materias: en este colegio, 13 de los 33
    docentes dan dos o tres. Esta tabla es la única que dice quién dicta qué.
    """

    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='asignaciones', limit_choices_to={'rol': 'PROFESOR'},
    )
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='asignaciones')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='asignaciones')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['curso', 'materia'], name='una_materia_por_curso'),
        ]
        ordering = ['curso', 'materia']
        verbose_name = 'Asignación docente'
        verbose_name_plural = 'Asignaciones docentes'

    @property
    def gestion(self):
        return self.curso.gestion

    def __str__(self):
        return f'{self.profesor.get_full_name()} - {self.materia} - {self.curso}'


class Horario(models.Model):
    """Una clase en la grilla semanal: un período de un día, con su asignación.

    La clase no guarda hora propia: vive en la celda formada por su período y su
    día, que es como se lee un horario en la pared.
    """

    class Dia(models.TextChoices):
        LUNES = 'LUN', 'Lunes'
        MARTES = 'MAR', 'Martes'
        MIERCOLES = 'MIE', 'Miércoles'
        JUEVES = 'JUE', 'Jueves'
        VIERNES = 'VIE', 'Viernes'
        SABADO = 'SAB', 'Sábado'

    asignacion = models.ForeignKey(AsignacionDocente, on_delete=models.CASCADE, related_name='horarios')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='horarios')
    dia = models.CharField(max_length=3, choices=Dia.choices)
    aula = models.CharField(max_length=30, blank=True)

    class Meta:
        constraints = [
            # Una sola clase por curso, día y período: es la celda de la grilla.
            models.UniqueConstraint(fields=['periodo', 'dia'], name='una_clase_por_celda'),
        ]
        ordering = ['dia', 'periodo__orden']
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'

    def clean(self):
        if self.asignacion_id and self.periodo_id:
            if self.periodo.curso_id != self.asignacion.curso_id:
                raise ValidationError(
                    'El período pertenece a otro curso distinto al de la asignación.'
                )
            if self.periodo.es_recreo:
                raise ValidationError('No se pueden poner clases en un recreo.')

    def __str__(self):
        return f'{self.asignacion} - {self.get_dia_display()} {self.periodo.nombre}'


class DiaCapacitacion(models.Model):
    """Día de la semana en que un curso pasa clases de capacitación.

    Esos días el curso **no entra por la puerta** con el resto del colegio: su
    asistencia la registra el administrador desde su propia pantalla. Un curso
    es "especial" precisamente porque tiene días registrados aquí, así que no
    hace falta codificar en el programa qué grados lo son.
    """

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='dias_capacitacion')
    dia = models.CharField('Día', max_length=3, choices=Horario.Dia.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['curso', 'dia'], name='un_dia_de_capacitacion_por_curso'),
        ]
        ordering = ['curso', 'dia']
        verbose_name = 'Día de capacitación'
        verbose_name_plural = 'Días de capacitación'

    def __str__(self):
        return f'{self.curso} - {self.get_dia_display()}'
