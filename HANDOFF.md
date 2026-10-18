# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 18 de octubre de 2026
**Fase:** **G0 y G1-core cerradas.** P0 y P1 del plan G1-MP ejecutadas y
auditadas, más el ajuste de trazabilidad previo a P2. **P2 esperando
autorización**; la compuerta sigue en G2.

## Qué está hecho

- **G0, veredicto PROCEED** — `00_source_feasibility.json`. Sus cuatro hallazgos
  y el universo elegible están en el README y en `datos.md`.
- **G1-core ejecutada de verdad** — `01_vertical_slice.json`: `s_dev = 4967.25`
  sobre 24 pares, 14 cortes de replay, 30 predicciones inmutables, figura de
  tres paneles, corrida observada con `INVESTIGAR_DATO`. `load_as_of`
  reconstruye desde **una** consulta de `/archive/`, y `confirmatory=True` falla
  sin acta antes de tocar la red.
- **El producto es un nowcast, no un pronóstico a una semana.** A horizonte +1
  `PRE_WEEK_FORECAST` es inalcanzable por aritmética; la derivación está en el
  docstring de `classify_emission`. Contado: **0 pre-semana**, 1
  `intra_week_nowcast`, 29 `post_event`.
- **Soporte medido** — `01_modeling_support.json`: **100** cortes semanales
  programados, los 100 `complete`, **93** elegibles a 45 días (91 a 60, 87 a
  90). Retraso de publicación mediana 7 días, **máximo 49**. La viabilidad de
  entrenamiento por candidato queda `pending_P2`, separada a propósito.
- **Dos documentos rectores sellados** por SHA-256 con `schema_version`: un
  manifiesto antiguo se verifica bajo su propio esquema y no se le exige un
  campo posterior. Excepción declarada en `alcance.md`; `git ls-files '*.txt'`
  devuelve exactamente dos.
- **El calendario de cortes está anclado** al sábado de la fuente
  (`scheduled_cut`) y `parse_week_end` lo exige. Corrige que los cortes se
  derivaran de `datetime.now()`: correr en domingo emitió un juego paralelo de
  15 predicciones, que se conservan con el cruce registrado.
- **Un registro semanal por ejecución** — `AAAA-Wnn__<run>__a<n>.json`. Antes el
  nombre era la semana y una segunda corrida pisaba la primera. La conciliación
  lee los dos esquemas y cuenta **semanas ISO distintas**, no ficheros. Hoy: 3
  capturas en 1 semana, 2 locales (`scheduled_runner: false`).
- **`DELPHI_EPIDATA_KEY` es secreto del repositorio** y `weekly.yml:49-50` lo
  pasa al entorno; el runner `39106257967` lo confirma. Pero eso dice que la
  variable **está presente**, no que algo se autenticara: la captura lee el hub
  y no hace ninguna petición a V5.
- **Decisiones A y B registradas** en la sección 6 BIS del plan G1-MP, con fecha
  y antes de que exista resultado alguno de candidatos.
- **26 cifras rastreadas** y **72 pruebas**, todo verde. CI corre `--locked`.

## Lo que NO está hecho

- **P2–P4 sin empezar**: no hay Ridge, LightGBM ni AutoGluon, ni
  `01_model_comparison.json` ni `01_model_selection.json`. Es deliberado.
- **`selection_config_sha256` es `null`**: la configuración de selección no
  existe. Ausente significa «aún no declarada», nunca «declarada vacía».
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **Una sola semana cubierta** (`2026-W42`); el cron sigue provisional.

## Siguiente acción concreta

1. **Autorizar P2.** Está parado esperando revisión del ajuste de trazabilidad
   y de las decisiones A y B.
2. **P2, en este orden:** EDA mínima sobre los 93 orígenes; M0 revisado; Ridge
   con `Pipeline` y los conjuntos F0/F1 predeclarados; comparación rolling as-of
   sobre orígenes comunes. LightGBM solo si el soporte lo justifica. Nada de
   AutoGluon: eso es P3 y exige smoke test.
3. **Declarar antes de P4**, en config versionada y sellada: `delta_min`,
   bloques disjuntos de 4 semanas, `n ≥ 12` y la receta de desempate.
4. **Redefinir las señales R y C a igual rezago** antes de G2. Ambas disparan
   estructuralmente en el borde, así que los umbrales declarados (25 %, 2
   puntos) no son informativos tal como están.

## Decisiones abiertas

- **Malla de umbrales para N1** en lugar de un punto, y **soporte mínimo
  predeclarado**. El techo es 93 orígenes; se fija antes de ver el resultado.
- **Cómo se estratifica el horizonte efectivo.** La Decisión B fija *que* se
  distinguirá; los cortes concretos de la estratificación se declaran en P2,
  antes de usarlos.
