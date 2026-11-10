# Guión de la demostración

Todo lo que sigue corre **en esta computadora**, sin internet. Los 402
estudiantes son inventados: ningún dato real de un menor sale de aquí.

## Antes de entrar a la sala

1. Doble clic en **`demo\demo.bat`**. Se abre una ventana negra y, a los cuatro
   segundos, el navegador.
2. **No cierres la ventana negra.** Es el servidor. Minimízala.
3. Deja el navegador en pantalla completa (F11) y el zoom al 100 % (Ctrl+0).

Si el navegador no abre solo, escribe en él: `127.0.0.1:8080`

> La demostración **no usa el puerto 8000** a propósito: ese es el que toma
> `manage.py runserver` a secas, y si tienes el servidor de desarrollo abierto
> estarías mostrando la base del colegio en vez de la demostración. La ventana
> negra dice siempre cuál es la dirección buena.

---

## Credenciales

| Para mostrar | Pestaña | Usuario | Contraseña |
|---|---|---|---|
| Dirección | Administración | `admin` | `khantuta954` |
| Secretaría | Administración | `secretario` | `pututu887` |
| Regencia | Administración | `myujra` | `sajama552` |
| Docente | Docente | `gquispe` | `chacana236` |
| Estudiante | Estudiante | `999900000000001` | `90000001` |
| Familia | Padre de familia | `95900001` | `95900001` |

> Ten esta tabla abierta en el celular. Escribir mal una contraseña delante de
> alguien cuesta más nervios que tiempo.

---

## El recorrido (12 minutos)

Cada bloque dice **qué abrir**, **qué decir** y **qué mirar**. Si vas corto de
tiempo, los marcados con ★ son los que muestran trabajo nuevo.

### 1 · Quién entra y cómo (1 min)

**Abre:** la portada, sin iniciar sesión.

> «El sistema sabe quién es cada uno antes de que escriba nada: el estudiante
> entra con su RUDE, el padre con su carnet, el docente con su usuario. Los
> rótulos cambian según el botón, porque un padre no sabe qué es un RUDE.»

Toca los cuatro botones y muestra cómo cambian las etiquetas y las ayudas.

### 2 · ★ Lo que pediste la vez pasada (2 min)

**Entra como `admin`** → menú **Más → Gestionar datos → Estudiantes**.

> «Lo que me pediste fue la interfaz: los buscadores y las fechas.»

- Escribe `quispe` en el buscador **sin apretar nada**. La lista se filtra
  mientras escribes: 402 → 33 → 1.
- Abre **Editar** en cualquier estudiante y muestra la **fecha de nacimiento**:
  antes era una caja de texto donde había que adivinar el formato; ahora abre
  el calendario y no deja elegir el futuro.

### 3 · ★ Gestión de datos completa (2 min)

Sigue en la misma pantalla.

> «Antes esto mandaba al panel técnico de Django, donde ni la directora ni la
> secretaria podían entrar: su cuenta no pasaba el segundo inicio de sesión.
> Ahora es una pantalla del colegio, en el idioma del colegio.»

- **Volver a gestión de datos**: nueve secciones, cada una con su cuenta.
- Entra a **Materias** → **Nueva materia** → guarda una (`Taller de Lectura`).
- **Borrar** esa misma materia: la pantalla dice qué se perdería.
- Ahora abre **Borrar** en un **estudiante**: dice
  «*esto también borra 120 puntajes, 20 notas, 15 asistencias…*» y ofrece
  **dar de baja** al lado.

> «Borrar en cascada es silencioso. Si no te dice qué se lleva, un clic borra
> el año entero de alguien. Por eso al lado está la opción que casi siempre se
> quería: dar de baja, que no pierde nada.»

**No confirmes el borrado.** Cancela.

### 4 · ★ El panel de cada rol (3 min)

Esto es lo que más se nota. **Sal y entra con cada uno**, 40 segundos cada uno:

- **`myujra` (regencia)** → su panel. Los 18 cursos con cuánta gente falta por
  entrar, de peor a mejor; quiénes se acercan al umbral de faltas; cómo viene
  la semana. Toca un curso: abre la lista de ese curso en el control de entrada.
- **`gquispe` (docente)** → sus clases de hoy, y por cada materia el promedio
  del trimestre, cuántos están debajo de 51 y qué entregas le esperan.
- **`999900000000001` (estudiante)** → su promedio, **materia por materia**,
  las que van mal primero.
- **`admin`** → asistencia del día, promedio del colegio, y «**esperando a
  alguien**»: lo trabado, con el botón para ir a destrabarlo.

> «Antes cada panel mostraba lo que su dueño ya sabía de memoria: su nombre y
> la lista de sus materias. Ahora muestra lo que no sabe y lo que tiene que
> hacer.»

### 5 · ★ El horario, impreso (1 min)

**Como `gquispe`** → **Horario** → botón **Imprimir** → en el diálogo elige
**Guardar como PDF**.

> «Lo que sale no es la pantalla: es una hoja del colegio, con escudo, de quién
> es el horario y de qué gestión. Entra en una sola página apaisada.»

Muestra la vista previa y **cancela** (no hace falta imprimir de verdad).

### 6 · ★ Contraseñas (1 min)

**Sal.** En la portada, **¿Olvidaste tu contraseña?** → escribe `gquispe` →
enviar.

> «No se restablece solo: el carnet no es un secreto, está en la carpeta de
> cada estudiante. El pedido llega a secretaría, que es quien conoce a la
> persona.»

**Entra como `admin`** → la campanita tiene un aviso → **Pedidos de contraseña**
→ se ve el pedido esperando. **No lo atiendas**, solo muéstralo.

### 7 · ★ Cerrar el año escolar (2 min)

**Como `admin`** → **Más → Cerrar el año escolar**.

> «Es la operación más grande del sistema y la única que no se deshace: mueve
> de grado a los 402 estudiantes de una vez.»

Muestra, sin confirmar:
- El aviso de arriba y el recordatorio del respaldo.
- Los 402 con su casilla, agrupados por curso, **todos marcados**; los señalados
  en ámbar son los que tienen materias debajo de 51.
- «Marcar o desmarcar todo el curso».
- Abajo: hay que **escribir el año** para confirmar.

> «El sistema propone; quién repite lo decide la secretaría. Y para confirmar
> hay que escribir el año: un "¿estás seguro?" se aprieta sin leer.»

**No lo confirmes.** Es lo único de la demostración que cambiaría todo.

---

## Si algo sale mal

| Qué pasa | Qué hacer |
|---|---|
| El navegador dice «no se puede conectar» | Espera 10 segundos y recarga (F5). El servidor tarda en arrancar. |
| La ventana negra se cerró | Vuelve a abrir `demo\demo.bat`. |
| «Esa página no existe» | Vuelve a `127.0.0.1:8080` y entra de nuevo. |
| Cerraste la sesión sin querer | Las credenciales están arriba. |
| **Confirmaste el cierre de año sin querer** | No pasa nada grave: es una base de demostración. Para dejarla como estaba, corre otra vez `demo\instalar_demo.bat`. |

---

## Lo que conviene tener dicho

Tres frases para cuando pregunte «¿y esto qué tiene de nuevo?»:

1. **«Lo que pediste está hecho»** — los buscadores filtran mientras se escribe
   y las fechas se eligen en un calendario.
2. **«La secretaría ya no necesita al programador»** — puede dar de alta,
   corregir, dar de baja y cerrar el año desde el sistema, sin entrar al panel
   técnico.
3. **«Cada pantalla dice lo que hay que hacer»** — los paneles pasaron de
   mostrar datos a mostrar pendientes.
