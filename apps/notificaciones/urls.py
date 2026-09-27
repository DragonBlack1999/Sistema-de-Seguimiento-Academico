from django.urls import path

from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('avisos/activar/', views.activar_avisos, name='activar_avisos'),
    path('avisos/desactivar/', views.desactivar_avisos, name='desactivar_avisos'),
    path('<int:pk>/abrir/', views.abrir, name='abrir'),
    path('marcar-todas/', views.marcar_todas, name='marcar_todas'),
    path('contador/', views.contador, name='contador'),
]
