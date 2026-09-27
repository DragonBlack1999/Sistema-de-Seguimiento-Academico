from django import forms

from apps.accounts.models import Usuario
from apps.accounts.services import (
    desactivar_tutor_huerfano, obtener_o_crear_tutor, validar_ci_tutor_disponible,
)

from .models import AsignacionDocente, Curso, Estudiante, Materia, Matricula


class EstudianteForm(forms.ModelForm):
    """Alta y edicion de un estudiante.

    Tres bloques de datos que ya NO son columnas de `Estudiante` y por eso se
    declaran a mano aqui:
      - los del propio alumno (nombres, CI, correo) viven en su `Usuario`;
      - el curso se materializa como una `Matricula`;
      - los del tutor viven en el `Usuario` del tutor.
    El formulario los sigue pidiendo juntos, que es lo comodo para secretaria.
    """

    nombres = forms.CharField(label='Nombres', max_length=150)
    apellidos = forms.CharField(label='Apellidos', max_length=150)
    ci_estudiante = forms.CharField(
        label='CI del estudiante',
        help_text='Se usara como contrasena de acceso del estudiante (el usuario de acceso es el RUDE).',
    )
    email_estudiante = forms.EmailField(label='Correo del estudiante', required=False)

    curso = forms.ModelChoiceField(
        label='Curso', queryset=Curso.objects.none(), required=False,
        help_text='Al guardar se crea o actualiza la matricula del estudiante en ese curso.',
    )

    nombre_tutor = forms.CharField(label='Nombre del padre/tutor', max_length=150, required=False)
    ci_tutor = forms.CharField(label='CI del padre/tutor', max_length=20, required=False)
    telefono_tutor = forms.CharField(label='Telefono del padre/tutor', max_length=20, required=False)
    email_tutor = forms.EmailField(label='Correo del padre/tutor', required=False)

    class Meta:
        model = Estudiante
        fields = [
            'rude', 'fecha_nacimiento', 'genero', 'nacionalidad', 'departamento',
            'direccion', 'celular', 'grupo_sanguineo', 'foto_perfil',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.select_related('gestion').order_by(
            '-gestion__anio', 'nivel', 'grado', 'paralelo',
        )

        usuario = getattr(self.instance, 'usuario', None)
        if usuario is not None:
            self.fields['nombres'].initial = usuario.first_name
            self.fields['apellidos'].initial = usuario.last_name
            self.fields['ci_estudiante'].initial = usuario.ci
            self.fields['email_estudiante'].initial = usuario.email

        if self.instance.pk:
            self.fields['curso'].initial = self.instance.curso_actual
            tutor = self.instance.tutor
            if tutor is not None:
                self.fields['nombre_tutor'].initial = tutor.get_full_name()
                self.fields['ci_tutor'].initial = tutor.ci
                self.fields['telefono_tutor'].initial = tutor.telefono
                self.fields['email_tutor'].initial = tutor.email

    def clean_rude(self):
        rude = self.cleaned_data['rude']
        usuario_actual = getattr(self.instance, 'usuario', None)
        qs = Usuario.objects.filter(username__iexact=rude)
        if usuario_actual is not None:
            qs = qs.exclude(pk=usuario_actual.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con este RUDE.')
        # Simetrico de clean_ci_tutor: el padre entra escribiendo su CI, asi que
        # un RUDE no puede coincidir con el CI de un tutor ya registrado.
        if Usuario.objects.filter(rol=Usuario.Rol.PADRE, ci__iexact=rude).exists():
            raise forms.ValidationError('Este RUDE coincide con el CI de un padre/tutor ya registrado.')
        return rude

    def clean_ci_tutor(self):
        return validar_ci_tutor_disponible(self.cleaned_data.get('ci_tutor', ''))

    def save(self, commit=True):
        estudiante = super().save(commit=False)
        usuario = getattr(estudiante, 'usuario', None) or Usuario(rol=Usuario.Rol.ESTUDIANTE)

        usuario.username = self.cleaned_data['rude']
        usuario.first_name = self.cleaned_data['nombres']
        usuario.last_name = self.cleaned_data['apellidos']
        usuario.email = self.cleaned_data['email_estudiante']
        usuario.ci = self.cleaned_data['ci_estudiante']
        usuario.rol = Usuario.Rol.ESTUDIANTE
        usuario.set_password(self.cleaned_data['ci_estudiante'])
        usuario.save()

        estudiante.usuario = usuario

        # Cuenta de acceso del padre/tutor: se crea o se reutiliza segun el CI.
        tutor_anterior_id = estudiante.tutor_id
        estudiante.tutor = obtener_o_crear_tutor(
            ci=self.cleaned_data.get('ci_tutor', ''),
            nombre=self.cleaned_data.get('nombre_tutor', ''),
            email=self.cleaned_data.get('email_tutor', ''),
            telefono=self.cleaned_data.get('telefono_tutor', ''),
        )
        if commit:
            estudiante.save()
            self._sincronizar_matricula(estudiante, self.cleaned_data.get('curso'))
        if tutor_anterior_id and tutor_anterior_id != estudiante.tutor_id:
            desactivar_tutor_huerfano(tutor_anterior_id, excluir_estudiante_id=estudiante.pk)
        return estudiante

    @staticmethod
    def _sincronizar_matricula(estudiante, curso):
        """El curso elegido se guarda como matricula, que es donde vive de verdad."""
        if curso is None:
            return
        # Una sola matricula por ano: si ya habia otra en esa gestion, se desactiva.
        Matricula.objects.filter(
            estudiante=estudiante, curso__gestion=curso.gestion,
        ).exclude(curso=curso).update(activa=False)
        Matricula.objects.update_or_create(
            estudiante=estudiante, curso=curso, defaults={'activa': True},
        )


class AsignacionDocenteForm(forms.ModelForm):
    """Quién dicta qué materia en qué curso.

    La materia se elige: un profesor puede dictar varias. Antes se deducía de
    `Usuario.materia`, que solo alcanza para uno de sus cursos.
    """

    class Meta:
        model = AsignacionDocente
        # La gestion no se elige: la determina el curso.
        fields = ['profesor', 'curso', 'materia']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profesor'].queryset = Usuario.objects.filter(
            rol=Usuario.Rol.PROFESOR
        ).order_by('last_name', 'first_name')
        self.fields['materia'].queryset = Materia.objects.order_by('nombre')

    def clean(self):
        cleaned_data = super().clean()
        curso = cleaned_data.get('curso')
        materia = cleaned_data.get('materia')

        # Una materia, un profesor por curso. La restriccion existe en la base,
        # pero aqui el aviso dice quien la tiene ya.
        if curso is not None and materia is not None:
            ya_existe = AsignacionDocente.objects.filter(
                curso=curso, materia=materia,
            ).exclude(pk=self.instance.pk)
            if ya_existe.exists():
                a_cargo = ya_existe.first().profesor
                raise forms.ValidationError(
                    f'"{materia}" en {curso} ya está a cargo de '
                    f'{a_cargo.get_full_name() or a_cargo.username}.'
                )
        return cleaned_data


class PerfilEstudianteForm(forms.ModelForm):
    """Formulario para que el propio estudiante edite solo sus datos de contacto."""

    correo = forms.EmailField(label='Correo electrónico', required=False)

    class Meta:
        model = Estudiante
        fields = ['direccion', 'celular', 'grupo_sanguineo', 'foto_perfil']
        widgets = {
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'celular': forms.TextInput(attrs={'class': 'form-control'}),
            'grupo_sanguineo': forms.Select(attrs={'class': 'form-select'}),
            'foto_perfil': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['correo'].widget.attrs.update({'class': 'form-control'})
        if self.instance and self.instance.pk:
            self.fields['correo'].initial = self.instance.usuario.email

    def save(self, commit=True):
        estudiante = super().save(commit=False)
        estudiante.usuario.email = self.cleaned_data['correo']
        if commit:
            estudiante.usuario.save()
            estudiante.save()
        return estudiante
