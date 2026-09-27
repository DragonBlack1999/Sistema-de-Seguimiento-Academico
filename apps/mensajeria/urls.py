from django.urls import path

from . import views

app_name = 'mensajeria'

urlpatterns = [
    path('', views.bandeja, name='bandeja'),
    path('buscar/', views.sugerencias_contactos, name='sugerencias_contactos'),
    path('con/<int:usuario_id>/', views.conversacion, name='conversacion'),
    path('con/<int:usuario_id>/nuevos/', views.nuevos_mensajes, name='nuevos_mensajes'),
    path('adjunto/<int:mensaje_id>/', views.descargar_adjunto, name='descargar_adjunto'),
]
