# -*- coding: utf-8 -*-
"""Recorre el guión de la demostración entero, pantalla por pantalla.

    demoevisar.bat

Lo que esto atrapa es lo único que no se puede arreglar en la sala: una
pantalla que da error delante de alguien. Entra con cada una de las seis
cuentas del guión, abre todas las pantallas del recorrido y comprueba que los
datos se vean llenos.

Vive en el repositorio y no en una carpeta temporal a propósito: las pruebas
que se escribieron sueltas se perdieron tres veces.
"""
import io
import os
import re
import sys

import django

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# La raíz del proyecto es la carpeta de arriba, sea cual sea la computadora.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DB_NAME', 'seguimiento_demo')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import authenticate  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from apps.academico.models import Curso, Estudiante, Matricula  # noqa: E402
from apps.accounts.models import Usuario  # noqa: E402
from apps.asistencia.models import Asistencia  # noqa: E402
from apps.calificaciones.models import Nota  # noqa: E402
from apps.tareas.models import Tarea  # noqa: E402

print(f'base: {settings.DATABASES["default"]["NAME"]}\n')

fallos = []


def revisar(condicion, texto):
    print(('ok ' if condicion else '!! ') + texto)
    if not condicion:
        fallos.append(texto)


# Las mismas credenciales que estan en el GUION.
CUENTAS = [
    ('Dirección', 'admin', 'khantuta954'),
    ('Secretaría', 'secretario', 'pututu887'),
    ('Regencia', 'myujra', 'sajama552'),
    ('Docente', 'gquispe', 'chacana236'),
    ('Estudiante', '999900000000001', '90000001'),
    ('Familia', '95900001', '95900001'),
]

print('las credenciales del guión')
entrados = {}
for rotulo, usuario, clave in CUENTAS:
    persona = authenticate(username=usuario, password=clave)
    revisar(persona is not None, f'{rotulo}: {usuario} entra')
    if persona is not None:
        entrados[rotulo] = persona

# ───────────────────── los datos se ven llenos ─────────────────────
print('\nque haya algo que mostrar')
notas = Nota.objects.calificadas().count()
revisar(notas > 10000, f'planillas llenas: {notas} notas calificadas')

cursos_con_notas = len({n['asignacion__curso_id'] for n in
                        Nota.objects.calificadas().values('asignacion__curso_id')})
revisar(cursos_con_notas >= 18, f'y en los {cursos_con_notas} cursos, no solo en tres')

trimestres = sorted({n['trimestre'] for n in Nota.objects.calificadas().values('trimestre')})
revisar(trimestres == [1, 2, 3], f'con los tres trimestres cargados ({trimestres})')

asistencias = Asistencia.objects.count()
dias = len({a['fecha'] for a in Asistencia.objects.values('fecha')})
revisar(asistencias > 10000 and dias >= 30,
        f'asistencia de {dias} días de clase ({asistencias} marcas)')

revisar(Tarea.objects.count() >= 50, f'tareas: {Tarea.objects.count()}')
con_tutor = Estudiante.objects.exclude(tutor=None).count()
revisar(con_tutor >= 390, f'familias: {con_tutor} de 402 estudiantes tienen tutor')

# ───────────────────── cada pantalla del guión ─────────────────────
print('\ncada pantalla del recorrido')


def mirar(rotulo, persona, nombre_url, argumentos=None, parametros=None):
    c = Client()
    c.force_login(persona)
    url = reverse(nombre_url, args=argumentos or [])
    r = c.get(url, parametros or {}, HTTP_HOST='127.0.0.1')
    ok = r.status_code in (200, 302)
    revisar(ok, f'{rotulo}: {url} → {r.status_code}')
    return r.content.decode() if r.status_code == 200 else ''


# 1. La portada, sin entrar.
portada = Client().get(reverse('accounts:login'), HTTP_HOST='127.0.0.1')
revisar(portada.status_code == 200, 'la portada abre sin iniciar sesión')
revisar('Olvidaste tu contraseña' in portada.content.decode(),
        'y ofrece «¿Olvidaste tu contraseña?»')

admin = entrados.get('Dirección')
if admin:
    mirar('dirección', admin, 'accounts:dashboard_admin')
    mirar('dirección', admin, 'accounts:tablero')
    mirar('dirección', admin, 'datos:indice')
    for clave in ('estudiantes', 'docentes', 'personal', 'familias',
                  'gestiones', 'cursos', 'materias', 'asignaciones', 'matriculas'):
        mirar('datos', admin, 'datos:lista', [clave])
    mirar('datos', admin, 'datos:nuevo', ['materias'])

    # Las dos pantallas del guión que no hay que confirmar.
    html = mirar('dirección', admin, 'academico:cerrar_gestion')
    revisar('name="pasa"' in html, 'el cierre de año muestra las casillas')
    casillas = html.count('type="checkbox" name="pasa"')
    revisar(casillas == Matricula.objects.filter(activa=True).count(),
            f'una por estudiante ({casillas})')

    mirar('dirección', admin, 'accounts:solicitudes_de_clave')
    mirar('dirección', admin, 'asistencia:puerta')
    mirar('dirección', admin, 'comunicaciones:buscar_boletines')
    mirar('dirección', admin, 'academico:mi_horario')
    mirar('dirección', admin, 'academico:horario_constructor')
    mirar('dirección', admin, 'noticias:lista')
    mirar('dirección', admin, 'comunicaciones:lista_citaciones')

    # El buscador en vivo de la demostración: «quispe».
    c = Client()
    c.force_login(admin)
    pedazo = c.get(reverse('datos:lista', args=['estudiantes']), {'q': 'quispe'},
                   HTTP_HOST='127.0.0.1', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    revisar(pedazo.status_code == 200 and '<table' in pedazo.content.decode(),
            'el buscador en vivo responde solo con la tabla')

    # Borrar un estudiante: tiene que decir qué se pierde.
    alumno = Estudiante.objects.first()
    html = mirar('dirección', admin, 'datos:eliminar', ['estudiantes', alumno.pk])
    revisar('también borra' in html, 'borrar dice qué se perdería')
    revisar('Dar de baja' in html, 'y ofrece dar de baja al lado')

regente = entrados.get('Regencia')
if regente:
    html = mirar('regencia', regente, 'accounts:dashboard_regente')
    revisar('A qué curso le falta gente' in html, 'el panel del regente trae los cursos')
    curso = Curso.objects.filter(gestion__activa=True).first()
    mirar('regencia', regente, 'asistencia:puerta', parametros={'curso': curso.pk})

docente = entrados.get('Docente')
if docente:
    html = mirar('docente', docente, 'accounts:dashboard_profesor')
    revisar('Cómo va cada curso' in html, 'el panel del docente trae sus cursos')
    revisar('sin cargar' not in html,
            'y con las planillas llenas, ninguna materia dice «sin cargar»')
    mirar('docente', docente, 'academico:mi_horario')
    from apps.academico.models import AsignacionDocente
    suya = AsignacionDocente.objects.filter(profesor=docente).first()
    if suya:
        mirar('docente', docente, 'calificaciones:registrar_notas', [suya.pk, 1])
        mirar('docente', docente, 'tareas:lista_tareas', [suya.pk])

alumno = entrados.get('Estudiante')
if alumno:
    html = mirar('estudiante', alumno, 'accounts:dashboard_estudiante')
    revisar('Cómo voy en cada materia' in html, 'el panel del estudiante trae sus materias')
    revisar(len(re.findall(r'badge bg-(success|danger)">\d', html)) >= 8,
            'con una nota por materia, no vacías')
    mirar('estudiante', alumno, 'calificaciones:mis_notas')
    mirar('estudiante', alumno, 'tareas:mis_tareas')
    mirar('estudiante', alumno, 'asistencia:mi_asistencia')
    mirar('estudiante', alumno, 'academico:mi_horario')
    mirar('estudiante', alumno, 'calificaciones:historial_academico')
    mirar('estudiante', alumno, 'academico:mi_perfil')

familia = entrados.get('Familia')
if familia:
    html = mirar('familia', familia, 'padres:panel')
    revisar(len(html) > 2000, 'el panel de la familia trae a sus hijos')

# ───────────────────── el boletín, que es lo que se imprime ─────────────────────
print('\nel boletín en PDF')
if admin:
    c = Client()
    c.force_login(admin)
    alumno_con_notas = (Nota.objects.calificadas()
                        .select_related('estudiante').first().estudiante)
    try:
        url = reverse('comunicaciones:boletin_estudiante', args=[alumno_con_notas.pk])
    except Exception:
        url = None
    if url:
        r = c.get(url, HTTP_HOST='127.0.0.1')
        revisar(r.status_code == 200 and r['Content-Type'].startswith('application/pdf'),
                f'el boletín sale en PDF ({r.status_code}, {len(r.content)} bytes)')
    else:
        print('.. no hay url de boletín en PDF con ese nombre')

print(f'\nfallos: {len(fallos)}')
for f in fallos:
    print('   -', f)
