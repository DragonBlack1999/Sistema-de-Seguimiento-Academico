"""
Django settings for config project.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# La clave con la que se firman las sesiones. No tiene valor por omisión a
# propósito: un sistema publicado con una clave conocida es un sistema abierto.
SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        'Falta SECRET_KEY. En el servidor se agrega en Variables; en el colegio, en el '
        'archivo .env. Para generar una nueva:\n'
        '    python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"'
    )
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ¿Está en internet o en una computadora del colegio?
# Railway define RAILWAY_PUBLIC_DOMAIN por su cuenta; esa es la señal. De ella
# cuelga todo lo que allá hace falta y aquí estorbaría (redirigir a HTTPS, por
# ejemplo, dejaría la laptop inutilizable).
DOMINIO_PUBLICO = config('RAILWAY_PUBLIC_DOMAIN', default='')
EN_LA_NUBE = bool(DOMINIO_PUBLICO) or config('EN_LA_NUBE', default=False, cast=bool)

if DOMINIO_PUBLICO:
    ALLOWED_HOSTS += [DOMINIO_PUBLICO, config('RAILWAY_PRIVATE_DOMAIN', default='')]
    # El vigilante de Railway golpea la aplicación con este nombre de host.
    ALLOWED_HOSTS.append('healthcheck.railway.app')
    ALLOWED_HOSTS = [h for h in ALLOWED_HOSTS if h]

# Desde qué direcciones se aceptan formularios. Sin esto, con HTTPS detrás de un
# intermediario, Django rechaza todos los envíos por CSRF.
CSRF_TRUSTED_ORIGINS = [f'https://{d}' for d in [DOMINIO_PUBLICO] if d]
CSRF_TRUSTED_ORIGINS += config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'crispy_forms',
    'crispy_bootstrap5',

    'apps.accounts',
    'apps.academico',
    'apps.calificaciones',
    'apps.asistencia',
    'apps.comunicaciones',
    'apps.tareas',
    'apps.notificaciones',
    'apps.noticias',
    'apps.padres',
    'apps.mensajeria',
    'apps.mantenimiento',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # En el servidor no hay nadie delante que sirva los archivos estáticos:
    # los sirve la propia aplicación, comprimidos y con caché larga.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.notificaciones.context_processors.notificaciones',
                'apps.mensajeria.context_processors.mensajeria',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# En el servidor, PostgreSQL llega en una sola variable (DATABASE_URL) que arma
# el propio Railway. En el colegio siguen los cinco datos sueltos del .env.
# Apuntando DATABASE_URL a la base de internet, «manage.py respaldar» corre
# desde la laptop y deja el respaldo aquí, fuera del servidor: es justo donde
# tiene que estar.
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    import dj_database_url

    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

AUTH_USER_MODEL = 'accounts.Usuario'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.CarnetBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:redirigir_dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'es-bo'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# En el servidor los archivos se guardan con su huella en el nombre, así el
# navegador puede guardarlos para siempre y aun así recibir los cambios.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage' if EN_LA_NUBE
        else 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

MEDIA_URL = 'media/'
# Lo que sube la gente (tareas, fotos) tiene que vivir en un disco que sobreviva
# a cada actualización del programa. En Railway eso es un «Volume» montado
# justamente aquí; si no, los archivos se borran en el siguiente despliegue.
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Número de faltas acumuladas en la gestión a partir del cual se genera
# automáticamente una citación por inasistencias.
UMBRAL_FALTAS_ALERTA = config('UMBRAL_FALTAS_ALERTA', default=3, cast=int)

# Cuántas tareas vencidas sin entregar convierten el aviso en urgente. Se repite
# cada vez que se completa otro grupo de este tamaño (3, 6, 9…).
UMBRAL_TAREAS_SIN_ENTREGAR = config('UMBRAL_TAREAS_SIN_ENTREGAR', default=3, cast=int)

# Hora límite de entrada al colegio. Quien es marcado después de esta hora
# queda como "Atraso" en vez de "Presente". Formato HH:MM.
HORA_ENTRADA = config('HORA_ENTRADA', default='13:50')


# Seguridad cuando está publicado en internet
# Nada de esto se enciende en la laptop: redirigir a HTTPS o exigir cookies
# seguras dejaría el sistema inaccesible en la computadora del colegio.
if EN_LA_NUBE:
    # El servidor termina el HTTPS y habla HTTP con la aplicación; sin esto
    # Django cree que la conexión es insegura y redirige en círculo.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Una hora de HSTS mientras se prueba. Al pasar a un dominio propio del
    # colegio conviene subirlo a un año; en un subdominio prestado no, porque
    # afectaría a todo lo demás que viva en ese dominio.
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=3600, cast=int)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_HTTPONLY = True
    # Un turno de clases dura menos que esto; obliga a entrar de nuevo al día
    # siguiente, que es lo razonable en computadoras compartidas.
    SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=8 * 60 * 60, cast=int)


# Registro
# En el servidor no hay consola donde mirar: todo va a la salida estándar, que
# es lo que Railway muestra y guarda.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'}},
    'handlers': {'consola': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['consola'], 'level': config('NIVEL_REGISTRO', default='INFO')},
    'loggers': {
        'django.request': {'handlers': ['consola'], 'level': 'ERROR', 'propagate': False},
    },
}


# Copias de respaldo
# Dónde se guardan. Conviene que no sea el mismo disco donde vive la base: si
# ese disco se daña, se pierden las dos cosas a la vez. RESPALDOS_COPIA es el
# segundo lugar —un USB, un disco externo, una carpeta sincronizada— y se llena
# solo cuando está conectado.
RESPALDOS_DIR = config('RESPALDOS_DIR', default=str(BASE_DIR / 'respaldos'))
RESPALDOS_COPIA = config('RESPALDOS_COPIA', default='')
# Se guardan todos los de los últimos días, y además el primero de cada mes
# durante estos meses: un dato borrado por error en marzo se suele descubrir en
# mayo, cuando ya no queda ninguna copia anterior al error.
RESPALDOS_DIAS = config('RESPALDOS_DIAS', default=14, cast=int)
RESPALDOS_MESES = config('RESPALDOS_MESES', default=12, cast=int)
# Cuenta con permiso para crear bases, solo para «probar_respaldo». Se puede
# dejar vacía y pasarla en el momento con --usuario y la variable PGPASSWORD,
# que es lo recomendable: una contraseña de administrador no necesita vivir
# escrita en ningún archivo.
RESPALDOS_CLAVE = config('RESPALDOS_CLAVE', default='')
# Carpeta de los programas de PostgreSQL (pg_dump, pg_restore, psql). Vacío =
# el sistema la busca solo; solo hace falta si PostgreSQL está en otro lugar.
PG_BIN = config('PG_BIN', default='')


# Avisos al celular (Web Push)
# Las llaves VAPID identifican a este servidor ante el servicio de push del
# navegador. Sin ellas el sistema funciona igual: la campanita sigue, y lo único
# que no ocurre es el aviso en el teléfono. Así la demo de la laptop, que corre
# sin internet, no necesita configurar nada.
VAPID_PUBLIC_KEY = config('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = config('VAPID_PRIVATE_KEY', default='')
# Quién responde por estos avisos: el servicio de push lo exige por si algo falla.
VAPID_CONTACTO = config('VAPID_CONTACTO', default='mailto:direccion@ejemplo.edu.bo')


# Correo electrónico
# (nombres en minúscula a propósito: Django 6.1 no permite definir las
# variables de settings EMAIL_HOST_USER/EMAIL_HOST_PASSWORD junto con MAILERS)
_email_host_user = config('EMAIL_HOST_USER', default='')
_email_host_password = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=_email_host_user or 'webmaster@localhost')

if _email_host_user and _email_host_password:
    # Credenciales configuradas: enviar correos reales por SMTP.
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'OPTIONS': {
                'host': config('EMAIL_HOST', default='smtp.gmail.com'),
                'port': config('EMAIL_PORT', default=587, cast=int),
                'username': _email_host_user,
                'password': _email_host_password,
                'use_tls': config('EMAIL_USE_TLS', default=True, cast=bool),
            },
        },
    }
else:
    # Sin credenciales: los correos se escriben en la consola del servidor.
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.console.EmailBackend',
        },
    }
