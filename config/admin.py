"""Cómo se presenta el panel de administración.

El admin de Django es una herramienta potente pero muda: dice «Django
administration» y ordena los modelos por orden alfabético del nombre en inglés
de cada aplicación. Quien lo usa aquí es la secretaría del colegio, no un
programador, así que vale la pena ponerle el nombre del colegio, el idioma de
la casa y un orden que se parezca a cómo se piensa el trabajo: primero las
personas y los cursos, después lo que ocurre cada día, y al final lo técnico.

Se importa desde `config/urls.py`, que es lo que garantiza que corra una vez.
"""
from django.contrib import admin

from apps.accounts.forms import AdminLoginForm

admin.site.site_header = 'U.E. «Eduardo Abaroa Tarde» · Administración'
admin.site.site_title = 'Administración del colegio'
admin.site.index_title = 'Datos del colegio'
# El enlace del título lleva al sistema, no al admin de nuevo.
admin.site.site_url = '/'
# El mismo límite de intentos fallidos que el inicio de sesión del sistema.
admin.site.login_form = AdminLoginForm

# En qué orden se muestran los grupos, y con qué nombre. Lo que no esté aquí
# va después, en orden alfabético: así, agregar una aplicación nueva no rompe
# esta pantalla, solo la deja un poco desordenada hasta que se la nombre.
ORDEN = {
    'academico': (1, 'El colegio: cursos, materias y estudiantes'),
    'accounts': (2, 'Cuentas de acceso'),
    'calificaciones': (3, 'Calificaciones'),
    'asistencia': (4, 'Asistencia'),
    'tareas': (5, 'Tareas'),
    'comunicaciones': (6, 'Citaciones'),
    'noticias': (7, 'Noticias'),
    'notificaciones': (8, 'Avisos'),
    'mensajeria': (9, 'Mensajes'),
    'auth': (98, 'Permisos'),
}

_indice_original = admin.site.get_app_list


def _indice_ordenado(request, app_label=None):
    """Los mismos grupos, en un orden que tiene sentido para el colegio."""
    aplicaciones = _indice_original(request, app_label)
    for aplicacion in aplicaciones:
        posicion, nombre = ORDEN.get(aplicacion['app_label'], (50, None))
        aplicacion['orden_colegio'] = posicion
        if nombre:
            aplicacion['name'] = nombre
    return sorted(aplicaciones, key=lambda a: (a['orden_colegio'], a['name']))


admin.site.get_app_list = _indice_ordenado
