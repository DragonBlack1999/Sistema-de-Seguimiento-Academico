from django.urls import path

from . import views

app_name = 'asistencia'

urlpatterns = [
    path('puerta/', views.puerta, name='puerta'),
    path('puerta/marcar/<int:estudiante_id>/', views.marcar, name='marcar'),
    path('puerta/cerrar/', views.cerrar, name='cerrar'),
    path('capacitacion/', views.capacitacion, name='capacitacion'),
    path('capacitacion/excel/', views.capacitacion_excel, name='capacitacion_excel'),
    path('mi-asistencia/', views.mi_asistencia, name='mi_asistencia'),
]
