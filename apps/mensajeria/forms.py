from django import forms

from .models import Mensaje


class MensajeForm(forms.ModelForm):
    class Meta:
        model = Mensaje
        fields = ['cuerpo', 'archivo']
        labels = {'cuerpo': '', 'archivo': 'Adjuntar imagen o PDF'}
        widgets = {
            'cuerpo': forms.Textarea(attrs={
                'rows': 2, 'class': 'form-control', 'placeholder': 'Escribe tu mensaje…',
            }),
        }

    def clean(self):
        datos = super().clean()
        if not (datos.get('cuerpo') or '').strip() and not datos.get('archivo'):
            raise forms.ValidationError('Escribe un mensaje o adjunta un archivo.')
        return datos
