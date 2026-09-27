import io
from pathlib import Path

from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.calificaciones.models import (
    MAXIMO, MAXIMO_AUTOEVALUACION, MAXIMO_EXTRACURRICULAR, Dimension, Trimestre,
)
from apps.calificaciones.services import gestion_actual, notas_de_gestion

COLEGIO = 'Unidad Educativa «Eduardo Abaroa Tarde»'
NIVEL = 'Nivel Secundario'
# La versión de 260 px: dibujada a 62 puntos da ~300 ppp al imprimir, y evita
# meter medio mega de imagen en cada boletín.
ESCUDO = Path(settings.BASE_DIR) / 'static' / 'img' / 'escudo-impreso.png'

# Las columnas del detalle, con la x donde empieza cada una.
COLUMNAS_DETALLE = [
    ('Materia', 50),
    (f'Ser ({MAXIMO[Dimension.SER]:.0f})', 250),
    (f'Saber ({MAXIMO[Dimension.SABER]:.0f})', 310),
    (f'Hacer ({MAXIMO[Dimension.HACER]:.0f})', 375),
    (f'Autoev. ({MAXIMO_AUTOEVALUACION:.0f})', 440),
    (f'Extra ({MAXIMO_EXTRACURRICULAR:.0f})', 505),
    ('Nota', 555),
]


def _membrete(p, alto):
    """Escudo y nombre del colegio: el boletín sale del colegio, no del programa."""
    izquierda = 50
    if ESCUDO.exists():
        # mask='auto' respeta la transparencia del escudo sobre el papel blanco.
        p.drawImage(ImageReader(str(ESCUDO)), 50, alto - 95, width=62, height=72,
                    mask='auto', preserveAspectRatio=True)
        izquierda = 125

    p.setFont('Helvetica-Bold', 13)
    p.drawString(izquierda, alto - 45, COLEGIO)
    p.setFont('Helvetica', 9)
    p.drawString(izquierda, alto - 59, NIVEL)
    p.setFont('Helvetica-Bold', 15)
    p.drawString(izquierda, alto - 82, 'Boletín de Calificaciones')
    p.line(50, alto - 103, 562, alto - 103)
    return izquierda


def _texto(valor):
    return '-' if valor is None else f'{valor:.2f}'.rstrip('0').rstrip('.')


def _pagina_del_trimestre(p, alto, trimestre, notas):
    """Una página por trimestre con el desglose que pide la planilla del colegio."""
    p.showPage()
    _membrete(p, alto)

    p.setFont('Helvetica-Bold', 12)
    p.drawString(50, alto - 125, f'Detalle del {Trimestre(trimestre).label.lower()}')
    p.setFont('Helvetica', 8.5)
    p.drawString(50, alto - 139, 'La nota del trimestre es la suma de las cuatro partes, más lo '
                                 'extracurricular, sin pasar de 100.')

    y = alto - 165
    p.setFont('Helvetica-Bold', 9)
    for etiqueta, x in COLUMNAS_DETALLE:
        p.drawString(x, y, etiqueta)
    y -= 12
    p.line(50, y, 585, y)
    y -= 14

    p.setFont('Helvetica', 9)
    for nota in sorted(notas, key=lambda n: n.asignacion.materia.nombre):
        if y < 60:
            p.showPage()
            y = alto - 50
            p.setFont('Helvetica', 9)
        valores = [
            nota.asignacion.materia.nombre[:34],
            _texto(nota.ser), _texto(nota.saber), _texto(nota.hacer),
            _texto(nota.autoevaluacion), _texto(nota.extracurricular),
        ]
        for (_etiqueta, x), valor in zip(COLUMNAS_DETALLE, valores):
            p.drawString(x, y, str(valor))
        p.setFont('Helvetica-Bold', 9)
        p.drawString(COLUMNAS_DETALLE[-1][1], y, _texto(nota.nota))
        p.setFont('Helvetica', 9)
        y -= 16


def generar_boletin_pdf(estudiante):
    """Genera el PDF del boletín de notas de un estudiante y devuelve los bytes."""
    gestion = gestion_actual(estudiante)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    ancho, alto = letter

    _membrete(p, alto)

    p.setFont('Helvetica', 11)
    p.drawString(50, alto - 125, f'Estudiante: {estudiante.usuario.get_full_name()}')
    p.drawString(50, alto - 140, f'RUDE: {estudiante.rude}')
    p.drawString(50, alto - 155, f'Curso: {estudiante.curso_actual}')
    p.drawString(50, alto - 170, f'Gestión: {gestion.anio if gestion else "sin definir"}')

    y = alto - 205
    p.setFont('Helvetica-Bold', 11)
    p.drawString(50, y, 'Materia')
    p.drawString(280, y, 'Trimestre 1')
    p.drawString(370, y, 'Trimestre 2')
    p.drawString(460, y, 'Trimestre 3')
    y -= 15
    p.line(50, y, 545, y)
    y -= 15

    notas = list(notas_de_gestion(estudiante, gestion).select_related('asignacion__materia'))
    por_materia = {}
    por_trimestre = {}
    for nota in notas:
        por_materia.setdefault(nota.asignacion.materia.nombre, {})[nota.trimestre] = nota.nota
        por_trimestre.setdefault(nota.trimestre, []).append(nota)

    p.setFont('Helvetica', 10)
    for materia, trimestres in sorted(por_materia.items()):
        if y < 60:
            p.showPage()
            y = alto - 50
        p.drawString(50, y, materia)
        p.drawString(280, y, str(trimestres.get(1, '-')))
        p.drawString(370, y, str(trimestres.get(2, '-')))
        p.drawString(460, y, str(trimestres.get(3, '-')))
        y -= 18

    # Después del resumen, una página por trimestre con el desglose.
    for trimestre in sorted(por_trimestre):
        _pagina_del_trimestre(p, alto, trimestre, por_trimestre[trimestre])

    p.showPage()
    p.save()
    return buffer.getvalue()
