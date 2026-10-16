---
name: handoff
description: Reescribe HANDOFF.md con el estado exacto del trabajo al cerrar una sesión, sin que se convierta en un historial. Usar al terminar una sesión de trabajo, antes de un cambio de contexto, y cuando el estado real del proyecto ya no coincida con lo que el archivo dice.
allowed-tools: Read, Grep, Glob, Edit(HANDOFF.md), Bash(git status*), Bash(git log*), Bash(ls *)
---

# Reescribir el HANDOFF

`HANDOFF.md` no es un archivo estándar de Claude Code: es una convención de este
proyecto, y es el **único documento de estado** que tiene. Su valor entero
depende de una propiedad frágil:

> **Se reescribe, no se acumula.** Es el estado actual, no un historial.

Un HANDOFF que crece se convierte en una bitácora, y una bitácora es un
documento de gobierno — exactamente lo que `alcance.md` prohíbe, y exactamente
lo que infló al proyecto anterior a 39 documentos y 35 000 palabras de prosa
contra 3 archivos de resultados.

## Las cinco secciones, y nada más

```markdown
# HANDOFF

> Estado actual, corto. No es un historial — se reescribe, no se acumula.

**Última actualización:** <fecha>
**Fase:** <A..G, o «antes de A»>

## Qué está hecho
## Lo que NO está hecho
## Siguiente acción concreta
## Decisiones abiertas
```

Reglas de contenido:

- **Qué está hecho**: solo lo verificado, con la cifra o el nombre del artefacto
  que lo prueba. Nada de «se avanzó en».
- **Lo que NO está hecho**: lo que falta y **por qué**, cuando la razón es una
  decisión. Un `reports/results/` vacío a propósito es distinto de uno vacío por
  descuido, y el archivo tiene que distinguirlos.
- **Siguiente acción concreta**: numerada, en orden, accionable sin releer el
  README. La primera debe poder empezarse en un minuto.
- **Decisiones abiertas**: con lo que cuesta postergarlas. El idioma del
  entregable cuesta poco ahora y mucho con 3 000 palabras encima; eso se dice.

## Procedimiento

1. Leer el `HANDOFF.md` actual.
2. Leer el estado real: `reports/results/`, `reports/weekly/`, `git status`,
   `git log --oneline -5`. El hook de `SessionStart` ya resume esto; aquí se
   comprueba de primera mano.
3. **Reescribir el archivo completo.** No añadir una sección «sesión del
   <fecha>». Si algo ya pasó y dejó artefacto, pertenece a «qué está hecho» en
   una línea, no a un relato.
4. Si el archivo pasa de **unas 70 líneas**, sobra contenido: lo que se puede
   leer del repositorio no va en el HANDOFF.

## Lo que no va nunca en el HANDOFF

- Historial de sesiones, relato de lo que se intentó, decisiones ya tomadas.
- Cifras que no estén en `reports/results/`. La regla de evidencia vale aquí
  igual que en el README.
- Planes de fases futuras más allá de la siguiente acción. El orden A–G está en
  el README y en `CLAUDE.md`; repetirlo lo desincroniza.
