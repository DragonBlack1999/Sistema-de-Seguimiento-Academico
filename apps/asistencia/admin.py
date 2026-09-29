from django.contrib import admin

from .models import Asistencia


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    """Lo que se marcó en la puerta.

    Se corrige desde aquí cuando hubo un error —alguien que sí vino y quedó
    como falta—, pero lo normal es marcarla en la pantalla de Entrada.
    """

    list_display = ('estudiante', 'fecha', 'estado', 'hora_llegada', 'registrado_por')
    list_filter = ('estado', 'fecha')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name')
    autocomplete_fields = ('estudiante',)
    list_select_related = ('estudiante__usuario', 'registrado_por')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)
    list_per_page = 50
