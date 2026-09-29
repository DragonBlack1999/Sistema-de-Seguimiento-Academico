from django.contrib import admin

from .models import Actividad, Nota, Puntaje


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    """Las columnas de la planilla. Se crean desde «Registrar notas»."""

    list_display = ('etiqueta', 'dimension', 'asignacion', 'trimestre', 'orden', 'viene_de_tarea')
    list_filter = ('dimension', 'trimestre', 'asignacion__curso__gestion', 'asignacion__materia')
    search_fields = ('nombre', 'tarea__titulo')
    autocomplete_fields = ('asignacion',)
    list_select_related = ('asignacion__materia', 'asignacion__curso', 'tarea')
    list_per_page = 50

    @admin.display(description='Es una tarea', boolean=True)
    def viene_de_tarea(self, obj):
        return obj.es_tarea


@admin.register(Puntaje)
class PuntajeAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'actividad', 'valor', 'fecha_registro')
    list_filter = ('actividad__dimension', 'actividad__trimestre',
                   'actividad__asignacion__materia')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name')
    autocomplete_fields = ('estudiante', 'actividad')
    list_select_related = ('estudiante__usuario', 'actividad')
    date_hierarchy = 'fecha_registro'
    list_per_page = 50


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    """La nota del trimestre. Se mira: se calcula sola con los puntajes.

    Ser, saber, hacer y el total no se pueden escribir a mano a propósito. Si
    un número está mal, lo que está mal es un puntaje, y se corrige en la
    planilla del docente; cambiarlo aquí duraría hasta el siguiente guardado.
    """

    list_display = (
        'estudiante', 'asignacion', 'trimestre',
        'ser', 'saber', 'hacer', 'autoevaluacion', 'extracurricular', 'nota', 'fecha_registro',
    )
    list_filter = ('trimestre', 'asignacion__curso__gestion', 'asignacion__curso',
                   'asignacion__materia')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name')
    autocomplete_fields = ('estudiante', 'asignacion')
    list_select_related = ('estudiante__usuario', 'asignacion__materia', 'asignacion__curso')
    readonly_fields = ('ser', 'saber', 'hacer', 'nota', 'fecha_registro')
    list_per_page = 50
    fieldsets = (
        ('De quién y de qué materia', {
            'fields': ('estudiante', 'asignacion', 'trimestre'),
        }),
        ('Lo que se calcula solo', {
            'fields': ('ser', 'saber', 'hacer', 'nota'),
            'description': 'Estos cuatro números no se pueden escribir: salen del promedio '
                           'de las actividades de la planilla. Si alguno está mal, lo que '
                           'está mal es un puntaje, y se corrige en «Registrar notas» del '
                           'docente; cambiarlo aquí duraría hasta el siguiente guardado.',
        }),
        ('Lo que sí se escribe', {
            'fields': ('autoevaluacion', 'autoevaluacion_por', 'extracurricular'),
            'description': 'La autoevaluación la pone el estudiante o su docente (hasta 5 '
                           'puntos). El puntaje extracurricular, de 1 a 5, lo da el colegio '
                           'por actividades fuera del aula.',
        }),
        ('Registro', {'fields': ('registrado_por', 'fecha_registro'), 'classes': ('collapse',)}),
    )
