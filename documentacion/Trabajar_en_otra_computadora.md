# Trabajar desde otra computadora

Sistema de Seguimiento Académico · U.E. «Eduardo Abaroa Tarde»

Para seguir desarrollando en un segundo equipo. Lleva media hora la primera
vez; después, empezar a trabajar son dos comandos.

---

## Lo que viaja por GitHub y lo que no

| | ¿Está en el repositorio? |
|---|---|
| Todo el código, plantillas y estilos | **Sí** |
| `.env` con las claves | **No** — y está bien que no esté |
| La base de datos | **No** |
| `media/` (tareas y fotos subidas) | **No** |
| `venv/` (el entorno de Python) | **No**, se recrea en cada máquina |

Las tres últimas hay que llevarlas a mano. La primera —las claves— **nunca por
correo ni por chat**: en un USB, o escribiéndolas de nuevo.

---

## Primera vez en la computadora nueva

### 1. Instalar lo que hace falta

- **Python 3.12** (la misma versión que usa el servidor). Al instalarlo, marcar
  *«Add Python to PATH»*.
- **PostgreSQL 16**. Anotar la contraseña que pide para el usuario `postgres`:
  se necesita más abajo.
- **Git** y **Visual Studio Code**.

### 2. Traer el código

```
git clone https://github.com/DragonBlack1999/Sistema-de-Seguimiento-Academico.git
cd Sistema-de-Seguimiento-Academico
```

### 3. El entorno de Python

```
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements-nube.txt` agrega `pywebpush`, que es lo que empuja los avisos al
celular. En una computadora de desarrollo no hace falta: sin esa librería el
sistema funciona igual y lo único que no hace es enviar avisos.

### 4. La base de datos

Abrir **SQL Shell (psql)** —viene con PostgreSQL— y entrar como `postgres`.
Después, estas dos líneas, con **la misma contraseña que tenga `DB_PASSWORD` en
el `.env`** del otro equipo:

```sql
CREATE ROLE academico_app LOGIN PASSWORD 'la-del-env';
CREATE DATABASE seguimiento_academico OWNER academico_app;
```

El sistema trabaja con ese usuario limitado a propósito, no con `postgres`.

### 5. El archivo `.env`

Copiar `.env.ejemplo` como `.env` y llenarlo con los valores del otro equipo
(vienen en su propio `.env`, que se lleva en el USB):

```
copy .env.ejemplo .env
```

Los que no pueden faltar: `SECRET_KEY`, `DB_PASSWORD`, y las dos llaves
`VAPID_*` si se van a probar los avisos. `DEBUG=True` en una computadora de
desarrollo.

> Las llaves VAPID tienen que ser **las mismas en todas partes**. Si se generan
> nuevas, los teléfonos que ya activaron los avisos dejan de recibirlos.

### 6. Los datos

En la computadora **vieja**, una copia fresca:

```
venv\Scripts\python.exe manage.py respaldar
```

Llevar en el USB la carpeta que acaba de aparecer en `respaldos\` (la de fecha
más reciente). En la computadora **nueva**, con la base ya creada y vacía:

```
"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -U postgres -d seguimiento_academico "ruta\del\usb\base.dump"
```

Si el respaldo trae `archivos.zip`, descomprimirlo dentro de la carpeta `media`
del proyecto.

### 7. Comprobar que quedó andando

```
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py runserver
```

Abrir `http://localhost:8000/`, entrar y mirar que estén los estudiantes y las
notas. Comparar los números con el `informe.txt` del respaldo.

---

## El día a día con dos computadoras

**Al empezar**, siempre:

```
git pull
venv\Scripts\python.exe manage.py migrate
```

El `migrate` no es opcional: si en la otra máquina se agregó un campo, la
migración viaja por Git pero **la base de cada computadora es suya** y hay que
aplicársela.

**Al terminar**, siempre:

```
git add -A
git commit -m "qué se hizo y por qué"
git push
```

### La regla que evita el 90 % de los líos

**No dejar cambios sin subir en una máquina y ponerse a editar en la otra.** Si
pasa, Git no pierde nada, pero hay que reconciliar a mano:

```
git pull --rebase
```

Si avisa de conflictos, los marca dentro de los archivos entre `<<<<<<<` y
`>>>>>>>`: se elige qué queda, se borran esas marcas y después
`git add` + `git rebase --continue`.

### Lo que Git **no** sincroniza

- **La base de datos.** Cada computadora tiene la suya. Si se cargan datos
  reales en una, se llevan a la otra con un respaldo, como en el paso 6.
- **`media/`.** Los archivos subidos viven en el disco de cada máquina.
- **El `.env`.** Si se agrega una variable nueva, hay que ponerla a mano en la
  otra computadora **y en Railway**. Por eso conviene dejarla anotada en
  `.env.ejemplo`, que sí viaja.

---

## Si algo no arranca

| Dice | Qué pasa |
|---|---|
| `Falta SECRET_KEY` | No existe el `.env`, o está vacío |
| `password authentication failed for user "academico_app"` | La contraseña del `.env` no coincide con la del rol; se cambia con `ALTER ROLE academico_app PASSWORD 'otra';` |
| `database "seguimiento_academico" does not exist` | Falta el paso 4 |
| `No module named django` | Se está usando el Python del sistema en vez del `venv\Scripts\python.exe` |
| Las pantallas sin estilos | Correr `manage.py collectstatic` solo si `DEBUG=False`; en desarrollo no hace falta |
