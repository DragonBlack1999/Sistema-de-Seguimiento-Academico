from django.contrib import admin

from .models import EntregaTarea, Tarea


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'asignacion', 'trimestre', 'fecha_entrega', 'permite_archivo', 'permite_atraso')
    list_filter = ('trimestre', 'asignacion__curso__gestion', 'asignacion__materia', 'permite_archivo')
    search_fields = ('titulo', 'descripcion')
    list_select_related = ('asignacion__materia', 'asignacion__curso')


@admin.register(EntregaTarea)
class EntregaTareaAdmin(admin.ModelAdmin):
    # La nota no está aquí: vive en el puntaje de la columna de la tarea.
    list_display = ('estudiante', 'tarea', 'estado', 'fecha_entrega_real')
    list_filter = ('estado', 'tarea__trimestre', 'tarea__asignacion__materia')
    search_fields = (
        'estudiante__rude', 'estudiante__usuario__first_name',
        'estudiante__usuario__last_name', 'tarea__titulo',
    )
    list_select_related = ('estudiante__usuario', 'tarea')
