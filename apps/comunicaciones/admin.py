from django.contrib import admin

from .models import AlertaEmitida, Citacion


@admin.register(Citacion)
class CitacionAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'fecha', 'hora', 'lugar', 'estado', 'es_automatica',
                    'generado_por')
    list_filter = ('estado', 'es_automatica', 'fecha')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name', 'motivo')
    autocomplete_fields = ('estudiante',)
    list_select_related = ('estudiante__usuario', 'generado_por')
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)
    list_per_page = 50


@admin.register(AlertaEmitida)
class AlertaEmitidaAdmin(admin.ModelAdmin):
    """La memoria de lo que ya se avisó, para no repetirlo cada noche.

    Borrar una marca hace que ese aviso vuelva a salir. Es útil para probar;
    en el uso diario no hay que tocarlo.
    """

    list_display = ('estudiante', 'clave', 'fecha_creacion')
    search_fields = ('estudiante__rude', 'estudiante__usuario__first_name',
                     'estudiante__usuario__last_name', 'clave')
    autocomplete_fields = ('estudiante',)
    list_select_related = ('estudiante__usuario',)
    date_hierarchy = 'fecha_creacion'
    list_per_page = 50
