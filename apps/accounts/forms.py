from django.contrib.auth.forms import AuthenticationForm
from django import forms


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario (RUDE para estudiantes, CI para padres)',
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'}),
    )
    password = forms.CharField(
        label='Contraseña (Carnet de Identidad)',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
