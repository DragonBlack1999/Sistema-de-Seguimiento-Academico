"""Excel de asistencia del curso, con una columna por fecha registrada."""
import re
from collections import Counter

from django.utils import formats, timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Asistencia


FILA_TITULOS = 4
COLORES = {
    Asistencia.Estado.PRESENTE: 'D6F0E4',
    Asistencia.Estado.FALTA: 'F8D8D4',
    Asistencia.Estado.ATRASO: 'FCE9CE',
    Asistencia.Estado.LICENCIA: 'DEE5F7',
}
CENTRADO = Alignment(horizontal='center', vertical='center')
NEGRITA = Font(bold=True)


def nombre_de_hoja(texto):
    """Excel no admite \\ / * ? : [ ] en el nombre de la hoja, y corta en 31.

    También la usan las planillas de notas (comunicaciones/planilla_notas.py).
    """
    return re.sub(r'[\\/*?:\[\]]', ' ', texto)[:31] or 'Asistencia'


def planilla_por_fechas(curso, matriculas, registros, *, capacitacion, periodo=None):
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Asistencia del curso' if capacitacion else 'Control de entrada'
    hoja['A1'] = f'{hoja.title} · {curso}'
    hoja['A1'].font = Font(bold=True, size=14)
    rotulo = formats.date_format(periodo, 'F Y').capitalize() if periodo else f'Gestión {curso.gestion.anio}'
    hoja['A2'] = f'{rotulo} · Generado el {formats.date_format(timezone.localdate(), "d/m/Y")}'
    hoja['A2'].font = Font(italic=True, color='666666')

    por_dia = {(r.estudiante_id, r.fecha): r for r in registros}
    fechas = sorted({fecha for _, fecha in por_dia})
    estados = [Asistencia.Estado.PRESENTE, Asistencia.Estado.FALTA]
    if not capacitacion:
        estados += [Asistencia.Estado.ATRASO, Asistencia.Estado.LICENCIA]
    totales = ['Presentes', 'Faltas'] if capacitacion else ['Presentes', 'Faltas', 'Atrasos', 'Licencias']
    titulos = ['Estudiante', 'RUDE', *fechas, *totales, 'Asistencia']
    hoja.column_dimensions['A'].width = 37
    hoja.column_dimensions['B'].width = 22
    for columna, titulo in enumerate(titulos, start=1):
        celda = hoja.cell(FILA_TITULOS, columna, titulo)
        celda.font = NEGRITA
        celda.alignment = CENTRADO
        celda.fill = PatternFill('solid', fgColor='EDF6F4')
        if columna > 2:
            hoja.column_dimensions[get_column_letter(columna)].width = 19
        if 3 <= columna <= 2 + len(fechas):
            celda.number_format = 'dd/mm/yyyy'

    faltas_por_fecha = Counter()
    for fila, matricula in enumerate(matriculas, start=FILA_TITULOS + 1):
        estudiante = matricula.estudiante
        hoja.cell(fila, 1, estudiante.usuario.get_full_name()).data_type = 's'
        rude = hoja.cell(fila, 2, estudiante.rude)
        rude.data_type = 's'
        rude.alignment = CENTRADO
        conteo = Counter()
        for columna, fecha in enumerate(fechas, start=3):
            registro = por_dia.get((estudiante.pk, fecha))
            celda = hoja.cell(fila, columna)
            celda.alignment = CENTRADO
            if registro is None:
                celda.value = '—'
                continue
            conteo[registro.estado] += 1
            faltas_por_fecha[fecha] += registro.estado == Asistencia.Estado.FALTA
            valor = registro.get_estado_display()
            if not capacitacion and registro.hora_llegada:
                valor += f' {registro.hora_llegada:%H:%M}'
            celda.value = valor
            celda.fill = PatternFill('solid', fgColor=COLORES[registro.estado])

        for columna, estado in enumerate(estados, start=3 + len(fechas)):
            hoja.cell(fila, columna, conteo[estado]).alignment = CENTRADO
        porcentaje = hoja.cell(fila, len(titulos))
        if conteo:
            porcentaje.value = (conteo[Asistencia.Estado.PRESENTE] + conteo[Asistencia.Estado.ATRASO]) / sum(conteo.values())
        porcentaje.number_format = '0%'
        porcentaje.alignment = CENTRADO

    fila_final = hoja.max_row + 1
    if fechas:
        hoja.cell(fila_final, 1, 'Faltas del curso').font = NEGRITA
        for columna, fecha in enumerate(fechas, start=3):
            hoja.cell(fila_final, columna, faltas_por_fecha[fecha]).alignment = CENTRADO
    else:
        mensaje = 'No hay entradas registradas en el mes elegido.' if periodo else 'Todavía no hay asistencia registrada para este curso.'
        hoja.cell(fila_final, 1, mensaje)

    hoja.freeze_panes = 'C5'
    hoja.print_title_rows = '1:4'
    hoja.print_title_cols = 'A:B'
    hoja.page_setup.orientation = 'landscape'
    return libro
