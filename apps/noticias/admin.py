from django.contrib import admin

from .models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'curso', 'publicada', 'fijada', 'fecha_publicacion')
    list_filter = ('tipo', 'publicada', 'fijada', 'curso')
    search_fields = ('titulo', 'cuerpo')
    list_select_related = ('curso', 'publicado_por')
