from django.contrib import admin

from .models import Actividad, Nota, Puntaje


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dimension', 'asignacion', 'trimestre', 'orden')
    list_filter = ('dimension', 'trimestre', 'asignacion__curso__gestion', 'asignacion__materia')
    search_fields = ('nombre',)


@admin.register(Puntaje)
class PuntajeAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'actividad', 'valor', 'fecha_registro')
    list_filter = ('actividad__dimension', 'actividad__trimestre', 'actividad__asignacion__materia')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name', 'estudiante__usuario__last_name')


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    # La nota sale de los puntajes: aquí se mira, no se escribe a mano.
    list_display = (
        'estudiante', 'asignacion', 'trimestre',
        'ser', 'saber', 'hacer', 'autoevaluacion', 'extracurricular', 'nota', 'fecha_registro',
    )
    list_filter = ('trimestre', 'asignacion__curso__gestion', 'asignacion__materia')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name', 'estudiante__usuario__last_name')
    readonly_fields = ('ser', 'saber', 'hacer', 'nota')
