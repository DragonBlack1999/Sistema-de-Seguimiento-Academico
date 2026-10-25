from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
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


class CambiarClaveForm(PasswordChangeForm):
    """La de Django, en el idioma del colegio.

    Se reutiliza entera porque trae lo que importa: pide la contraseña actual
    (si no, cualquiera que encuentre una sesión abierta se queda con la cuenta)
    y pasa la nueva por los validadores de settings.
    """

    old_password = forms.CharField(
        label='Tu contraseña de ahora',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autofocus': True,
                                          'autocomplete': 'current-password'}),
    )
    new_password1 = forms.CharField(
        label='La nueva',
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='La nueva otra vez',
        help_text='Para estar seguros de que no se escribió mal.',
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'autocomplete': 'new-password'}),
    )


class OlvideClaveForm(forms.Form):
    """Un solo campo: lo mismo con lo que la persona entra al sistema."""

    escrito = forms.CharField(
        label='Tu usuario, tu RUDE o tu carnet',
        max_length=150,
        help_text='Lo mismo que escribes arriba de todo cuando entras.',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg',
                                      'autofocus': True}),
    )


class CarnetForm(forms.Form):
    """El carnet con el que la secretaría restablece una contraseña.

    Solo aparece cuando el colegio todavía no tiene el carnet de esa persona
    —hoy, los 33 docentes y la dirección—. Al atender el pedido queda guardado.
    """

    ci = forms.CharField(
        label='Carnet de identidad',
        max_length=20,
        help_text='Pasa a ser su contraseña. Solo los números, sin el complemento.',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def clean_ci(self):
        return self.cleaned_data['ci'].strip()
