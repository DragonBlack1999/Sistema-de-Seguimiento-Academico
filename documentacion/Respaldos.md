# Copias de respaldo

Sistema de Seguimiento Académico · U.E. «Eduardo Abaroa Tarde» · Nivel Secundario

Un respaldo sirve para una sola cosa: **poder volver**. Todo lo que sigue está
pensado alrededor de eso, incluida la parte que casi nadie hace, que es
comprobar de vez en cuando que la copia de verdad se puede restaurar.

---

## Qué se guarda

Cada copia es una carpeta con la fecha y la hora:

```
respaldos/
    2026-09-26_2252/
        base.dump      la base de datos entera, comprimida
        archivos.zip   lo que subieron docentes y estudiantes, y las fotos
        informe.txt    de qué base salió, cuánto pesa y cuántas filas tenía
    registro.txt       qué pasó cada noche
```

El `informe.txt` es lo que después permite saber si una restauración salió
completa: anota cuántos estudiantes, usuarios, notas y asistencias había en el
momento exacto de la copia.

Mientras se está armando, la carpeta se llama `…parcial`. Si se corta la luz a
la mitad, queda con ese nombre y se borra sola en la siguiente corrida: nunca
se confunde una copia a medias con una buena.

## Hacer una copia

```
venv\Scripts\python.exe manage.py respaldar
```

Hace la copia, **la verifica** (lee su índice para confirmar que no salió
cortada), la deja también en el segundo lugar si está configurado, y borra las
vencidas. Si algo falla, termina con error y lo dice.

Opciones: `--sin-rotar` (no borra nada viejo) y `--solo-rotar` (solo limpia).

## Cuántas se guardan

- **Todas las de los últimos 14 días.**
- **La primera de cada mes, durante 12 meses.**

La segunda regla es la importante: un dato borrado por error en marzo se suele
descubrir en mayo, cuando de las copias diarias ya no queda ninguna anterior al
error. Se cambian con `RESPALDOS_DIAS` y `RESPALDOS_MESES` en el `.env`.

## Dónde se guardan

Por defecto, en la carpeta `respaldos` del propio sistema. **Eso no alcanza**:
si se daña el disco, se pierden la base y sus copias al mismo tiempo. En el
`.env`:

```
RESPALDOS_DIR=E:\Respaldos Seguimiento
RESPALDOS_COPIA=D:\Respaldos Seguimiento
```

`RESPALDOS_COPIA` es el segundo lugar — un USB, un disco externo, una carpeta
sincronizada con la nube. Si ese disco no está conectado, el respaldo local se
hace igual y el comando lo avisa.

> La carpeta de respaldos contiene los datos de 402 estudiantes menores de edad.
> Va en un disco que solo maneje la Dirección, no en uno que circule por el
> colegio.

## Que corra sola todas las noches

Con doble clic a `respaldar.bat` se prueba a mano. Para que corra sin que nadie
se acuerde, en el **Programador de tareas** de Windows:

1. Abrir «Programador de tareas» (buscarlo en el menú Inicio).
2. *Crear tarea básica…* → nombre: `Respaldo Seguimiento Académico`.
3. Cuándo: *Diariamente*, a una hora en que la computadora esté encendida y
   nadie esté usando el sistema (por ejemplo 20:00).
4. Acción: *Iniciar un programa* → Programa:
   `E:\CLAUDE\Sistema de Seguimiento Academico\respaldar.bat`
5. Terminar, y en las propiedades de la tarea marcar **«Ejecutar tanto si el
   usuario inició sesión como si no»** y **«Ejecutar la tarea lo antes posible
   tras un inicio programado que no se realizó»** — esta última hace que, si la
   computadora estuvo apagada, el respaldo se haga al prenderla.

En un mismo renglón, desde una consola de administrador:

```
schtasks /create /tn "Respaldo Seguimiento Academico" /tr "\"E:\CLAUDE\Sistema de Seguimiento Academico\respaldar.bat\"" /sc daily /st 20:00 /rl highest
```

Cuando el sistema pase al servidor de internet, esto mismo se programa allá con
cron y el comando `manage.py respaldar`.

## Comprobar que el respaldo sirve

**Una vez al mes, y siempre antes de tocar algo grande.** Restaura la copia en
una base aparte y compara las filas contra lo que dice su informe:

```
set PGPASSWORD=la-clave-de-postgres
venv\Scripts\python.exe manage.py probar_respaldo --usuario postgres
```

La cuenta con la que trabaja el sistema (`academico_app`) no puede crear bases
—y está bien que no pueda—, por eso esta prueba pide una cuenta de
administrador de PostgreSQL. La contraseña se pasa en el momento, por la
variable `PGPASSWORD`, para no dejarla escrita en ningún archivo.

Si todo está bien, termina diciendo **«El respaldo se restaura completo. Sirve
para volver.»** y borra la base de prueba. Si una sola tabla no coincide con el
informe, falla y lo nombra.

Este comando **solo acepta bases cuyo nombre lleve la palabra «prueba»**. No es
un capricho: borra entera la base que se le indique.

## Restaurar de verdad

Esto se hace a mano, a propósito: es la operación que reemplaza los datos del
colegio y conviene que alguien esté mirando cada paso.

**1. Detener el sistema** (cerrar el servidor, para que nadie escriba mientras).

**2. Poner a salvo lo que haya ahora**, aunque parezca roto — puede tener datos
de hoy que el respaldo no tiene:

```
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -Fc -f antes-de-restaurar.dump seguimiento_academico
```

**3. Volver a crear la base vacía**, con el mismo dueño:

```
"C:\Program Files\PostgreSQL\16\bin\dropdb.exe" -U postgres --force --if-exists seguimiento_academico
"C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres -O academico_app seguimiento_academico
```

**4. Cargar el respaldo:**

```
"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -U postgres -d seguimiento_academico "respaldos\2026-09-26_2252\base.dump"
```

**5. Devolver los archivos subidos:** descomprimir `archivos.zip` dentro de la
carpeta `media` del sistema.

**6. Comprobar** que quedó bien:

```
venv\Scripts\python.exe manage.py showmigrations
venv\Scripts\python.exe manage.py runserver
```

Entrar y mirar que estén los estudiantes, las notas del trimestre y las
noticias. Comparar los números con el `informe.txt` de esa copia.

## Si el respaldo falla una noche

Mirar `respaldos\registro.txt`. Los dos motivos habituales:

- **«No encuentro pg_dump»** — PostgreSQL está instalado en otra carpeta.
  Escribir la ruta en el `.env`: `PG_BIN=C:\Program Files\PostgreSQL\16\bin`.
- **«No se pudo copiar a D:\…»** — el disco del segundo respaldo no estaba
  conectado. La copia local igual se hizo; conectar el disco y correr
  `manage.py respaldar` a mano, o esperar a la noche siguiente.
