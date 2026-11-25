# Cerrar el año escolar

Es la única operación del sistema que mueve a todo el colegio de una vez y
**no se deshace**. Se hace una sola vez al año, cuando ya no se va a cargar
nada más de la gestión que termina.

## Antes de empezar

1. **Haz un respaldo.** Es la única forma de volver atrás si algo sale mal.
   Está explicado en [Respaldos.md](Respaldos.md); en el colegio, es correr
   `respaldar.bat`.
2. **Termina de cargar las notas.** El sistema señala en ámbar a quien no
   tiene notas cargadas, pero no te impide cerrar: la decisión de quién pasa
   es de la secretaría, no del programa.
3. **Revisa que estén todos los cursos.** Si al colegio le falta, por ejemplo,
   el 4° «C» al que pasarían los de 3° «C», el sistema se niega a cerrar y te
   dice cuál falta. Créalo en *Gestión de datos → Cursos* y vuelve.

## Cómo se hace

En el menú de administración: **Más → Cerrar el año escolar**, o desde
*Gestión de datos*, el primer enlace de la lista.

La pantalla muestra:

- **Qué se lleva al año nuevo.** Los cursos van siempre; los períodos, el
  horario y quién dicta qué son opcionales y vienen marcados. El horario
  cuelga de las asignaciones, así que no se puede copiar uno sin el otro: la
  casilla se desactiva sola.
- **Quién pasa de grado.** Todos los estudiantes, agrupados por curso, con una
  casilla marcada. **Desmarca a quien repite.** Cada curso tiene un botón para
  marcar o desmarcar su lista entera.
- Los señalados en **ámbar** tienen algo que mirar: alguna materia debajo de
  51, o ninguna nota cargada.

Al final hay que **escribir el año que se cierra**. No es un «¿estás seguro?»:
es el único paso que obliga a leer qué año se está cerrando.

## Qué pasa al confirmar

Todo junto, o nada: si algo falla a mitad de camino, no queda nada escrito.

| | |
|---|---|
| Estudiante marcado | Pasa al grado siguiente, con **su mismo paralelo** |
| Estudiante desmarcado | Repite su grado, también con su paralelo |
| Estudiante de 6° marcado | **Egresa**: su cuenta deja de entrar al sistema |
| Estudiante de 6° desmarcado | Repite 6° |

Si el estudiante ya tiene una matrícula activa en el nivel y grado que le
corresponden para el año siguiente, conserva el paralelo en el que fue inscrito.
Si la inscripción contradice la promoción o el egreso, o si ya hay varias
matrículas activas para ese estudiante en la nueva gestión, el cierre se
detiene y señala el caso para que Secretaría lo revise.

Además:

- Se crea la gestión nueva y pasa a ser la activa.
- Las matrículas del año que cerró quedan **inactivas, no borradas**: el
  historial, las notas, la asistencia y los boletines siguen enteros y se
  consultan desde *Gestión de datos*.
- Queda un acta con quién lo hizo, cuándo, y cuántos pasaron, repitieron y
  egresaron.

## Después

- **Un año cerrado no se vuelve a cerrar.** Si entras otra vez, la pantalla te
  ofrece cerrar el año nuevo, que es el acto del año que viene.
- **Los egresados no pueden entrar.** Si alguno necesita su boletín, se lo
  emite la secretaría desde *Boletines de notas*; sus datos están todos.
- Si te equivocaste con alguien —lo pasaste y debía repetir, o al revés—, se
  corrige su matrícula a mano desde *Gestión de datos → Matrículas*. No hace
  falta deshacer el cierre entero.
