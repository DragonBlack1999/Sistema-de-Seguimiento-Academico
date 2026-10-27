"""Los formularios de alta y edición que no existían en ninguna otra pantalla.

Los de estudiante y asignación ya estaban escritos y validados en
`apps.academico.forms`: se reutilizan tal cual. Aquí están los seis que
faltaban, cada uno con la validación que el modelo solo no alcanza a cubrir.

Una regla común: la contraseña NO se toca al editar. Se fija al crear y se
cambia desde «Pedidos de contraseña» o desde la pantalla de la propia persona.
Si un guardado cualquiera la reescribiera, corregir un teléfono le borraría a
alguien la contraseña que eligió.
"""
from django import forms
from django.db import transaction

from apps.academico.models import Curso, Gestion, Materia, Matricula
from apps.accounts.models import Usuario
from apps.accounts.services import username_tutor, validar_ci_tutor_disponible
from apps.campos import campo_fecha


def _caja(**extra):
    atributos = {'class': 'form-control'}
    atributos.update(extra)
    return forms.TextInput(attrs=atributos)


class _PersonaForm(forms.ModelForm):
    """Lo común de docentes, dirección y regencia: una cuenta con contraseña.

    El rol no se elige en el formulario base: lo fija cada subclase, porque de
    él depende en qué lista aparece la persona y qué puede hacer.
    """

    rol_fijo = None

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'ci', 'telefono', 'email']
        labels = {
            'username': 'Usuario de acceso',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'ci': 'Carnet de identidad',
            'telefono': 'Teléfono',
            'email': 'Correo',
        }
        help_texts = {
            'username': 'Sin espacios ni tildes. Es lo que escribe para entrar.',
            'ci': 'Al crear la cuenta, pasa a ser su contraseña.',
        }
        widgets = {
            'username': _caja(autocomplete='off'),
            'first_name': _caja(), 'last_name': _caja(),
            'ci': _caja(), 'telefono': _caja(),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        usuario = (self.cleaned_data['username'] or '').strip()
        choque = Usuario.objects.filter(username__iexact=usuario).exclude(pk=self.instance.pk)
        if choque.exists():
            raise forms.ValidationError(
                f'Ya hay alguien con el usuario «{usuario}»: {choque.first().get_full_name()}.'
            )
        return usuario

    def save(self, commit=True):
        persona = super().save(commit=False)
        if self.rol_fijo and not persona.rol:
            persona.rol = self.rol_fijo
        es_nueva = persona.pk is None
        if commit:
            persona.save()
            if es_nueva:
                # Entra con su carnet; si todavía no lo entregó, con su usuario.
                # Es lo que ya hacía el cargador del colegio.
                persona.set_password((persona.ci or '').strip() or persona.username)
                persona.save(update_fields=['password'])
        return persona


class DocenteForm(_PersonaForm):
    rol_fijo = Usuario.Rol.PROFESOR

    def save(self, commit=True):
        self.instance.rol = Usuario.Rol.PROFESOR
        return super().save(commit)


class PersonalForm(_PersonaForm):
    """Dirección, secretaría y regencia: aquí sí se elige la función."""

    rol = forms.ChoiceField(
        label='Función',
        choices=[(Usuario.Rol.ADMIN, 'Administrador'), (Usuario.Rol.REGENTE, 'Regente')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='El administrador gestiona los datos; el regente toma la asistencia.',
    )

    class Meta(_PersonaForm.Meta):
        fields = ['username', 'first_name', 'last_name', 'rol', 'ci', 'telefono', 'email']


class TutorForm(forms.ModelForm):
    """Un padre o tutor. Entra con su carnet en los dos campos.

    Su usuario no se escribe: se deriva del carnet (`TUT-<ci>`), igual que
    cuando la cuenta nace al dar de alta a un estudiante. Si se pudiera
    escribir a mano, dos caminos crearían dos cuentas para la misma persona.
    """

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'ci', 'telefono', 'email']
        labels = {
            'first_name': 'Nombres', 'last_name': 'Apellidos',
            'ci': 'Carnet de identidad', 'telefono': 'Teléfono', 'email': 'Correo',
        }
        help_texts = {'ci': 'Es su usuario y su contraseña para entrar.'}
        widgets = {
            'first_name': _caja(), 'last_name': _caja(),
            'ci': _caja(), 'telefono': _caja(),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_ci(self):
        ci = validar_ci_tutor_disponible(self.cleaned_data.get('ci', ''))
        if not ci:
            raise forms.ValidationError('El carnet es obligatorio: es con lo que entra.')
        choque = Usuario.objects.filter(
            rol=Usuario.Rol.PADRE, ci__iexact=ci).exclude(pk=self.instance.pk)
        if choque.exists():
            raise forms.ValidationError(
                f'Ya hay un tutor con ese carnet: {choque.first().get_full_name()}.'
            )
        return ci

    def save(self, commit=True):
        tutor = super().save(commit=False)
        tutor.rol = Usuario.Rol.PADRE
        tutor.username = username_tutor(tutor.ci)
        es_nuevo = tutor.pk is None
        if commit:
            tutor.save()
            if es_nuevo:
                tutor.set_password(tutor.ci)
                tutor.save(update_fields=['password'])
        return tutor


class GestionForm(forms.ModelForm):
    """Un año escolar. Solo uno puede estar en curso."""

    fecha_inicio = campo_fecha('Empieza el', required=False)
    fecha_fin = campo_fecha('Termina el', required=False)

    class Meta:
        model = Gestion
        fields = ['anio', 'activa', 'fecha_inicio', 'fecha_fin']
        labels = {'anio': 'Año', 'activa': 'Es la gestión en curso'}
        widgets = {
            'anio': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get('fecha_inicio'), datos.get('fecha_fin')
        if inicio and fin and fin < inicio:
            self.add_error('fecha_fin', 'No puede terminar antes de empezar.')
        return datos

    @transaction.atomic
    def save(self, commit=True):
        gestion = super().save(commit=False)
        if commit:
            # Hay una restricción de una sola gestión activa: si no se apaga la
            # anterior primero, la base rechaza el guardado con un error que no
            # le dice nada a nadie.
            if gestion.activa:
                Gestion.objects.filter(activa=True).exclude(pk=gestion.pk).update(activa=False)
            gestion.save()
        return gestion


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['gestion', 'nivel', 'grado', 'paralelo']
        labels = {'gestion': 'Año escolar', 'nivel': 'Nivel', 'grado': 'Grado',
                  'paralelo': 'Paralelo'}
        help_texts = {'grado': 'Solo el número: 1 para primero.',
                      'paralelo': 'Una letra: A, B, C…'}
        widgets = {
            'gestion': forms.Select(attrs={'class': 'form-select'}),
            'nivel': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'paralelo': _caja(maxlength=2),
        }

    def clean_paralelo(self):
        return (self.cleaned_data['paralelo'] or '').strip().upper()

    def clean(self):
        datos = super().clean()
        gestion, nivel = datos.get('gestion'), datos.get('nivel')
        grado, paralelo = datos.get('grado'), datos.get('paralelo')
        if gestion and nivel and grado and paralelo:
            choque = Curso.objects.filter(
                gestion=gestion, nivel=nivel, grado=grado, paralelo=paralelo,
            ).exclude(pk=self.instance.pk)
            if choque.exists():
                raise forms.ValidationError(f'{choque.first()} ya existe.')
        return datos


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ['nombre']
        labels = {'nombre': 'Nombre de la materia'}
        widgets = {'nombre': _caja()}

    def clean_nombre(self):
        nombre = (self.cleaned_data['nombre'] or '').strip()
        choque = Materia.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if choque.exists():
            raise forms.ValidationError(f'«{choque.first().nombre}» ya está en la lista.')
        return nombre


class MatriculaForm(forms.ModelForm):
    """La inscripción de un estudiante en un curso.

    Una sola vigente por año: al guardar una nueva, la que el estudiante
    tuviera en esa misma gestión se da de baja. Es lo que pasa de verdad cuando
    alguien cambia de paralelo a mitad de año.
    """

    class Meta:
        model = Matricula
        fields = ['estudiante', 'curso', 'activa']
        labels = {'estudiante': 'Estudiante', 'curso': 'Curso', 'activa': 'Vigente'}
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = (
            self.fields['estudiante'].queryset.select_related('usuario')
            .order_by('usuario__last_name', 'usuario__first_name')
        )
        self.fields['curso'].queryset = (
            Curso.objects.select_related('gestion')
            .order_by('-gestion__anio', 'nivel', 'grado', 'paralelo')
        )

    def _post_clean(self):
        # El modelo prohíbe dos matrículas vigentes en el mismo año, y este
        # formulario existe justamente para mover a alguien de curso: al
        # guardar da de baja la anterior. Se lo avisa antes de validar, o se
        # rechazaría a sí mismo con «ya tiene una matrícula vigente».
        self.instance.reemplaza_a_la_vigente = True
        super()._post_clean()

    @transaction.atomic
    def save(self, commit=True):
        matricula = super().save(commit=False)
        if commit:
            if matricula.activa:
                Matricula.objects.filter(
                    estudiante=matricula.estudiante,
                    curso__gestion=matricula.curso.gestion,
                ).exclude(pk=matricula.pk).update(activa=False)
            matricula.save()
        return matricula
