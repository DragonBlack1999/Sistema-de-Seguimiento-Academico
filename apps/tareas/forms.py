from django import forms
from django.utils import timezone

from apps.campos import campo_fecha

from .models import EntregaTarea, Tarea


class TareaForm(forms.ModelForm):
    # initial explícito: al declarar el campo se pierde el default del modelo.
    fecha_asignacion = campo_fecha('Fecha de asignación', initial=timezone.localdate)
    fecha_entrega = campo_fecha('Fecha límite de entrega')

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
