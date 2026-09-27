from django.apps import AppConfig


class MantenimientoConfig(AppConfig):
    """Las tareas de cuidado del sistema: respaldos y, más adelante, limpiezas.

    No tiene modelos ni pantallas: existe para que sus comandos de consola
    tengan dónde vivir, en vez de colgarlos de un app académico al que no
    pertenecen.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mantenimiento'
    verbose_name = 'Mantenimiento'
