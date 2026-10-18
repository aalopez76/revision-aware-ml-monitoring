# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 18 de octubre de 2026
**Fase:** **G0, G1-core y P2 cerradas.** La comparación de modelos terminó sin
promoción: **M0 sigue siendo el Champion**. Siguiente: **G2**, que es la
compuerta. P3 (AutoGluon/Chronos) queda opcional y sin empezar.

## Qué está hecho

- **G0, veredicto PROCEED** — `00_source_feasibility.json`. Sus cuatro hallazgos
  y el universo elegible están en el README y en `datos.md`.
- **G1-core ejecutada de verdad** — `01_vertical_slice.json`: `s_dev = 4967.25`
  sobre 24 pares, 14 cortes de replay, 30 predicciones inmutables, corrida
  observada con `INVESTIGAR_DATO`. `load_as_of` reconstruye desde **una**
  consulta de `/archive/` y `confirmatory=True` falla sin acta antes de la red.
- **El producto es un nowcast, no un pronóstico a una semana.** A horizonte +1
  `PRE_WEEK_FORECAST` es inalcanzable por aritmética (derivación en el docstring
  de `classify_emission`): **0 pre-semana**, 1 nowcast, 29 `post_event`.
- **Soporte medido** — `01_modeling_support.json`: **100** cortes programados,
  los 100 `complete`, **93** elegibles a 45 días (91 a 60, 87 a 90). Retraso de
  publicación mediana 7 días, **máximo 49**.
- **Dos documentos rectores sellados** por SHA-256 con `schema_version`: un
  manifiesto antiguo se verifica bajo su propio esquema. Excepción declarada en
  `alcance.md`.
- **El calendario de cortes está anclado** al sábado de la fuente
  (`scheduled_cut`), exigido por `parse_week_end`. Corrige que se derivaran de
  `datetime.now()`: correr en domingo emitió 15 predicciones paralelas, que se
  conservan con el cruce registrado.
- **Un registro semanal por ejecución** — `AAAA-Wnn__<run>__a<n>.json`. La
  conciliación lee los dos esquemas y cuenta **semanas ISO distintas**, no
  ficheros. Hoy: 3 capturas en 1 semana, 2 locales.
- **`DELPHI_EPIDATA_KEY` es secreto del repositorio** y `weekly.yml:49-50` lo
  pasa al entorno. Eso dice que la variable **está presente**, no que algo se
  autenticara: la captura lee el hub y no pide nada a V5.
- **Decisiones A y B registradas** en la sección 6 BIS del plan G1-MP, con fecha
  y antes de que existiera resultado alguno de candidatos.
- **P2 cerrada sin promoción** — `01_model_comparison.json`. Sobre **55 semanas
  objetivo distintas**: M0 `0.3146`, `ridge_F1` `0.3781`, `ridge_F0` `0.6029`.
  Emparejado, `ridge_F1` gana 8 semanas y pierde 47. F1 mejora sobre F0 y
  ninguno sobre M0. Alpha y la receta se eligieron **solo en desarrollo**,
  cortado donde se fijó `s_dev`. Los tres candidatos cubren los 61 orígenes sin
  exclusiones, así que `MIN_TRAIN_ROWS` nunca ató.
- **Dos hallazgos de la estratificación de la Decisión B:** el estrato de
  publicación tardía es **una interrupción vista seis veces** (misma semana
  visible, mismo objetivo, misma etiqueta), soporte efectivo 1; y eso inflaba el
  denominador — 61 orígenes comunes contra **55** semanas distintas, porque una
  interrupción de siete semanas hizo que `2025-09-27` fuera el objetivo de
  siete orígenes. Se colapsa al origen **más temprano**, por calendario.
- **35 cifras rastreadas**, **85 pruebas** y **6 sellos**, todo verde.

## Lo que NO está hecho

- **P3 y P4 sin empezar**: no hay LightGBM ni AutoGluon, ni
  `01_model_selection.json`. P4 queda sin objeto mientras no haya candidato que
  promover; P3 es opcional y exige smoke test antes de instalar nada.
- **`selection_config_sha256` es `null`**: la configuración de selección no
  existe. Ausente significa «aún no declarada», nunca «declarada vacía».
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **Una sola semana cubierta** (`2026-W42`); el cron sigue provisional.

## Siguiente acción concreta

**G2 es lo único que queda en el camino principal, y es la compuerta.** Tres
cosas se declaran antes de calcularla, en config versionada:

1. **Redefinir las señales R y C a igual rezago.** Ambas disparan
   estructuralmente en el borde de la serie, así que los umbrales actuales
   (25 %, 2 puntos) no son informativos. Es lo único que bloquea G2.
2. **Malla de umbrales para N1** en lugar de un punto, y **soporte mínimo**
   con el que N1 se considera estimable. El techo medido es 55 semanas
   distintas, no 93 orígenes — la deduplicación de P2 también aplica aquí.
3. **Los cortes concretos de la estratificación por horizonte.** La Decisión B
   fijó *que* se distinguiría; P2 midió que el estrato tardío tiene soporte 1,
   así que la malla tiene que declararse sabiendo eso.

P3 (un TSFM zero-shot vía AutoGluon) queda **opcional**: M0 ganó, así que ya no
hay promoción que perseguir, y entra solo si aporta un contraste y pasa su smoke
test. P4 queda sin objeto mientras no haya candidato que promover.
