from django.urls import path

from . import views

app_name = 'academico'

urlpatterns = [
    path('mi-horario/', views.mi_horario, name='mi_horario'),
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    path('horarios/constructor/', views.horario_constructor, name='horario_constructor'),
    path('horarios/periodos/agregar/', views.agregar_periodo, name='agregar_periodo'),
    path('horarios/periodos/<int:periodo_id>/eliminar/', views.eliminar_periodo, name='eliminar_periodo'),
    path('horarios/periodos/copiar/', views.copiar_periodos, name='copiar_periodos'),
    path('horarios/materias/agregar/', views.agregar_materia_curso, name='agregar_materia_curso'),
    path('horarios/colocar/', views.colocar_horario, name='colocar_horario'),
    path('horarios/<int:horario_id>/quitar/', views.quitar_horario, name='quitar_horario'),
]
