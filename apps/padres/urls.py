from django.urls import path

from . import views

app_name = 'padres'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('hijo/<int:estudiante_id>/notas/', views.notas_hijo, name='notas_hijo'),
    path('hijo/<int:estudiante_id>/asistencia/', views.asistencia_hijo, name='asistencia_hijo'),
    path('hijo/<int:estudiante_id>/tareas/', views.tareas_hijo, name='tareas_hijo'),
    path('hijo/<int:estudiante_id>/citaciones/', views.citaciones_hijo, name='citaciones_hijo'),
]
