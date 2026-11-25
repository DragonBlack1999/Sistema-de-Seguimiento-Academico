from django.contrib import admin

from .models import EntregaTarea, Tarea
from .notas import guardar_con_planilla


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    """Cada tarea es además una columna de «hacer» en la planilla de su materia."""

    list_display = ('titulo', 'asignacion', 'trimestre', 'fecha_entrega',
                    'permite_archivo', 'permite_atraso')
    list_filter = ('trimestre', 'asignacion__curso__gestion', 'asignacion__curso',
                   'asignacion__materia', 'permite_archivo')
    search_fields = ('titulo', 'descripcion')
    autocomplete_fields = ('asignacion',)
    list_select_related = ('asignacion__materia', 'asignacion__curso')
    date_hierarchy = 'fecha_entrega'
    ordering = ('-fecha_entrega',)
    list_per_page = 50
    readonly_fields = ('actividad',)

    def save_model(self, request, obj, form, change):
        guardar_con_planilla(obj, request.user)


@admin.register(EntregaTarea)
class EntregaTareaAdmin(admin.ModelAdmin):
    """La nota no está aquí: vive en el puntaje de la columna de la tarea."""

    list_display = ('estudiante', 'tarea', 'estado', 'fecha_entrega_real')
    list_filter = ('estado', 'tarea__trimestre', 'tarea__asignacion__materia')
    search_fields = (
        'estudiante__rude', 'estudiante__usuario__first_name',
        'estudiante__usuario__last_name', 'tarea__titulo',
    )
    autocomplete_fields = ('estudiante', 'tarea')
    list_select_related = ('estudiante__usuario', 'tarea')
    list_per_page = 50
