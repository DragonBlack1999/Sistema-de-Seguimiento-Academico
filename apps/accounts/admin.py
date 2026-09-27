from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'rol', 'ci', 'is_active')
    list_filter = ('rol', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'ci')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del colegio', {'fields': ('rol', 'ci', 'telefono', 'materia')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos del colegio', {'fields': ('rol', 'ci', 'telefono', 'materia')}),
    )
