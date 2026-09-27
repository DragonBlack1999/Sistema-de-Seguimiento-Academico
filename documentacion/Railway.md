# Poner el sistema en internet (Railway)

Sistema de Seguimiento Académico · U.E. «Eduardo Abaroa Tarde»

Esta guía es para la **prueba**: dejar el sistema andando en internet, con
HTTPS, para que un par de docentes y un par de padres lo usen desde su teléfono
y digan qué falta. No es todavía la puesta en marcha para todo el colegio; lo
que falta para eso está al final.

---

## 0. Antes de tocar Railway

**La prueba va con datos inventados.** Poner en internet la base real sería
publicar los datos de 402 menores de edad, con contraseñas que hoy son iguales
al nombre de usuario. La base de prueba tiene el colegio entero —los 18 cursos,
las 13 materias, las 216 asignaciones, los 637 bloques de horario y los 402
estudiantes en su curso— con todos los nombres, carnets, RUDE, teléfonos y
direcciones inventados, y encima el movimiento de tres semanas de clases.

Se arma con dos comandos, sobre una copia de la base (nunca sobre la real, y
los comandos se niegan si el nombre no lleva «prueba»):

```
createdb -U postgres -T seguimiento_academico seguimiento_prueba_publica
set DB_NAME=seguimiento_prueba_publica
venv\Scripts\python.exe manage.py anonimizar
venv\Scripts\python.exe manage.py datos_de_ejemplo
venv\Scripts\python.exe manage.py alertas_diarias
```

El primero cambia todo lo que señala a una persona; el segundo agrega familias,
asistencia, notas y tareas; el tercero deja avisos pendientes para que las
pantallas de la familia tengan algo que mostrar. `anonimizar` escribe además
`cuentas_de_prueba.txt`, la lista de usuarios y contraseñas para repartir a
quienes vayan a probar.

> **Los archivos subidos no se anonimizan.** Lo que está en `media/` —fotos,
> adjuntos, entregas— son archivos reales, y la base anonimizada simplemente
> deja de apuntarlos. Al servidor de prueba **no se sube `media/` ni el
> `archivos.zip` de ningún respaldo**.

**Tener el código en un repositorio.** Railway despliega desde GitHub (o desde
la consola con `railway up`). El repositorio va **privado**. El `.gitignore` ya
deja fuera lo que nunca debe subir: `.env`, `media/`, `respaldos/`.

```
git init
git add .
git commit -m "Sistema de Seguimiento Académico"
```

---

## 1. Crear el proyecto y la base de datos

1. En [railway.app](https://railway.app), **New Project → Deploy from GitHub
   repo** y elegir el repositorio.
2. En el mismo proyecto, **New → Database → Add PostgreSQL**.

Railway detecta Python solo. Lo que hace después lo manda `railway.json`, que ya
está en el proyecto:

- **al construir:** instala `requirements-nube.txt` (agrega `pywebpush`, que es
  lo que empuja los avisos al celular) y prepara los archivos estáticos;
- **al arrancar:** aplica las migraciones y levanta el servidor;
- **para vigilar:** pregunta por `/salud/`, que responde «bien» solo si la
  aplicación alcanza su base de datos.

## 2. Las variables

En el servicio de la aplicación, pestaña **Variables**. La lista completa está
en `.env.ejemplo`. Las imprescindibles:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | una nueva, larga. `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | `False` — con `True`, cualquier error muestra el código y las claves |
| `DATABASE_URL` | **Add Reference → Postgres → DATABASE_URL** (no copiarla a mano) |
| `MEDIA_ROOT` | `/app/media` |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | las mismas de siempre: si cambian, todos los teléfonos que ya activaron los avisos dejan de recibirlos |
| `VAPID_CONTACTO` | `mailto:` del colegio |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | la cuenta de Gmail y su contraseña de aplicación |
| `HORA_ENTRADA`, `UMBRAL_FALTAS_ALERTA`, `UMBRAL_TAREAS_SIN_ENTREGAR` | las reglas del colegio |

`ALLOWED_HOSTS` no hace falta: el sistema toma el dominio que Railway le da.

## 3. El disco para los archivos subidos

Sin esto, **cada actualización borra las tareas y las fotos que hayan subido**:
el disco del contenedor se rehace en cada despliegue.

En el servicio de la aplicación: **Settings → Volumes → Add Volume**, punto de
montaje `/app/media`.

## 4. Llevar los datos

Se hace **una vez, con la base recién creada y vacía**, desde la laptop. En
Railway, el servicio Postgres → **Variables** → copiar `DATABASE_PUBLIC_URL`.

```
set URL=postgresql://postgres:...@...proxy.rlwy.net:12345/railway
"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" --no-owner --no-privileges -d "%URL%" "respaldos\para-railway\2026-09-27_002113\base.dump"
```

Ese archivo es la base de prueba ya armada: 402 estudiantes con nombres
inventados, 815 cuentas (con sus familias), 6.030 marcas de asistencia, 1.171
notas de trimestre y 18 tareas con sus entregas.

`--no-owner` es necesario: el dueño de las tablas aquí es `academico_app`, un
usuario que allá no existe.

No se sube ningún archivo de `media/`: son archivos reales y la base de prueba
no los necesita.

Para comprobar que llegó todo, comparar con el `informe.txt` de ese respaldo:

```
"C:\Program Files\PostgreSQL\16\bin\psql.exe" "%URL%" -c "select count(*) from academico_estudiante"
```

## 5. Comprobar que funciona

1. Abrir `https://<lo-que-diga-Railway>/salud/` → debe decir **bien**.
2. Entrar como dirección y mirar el tablero.
3. Abrirlo **en un teléfono**, activar los avisos y provocar uno (marcar una
   falta desde la puerta, por ejemplo). Es lo único que no se puede probar en la
   laptop: los avisos al celular necesitan HTTPS de verdad.

### En el teléfono

**Android (Chrome).** Al entrar, el propio Chrome ofrece instalarla; también
está el botón «Instalar la app» en la pantalla de Notificaciones, o el menú de
Chrome → «Instalar aplicación». Los avisos funcionan **aunque no se instale**:
basta con activarlos desde la pantalla de Notificaciones.

**iPhone y iPad (Safari).** Aquí el orden importa y no hay vuelta:

1. Abrir la dirección **en Safari** (no en Chrome).
2. Botón de compartir → **«Añadir a pantalla de inicio»**.
3. Abrir el sistema **desde ese ícono**.
4. Recién ahí, en Notificaciones, «Activar los avisos en este dispositivo».

En una pestaña de Safari, iOS no permite avisos de ningún sitio web: el sistema
lo detecta y muestra estos pasos en lugar del botón. Hace falta **iOS 16.4 o
más nuevo** (marzo de 2023); un iPhone que se quedó en iOS 15 puede usar todo el
sistema, pero no recibirá avisos.

Si alguien borra el ícono de la pantalla de inicio, su teléfono deja de estar
suscrito y hay que volver a activarlo.

## 6. Lo que tiene que correr cada día

`alertas_diarias` es el que revisa tareas vencidas y promedios, y manda el
resumen del día a cada familia. En Railway: **New → Empty Service**, del mismo
repositorio, y en **Settings**:

- **Start Command:** `python manage.py alertas_diarias`
- **Cron Schedule:** `0 1 * * *` (una vez al día; Railway usa UTC, así que esto
  es a las 21:00 de Bolivia)

Ese servicio necesita las mismas variables que la aplicación.

## 7. Los respaldos

Los respaldos **no se guardan en el servidor**: se traen. Desde la laptop, con
`DATABASE_URL` apuntando a la base de internet:

```
set DATABASE_URL=postgresql://postgres:...@...proxy.rlwy.net:12345/railway
venv\Scripts\python.exe manage.py respaldar
```

La copia queda en la carpeta de respaldos de la laptop, con su informe, igual
que la del colegio. Conviene programarla igual que la otra (ver
`documentacion/Respaldos.md`).

## 8. Cuando algo falle

- **La aplicación no levanta:** Railway → el servicio → **Deploy Logs**. Ahí
  sale el error de Python completo.
- **«DisallowedHost»:** el dominio cambió; agregarlo en `ALLOWED_HOSTS`.
- **«CSRF verification failed»:** falta el dominio en `CSRF_TRUSTED_ORIGINS`.
- **Las pantallas se ven sin estilos:** falló `collectstatic` al construir; está
  en los **Build Logs**.
- **Los avisos no llegan:** revisar que las dos llaves VAPID estén puestas y que
  el teléfono los haya activado en *ese* navegador; cada aparato se activa por
  separado.

## 9. Lo que falta para dejarlo en serio

Esto es una prueba. Antes de darle la dirección a todo el colegio:

1. **Contraseñas.** Hoy la de cada docente es su nombre de usuario. Hay que
   generarlas al azar, entregarlas en mano y obligar a cambiarla al entrar.
2. **Dominio propio** del colegio, y recién ahí subir el HSTS a un año con
   subdominios (en un subdominio prestado de Railway eso afectaría a terceros).
3. **Respaldos programados** y probados también contra la base de internet.
4. **Aviso de privacidad firmado** por las familias en la matrícula, que ya está
   escrito en `/privacidad/`.
5. **Cuánto cuesta**: el plan Hobby de Railway son unos 5 USD al mes más el
   consumo; para este tamaño, la cuenta suele quedar entre 7 y 12 USD mensuales.
