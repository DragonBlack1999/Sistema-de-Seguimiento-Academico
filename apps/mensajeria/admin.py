from django.contrib import admin

from .models import Conversacion, Mensaje


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ('usuario_menor', 'usuario_mayor', 'fecha_ultimo_mensaje')
    list_select_related = ('usuario_menor', 'usuario_mayor')


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('conversacion', 'autor', 'destinatario', 'leido', 'fecha_envio')
    list_filter = ('leido',)
    list_select_related = ('conversacion', 'autor', 'destinatario')
