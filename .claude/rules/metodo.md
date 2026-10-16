# Regla: cómo se eligen y se juzgan los métodos

## El criterio

> **Los métodos se juzgan por las decisiones que producen, no por si detectan
> el cambio.**

Es el criterio de Regol y coautores (ICML 2025), en sus palabras:
*«distribution shift detection falls short as it cannot account for the cost
trade-off»*. Un detector con sensibilidad impecable puede ser la elección
equivocada si dispara sobre revisiones, porque lo que se paga es el
reentrenamiento, no la detección.

De ahí que la unidad medida sea **la recomendación**, no la alarma: una alarma
que cambia sin cambiar la recomendación no cuesta nada.

## La unidad de decisión, cerrada

Un **modelo nacional**, una **recomendación semanal** de mantenimiento, en
cortes programados de antemano. Los datos estatales caracterizan cobertura,
revisiones y discrepancias entre canales, pero **cincuenta estados no son
cincuenta réplicas de la decisión sobre el modelo nacional**: sumar filas
estatales al denominador de N1 cambiaría el estimando mientras finge que es la
misma cantidad.

El soporte será pequeño y eso se reporta, no se compensa inflando *n*.

## El cruce factorial 2x2

Dos factores de información, cruzados, con todo lo demás idéntico en el mismo
corte: **R** (historial de revisiones disponible) y **C** (indicadores de
cobertura disponibles).

```
d_00  base          d_10  +R          d_01  +C          d_11  +R +C
```

Cruzado y no en cadena, porque una ablación secuencial mide el aporte de la
cobertura *condicionado* a haber introducido antes la revisión, y ese número
depende del orden. El cruce elimina esa dependencia y hace observable la
interacción: **si la cobertura solo aporta cuando no hay historial de
revisiones, el sistema especializado es redundante**, y eso es un hallazgo.

Cuesta un parámetro de configuración y un bucle de cuatro iteraciones. Si
empieza a exigir código nuevo por rama, se salió del alcance y se vuelve a dos.

## El estimando, y cómo NO se llama

**N1 = D(11,00)**, la proporción de cortes elegibles en que la recomendación
cambia.

- Se llama **discordancia de recomendaciones**. **No** «valor de información»:
  eso tiene un significado decision-teórico preciso —ganancia esperada de
  utilidad por observar una señal antes de decidir— y esto no es eso. Mide
  **que** la recomendación cambió, no que mejorara.
- **No** «falsa alarma»: una recomendación que cambia en un contraste no
  identifica la causa de la original.
- La discordancia es un funcional **no aditivo** de las ramas, así que los dos
  contrastes de interacción no tienen por qué coincidir y ninguno es un término
  lineal. Se reportan los dos, como descriptivos, y no se suman.

### El denominador es exógeno

`T_evaluable` se define por criterios **ajenos a lo que hicieron las ramas**:
fuente, modelo y datos mínimos para ejecutar la regla base. Exigir que las
cuatro ramas emitan una decisión «normal» para incluir un corte sería
**condicionar en una variable posterior al tratamiento**, y entonces la
información que se mide selecciona su propio denominador.

**ABSTENERSE es una categoría**, no una observación perdida. Las tasas
condicionadas a intervención usan el mismo subconjunto en numerador y
denominador, y se informa su tamaño aunque valga cero.

## El orden: medir → explicar → descartar

Los diagnósticos van **después** de la comparación. Usarlos como filtro previo
invertiría el criterio.

## Lo que se declara de antemano

1. **La política de madurez**, con su malla de sensibilidad `(45, 60, 90)`.
2. **La métrica de pérdida y la escala `s_dev`**, calculada en una ventana de
   calibración retrospectiva, la misma para todas las políticas y todos los
   periodos, **nunca actualizada con el futuro**. Si no puede calcularse una
   `s_dev` positiva, el fallback a MAE absoluto está predefinido; no se elige el
   denominador mirando el conjunto confirmatorio.
3. **La malla de costos** sobre la que se reporta la frontera.
4. **Los umbrales del monitor y la precedencia entre reglas.**

Ninguno se elige mirando la cohorte confirmatoria.

**No se usa WIS.** El hub puntúa pronósticos cuantílicos con WIS relativo sobre
23 cuantiles; este prototipo emite puntos. Tomarlo prestado obligaría a producir
cuantiles por prestigio.

## El costo es una frontera, no un número

```
L_p(c) = e_p + c * r_p        Delta(c) = (e_A - e_P) + c * (r_A - r_P)
```

Se reporta el **conjunto de `c >= 0`** donde la política especializada pierde
menos, más los casos de dominancia. `c_star` solo si hay cruce **positivo y
estable**: si el denominador es cercano a cero el umbral es inestable, y si la
propia regla depende de `c` las trayectorias se recalculan y la frontera no es
necesariamente lineal. `c` está en unidades de pérdida predictiva por periodo,
**no en dinero ni en salud**.

## Las trayectorias completas

Cada política se simula desde el mismo estado inicial: reentrenar cambia el
modelo, y el modelo cambia las predicciones, los errores y las alarmas de las
semanas siguientes. **Aplicar un mismo vector de alarmas a las cuatro políticas
invalidaría la comparación.**

Por eso G3 lleva por omisión **solo dos configuraciones de información** (00 y
11): cuatro por cuatro serían dieciséis trayectorias. La interacción medida en
G2 decide si entra una tercera.

## La congelación

Los vintages retrospectivos son para desarrollar; la cohorte confirmatoria se
evalúa **una sola vez** con el método fijado. No se pueden mirar antes porque no
han ocurrido.

El acta es `reports/results/frozen_method.json` y la escribe **la persona**: los
permisos deniegan `Edit(reports/**)`, así que el modelo no puede escribir el
archivo que lo desbloquearía. Su forma exacta y sus precondiciones están en la
skill `/congelar-metodo`.

### El sello necesita dos cotas

Una **fecha de commit propia no es prueba**: la del committer es una variable de
entorno que fija quien commitea.

- **Cota inferior:** incluir en el acta un valor externo que antes no existía
  —sha del hub, `report_time` máximo conocido— prueba que no se creó *antes* de
  que ese valor existiera.
- **Cota superior:** exige un testigo externo al congelar — un sello RFC 3161 de
  una autoridad de tiempo, o una prueba OpenTimestamps **completada**, que no es
  lo mismo que enviada: una prueba pendiente no es prueba hasta que `ots upgrade`
  la cierra contra la cadena.

Con las dos, el orden «método fijado antes de las semanas evaluadas» se verifica
sin confiar en este repositorio. Y ninguna de las dos demuestra que el autor no
viera otros datos: el aislamiento sigue siendo necesario.

Los permisos deniegan `git commit --amend`, `git rebase` y `git push --force`
porque el commit de congelación **es** la evidencia.

### El guardián retirado, y qué lo sustituye

`.claude/hooks/freeze_guard.py` **se retiró**. Hacía `re.search` sobre el texto
del comando, así que vigilaba la capa equivocada: bloqueaba escribir prosa que
mencionara un nombre de archivo e impedía desarrollar los propios scripts de
evaluación sobre datos de desarrollo. Un guardián que grita en falso enseña a
ignorarlo.

Lo sustituye el control **en el dato**: `panel.as_of_view` con los modos de
`ReplayMode`, probado con propiedades generadas y no con tres ejemplos.

**El hueco se declara en lugar de taparse:** hasta que G1 complete `load_as_of`,
lo único que protege la cohorte confirmatoria es que esas semanas **no han
ocurrido**, más que el hook de arranque informe el estado de congelación en cada
sesión. Cerrarlo es criterio de aceptación de G1 — `load_as_of` rechaza un corte
confirmatorio si el acta no existe o su hash no coincide — y está escrito en el
contrato de esa función.

## El resultado negativo es un resultado

El antecedente ejecutado más cercano (Agyekum y Obese, 2026) encuentra el efecto
agregado **pequeño e indistinguible** bajo pruebas de Diebold-Mariano. La
expectativa de este proyecto es modesta y está escrita antes de medir.

Las tres conclusiones admisibles cierran el caso:

- **A.** Hay una región de costos donde la política especializada pierde menos.
- **B.** La sencilla domina, empata o no puede mejorarse justificadamente.
- **C.** El soporte no permite distinguir.

En B y C se publican los límites y **no se amplía el alcance para rescatar la
compuerta.** Y la sección de **dónde falla** no es opcional: en qué fracción de
periodos comparables la política elegida decide peor que la simple, con su
denominador y la magnitud, no solo la frecuencia.
