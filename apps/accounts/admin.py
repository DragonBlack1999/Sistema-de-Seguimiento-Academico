from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import IntentoFallido, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Las cuentas de todo el colegio.

    Los estudiantes y los tutores casi nunca se tocan desde aquí: se crean
    solos al cargar o editar un estudiante, y entran con su RUDE o su carnet,
    sin contraseña que administrar. Esta pantalla es sobre todo para docentes,
    regencia y dirección.
    """

    list_display = ('username', 'nombre_completo', 'rol', 'ci', 'telefono', 'is_active')
    list_filter = ('rol', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'ci')
    ordering = ('rol', 'last_name', 'first_name')
    list_per_page = 50

    # El campo `materia` se quitó del modelo al normalizar: qué dicta un
    # profesor sale de sus asignaciones, porque trece de los 33 dan dos o tres.
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Nombre', {'fields': ('first_name', 'last_name', 'email')}),
        ('Datos del colegio', {
            'fields': ('rol', 'ci', 'telefono'),
            'description': 'El estudiante entra con su RUDE y su carnet; '
                           'el padre o tutor, con su carnet en los dos campos.',
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
            'description': 'Solo dirección y secretaría necesitan «Es staff» para entrar aquí.',
        }),
        ('Fechas', {'fields': ('last_login', 'date_joined'), 'classes': ('collapse',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Nombre', {'classes': ('wide',), 'fields': ('first_name', 'last_name')}),
        ('Datos del colegio', {'classes': ('wide',), 'fields': ('rol', 'ci', 'telefono')}),
    )
    filter_horizontal = ('groups', 'user_permissions')

    @admin.display(description='Nombre', ordering='last_name')
    def nombre_completo(self, obj):
        return obj.get_full_name() or '—'


@admin.register(IntentoFallido)
class IntentoFallidoAdmin(admin.ModelAdmin):
    """Para ver quién está probando claves, y desbloquear a alguien borrando sus fallos."""

    list_display = ('usuario', 'ip', 'fecha')
    search_fields = ('usuario', 'ip')
    date_hierarchy = 'fecha'
    readonly_fields = ('usuario', 'ip', 'fecha')

    def has_add_permission(self, request):
        return False
