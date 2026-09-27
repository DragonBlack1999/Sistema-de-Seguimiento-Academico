from django import forms
from django.utils import timezone

from .models import EntregaTarea, Tarea


def _campo_fecha(label, initial=None):
    """Fuerza el formato ISO en ambos sentidos.

    Con LANGUAGE_CODE='es-bo', DateInput renderiza dd/mm/aaaa y el navegador deja el
    <input type="date"> vacío, borrando la fecha al guardar. Es el mismo problema de
    localización que ya obligó a usar |unlocalize en los inputs numéricos.
    """
    return forms.DateField(
        label=label,
        initial=initial,
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )


class TareaForm(forms.ModelForm):
    # initial explícito: al declarar el campo se pierde el default del modelo.
    fecha_asignacion = _campo_fecha('Fecha de asignación', initial=timezone.localdate)
    fecha_entrega = _campo_fecha('Fecha límite de entrega')

    class Meta:
        model = Tarea
        # Sin peso: cada tarea es una actividad de "hacer" y todas valen lo mismo.
        fields = [
            'trimestre', 'titulo', 'descripcion', 'fecha_asignacion', 'fecha_entrega',
            'permite_archivo', 'permite_atraso', 'archivo_adjunto',
        ]
        widgets = {
            'trimestre': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'permite_archivo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'permite_atraso': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'archivo_adjunto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class EntregaEstudianteForm(forms.ModelForm):
    class Meta:
        model = EntregaTarea
        fields = ['archivo', 'comentario_estudiante']
        widgets = {
            # Sin required: el estudiante puede entregar sin subir nada (marcar como completada).
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'comentario_estudiante': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
