from django.urls import path

from . import views

app_name = 'datos'

urlpatterns = [
    path('', views.indice, name='indice'),
    path('<slug:clave>/', views.lista, name='lista'),
    path('<slug:clave>/nuevo/', views.editar, name='nuevo'),
    path('<slug:clave>/<int:pk>/editar/', views.editar, name='editar'),
    path('<slug:clave>/<int:pk>/baja/', views.cambiar_estado, {'encender': False}, name='baja'),
    path('<slug:clave>/<int:pk>/alta/', views.cambiar_estado, {'encender': True}, name='alta'),
    path('<slug:clave>/<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
