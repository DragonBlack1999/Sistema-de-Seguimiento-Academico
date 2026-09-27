from django.contrib import admin

from .models import Asistencia


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'fecha', 'estado', 'hora_llegada', 'registrado_por')
    list_filter = ('estado', 'fecha')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name', 'estudiante__usuario__last_name')
    list_select_related = ('estudiante__usuario', 'registrado_por')
    date_hierarchy = 'fecha'
