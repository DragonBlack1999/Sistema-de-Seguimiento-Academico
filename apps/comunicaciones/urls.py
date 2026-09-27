from django.urls import path

from . import views

app_name = 'comunicaciones'

urlpatterns = [
    path('citaciones/', views.lista_citaciones, name='lista_citaciones'),
    path('citaciones/nueva/', views.crear_citacion, name='crear_citacion'),
    path('citaciones/estudiantes/', views.sugerencias_estudiantes, name='sugerencias_estudiantes'),
    path('citaciones/<int:citacion_id>/estado/<str:estado>/', views.cambiar_estado_citacion, name='cambiar_estado_citacion'),
    path('boletines/', views.buscar_boletines, name='buscar_boletines'),
    path('boletines/notas-por-curso.xlsx', views.notas_por_curso_excel, name='notas_por_curso_excel'),
    path('boletin/<int:estudiante_id>/', views.boletin_estudiante, name='boletin_estudiante'),
    path('boletin/<int:estudiante_id>/enviar/', views.enviar_boletin_correo, name='enviar_boletin_correo'),
]
