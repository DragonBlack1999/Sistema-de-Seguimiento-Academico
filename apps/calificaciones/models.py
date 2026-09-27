"""Calificación por dimensiones, como la planilla del colegio.

Cada trimestre se arma con cuatro partes que suman 100:

    ser 10 · saber 45 · hacer 40 · autoevaluación 5

Dentro de ser, saber y hacer el docente registra varias **actividades**; la nota
de la dimensión es el promedio de sus actividades, calificada cada una sobre el
máximo de esa dimensión (una actividad de saber se pone sobre 45), tal como lo
hacen en su planilla de papel.

Aparte, el estudiante puede recibir de 1 a 5 puntos por actividades
extracurriculares. Se suman al final, pero el trimestre nunca pasa de 100.

`Nota.nota` sigue siendo el total del trimestre: es lo que leen el boletín, el
Excel, el tablero y las pantallas del estudiante y del padre. Lo nuevo son las
columnas que explican de dónde sale ese número.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg

from apps.academico.models import AsignacionDocente, Estudiante

NOTA_APROBACION = 51
NOTA_MAXIMA = Decimal('100')


class Trimestre(models.IntegerChoices):
    PRIMERO = 1, 'Primer trimestre'
    SEGUNDO = 2, 'Segundo trimestre'
    TERCERO = 3, 'Tercer trimestre'


class Dimension(models.TextChoices):
    SER = 'SER', 'Ser'
    SABER = 'SABER', 'Saber'
    HACER = 'HACER', 'Hacer'


# Cuánto vale cada parte. Si el colegio cambia la ponderación, se cambia aquí y
# en ningún otro lado: las pantallas y los reportes leen estos valores.
MAXIMO = {
    Dimension.SER: Decimal('10'),
    Dimension.SABER: Decimal('45'),
    Dimension.HACER: Decimal('40'),
}
MAXIMO_AUTOEVALUACION = Decimal('5')      # la columna "decidir" de la planilla
MAXIMO_EXTRACURRICULAR = Decimal('5')


def maximo_de(dimension):
    return MAXIMO[Dimension(dimension)]


def redondear(valor):
    """Las notas del colegio son números enteros, también los promedios.

    Se redondea aquí y no al mostrar: si cada pantalla redondeara por su cuenta,
    el boletín, el Excel y «Mis notas» podrían discrepar en un punto.
    """
    return None if valor is None else Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def aprueba(valor, maximo=NOTA_MAXIMA):
    """Si un puntaje alcanza para aprobar, en la escala que sea.

    Aprobar es 51 sobre 100; sobre 40, que es lo que vale una tarea, son 20,4.
    El criterio vive en un solo lugar aunque las escalas cambien.
    """
    if valor is None:
        return False
    return Decimal(valor) >= Decimal(maximo) * NOTA_APROBACION / NOTA_MAXIMA


class Actividad(models.Model):
    """Una casilla de la planilla: un trabajo, una prueba, una exposición.

    Vive en una dimensión de una materia y un trimestre. El nombre es del
    docente ("Práctico 1", "Examen"), para que reconozca su propia planilla.
    """

    asignacion = models.ForeignKey(
        AsignacionDocente, on_delete=models.CASCADE, related_name='actividades'
    )
    trimestre = models.PositiveSmallIntegerField(choices=Trimestre.choices)
    dimension = models.CharField(max_length=5, choices=Dimension.choices)
    nombre = models.CharField(
        max_length=60, blank=True,
        help_text='Vacío cuando la actividad es una tarea: el nombre lo pone la tarea.',
    )
    orden = models.PositiveSmallIntegerField(default=0)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='actividades_creadas',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['asignacion', 'trimestre', 'dimension', 'orden', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['asignacion', 'trimestre', 'dimension', 'orden'],
                name='un_orden_por_dimension',
            ),
        ]
        verbose_name = 'Actividad'
        verbose_name_plural = 'Actividades'

    @property
    def maximo(self):
        """Sobre cuánto se califica: el máximo de su dimensión."""
        return maximo_de(self.dimension)

    @property
    def etiqueta(self):
        """Cómo se llama la columna. Si es una tarea, se llama como la tarea.

        Así el título no queda copiado en dos tablas y renombrar la tarea no
        necesita ir a corregir nada más.
        """
        tarea = getattr(self, 'tarea', None)
        return tarea.titulo if tarea is not None else self.nombre

    @property
    def es_tarea(self):
        return getattr(self, 'tarea', None) is not None

    def __str__(self):
        return f'{self.get_dimension_display()} · {self.etiqueta} ({self.asignacion} T{self.trimestre})'


class Puntaje(models.Model):
    """Lo que sacó un estudiante en una actividad, sobre el máximo de su dimensión."""

    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name='puntajes')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='puntajes')
    valor = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='puntajes_registrados',
    )
    fecha_registro = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['actividad', 'estudiante']
        constraints = [
            models.UniqueConstraint(
                fields=['actividad', 'estudiante'], name='un_puntaje_por_actividad',
            ),
            # 45 es el máximo de la dimensión más alta: el tope exacto depende de
            # la dimensión y lo comprueba `clean()`, pero un disparate no entra.
            models.CheckConstraint(condition=models.Q(valor__gte=0, valor__lte=45),
                                   name='puntaje_en_rango'),
        ]
        verbose_name = 'Puntaje'
        verbose_name_plural = 'Puntajes'

    def clean(self):
        # El tope depende de la dimensión, así que no puede ser un validador fijo.
        if self.valor is not None and self.actividad_id and self.valor > self.actividad.maximo:
            raise ValidationError(
                f'{self.actividad.get_dimension_display()} se califica sobre {self.actividad.maximo}.'
            )

    def __str__(self):
        return f'{self.estudiante} · {self.actividad.nombre}: {self.valor}'


class NotaQuerySet(models.QuerySet):
    def calificadas(self):
        """Solo las que el docente ya empezó a calificar.

        Un estudiante puede ponerse su autoevaluación antes de que el docente
        cargue nada. Sin este filtro, esa materia aparecería con un 5 como si
        estuviera calificada y reprobada, y arrastraría los promedios.
        """
        return self.filter(
            models.Q(ser__isnull=False) | models.Q(saber__isnull=False) | models.Q(hacer__isnull=False)
        )


class Nota(models.Model):
    """El trimestre de un estudiante en una materia, con su desglose.

    `nota` es la suma de las cuatro partes más lo extracurricular, topada en 100.
    No se escribe a mano: la rehace `recalcular()` a partir de los puntajes.
    """

    objects = NotaQuerySet.as_manager()

    asignacion = models.ForeignKey(AsignacionDocente, on_delete=models.CASCADE, related_name='notas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='notas')
    trimestre = models.PositiveSmallIntegerField(choices=Trimestre.choices)

    ser = models.DecimalField('Ser', max_digits=5, decimal_places=2, null=True, blank=True)
    saber = models.DecimalField('Saber', max_digits=5, decimal_places=2, null=True, blank=True)
    hacer = models.DecimalField('Hacer', max_digits=5, decimal_places=2, null=True, blank=True)
    autoevaluacion = models.DecimalField(
        'Autoevaluación', max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAXIMO_AUTOEVALUACION)],
        help_text='De 0 a 5. La pone el estudiante o su docente.',
    )
    autoevaluacion_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='autoevaluaciones_puestas',
        help_text='Quién la puso: sirve para que el docente sepa si el estudiante ya se evaluó.',
    )
    extracurricular = models.DecimalField(
        'Actividad extracurricular', max_digits=4, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(0), MaxValueValidator(MAXIMO_EXTRACURRICULAR)],
        help_text='De 0 a 5 puntos. Se suman, pero el trimestre no pasa de 100.',
    )

    nota = models.DecimalField(
        'Nota del trimestre', max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='notas_registradas'
    )
    fecha_registro = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('asignacion', 'estudiante', 'trimestre')
        ordering = ['asignacion', 'trimestre', 'estudiante']
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        constraints = [
            models.CheckConstraint(condition=models.Q(nota__gte=0, nota__lte=100),
                                   name='nota_en_rango'),
            models.CheckConstraint(
                condition=models.Q(autoevaluacion__isnull=True)
                | models.Q(autoevaluacion__gte=0, autoevaluacion__lte=5),
                name='autoevaluacion_en_rango',
            ),
            models.CheckConstraint(
                condition=models.Q(extracurricular__gte=0, extracurricular__lte=5),
                name='extracurricular_en_rango',
            ),
        ]

    @property
    def aprobado(self):
        return self.nota >= NOTA_APROBACION

    @property
    def desglose(self):
        """Las partes en el orden de la planilla, para mostrarlas en pantalla."""
        return [
            ('Ser', self.ser, MAXIMO[Dimension.SER]),
            ('Saber', self.saber, MAXIMO[Dimension.SABER]),
            ('Hacer', self.hacer, MAXIMO[Dimension.HACER]),
            ('Autoevaluación', self.autoevaluacion, MAXIMO_AUTOEVALUACION),
            ('Extracurricular', self.extracurricular, MAXIMO_EXTRACURRICULAR),
        ]

    def promedios_de_dimension(self):
        """Promedio de las actividades de cada dimensión, o None si no hay ninguna."""
        filas = (
            Puntaje.objects
            .filter(
                estudiante_id=self.estudiante_id,
                actividad__asignacion_id=self.asignacion_id,
                actividad__trimestre=self.trimestre,
            )
            .values('actividad__dimension')
            .annotate(promedio=Avg('valor'))
        )
        return {fila['actividad__dimension']: redondear(fila['promedio']) for fila in filas}

    def recalcular(self, guardar=True):
        """Rehace el desglose y el total desde los puntajes cargados.

        No hay señales en el proyecto: la llaman las vistas después de guardar.
        """
        promedios = self.promedios_de_dimension()
        self.ser = promedios.get(Dimension.SER)
        self.saber = promedios.get(Dimension.SABER)
        self.hacer = promedios.get(Dimension.HACER)

        suma = sum(
            (valor for valor in (self.ser, self.saber, self.hacer,
                                 self.autoevaluacion, self.extracurricular)
             if valor is not None),
            Decimal('0'),
        )
        self.nota = redondear(min(NOTA_MAXIMA, suma))
        if guardar:
            self.save()
        return self.nota

    def __str__(self):
        return f'{self.estudiante} - {self.asignacion.materia} T{self.trimestre}: {self.nota}'
