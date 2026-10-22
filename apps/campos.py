"""Campos de formulario que se repiten en todo el sistema.

Vive aquí, suelto en `apps/`, porque lo usan tareas, noticias, citaciones y las
fichas de estudiante: ponerlo dentro de cualquiera de esas aplicaciones haría
que las otras tres dependan de ella sin razón.

**El problema de la fecha, explicado una vez.** Con `LANGUAGE_CODE='es-bo'`,
Django dibuja las fechas como `dd/mm/aaaa`. Pero un `<input type="date">` del
navegador solo entiende `aaaa-mm-dd`: si recibe otra cosa, se muestra **vacío**
y al guardar borra la fecha que había. Por eso cada campo de fecha necesita
`format='%Y-%m-%d'` al dibujarse, y aceptar las dos formas al recibir —la ISO
que manda el navegador y la de toda la vida, por si alguien escribe a mano.

Esto ya estaba resuelto tres veces, una por formulario, con el mismo comentario
copiado. Ahora está en un solo sitio.
"""
from django import forms
from django.utils import timezone


class EntradaFecha(forms.DateInput):
    """Un calendario de verdad, no una caja de texto donde adivinar el formato."""

    input_type = 'date'

    def __init__(self, attrs=None, format=None):
        base = {'class': 'form-control'}
        base.update(attrs or {})
        super().__init__(attrs=base, format=format or '%Y-%m-%d')


def campo_fecha(label, *, initial=None, required=True, ayuda='', maximo=None, minimo=None):
    """Un campo de fecha con calendario, en el formato que el navegador entiende.

    `maximo` y `minimo` son fechas (o 'hoy'): el navegador no deja elegir fuera
    de ese rango, que es mejor que explicarlo en un mensaje de error después.
    """
    atributos = {}
    if maximo is not None:
        atributos['max'] = _como_texto(maximo)
    if minimo is not None:
        atributos['min'] = _como_texto(minimo)

    return forms.DateField(
        label=label,
        initial=initial,
        required=required,
        help_text=ayuda,
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=EntradaFecha(attrs=atributos),
    )


def campo_hora(label, *, initial=None, required=True, ayuda=''):
    """Lo mismo para una hora: el reloj del navegador en vez de escribir 14:30."""
    return forms.TimeField(
        label=label,
        initial=initial,
        required=required,
        help_text=ayuda,
        input_formats=['%H:%M', '%H:%M:%S'],
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
    )


def _como_texto(fecha):
    if fecha == 'hoy':
        fecha = timezone.localdate()
    return fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)
