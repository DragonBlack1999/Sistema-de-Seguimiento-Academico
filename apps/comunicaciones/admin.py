from django.contrib import admin

from .models import Citacion


@admin.register(Citacion)
class CitacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'fecha', 'estado', 'es_automatica', 'generado_por')
    list_filter = ('estado', 'es_automatica', 'fecha')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name', 'estudiante__usuario__last_name')
