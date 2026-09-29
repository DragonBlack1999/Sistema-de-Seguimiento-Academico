from django.contrib import admin

from .forms import AsignacionDocenteForm, EstudianteForm
from .models import (
    AsignacionDocente, Curso, DiaCapacitacion, Estudiante, Gestion, Horario,
    Materia, Matricula, Periodo,
)


def enviar_boletin_por_correo(modeladmin, request, queryset):
    from apps.comunicaciones.emails import destinatarios_estudiante, enviar_correo
    from apps.comunicaciones.reportes import generar_boletin_pdf

    enviados, sin_correo, fallidos = 0, 0, 0
    for estudiante in queryset:
        destinatarios = destinatarios_estudiante(estudiante)
        if not destinatarios:
            sin_correo += 1
            continue
        try:
            pdf_bytes = generar_boletin_pdf(estudiante)
            enviar_correo(
                f'Boletín de calificaciones - {estudiante.usuario.get_full_name()}',
                'Adjuntamos el boletín de calificaciones actualizado.\n\n'
                'Unidad Educativa «Eduardo Abaroa Tarde» - Nivel Secundario',
                destinatarios,
                adjunto_bytes=pdf_bytes, adjunto_nombre=f'boletin_{estudiante.rude}.pdf',
            )
            enviados += 1
        except Exception:
            fallidos += 1

    modeladmin.message_user(
        request,
        f'Boletines enviados: {enviados}. Sin correo registrado: {sin_correo}. Fallidos: {fallidos}.',
    )


enviar_boletin_por_correo.short_description = 'Enviar boletín por correo (estudiante y tutor)'


@admin.register(Gestion)
class GestionAdmin(admin.ModelAdmin):
    """El año escolar. Solo uno puede estar activo: es el que ve todo el sistema."""

    list_display = ('anio', 'activa', 'fecha_inicio', 'fecha_fin')
    list_filter = ('activa',)
    ordering = ('-anio',)
    search_fields = ('anio',)


class DiaCapacitacionInline(admin.TabularInline):
    model = DiaCapacitacion
    extra = 1
    verbose_name_plural = 'Días de capacitación (esos días el curso no entra por la puerta)'


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'gestion', 'nivel', 'grado', 'paralelo',
                    'cuantos_estudiantes', 'dias_de_capacitacion')
    list_filter = ('gestion', 'nivel', 'grado')
    search_fields = ('grado', 'paralelo')
    ordering = ('-gestion__anio', 'grado', 'paralelo')
    inlines = [DiaCapacitacionInline]
    list_select_related = ('gestion',)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('dias_capacitacion')

    @admin.display(description='Estudiantes')
    def cuantos_estudiantes(self, obj):
        return obj.matriculas.filter(activa=True).count()

    @admin.display(description='Capacitación')
    def dias_de_capacitacion(self, obj):
        return ', '.join(d.get_dia_display() for d in obj.dias_capacitacion.all()) or '—'


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuantos_cursos')
    search_fields = ('nombre',)
    ordering = ('nombre',)

    @admin.display(description='Cursos en los que se dicta')
    def cuantos_cursos(self, obj):
        return obj.asignaciones.count()


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    """La ficha del estudiante.

    Al guardar, el formulario crea o actualiza tres cosas a la vez: su cuenta
    de acceso, su matrícula en el curso y la cuenta de su tutor a partir del
    carnet. Por eso se edita aquí y no en «Cuentas de acceso».
    """

    form = EstudianteForm
    list_display = ('rude', 'nombre', 'curso_de', 'tutor', 'celular')
    list_display_links = ('rude', 'nombre')
    search_fields = ('rude', 'usuario__first_name', 'usuario__last_name',
                     'tutor__first_name', 'tutor__last_name', 'usuario__ci')
    list_filter = ('matriculas__curso__gestion', 'matriculas__curso', 'genero')
    ordering = ('usuario__last_name', 'usuario__first_name')
    list_select_related = ('usuario', 'tutor')
    list_per_page = 40
    actions = [enviar_boletin_por_correo]
    readonly_fields = ('tutor',)   # derivado del CI que se escribe en el formulario

    @admin.display(description='Estudiante', ordering='usuario__last_name')
    def nombre(self, obj):
        # Sin el «(Estudiante)» que agrega el __str__ del usuario: en una lista
        # de estudiantes, repetirlo 402 veces no informa de nada.
        return obj.usuario.get_full_name() or obj.usuario.username

    @admin.display(description='Curso')
    def curso_de(self, obj):
        return obj.curso_actual or '—'

    fieldsets = (
        ('Datos de acceso (usuario del estudiante)', {
            'fields': ('nombres', 'apellidos', 'rude', 'ci_estudiante', 'email_estudiante'),
            'description': 'Entra al sistema con su RUDE como usuario y su carnet como contraseña.',
        }),
        ('Datos personales', {
            'fields': ('fecha_nacimiento', 'genero', 'nacionalidad', 'departamento'),
        }),
        ('Contacto y datos adicionales', {
            'fields': ('direccion', 'celular', 'grupo_sanguineo', 'foto_perfil'),
        }),
        ('Datos académicos', {
            'fields': ('curso',),
            'description': 'Al cambiar el curso se cierra la matrícula anterior y se abre la nueva.',
        }),
        ('Datos del padre/tutor', {
            'fields': ('nombre_tutor', 'ci_tutor', 'telefono_tutor', 'email_tutor'),
            'description': 'Con el carnet se crea su cuenta, si todavía no la tiene. '
                           'Entra escribiendo ese mismo carnet en los dos campos.',
        }),
    )


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'curso', 'activa', 'fecha_matricula')
    list_filter = ('curso__gestion', 'curso', 'activa')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name')
    autocomplete_fields = ('estudiante', 'curso')
    list_select_related = ('estudiante__usuario', 'curso')
    date_hierarchy = 'fecha_matricula'
    list_per_page = 50


@admin.register(AsignacionDocente)
class AsignacionDocenteAdmin(admin.ModelAdmin):
    """Quién dicta qué, y en qué curso. De aquí cuelgan las planillas y el horario."""

    form = AsignacionDocenteForm
    list_display = ('profesor', 'materia', 'curso')
    list_filter = ('curso__gestion', 'curso', 'materia')
    search_fields = ('profesor__first_name', 'profesor__last_name', 'materia__nombre')
    ordering = ('curso__grado', 'curso__paralelo', 'materia__nombre')
    list_select_related = ('profesor', 'materia', 'curso')
    list_per_page = 50


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('asignacion', 'dia', 'periodo', 'aula')
    list_filter = ('dia', 'periodo__curso')
    search_fields = ('asignacion__materia__nombre', 'asignacion__profesor__last_name', 'aula')
    autocomplete_fields = ('asignacion', 'periodo')
    list_select_related = ('asignacion__materia', 'asignacion__profesor', 'periodo')
    list_per_page = 50


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'orden', 'etiqueta', 'es_recreo')
    list_filter = ('curso', 'es_recreo')
    search_fields = ('etiqueta', 'curso__grado')
    autocomplete_fields = ('curso',)
    ordering = ('curso', 'orden')
