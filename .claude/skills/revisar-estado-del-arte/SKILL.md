---
name: revisar-estado-del-arte
description: Comprueba en la web si apareció trabajo nuevo que cambie el posicionamiento del proyecto, y si lo que se atribuye a las nueve referencias sigue siendo cierto. Usar antes de congelar el método, antes de publicar, si pasaron más de dos meses desde la última revisión, y siempre que se vaya a afirmar que algo no está hecho.
allowed-tools: Read, Grep, WebSearch, WebFetch, Edit(referencias.md), Edit(HANDOFF.md)
---

# Revisar el estado del arte

El posicionamiento de este proyecto descansa en trabajo **muy reciente**: ocho
de las nueve referencias son de 2025 y 2026, y cuatro son preprints de autor
único sin venue. Un posicionamiento escrito hace tres meses puede estar
desactualizado, y durante el planteamiento **la verificación corrigió tres
atribuciones falsas y un número**. Esta skill existe para que eso se descubra a
tiempo y no en una entrevista.

## Cuándo usarla

- **Antes de congelar el método.** Si apareció un detector o una política
  mejor, es el momento de saberlo — después ya no se puede cambiar.
- **Antes de publicar.**
- Si pasaron más de **dos meses** desde la última revisión anotada en el HANDOFF.
- **Siempre que se vaya a afirmar que algo no está hecho.** Esa clase de
  afirmación es la más frágil que existe.

## Procedimiento

### 1. Reconfirmar lo que ya se afirma

Para cada entrada de `referencias.md`, comprobar:

- **La fecha de aparición**, no la de la versión que se leyó.
- **Si cambió de estado.** Un preprint puede haberse publicado, y eso cambia su
  peso. Cuatro de las nueve son de autor único sin venue: ésas son las que más
  probablemente cambiaron.
- **Si lo que se le atribuye sigue siendo lo que dice.** Abrir la fuente. **No
  basta el resumen de un buscador** — así entraron las tres atribuciones falsas.
- Caso particular a vigilar: Ahmad (VINTAGE-TS) declaraba que los experimentos
  con ALFRED real y Chronos-2 **no se habían ejecutado**. Si ya se ejecutaron,
  la referencia cambia de protocolo a resultado y hay que reencuadrarla.

### 2. Buscar lo nuevo

Búsquedas en los ejes del proyecto, en modo extendido:

- detección de deriva y **tasas de falsa alarma** · *drift detector false alarm rate*
- **cuándo reentrenar** · *retraining policy concept drift cost*
- datos en **tiempo real contra revisados** · *real-time vintage data forecasting*
- *revision-aware* / *vintage-consistent* en series de tiempo
- revisiones de datos en vigilancia epidemiológica · *backfill nowcasting*
- evaluación de pronósticos del **CDC FluSight hub**

Y comprobar si alguien ya midió **la fracción de alarmas atribuibles a
revisión** — que es la compuerta G2. Si ya está medido, el proyecto
pasa a reproducir o contrastar, y se dice.

### 3. Comprobar lo que el proyecto declara no hecho

Tomar cada afirmación del tipo «nadie ha…» o «el antecedente más cercano es…» y
buscarla **activamente en contra**. Si se encuentra algo:

- **No se defiende la afirmación: se corrige el documento.**
- Y se degrada, si corresponde, de titular a paso. Ver `evidencia.md` §3.

Para esto conviene delegar al subagente `adversario`, que trabaja en contexto
aislado y cuyo único trabajo es encontrar el contraejemplo.

### 4. Juzgar el impacto

| Hallazgo | Qué hacer |
|---|---|
| Un detector o política mejor que los elegidos | Decirlo. **No añadirlo sin decidirlo explícitamente** — el alcance sigue en pie |
| Alguien ya midió la compuerta G2 | Reencuadrar el proyecto a réplica o contraste, y escribirlo |
| Cambió la fecha, el venue o el estado de una referencia | Corregir `referencias.md` y el README |
| Una atribución resulta falsa | Corregirla **y registrar la corrección**, no borrarla |
| Nada relevante | **Decirlo en una línea.** No inflar el reporte |

### 5. Reportar

Qué se buscó, qué se encontró, qué cambia y qué documentos hay que tocar. Si el
posicionamiento sigue en pie, decirlo y anotar la fecha de la revisión en
`HANDOFF.md`.

## Lo que esta skill no hace

- No reescribe los documentos por su cuenta: reporta y espera instrucción.
- No añade métodos al plan.
- No busca justificaciones para lo que el proyecto ya afirma. **Busca lo
  contrario**, que es para lo que sirve.
