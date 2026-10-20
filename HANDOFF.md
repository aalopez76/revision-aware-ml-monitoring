# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 19 de octubre de 2026
**Fase:** **G0, G1-core, P2 y G2-A cerradas.** M0 sigue siendo el Champion.
G2-A midió que **las dos señales del 2x2 estaban mal declaradas**, así que G2 no
se calcula hasta declarar la config. P3 queda opcional y sin empezar.

## Qué está hecho

- **G0, veredicto PROCEED** — `00_source_feasibility.json`. Sus cuatro hallazgos
  y el universo elegible están en el README y en `datos.md`.
- **G1-core ejecutada de verdad** — `01_vertical_slice.json`: `s_dev = 4967.25`
  sobre 24 pares, 14 cortes de replay, 30 predicciones inmutables, una corrida
  observada. `load_as_of` reconstruye desde **una** consulta de `/archive/` y
  `confirmatory=True` falla sin acta antes de la red.
- **El producto es un nowcast, no un pronóstico a una semana.** A horizonte +1
  `PRE_WEEK_FORECAST` es inalcanzable por aritmética: 0 pre-semana, 1 nowcast,
  29 `post_event`.
- **Soporte medido** — `01_modeling_support.json`: 100 cortes programados, 93
  elegibles a 45 días (91 a 60, 87 a 90). Retraso mediano 7 días, máximo 49.
- **P2 cerrada sin promoción** — `01_model_comparison.json`. Sobre **55 semanas
  objetivo distintas**: M0 `0.3146`, `ridge_F1` `0.3781`, `ridge_F0` `0.6029`.
  `ridge_F1` gana 8 semanas y pierde 47. Alpha y la receta se eligieron solo en
  desarrollo. El estrato de publicación tardía era una interrupción vista seis
  veces, soporte efectivo 1, y eso inflaba el denominador a 61 orígenes.
- **G2-A: las dos señales medidas, sin declarar umbral** —
  `02_signal_diagnostics.json`, 32 cortes de desarrollo, los dos tirones
  acotados en `2025-06-30` del lado del servidor.
  - **R como proporción no sirve: está saturada.** 1046 de 1046 pares
    comparables revisados, en todos los buckets de rezago, incluso más allá de
    180 días. Constante 1.0 **bajo las dos anclas**, así que reanclarla no lo
    arregla — el diagnóstico anterior de este archivo era equivocado.
  - **La magnitud sí tiene dispersión.** El cambio relativo mediano cae de
    3.76 % a 7 días de rezago a 0.16 % a 22-28 y se estabiliza en 0.03-0.06 %:
    la ventana estructural son **unas tres semanas, no ocho**. Como señal por
    corte, la magnitud media da 31 valores distintos en 32 cortes.
  - **C tiene el defecto simétrico:** su máximo observado es **0.119 puntos**
    contra una alarma declarada en **2.0**, así que nunca podía disparar.
  - **La rama PERFORMANCE se alcanza en 22 de 32 cortes** con el mínimo de 4
    etiquetas, contado por calendario y no por predicciones guardadas.
- **49 cifras rastreadas**, **97 pruebas** y **8 sellos**, todo verde.

## Lo que NO está hecho

- **La config de G2 no existe.** Sin ella no hay N1: con los umbrales de G1,
  `d_1*` dispararía siempre y `d_01` sería idéntica a `d_00`, así que la
  discordancia medida sería un artefacto de la saturación. Esto es derivado de
  las dos mediciones, no medido: nadie ha calculado N1.
- **`selection_config_sha256` es `null`**: ausente significa «aún no
  declarada», nunca «declarada vacía».
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **P3 y P4 sin empezar.** P4 no tiene objeto mientras no haya candidato que
  promover; P3 es opcional y exige smoke test antes de instalar nada.
- **Una sola semana cubierta** (`2026-W42`, 2 de 3 registros locales); el cron
  sigue provisional y `2026-W43` abrió sin captura.

## Siguiente acción concreta

1. **Declarar `config/g2_signals.json`**, versionado, con `declared_in`, y
   sellarlo en `selection_config_sha256`. Tres contenidos: la definición y el
   ancla de R y C; la malla de umbrales para N1 más el soporte mínimo con que
   se considera estimable (techo **55 semanas distintas**, no 93 orígenes); y
   los cortes de estratificación por horizonte, sabiendo que el estrato tardío
   tiene soporte 1.
2. **`scripts/02_discordance.py`**: N1 = D(11,00), los cuatro efectos simples,
   los dos contrastes sin sumarlos, contingencias y abstenciones, con el
   denominador exógeno y la deduplicación por calendario de P2.

## Decisiones abiertas

- **Si R pasa de proporción a magnitud.** Es un cambio de señal, no de umbral,
  y lo registra la persona antes de calcular N1. Postergarlo cuesta poco hoy y
  mucho después: declarado una vez calculada la discordancia, ya no es
  predeclarado y G2 deja de valer.
- **Si los 2 registros semanales locales se quedan** en la evidencia
  operacional, y si el cron deja de ser provisional antes de congelar.
