---
name: auditar-cifras
description: Audita que cada cifra de README.md y HANDOFF.md se pueda rastrear hasta un script del repositorio y su JSON en reports/results/, que tenga su fila en scripts/verify_results.py, y que cada referencia esté verificada. Usar antes de dar por terminada una fase, antes de congelar, antes de publicar, y siempre que se toque un script de scripts/ o un módulo de src/revmon/ que un documento describa.
allowed-tools: Read, Grep, Glob, Bash(uv run *), Bash(git diff*), Bash(git log*)
---

# Auditar cifras y referencias

Hace cumplir `.claude/rules/evidencia.md`. Es una auditoría: **reporta, no
corrige en silencio.**

## El rastro que se audita

```
scripts/NN_*.py  →  reports/results/NN_*.json  →  la cifra en el documento
                                              →  la fila en verify_results.py
```

Toda cifra debe poder señalarse como **script → archivo → clave**, y debe tener
su fila en el verificador. **Una cifra en el README sin su fila es un defecto**,
no una excepción: el verificador es lo que hace que el rastro no dependa de la
memoria de nadie.

## Procedimiento

### 1. Reunir las afirmaciones

Recorrer `README.md`, `HANDOFF.md`, `CLAUDE.md` y cualquier `.md` del
repositorio fuera de `.claude/`, y extraer:

- Toda cifra: fracciones, conteos, tamaños de muestra, errores estándar, la
  política de madurez y su malla, `s_dev` y su ventana de calibración, la malla
  de costos, `c_star`, los denominadores de N1 y las abstenciones, y las ventanas
  de cobertura temporal de las fuentes.
- Toda referencia bibliográfica, con su fecha y su venue.
- Toda afirmación comparativa («mejor que», «dispara menos», «gana en N de M»).

### 2. Rastrear cada cifra

Leer los JSON de `reports/results/` y buscar la clave que la produce.

| Estado | Significado |
|---|---|
| **Respaldada** | Existe la clave, el valor coincide, y hay fila en el verificador |
| **Sin fila** | El JSON la respalda pero el verificador no la rastrea — defecto |
| **Desfasada** | Existe la clave y da otro valor |
| **Huérfana** | Ningún JSON la contiene |
| **Atribuida** | Es de trabajo publicado; entonces verificar la cita, no el JSON |
| **No verificable** | El script existe pero no se pudo correr; decir por qué |

Para recomprobar: `uv run python scripts/verify_results.py`. Nunca el
Python global — hay un hook que lo bloquea.

**Si una cifra proviene de la cohorte confirmatoria y no existe
`reports/results/frozen_method.json`, es un hallazgo grave, no una cifra sin
fila:** significa que se evaluó antes de congelar. Reportarlo como tal. El
control vive en el contrato as-of del dato, así que esta comprobación es la
segunda línea y no la primera.

### 3. Revisar las referencias

- ¿Lleva ✓ y fecha de verificación en `referencias.md`?
- ¿Alguna ✓ le atribuye a la fuente una afirmación que no hace? Caso conocido:
  la frase «drift points are typically unknown in real-world data» **no está**
  en el abstract de Cerqueira y coautores; la puso un buscador.
- ¿Está dicho el venue y la provenance donde se usa? Dos de las nueve son
  revisadas por pares; cuatro son preprints de autor único.
- ¿Hay afirmaciones que **suenan** a literatura y no citan nada?

### 4. Revisar las etiquetas de evidencia

Toda afirmación visible lleva su clase, y las confusiones tienen una dirección
previsible: hacia arriba. Marcar:

- Una afirmación **E2** (replay, contrafactual, fallo inyectado) presentada como
  si fuera **E1**. Un snapshot reconstruido hoy no prueba que el sistema corriera
  en esa fecha.
- Una afirmación **E3** (rol, criterio de aprobación, arquitectura de evolución)
  presentada como experiencia, acuerdo o decisión tomada por alguien.
- **«Verificado documentalmente» pasando por «medido en datos».** Haber leído que
  un endpoint se comporta de un modo no es haberlo comprobado; la contradicción
  abierta sobre `/archive/` es el caso vivo.
- Los **tres nombres prohibidos** de `evidencia.md` §4: «valor de información»
  para una discordancia, «falsa alarma» para una recomendación que cambia bajo un
  contrafactual, y «concept drift demostrado» para un residuo sin explicar.
- Un `c` o un `c_star` presentado como dinero, ahorro o impacto sanitario.

### 5. Revisar el encuadre

El marco es demostración de oficio, no descubrimiento. Marcar toda redacción que:

- Reclame originalidad, o presente un método publicado como propio.
- **Convierta un hallazgo en tesis** en lugar de dejarlo como paso — el modo de
  falla propio de este portafolio, descrito en `evidencia.md` §3.
- Concluya más de lo que los datos permiten. «En una temporada de vigilancia de
  influenza en Estados Unidos, el detector X disparó por revisión en tal
  fracción» es correcto; «los monitores de la industria están mal» no lo es.
- Omita un resultado negativo, ambiguo o peor que la referencia simple.
- Afirme algo sobre operación que `reports/weekly/` no respalde. Para eso está
  `/registro-semanal`.
- Publique un resultado sin sus límites al lado.

### 6. Reportar

Una tabla, una fila por hallazgo: ubicación (`archivo:línea`), afirmación,
estado, y qué hace falta. Primero lo más grave.

**Si todo está respaldado, decirlo en una línea.** No inventar hallazgos para
que la auditoría parezca productiva.

## Lo que esta skill no hace

- No corrige los documentos. Reporta y espera instrucción.
- No añade cifras ni corre análisis que no existan.
- No juzga si el análisis es correcto, solo si lo escrito está respaldado por lo
  que hay en el repositorio.
