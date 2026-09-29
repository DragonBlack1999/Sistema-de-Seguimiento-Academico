"""Los mensajes, sin su contenido.

El aviso de privacidad del colegio dice, con todas las letras, que una
conversación la leen únicamente las dos personas que la tienen. El admin
mostraba el texto de todos los mensajes y convertía esa frase en mentira.

Queda lo que hace falta para administrar —quiénes conversan, cuántos mensajes,
cuándo, y poder borrar uno si alguien reporta un abuso— sin el texto. Quien
tenga que leer un mensaje por una denuncia, que lo pida a quien lo recibió,
que es como se haría en papel.
"""
from django.contrib import admin

from .models import Conversacion, Mensaje


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ('usuario_menor', 'usuario_mayor', 'cuantos_mensajes',
                    'fecha_ultimo_mensaje')
    search_fields = ('usuario_menor__last_name', 'usuario_mayor__last_name',
                     'usuario_menor__username', 'usuario_mayor__username')
    list_select_related = ('usuario_menor', 'usuario_mayor')
    autocomplete_fields = ('usuario_menor', 'usuario_mayor')
    date_hierarchy = 'fecha_ultimo_mensaje'
    list_per_page = 50

    @admin.display(description='Mensajes')
    def cuantos_mensajes(self, obj):
        return obj.mensajes.count()

    def has_add_permission(self, request):
        return False


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('fecha_envio', 'autor', 'destinatario', 'lleva_archivo', 'leido')
    list_filter = ('leido', 'fecha_envio')
    search_fields = ('autor__last_name', 'destinatario__last_name')
    list_select_related = ('autor', 'destinatario')
    date_hierarchy = 'fecha_envio'
    list_per_page = 50
    # El cuerpo y el archivo no se muestran: ver el título de este módulo.
    fields = ('conversacion', 'autor', 'destinatario', 'leido', 'fecha_envio')
    readonly_fields = fields

    @admin.display(description='Con archivo', boolean=True)
    def lleva_archivo(self, obj):
        return bool(obj.archivo)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
