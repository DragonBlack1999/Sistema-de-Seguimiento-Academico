from django.urls import path

from . import views

app_name = 'tareas'

urlpatterns = [
    # Profesor / admin
    path('asignacion/<int:asignacion_id>/', views.lista_tareas, name='lista_tareas'),
    path('asignacion/<int:asignacion_id>/nueva/', views.crear_tarea, name='crear_tarea'),
    path('<int:tarea_id>/editar/', views.editar_tarea, name='editar_tarea'),
    path('<int:tarea_id>/eliminar/', views.eliminar_tarea, name='eliminar_tarea'),
    path('<int:tarea_id>/calificar/', views.calificar_tarea, name='calificar_tarea'),

    # Estudiante
    path('mis-tareas/', views.mis_tareas, name='mis_tareas'),
    path('mis-tareas/<int:tarea_id>/', views.detalle_tarea, name='detalle_tarea'),

    # Descargas protegidas
    path('<int:tarea_id>/enunciado/', views.descargar_enunciado, name='descargar_enunciado'),
    path('entrega/<int:entrega_id>/archivo/', views.descargar_entrega, name='descargar_entrega'),
]
