---
name: registro-semanal
description: Audita la evidencia operacional del proyecto: que la captura semanal realmente corrió, que cada archivo de reports/weekly/ lo escribió el workflow y no una mano, y que las publicaciones del calendario de la fuente tienen su captura. Usar antes de afirmar cualquier cosa sobre operación, antes de congelar, antes de publicar, y cuando pase una semana sin revisarlo.
allowed-tools: Read, Grep, Glob, Bash(git log*), Bash(git show*), Bash(ls *), Bash(uv run *)
---

# Auditar el registro semanal

**Ésta es la skill que existe por una falla concreta.** El proyecto que precede
a éste reclamó 41 ejecuciones operacionales exitosas; las había generado un
script de simulación. Tres fases quedaron retractadas. El patrón: las fases de
ciencia eran reales y las de ingeniería eran las falsificadas, porque **se
falsifica lo que no se puede construir.**

Así que la única afirmación que este proyecto hace sobre operación es
deliberadamente mínima y deliberadamente comprobable:

> Cada corrida agendada deja un archivo fechado en `reports/weekly/`. **Si una
> corrida no ocurrió, no hay archivo.**

Esta skill comprueba que eso siga siendo verdad.

## Procedimiento

### 1. Inventario

Listar `reports/weekly/*.json`. Cada archivo se llama `AAAA-Wnn.json` y contiene
`run_at`, `iso_week`, `channel`, `hub_versions_known`, `newest_hub_version`,
`tip_rows`, `provenance`, `v5_api_key_configured` y `runner`.

### 2. La prueba que importa: ¿quién escribió cada archivo?

Para cada archivo, mirar el commit que lo introdujo:

```bash
git log --diff-filter=A --format='%H %cI %an' -- reports/weekly/<archivo>
```

| Autor del commit | Lectura |
|---|---|
| `github-actions[bot]` | **Evidencia válida.** La corrida ocurrió en el runner |
| Una persona | **Hallazgo grave.** Un registro operacional escrito a mano no es evidencia de operación. Reportarlo y no usarlo |

Y cruzar con el propio contenido: el campo `runner` trae `GITHUB_RUN_ID` cuando
corrió en Actions, y la cadena `local` cuando corrió en una máquina. Un archivo
con `runner: "local"` commiteado por una persona es una corrida local, y se
reporta como tal — **no se presenta como corrida agendada.**

### 3. Conciliación contra el calendario de la fuente

Contar archivos propios no detecta una publicación que nos perdimos: solo
detecta una semana sin corrida. La comprobación que sí lo hace es cruzar contra
el calendario de la fuente.

`/metadata/report_times/` lista las fechas de publicación de la fuente. Para la
ventana cubierta:

| | lectura |
|---|---|
| Publicación en el calendario **con** captura | correcto |
| Publicación en el calendario **sin** captura | **hallazgo.** Se publicó algo y no lo vimos. Decir si el dato es recuperable |
| Captura sin publicación en el calendario | una corrida que no encontró novedad. Deja su archivo igual, y eso es correcto |

Y la distinción que decide qué se puede arreglar:

> **Un dato perdido se reconsulta si la fuente conserva su historia. Una
> ejecución perdida no se recupera nunca.**

Reconsultar un vintage antiguo es legítimo y se etiqueta como lo que es. Correr
hoy el script y nombrar el archivo con la semana pasada **no es** una corrida de
la semana pasada; eso es fabricar evidencia operacional, que es la falla que
originó esta skill.

El calendario tampoco garantiza que cada señal y cada geografía se hayan
republicado en cada fecha: una fecha sin fila para nuestra señal no es una
captura perdida.

### 4. Semanas faltantes

La temporada 2026-2027 va del **7 de octubre de 2026 al 26 de mayo de 2027**.
Comparar las semanas ISO presentes contra las transcurridas desde la primera
corrida. Para cada hueco, decir lo que se sabe:

- ¿Falló el workflow? Está en el historial público de Actions.
- ¿No existía el remoto todavía? Ésa es la razón de los huecos iniciales y
  **se escribe tal cual**, no se rellena.

**Un hueco documentado es honesto; un hueco rellenado es fraude.** El README
dice cuántas corridas hay y cuántas semanas cubre; ninguna de esas dos cifras se
redondea hacia arriba.

### 5. Coherencia del cron

El horario del workflow es **provisional y está marcado como tal** hasta que G0
mida las fechas de publicación reales: hoy `cron: "17 11 * * 3"`, miércoles por
la mañana UTC, después del cierre de reporte a NHSN (martes 23:59 PT) y
deliberadamente fuera de la hora en punto, porque GitHub documenta que el
arranque de cada hora es un periodo de carga alta y que los trabajos en cola
**pueden descartarse**.

Comprobar que los `run_at` caen ahí. Un `run_at` en otro día es una corrida
manual (`workflow_dispatch`) y se dice. Y en repositorio público GitHub
desactiva el schedule tras **60 días sin actividad**: un hueco largo puede ser
eso y no un fallo, y la diferencia se comprueba en el historial de Actions.

### 6. Reportar

- Cuántas corridas válidas, de cuántas semanas transcurridas.
- Qué huecos hay y qué se sabe de cada uno.
- Cualquier archivo cuya procedencia no sea el runner.
- **La cifra que el README puede afirmar**, con su límite al lado.

Si todo está en orden, una línea: tantas corridas, tantas semanas, cero
anomalías.

## Lo que esta skill no hace

- **No escribe nada en `reports/weekly/`.** Los permisos lo deniegan; no es un
  obstáculo que haya que rodear, es la garantía.
- No rellena huecos, ni los explica con suposiciones.
- No corre el workflow para «ponerse al día». Una corrida de hoy no es evidencia
  de una semana pasada.
