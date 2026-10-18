# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 18 de octubre de 2026
**Fase:** **G0 y G1-core cerradas.** P0 y P1 del plan G1-MP ejecutadas y
auditadas. Siguiente: **P2 (modelado convencional)**; la compuerta sigue en G2.

## Qué está hecho

- **G0, veredicto PROCEED** — `reports/results/00_source_feasibility.json`. Sus
  cuatro hallazgos y el universo elegible están en el README y en `datos.md`.
- **G1-core ejecutada de verdad** — `reports/results/01_vertical_slice.json`.
  `s_dev = 4967.25` sobre 24 pares, 14 cortes de replay, 30 predicciones
  inmutables, figura de tres paneles, y una corrida observada que recomienda
  `INVESTIGAR_DATO`. `load_as_of` reconstruye desde **una** consulta de
  `/archive/`, y `confirmatory=True` falla sin acta antes de tocar la red.
- **El producto es un nowcast, no un pronóstico a una semana.** A horizonte +1
  `PRE_WEEK_FORECAST` es inalcanzable: con `W` la última semana visible y
  `lag ≥ 1`, el objetivo `W+7` abre en `W+1`, así que haría falta `corte ≤ W`
  mientras `W ≤ corte−1`. `classify_emission` lo clasifica y `emission_audit` lo
  cuenta: **0 pre-semana**, 1 `intra_week_nowcast`, 29 `post_event`.
- **Soporte medido** — `reports/results/01_modeling_support.json`: **100** cortes
  semanales programados, los 100 con estado `complete`, **93** elegibles con la
  política declarada de 45 días (91 a 60, 87 a 90). Retraso de publicación
  mediana 7 días, **máximo 49**. La viabilidad de entrenamiento por candidato
  queda `pending_P2`, separada a propósito.
- **Dos documentos rectores versionados y sellados** por SHA-256 en el
  manifiesto, con `schema_version`: un manifiesto antiguo se verifica bajo su
  propio esquema y no se le exige un campo posterior. La excepción está
  declarada en `alcance.md`; `git ls-files '*.txt'` devuelve exactamente dos.
- **`parse_week_end` exige sábado** y **`scheduled_cut` ancla el calendario** a
  esa frontera, corrigiendo un defecto hallado al ejecutar lo primero: los cortes
  se derivaban de `datetime.now()`, así que correr en domingo emitió un juego
  paralelo de 15 predicciones. Se conservan, con el cruce registrado.
- **26 cifras rastreadas** y **61 pruebas**, todo verde. CI corre `--locked`.

## Lo que NO está hecho

- **P2–P4 sin empezar**: no hay Ridge, LightGBM ni AutoGluon, ni
  `01_model_comparison.json` ni `01_model_selection.json`. Es deliberado — el
  plan los puso detrás de la compuerta de P0/P1, ya superada.
- **`selection_config_sha256` es `null`**: la configuración de selección no
  existe todavía. Ausente significa «aún no declarada», nunca «declarada vacía».
- **El método no está congelado** y el acta `frozen_method.json` no existe. La
  escribe la persona; los permisos deniegan al modelo escribir en `reports/`.
- **`DELPHI_EPIDATA_KEY` no es secreto del repositorio**: el registro semanal
  marca `v5_api_key_configured: False`, así que el bot corre anónimo a 60
  peticiones/hora. Local sí está configurada.
- **Una sola captura semanal** (`2026-W42`), y el horario del cron sigue
  marcado como provisional.

## Siguiente acción concreta

1. **Registrar la clave como secreto del repositorio.** Es tarea de la persona,
   cuesta un minuto y cada semana sin ella es evidencia operacional degradada.
2. **P2, en este orden:** EDA mínima sobre los 93 orígenes; M0 revisado; Ridge
   con `Pipeline` y los dos conjuntos F0/F1 predeclarados; comparación
   rolling as-of sobre orígenes comunes. LightGBM solo si el soporte lo
   justifica. Nada de AutoGluon todavía: eso es P3 y exige smoke test.
3. **Declarar antes de P4**, en config versionada y sellada: `delta_min`,
   bloques disjuntos de 4 semanas, `n ≥ 12` y la receta de desempate.
4. **Redefinir las dos señales R y C a igual rezago** antes de G2. Ambas disparan
   estructuralmente en el borde de la serie, así que los umbrales declarados
   (25 %, 2 puntos) no son informativos tal como están.

## Decisiones abiertas

- **Estratificación por horizonte.** Ya no es hipótesis: el rezago medido va de
  7 a 49 días, así que el horizonte efectivo varía y una pérdida promediada
  entre cortes mezcla horizontes. Se declara antes de usarla, en G2.
- **Malla de umbrales para N1** en lugar de un punto, y **soporte mínimo
  predeclarado**. El techo es 93 orígenes; se fija antes de ver el resultado.
- **Qué hacer con los dos calendarios de predicciones.** Las 15 del calendario
  desviado son emisiones reales e inmutables. Lo abierto es si entran al
  denominador de la comparación de P2 o se excluyen por declaración previa.
