from django import forms
from django.utils import timezone

from apps.campos import campo_fecha, campo_hora

from .models import Citacion


class CitacionForm(forms.ModelForm):
    # Una citación es para adelante: el calendario no ofrece días pasados.
    fecha = campo_fecha('Fecha de la citación', minimo='hoy')
    hora = campo_hora('Hora', required=False, ayuda='Si la dejas vacía, se cita sin hora fija.')

    class Meta:
        model = Citacion
        fields = ['estudiante', 'motivo', 'fecha', 'hora', 'lugar']
        widgets = {
            'motivo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'lugar': forms.TextInput(attrs={'class': 'form-control'}),
            # La pantalla lo reemplaza por un buscador con sugerencias; aquí
            # solo viaja el id del estudiante elegido.
            'estudiante': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El campo está oculto: "Este campo es obligatorio" no le dice nada a
        # quien ve un buscador con un nombre escrito dentro.
        self.fields['estudiante'].error_messages.update({
            'required': 'Escribe el nombre y elige al estudiante de la lista de sugerencias.',
            'invalid_choice': 'Ese estudiante ya no existe. Vuelve a buscarlo.',
        })
