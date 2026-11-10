# La demostración, en otra computadora

Esta carpeta deja el sistema andando en cualquier Windows, **sin internet** y
sin tocar nada de lo que ya haya instalado.

Los 402 estudiantes, los 33 docentes y las 376 familias son **inventados**.
Ningún dato real de un menor sale de la computadora del colegio.

---

## Instalación (una sola vez, ~5 minutos)

> **La instalación sí necesita internet** —baja las librerías de Python—, la
> presentación no. Instálalo la noche antes, no en la puerta de la sala.

### Lo que tiene que haber antes

| | Dónde se consigue | Cómo saber si ya está |
|---|---|---|
| **PostgreSQL 13 o más nuevo** | postgresql.org/download/windows | Existe la carpeta `C:\Program Files\PostgreSQL` |
| **Python 3.12 o más nuevo** | python.org/downloads/windows | En una consola, `python --version` responde |

Al instalar Python hay que marcar **«Add python.exe to PATH»**. Al instalar
PostgreSQL, anota la contraseña del usuario `postgres`: te la va a pedir.

### Los pasos

1. Copia la carpeta entera del proyecto a la otra computadora (USB, o
   `git clone` si ya la tienes ahí).
2. Entra a `demo\` y haz doble clic en **`instalar_demo.bat`**.
3. Te va a pedir la contraseña del usuario `postgres`. Escríbela y Enter.
4. Espera. Crea la base, restaura los datos e instala las librerías.
   Termina diciendo **LISTO**.

Si algo falla, el script se detiene y dice exactamente qué: no deja nada a
medias y se puede volver a correr tantas veces como haga falta.

---

## Para presentar

Doble clic en **`demo\demo.bat`**.

- Se abre una ventana negra: **es el servidor, no la cierres**. Minimízala.
- A los cuatro segundos se abre el navegador en `127.0.0.1:8080`.
- Para terminar, cierra la ventana negra.

El recorrido de qué mostrar y las credenciales están en
**[GUION.md](GUION.md)**.

---

## Preguntas que van a salir

**¿Necesita internet?**
No. Todo corre en la computadora.

**¿Son datos reales del colegio?**
No. Son inventados, los mismos que están publicados. Los nombres parecen reales
porque se generaron con los apellidos de la región, pero no corresponden a
ninguna persona.

**¿Esto rompe lo que ya tengo instalado?**
No. La demostración usa su propia base (`seguimiento_demo`) y su propia
configuración, por variables de entorno. Si en esa computadora ya trabajas en
el proyecto con tu `.env`, sigue funcionando igual.

**¿Puedo cambiar cosas durante la presentación?**
Sí: es una base de demostración, se puede agregar, editar y borrar sin miedo.
Para dejarla como al principio, vuelve a correr `instalar_demo.bat`.

---

## Archivos de esta carpeta

| | |
|---|---|
| `instalar_demo.bat` | Prepara todo. Se corre una vez. |
| `demo.bat` | Arranca la demostración. |
| `demo.dump` | Los datos inventados, comprimidos. |
| `GUION.md` | Qué mostrar, en qué orden, y las credenciales. |
| `configuracion.bat` | Lo genera el instalador. Lleva la contraseña de tu PostgreSQL, así que no se sube al repositorio. |
