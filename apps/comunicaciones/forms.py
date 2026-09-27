from django import forms

from .models import Citacion


class CitacionForm(forms.ModelForm):
    class Meta:
        model = Citacion
        fields = ['estudiante', 'motivo', 'fecha', 'hora', 'lugar']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
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
