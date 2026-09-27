from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.mantenimiento.views import salud

urlpatterns = [
    # El service worker se sirve desde la raíz porque solo manda sobre las
    # páginas que cuelgan de su carpeta: desde /static/ no cubriría nada.
    path('sw.js', TemplateView.as_view(
        template_name='pwa/sw.js', content_type='application/javascript',
    ), name='service_worker'),
    path('manifest.webmanifest', TemplateView.as_view(
        template_name='pwa/manifest.webmanifest', content_type='application/manifest+json',
    ), name='manifest'),

    # El servidor pregunta por aquí si la aplicación sigue en pie.
    path('salud/', salud, name='salud'),

    # Se lee sin haber entrado: un padre tiene que poder saber qué se guarda
    # de su hijo antes de tener cuenta.
    path('privacidad/', TemplateView.as_view(
        template_name='legal/privacidad.html',
    ), name='privacidad'),

    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('academico/', include('apps.academico.urls')),
    path('calificaciones/', include('apps.calificaciones.urls')),
    path('asistencia/', include('apps.asistencia.urls')),
    path('comunicaciones/', include('apps.comunicaciones.urls')),
    path('tareas/', include('apps.tareas.urls')),
    path('noticias/', include('apps.noticias.urls')),
    path('notificaciones/', include('apps.notificaciones.urls')),
    path('padres/', include('apps.padres.urls')),
    path('mensajeria/', include('apps.mensajeria.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
