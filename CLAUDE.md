# revision-aware-monitoring · When the Past Moves

> Instrucciones del proyecto. Se cargan en toda sesión, junto con
> `.claude/rules/*.md`. Si algo aquí contradice una regla, **manda la regla**:
> este archivo orienta, las reglas obligan.

## Qué es este proyecto

Un modelo en producción lo vigila un monitor. Cuando el monitor dispara, la
respuesta estándar es reentrenar — y eso supone que lo que cambió fue el mundo.
Pero el pasado registrado también se mueve: los valores llegan tarde y se
corrigen semanas después del periodo que describen. Y además cambia **quién
reporta**: en esta serie varía el número de hospitales que envían datos, así que
una subida de admisiones puede venir de que reportaron más.

**La pregunta, una sola:**

> Cuando se evalúa un modelo con registros revisables, ¿en qué medida la
> información sobre revisiones y cobertura cambia las recomendaciones de
> mantenimiento, y bajo qué condiciones de costo se justifica intervenir?

El entregable **es el `README.md`**, en inglés, con el repositorio como respaldo
reproducible. No hay otro entregable. La especificación congelada que gobierna
el método es `When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt`.

## Lo que hay que leer, en este orden

1. **`HANDOFF.md`** — el estado exacto y la siguiente acción concreta. **Es el
   primer archivo que se lee en cada sesión.**
2. **`README.md`** — el planteamiento completo y los límites.
3. **`.claude/rules/`** — las cuatro reglas vinculantes: `alcance.md` (qué queda
   fuera y qué significa terminado), `datos.md` (las dos puertas, los siete
   conceptos de tiempo, el denominador), `metodo.md` (el estimando, el 2x2, la
   congelación), `evidencia.md` (cifra→script→clave, E1/E2/E3, referencias).
4. **`referencias.md`** — las fuentes verificadas y las correcciones registradas.

## El entorno: siempre virtual, siempre `uv`

**Nunca se invoca el Python global.** Lo impide `.claude/hooks/venv_guard.py`.

```bash
uv sync --locked --extra dev
uv run ruff check .
uv run pytest
uv run python scripts/weekly_capture.py
```

`uv.lock` está versionado y CI corre `--locked`: si el lock y `pyproject.toml` se
separan, CI falla, que es el comportamiento deseado. El `Makefile` recoge la
misma secuencia, pero **`make` no está instalado en esta máquina**.

La clave de la API se lee de `DELPHI_EPIDATA_KEY`. Sin ella el acceso es anónimo
y está limitado a 60 peticiones por hora.

## Las compuertas, y dónde está la decisión

| Compuerta | Produce |
|---|---|
| **G0** | Viabilidad y procedencia: ventanas reales de `report_time`, reconstrucción `archive`→`snapshot`, contraste con el git del hub |
| **G1** | El ciclo completo: una predicción inmutable, una señal, una recomendación y un manifiesto **reales** |
| **G2** | **La compuerta.** N1 y el cruce 2x2, con incertidumbre y límites |
| **G3** | Trayectorias de políticas y región de costos — **solo si G2 lo autoriza** |

**Cada entrega vale por sí sola.** Si el proyecto se detiene al cerrar G0, lo que
hay sigue siendo publicable. Si G2 encuentra la discordancia pequeña o el
soporte insuficiente, **ése es el resultado** y el proyecto cierra corto.

La captura semanal corre **desde el principio, en paralelo**: un dato se
reconsulta si la fuente lo conserva, una corrida que no ocurrió no.

## Las decisiones ya cerradas, que no se reabren

- **Unidad:** un modelo nacional, una recomendación semanal. Los estados
  caracterizan; no son réplicas de esa decisión ni entran al denominador de N1.
- **N1 es discordancia de recomendaciones**, no «valor de información».
- **El denominador es exógeno** a lo que hicieron las ramas, y ABSTENERSE es una
  categoría, no un dato perdido.
- **Cinco acciones:** CONTINUAR, ESPERAR_MADUREZ, INVESTIGAR_DATO,
  EVALUAR_REENTRENO, ABSTENERSE. Una recomendación no es un despliegue.
- **Cruce 2x2** (R × C), no ablación en cadena.
- **Pérdida absoluta escalada** con `s_dev` fija de calibración retrospectiva.
  **No WIS**: el hub puntúa cuantiles, este prototipo emite puntos.
- **`c` es una frontera**, y `c_star` solo si el cruce es positivo y estable.
- **Universo elegible** declarado desde el mandato de noviembre de 2024.
- **`CONCEPT_DRIFT` no se declara**: queda como explicación residual posible.

## Cómo continuar una sesión

1. Leer `HANDOFF.md`. El hook de `SessionStart` ya imprime el estado mecánico
   —compuertas con artefacto, congelación, capturas, clave, remoto—, pero el
   juicio sobre qué sigue está en el HANDOFF.
2. Hacer **una** cosa de «Siguiente acción concreta».
3. Si eso produce cifras: añadir la fila al verificador **en el mismo commit**
   que ponga la cifra en el documento.
4. Antes de cerrar, invocar `/handoff`.

## Lo que no se hace, nunca

- **Crear un documento de gobierno nuevo.** El README crece y nada más; la
  lectura organizacional es una sección suya. Si parece necesario un documento
  nuevo, es una señal de alarma, no una tarea.
- **Escribir una cifra que no produjo un script del repositorio**, ni redondear
  de memoria, ni reusar un número de la conversación.
- **Confundir «verificado documentalmente» con «medido en datos».**
- **Citar una referencia sin abrirla.**
- **Convertir un hallazgo en tesis.** Si parece lo bastante importante para ser
  el titular, ésa es la señal de degradarlo a paso.
- **Leer `data/` sin pasar por `revmon.panel`, o importar un cliente de red
  fuera de `revmon.sources`.**
- **Editar a mano cualquier cosa bajo `data/` o `reports/`.**
- **Presentar un replay como una corrida, o una propuesta como experiencia.**

## El harness: qué pieza resuelve qué

| Pieza | Para qué |
|---|---|
| **`.claude/rules/*.md`** | Los cuatro límites vinculantes, cargados en toda sesión |
| **`hooks/venv_guard.py`** | Bloquea el Python global |
| **`hooks/puerta_unica.py`** | Tras cada edición: nadie llega al dato fuera de `panel.py` ni importa un cliente de red fuera de `sources.py` |
| **`hooks/estado_sesion.py`** | Imprime el estado mecánico al arrancar |
| **`skills/auditar-cifras`** | El rastro cifra → artefacto → clave, y las etiquetas E1/E2/E3 |
| **`skills/registro-semanal`** | Que la captura corrió de verdad, y la conciliación contra el calendario de publicaciones |
| **`skills/congelar-metodo`** | La congelación, una sola vez, con sus dos cotas |
| **`skills/revisar-estado-del-arte`** | Si el posicionamiento sigue en pie |
| **`skills/handoff`** | Reescribir el estado sin que se vuelva bitácora |
| **`agents/verificador-de-fuentes`** | Abrir la fuente primaria y devolver un veredicto |
| **`agents/adversario`** | Buscar activamente en contra de lo que el proyecto afirma |
| **`settings.json`** | Permisos y cableado de los hooks |

**Hooks para lo mecánico, skills para lo que exige juicio.** Un hook debe poder
fallar cerrado sin equivocarse; detectar «esta cifra necesita respaldo» no cumple
eso, así que vive en una skill.

Los hooks corren con el **Python global** y solo usan la biblioteca estándar. No
es una excepción a la regla del entorno: es su condición, porque `venv_guard`
tiene que poder ejecutarse antes de que `.venv` exista.

**`freeze_guard.py` se retiró.** Vigilaba la capa equivocada: hacía `re.search`
sobre el texto del comando, bloqueaba escribir prosa y no dejaba desarrollar los
scripts de evaluación. El control vive ahora en el dato (`panel.as_of_view` y los
modos de `ReplayMode`), con pruebas de propiedades. El hueco que queda hasta G1
está declarado en `.claude/rules/metodo.md`.

No hay MCP, ni equipos de agentes, ni plugin, y no se añaden: las razones están
en `alcance.md`, en una línea cada una.

## La memoria automática

Vive fuera del repositorio y guarda lo que es del **autor**: perfil,
preferencias, correcciones que ha dado. Lo que es del **proyecto** va aquí o en
`.claude/rules/`, que viajan con el repositorio. La memoria no se puede revisar
en un diff, y ésa es la razón de la división.

## El idioma

El `README.md` está en inglés — lo fija la especificación congelada y dejó de ser
una decisión abierta. La documentación de trabajo, las reglas, las skills y el
HANDOFF están en español. El código y sus docstrings, en inglés.
