from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.AccountsLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.redirigir_dashboard, name='redirigir_dashboard'),
    path('admin-dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('profesor-dashboard/', views.dashboard_profesor, name='dashboard_profesor'),
    path('estudiante-dashboard/', views.dashboard_estudiante, name='dashboard_estudiante'),
    path('regente-dashboard/', views.dashboard_regente, name='dashboard_regente'),
    path('tablero/', views.tablero_direccion, name='tablero'),

    # Contraseñas: cambiarla uno mismo, pedirla cuando se olvidó, y la bandeja
    # donde la secretaría atiende esos pedidos.
    path('clave/cambiar/', views.cambiar_clave, name='cambiar_clave'),
    path('clave/olvide/', views.olvide_clave, name='olvide_clave'),
    path('clave/solicitudes/', views.solicitudes_de_clave, name='solicitudes_de_clave'),
    path('clave/solicitudes/<int:solicitud_id>/atender/', views.atender_solicitud,
         name='atender_solicitud'),
]
