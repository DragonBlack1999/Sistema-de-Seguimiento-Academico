from django.urls import path

from . import views

app_name = 'calificaciones'

urlpatterns = [
    path('registrar/<int:asignacion_id>/<int:trimestre>/', views.registrar_notas, name='registrar_notas'),
    path('registrar/<int:asignacion_id>/<int:trimestre>/planilla.xlsx', views.planilla_excel, name='planilla_excel'),
    path('mis-notas/', views.mis_notas, name='mis_notas'),
    path('mi-autoevaluacion/<int:trimestre>/', views.mi_autoevaluacion, name='mi_autoevaluacion'),
    path('historial/', views.historial_academico, name='historial_academico'),
]
