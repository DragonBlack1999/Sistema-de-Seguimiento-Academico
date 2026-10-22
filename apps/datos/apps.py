from django.apps import AppConfig


class DatosConfig(AppConfig):
    """La pantalla de gestión de datos: el trabajo diario de la secretaría.

    No tiene modelos propios. Es una vista distinta —en el idioma del colegio y
    con los permisos del colegio— sobre los modelos que ya existen.

    Se llama «datos» y no «gestión» a propósito: `Gestion` es el año escolar, y
    tener las dos palabras significando cosas distintas en el mismo proyecto se
    presta a confusión en cada import.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.datos'
    verbose_name = 'Gestión de datos'
