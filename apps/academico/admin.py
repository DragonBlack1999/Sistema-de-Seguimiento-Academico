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
    list_display = ('anio', 'activa', 'fecha_inicio', 'fecha_fin')
    list_filter = ('activa',)


class DiaCapacitacionInline(admin.TabularInline):
    model = DiaCapacitacion
    extra = 1
    verbose_name_plural = 'Días de capacitación (esos días el curso no entra por la puerta)'


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'gestion', 'nivel', 'grado', 'paralelo', 'dias_de_capacitacion')
    list_filter = ('gestion', 'nivel')
    inlines = [DiaCapacitacionInline]

    @admin.display(description='Capacitación')
    def dias_de_capacitacion(self, obj):
        return ', '.join(d.get_dia_display() for d in obj.dias_capacitacion.all()) or '—'


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    search_fields = ('nombre',)


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    form = EstudianteForm
    # curso_actual y los datos del tutor ya no son columnas: se muestran calculados
    list_display = ('rude', 'usuario', 'curso_de', 'tutor')
    search_fields = ('rude', 'usuario__first_name', 'usuario__last_name',
                     'tutor__first_name', 'tutor__last_name')
    list_filter = ('matriculas__curso',)
    actions = [enviar_boletin_por_correo]
    readonly_fields = ('tutor',)   # derivado del CI que se escribe en el formulario

    @admin.display(description='Curso')
    def curso_de(self, obj):
        return obj.curso_actual or '—'
    fieldsets = (
        ('Datos de acceso (usuario del estudiante)', {
            'fields': ('nombres', 'apellidos', 'rude', 'ci_estudiante', 'email_estudiante'),
        }),
        ('Datos personales', {
            'fields': ('fecha_nacimiento', 'genero', 'nacionalidad', 'departamento'),
        }),
        ('Contacto y datos adicionales', {
            'fields': ('direccion', 'celular', 'grupo_sanguineo', 'foto_perfil'),
        }),
        ('Datos académicos', {
            'fields': ('curso',),
        }),
        ('Datos del padre/tutor', {
            'fields': ('nombre_tutor', 'ci_tutor', 'telefono_tutor', 'email_tutor'),
        }),
    )


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'curso', 'activa', 'fecha_matricula')
    list_filter = ('curso__gestion', 'curso', 'activa')


@admin.register(AsignacionDocente)
class AsignacionDocenteAdmin(admin.ModelAdmin):
    form = AsignacionDocenteForm
    list_display = ('profesor', 'materia', 'curso')
    list_filter = ('curso__gestion', 'curso', 'materia')


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('asignacion', 'dia', 'periodo', 'aula')
    list_filter = ('dia', 'periodo__curso')


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'orden', 'etiqueta', 'es_recreo')
    list_filter = ('curso', 'es_recreo')
