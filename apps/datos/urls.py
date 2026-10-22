from django.urls import path

from . import views

app_name = 'datos'

urlpatterns = [
    path('', views.indice, name='indice'),
    path('<slug:clave>/', views.lista, name='lista'),
]
