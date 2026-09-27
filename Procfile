# Railway puede tomar el arranque de aquí o de railway.json, según cómo esté
# configurado el servicio. Los dos dicen lo mismo a propósito: preparar los
# archivos estáticos, aplicar las migraciones y recién entonces levantar el
# servidor. Si solo arranca gunicorn, el sistema sube sin estáticos y sin
# tablas, que es peor que no subir.
web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile -
