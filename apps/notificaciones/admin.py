from django.contrib import admin

from .models import Notificacion, SuscripcionPush


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    """Lo que apareció en la campanita de cada persona."""

    list_display = ('usuario', 'nivel', 'tipo', 'titulo', 'estudiante', 'leida', 'avisada',
                    'fecha_creacion')
    list_filter = ('nivel', 'tipo', 'leida', 'avisada')
    search_fields = ('titulo', 'mensaje', 'usuario__username', 'usuario__last_name')
    autocomplete_fields = ('usuario', 'estudiante')
    list_select_related = ('usuario', 'estudiante__usuario')
    date_hierarchy = 'fecha_creacion'
    list_per_page = 50


@admin.register(SuscripcionPush)
class SuscripcionPushAdmin(admin.ModelAdmin):
    """Los teléfonos suscritos. Solo para mirar: se activan desde el propio celular."""

    list_display = ('usuario', 'dispositivo', 'fecha_creacion', 'ultimo_envio')
    list_filter = ('fecha_creacion',)
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name',
                     'dispositivo')
    list_select_related = ('usuario',)
    readonly_fields = ('endpoint', 'p256dh', 'auth', 'fecha_creacion', 'ultimo_envio')
    list_per_page = 50

    def has_add_permission(self, request):
        # Un teléfono se suscribe desde el teléfono; a mano no sirve de nada.
        return False
