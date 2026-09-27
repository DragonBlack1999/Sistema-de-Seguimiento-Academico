from django.urls import path

from . import views

app_name = 'noticias'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/imagen/', views.imagen, name='imagen'),
    path('<int:pk>/adjunto/', views.adjunto, name='adjunto'),
]
