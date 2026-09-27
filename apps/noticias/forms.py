from django import forms
from django.db.models import Q

from apps.academico.models import Gestion

from .models import Noticia


class NoticiaForm(forms.ModelForm):
    # Formato ISO forzado: con LANGUAGE_CODE='es-bo' el widget renderiza
    # dd/mm/aaaa y el navegador vacía el campo al editar.
    fecha_evento = forms.DateField(
        label='Fecha de la actividad', required=False,
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = Noticia
        fields = ['titulo', 'cuerpo', 'tipo', 'curso', 'fecha_evento',
                  'imagen', 'archivo', 'publicada', 'fijada']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'cuerpo': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'publicada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fijada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'curso': 'Curso destinatario'}
        help_texts = {
            'curso': 'Con un curso elegido, la noticia llega a ese curso, '
                     'a sus familias y a sus profesores.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields['curso']

        # Dejar el curso vacío ya significaba "para todos", pero la lista lo
        # mostraba como una fila de guiones: ahora es una opción con nombre.
        campo.empty_label = 'Todo el colegio'

        # Solo cursos del año en curso: publicar a un curso de una gestión
        # cerrada no le llega a nadie, porque sus matrículas ya no están activas.
        gestion = Gestion.objects.filter(activa=True).order_by('-anio').first()
        if gestion is not None:
            vigentes = Q(gestion=gestion)
            # Al editar una noticia antigua, su curso tiene que seguir en la
            # lista o el formulario no podría volver a guardarse.
            if self.instance.pk and self.instance.curso_id:
                vigentes |= Q(pk=self.instance.curso_id)
            campo.queryset = campo.queryset.filter(vigentes)

    def clean(self):
        datos = super().clean()
        if datos.get('tipo') == Noticia.Tipo.ACTIVIDAD and not datos.get('fecha_evento'):
            self.add_error('fecha_evento', 'Una actividad necesita su fecha.')
        return datos
