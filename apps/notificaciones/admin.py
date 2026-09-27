from django.contrib import admin

from .models import Notificacion, SuscripcionPush


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'titulo', 'leida', 'fecha_creacion')
    list_filter = ('tipo', 'leida')
    search_fields = ('titulo', 'mensaje', 'usuario__username')
    list_select_related = ('usuario',)


@admin.register(SuscripcionPush)
class SuscripcionPushAdmin(admin.ModelAdmin):
    """Los teléfonos suscritos. Solo para mirar: se activan desde el propio celular."""

    list_display = ('usuario', 'dispositivo', 'fecha_creacion', 'ultimo_envio')
    list_filter = ('fecha_creacion',)
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'dispositivo')
    list_select_related = ('usuario',)
    readonly_fields = ('endpoint', 'p256dh', 'auth', 'fecha_creacion', 'ultimo_envio')
