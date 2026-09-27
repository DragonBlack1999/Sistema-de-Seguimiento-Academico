"""Copias de respaldo: cómo se hacen, cómo se guardan y cuáles se borran.

Un respaldo sirve para una sola cosa: poder volver. Por eso aquí no alcanza con
generar un archivo — cada copia se **verifica** apenas se crea (se lee su índice
para comprobar que no salió cortada) y se anota en un informe qué había dentro.
Comprobar de verdad que se puede restaurar es trabajo del otro comando,
`probar_respaldo`, que la carga en una base aparte y cuenta las filas.

Cada copia es una carpeta con tres cosas:

    2026-09-26_1830/
        base.dump      la base de datos entera, comprimida (formato de pg_dump)
        archivos.zip   lo que subieron docentes y estudiantes, y las fotos
        informe.txt    qué día, de qué base, cuánto pesa y cuántas filas tenía

Se arma primero como `.parcial` y se renombra al terminar: si se corta la luz a
mitad, queda una carpeta con nombre raro que nadie va a confundir con un
respaldo bueno.
"""
import datetime
import glob
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from django.conf import settings

FORMATO_NOMBRE = '%Y-%m-%d_%H%M%S'
# Los primeros respaldos se guardaron sin segundos; se siguen reconociendo.
FORMATO_VIEJO = '%Y-%m-%d_%H%M'
PATRON_NOMBRE = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{4}(\d{2})?$')

# Lo que se cuenta en el informe. No es todo: son las tablas por las que uno
# preguntaría primero si tuviera que restaurar («¿están los estudiantes?»).
TABLAS_DEL_INFORME = [
    ('accounts', 'Usuario'),
    ('academico', 'Estudiante'),
    ('academico', 'Matricula'),
    ('calificaciones', 'Nota'),
    ('calificaciones', 'Puntaje'),
    ('asistencia', 'Asistencia'),
    ('tareas', 'EntregaTarea'),
    ('comunicaciones', 'Citacion'),
]


class ErrorDeRespaldo(Exception):
    """Algo impidió dejar una copia confiable. Nunca se calla."""


class BaseProtegida(Exception):
    """Se intentó borrar una base que no es de prueba."""


def asegurar_base_de_prueba(nombre):
    """Deja pasar solo bases desechables. Todo borrado tiene que pasar por aquí.

    La regla es el nombre y no la configuración: qué base es «la de verdad»
    depende de desde dónde se corra el comando, y esa duda ya costó una base
    borrada. Una base real del colegio no se va a llamar «…prueba…».
    """
    if not nombre or 'prueba' not in nombre.lower():
        raise BaseProtegida(
            f'«{nombre}» no es una base de prueba y esta operación la borraría entera. '
            'Solo se aceptan nombres que lleven la palabra «prueba». Restaurar sobre la '
            'base real del colegio se hace a mano, siguiendo documentacion/Respaldos.md.'
        )
    return nombre


def borrar_base_de_prueba(nombre, *, usuario=None):
    """dropdb, pero únicamente sobre una base desechable."""
    asegurar_base_de_prueba(nombre)
    return _correr([binario('dropdb'), *_conexion(usuario), '--force', '--if-exists', nombre],
                   usuario=usuario)


# ────────────────────────── herramientas de PostgreSQL ──────────────────────

def binario(nombre):
    """Ubica pg_dump, pg_restore, createdb… sin depender del PATH.

    En Windows los instaladores de PostgreSQL no agregan su carpeta al PATH, así
    que buscar solo ahí falla en la mayoría de las computadoras del colegio.
    """
    if getattr(settings, 'PG_BIN', ''):
        candidato = Path(settings.PG_BIN) / f'{nombre}.exe'
        if candidato.exists():
            return str(candidato)
        candidato = Path(settings.PG_BIN) / nombre
        if candidato.exists():
            return str(candidato)

    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado

    # Última carta: la instalación típica de Windows, la versión más nueva.
    patrones = [r'C:\Program Files\PostgreSQL\*\bin\%s.exe' % nombre,
                r'C:\Program Files (x86)\PostgreSQL\*\bin\%s.exe' % nombre]
    caminos = sorted(c for patron in patrones for c in glob.glob(patron))
    if caminos:
        return caminos[-1]

    raise ErrorDeRespaldo(
        f'No encuentro «{nombre}». Es parte de PostgreSQL. Si está instalado en otra '
        f'carpeta, escribe su ruta en el archivo .env como PG_BIN='
        r'C:\Program Files\PostgreSQL\16\bin'
    )


def credenciales(usuario=None):
    """Con qué cuenta se habla con PostgreSQL.

    Para copiar alcanza con la cuenta de la aplicación, que es limitada a
    propósito. Restaurar —o crear la base de prueba— necesita una cuenta con más
    permiso; esa se pasa en el momento (`--usuario`), y su contraseña se toma de
    PGPASSWORD, para no dejarla escrita en ningún archivo del proyecto.
    """
    base = settings.DATABASES['default']
    if usuario and usuario != base['USER']:
        clave = os.environ.get('PGPASSWORD') or getattr(settings, 'RESPALDOS_CLAVE', '')
        return usuario, clave
    return base['USER'], base['PASSWORD']


def entorno(usuario=None):
    """El entorno para los programas de PostgreSQL, con la contraseña adentro.

    Va por variable de entorno y no por la línea de comandos a propósito: los
    argumentos de un proceso los puede leer cualquiera en la misma máquina.
    """
    _, clave = credenciales(usuario)
    ambiente = os.environ.copy()
    ambiente['PGPASSWORD'] = clave
    return ambiente


def _correr(argumentos, *, usuario=None, **extra):
    resultado = subprocess.run(
        argumentos, env=entorno(usuario), capture_output=True, text=True,
        encoding='utf-8', errors='replace', **extra,
    )
    return resultado


def _conexion(usuario=None):
    base = settings.DATABASES['default']
    quien, _ = credenciales(usuario)
    return ['-h', base['HOST'] or 'localhost', '-p', str(base['PORT'] or 5432),
            '-U', quien]


# ────────────────────────────── crear una copia ─────────────────────────────

def carpeta_de_respaldos():
    destino = Path(settings.RESPALDOS_DIR)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _conteos():
    """Cuántas filas tiene cada tabla importante, para dejarlo escrito."""
    from django.apps import apps

    conteos = {}
    for etiqueta, modelo in TABLAS_DEL_INFORME:
        try:
            conteos[f'{etiqueta}.{modelo}'] = apps.get_model(etiqueta, modelo).objects.count()
        except Exception:                       # una tabla que ya no exista no frena el respaldo
            conteos[f'{etiqueta}.{modelo}'] = None
    return conteos


def _volcar_base(destino):
    """La base entera, en el formato comprimido de PostgreSQL."""
    base = settings.DATABASES['default']
    archivo = destino / 'base.dump'
    resultado = _correr([
        binario('pg_dump'), *_conexion(), '--format=custom', '--compress=6',
        '--file', str(archivo), base['NAME'],
    ])
    if resultado.returncode != 0 or not archivo.exists():
        raise ErrorDeRespaldo(f'pg_dump falló: {resultado.stderr.strip()[:500]}')
    return archivo


def _verificar(archivo):
    """Lee el índice del respaldo. Si salió cortado, esto lo descubre hoy y no
    el día que haga falta restaurar."""
    resultado = _correr([binario('pg_restore'), '--list', str(archivo)])
    if resultado.returncode != 0:
        raise ErrorDeRespaldo(
            f'El respaldo se creó pero no se puede leer: {resultado.stderr.strip()[:500]}'
        )
    tablas = [linea for linea in resultado.stdout.splitlines() if ' TABLE DATA ' in linea]
    if not tablas:
        raise ErrorDeRespaldo('El respaldo no contiene ninguna tabla con datos.')
    return len(tablas)


def _guardar_archivos(destino):
    """Los archivos subidos: tareas, adjuntos de mensajes y fotos de perfil."""
    origen = Path(settings.MEDIA_ROOT)
    if not origen.exists():
        return None, 0

    archivo = destino / 'archivos.zip'
    cuantos = 0
    with zipfile.ZipFile(archivo, 'w', zipfile.ZIP_DEFLATED) as zip_:
        for camino in sorted(origen.rglob('*')):
            if camino.is_file():
                zip_.write(camino, camino.relative_to(origen).as_posix())
                cuantos += 1
    if cuantos == 0:
        archivo.unlink()
        return None, 0
    return archivo, cuantos


def _escribir_informe(destino, *, base, tablas, archivos, cuantos_archivos, conteos, momento):
    lineas = [
        'Respaldo del Sistema de Seguimiento Académico',
        'U.E. «Eduardo Abaroa Tarde» · Nivel Secundario',
        '',
        f'Fecha:            {momento:%d/%m/%Y %H:%M}',
        f'Base de datos:    {base}',
        f'Tablas con datos: {tablas}',
        f'base.dump:        {_peso((destino / "base.dump").stat().st_size)}',
    ]
    if archivos:
        lineas.append(f'archivos.zip:     {_peso(archivos.stat().st_size)} · '
                      f'{cuantos_archivos} archivo(s)')
    else:
        lineas.append('archivos.zip:     no hay archivos subidos todavía')
    lineas += ['', 'Filas al momento de la copia:']
    for nombre, cuantas in conteos.items():
        lineas.append(f'  {nombre:<28} {"?" if cuantas is None else cuantas}')
    lineas += [
        '',
        'Para restaurar, ver documentacion/Respaldos.md. En resumen:',
        '  pg_restore --clean --if-exists -U postgres -d seguimiento_academico base.dump',
        '  y descomprimir archivos.zip dentro de la carpeta media/ del sistema.',
        '',
    ]
    (destino / 'informe.txt').write_text('\n'.join(lineas), encoding='utf-8')


def _peso(bytes_):
    for unidad in ('B', 'KB', 'MB', 'GB'):
        if bytes_ < 1024 or unidad == 'GB':
            return f'{bytes_:.0f} {unidad}' if unidad == 'B' else f'{bytes_:.1f} {unidad}'
        bytes_ /= 1024


def crear(momento=None):
    """Hace una copia completa y la deja verificada. Devuelve su carpeta."""
    momento = momento or datetime.datetime.now()
    raiz = carpeta_de_respaldos()
    nombre = momento.strftime(FORMATO_NOMBRE)
    final = raiz / nombre
    parcial = raiz / f'{nombre}.parcial'

    if final.exists():
        raise ErrorDeRespaldo(f'Ya existe un respaldo de este minuto: {final}')
    if parcial.exists():
        shutil.rmtree(parcial)
    parcial.mkdir(parents=True)

    try:
        _volcar_base(parcial)
        tablas = _verificar(parcial / 'base.dump')
        archivos, cuantos = _guardar_archivos(parcial)
        _escribir_informe(
            parcial, base=settings.DATABASES['default']['NAME'], tablas=tablas,
            archivos=archivos, cuantos_archivos=cuantos, conteos=_conteos(), momento=momento,
        )
    except Exception:
        shutil.rmtree(parcial, ignore_errors=True)
        raise

    parcial.rename(final)
    return final


# ─────────────────────────── la segunda copia ───────────────────────────────

def copiar_afuera(carpeta):
    """Deja el respaldo también en el otro lugar (un USB, un disco externo).

    Un respaldo en el mismo disco que la base no protege del único accidente que
    de verdad pasa: que ese disco se dañe. Si el destino no está conectado, se
    avisa y no se interrumpe nada: mañana estará.
    """
    destino_raiz = getattr(settings, 'RESPALDOS_COPIA', '')
    if not destino_raiz:
        return None, 'No hay segunda copia configurada (RESPALDOS_COPIA en el .env).'

    destino_raiz = Path(destino_raiz)
    try:
        destino_raiz.mkdir(parents=True, exist_ok=True)
        destino = destino_raiz / carpeta.name
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(carpeta, destino)
    except OSError as error:
        return None, f'No se pudo copiar a {destino_raiz}: {error}'
    return destino, None


# ──────────────────────────────── rotación ──────────────────────────────────

def listar(raiz=None):
    """Los respaldos buenos que hay, del más viejo al más nuevo."""
    raiz = Path(raiz) if raiz else carpeta_de_respaldos()
    if not raiz.exists():
        return []
    return sorted(c for c in raiz.iterdir() if c.is_dir() and PATRON_NOMBRE.match(c.name))


def fecha_de(carpeta):
    formato = FORMATO_NOMBRE if len(carpeta.name) == 17 else FORMATO_VIEJO
    return datetime.datetime.strptime(carpeta.name, formato)


def a_borrar(carpetas, *, dias, meses, hoy=None):
    """Cuáles sobran, según la regla: todos los de los últimos `dias` días, y
    además el primero de cada mes durante `meses` meses.

    Guardar solo los últimos días es poco: un error que nadie nota —un dato que
    se borró en marzo— se descubre en mayo, cuando ya no queda ninguna copia
    anterior al error.
    """
    hoy = hoy or datetime.datetime.now()
    limite_dias = hoy - datetime.timedelta(days=dias)
    primeros_del_mes = {}
    for carpeta in sorted(carpetas, key=fecha_de):
        clave = fecha_de(carpeta).strftime('%Y-%m')
        primeros_del_mes.setdefault(clave, carpeta)

    meses_que_se_guardan = set(sorted(primeros_del_mes)[-meses:]) if meses else set()
    mensuales = {primeros_del_mes[m] for m in meses_que_se_guardan}

    sobran = []
    for carpeta in sorted(carpetas, key=fecha_de):
        if fecha_de(carpeta) >= limite_dias or carpeta in mensuales:
            continue
        sobran.append(carpeta)
    return sobran


def rotar(raiz=None, *, dias=None, meses=None, hoy=None):
    """Borra los respaldos que ya no hacen falta. Devuelve los borrados."""
    dias = settings.RESPALDOS_DIAS if dias is None else dias
    meses = settings.RESPALDOS_MESES if meses is None else meses
    borrados = []
    for carpeta in a_borrar(listar(raiz), dias=dias, meses=meses, hoy=hoy):
        shutil.rmtree(carpeta, ignore_errors=True)
        borrados.append(carpeta)
    return borrados
