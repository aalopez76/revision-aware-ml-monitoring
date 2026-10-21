# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 20 de octubre de 2026
**Fase:** **G2 cerrada y llevada al README.** N1 = 0.454545 sobre 55 semanas.
G3 queda autorizado por el criterio declarado y **no se ha corrido**.

## Qué está hecho

- **G0 PROCEED, G1-core real y P2 sin promoción** —
  `00_source_feasibility.json`, `01_vertical_slice.json`,
  `01_modeling_support.json`, `01_model_comparison.json`. `s_dev = 4967.25`;
  93 orígenes elegibles a 45 días; sobre 55 semanas M0 `0.314624` contra
  `ridge_F1` `0.378141`, que gana 8 y pierde 47. **M0 sigue siendo el Champion**,
  y el producto es un **nowcast**, no un pronóstico a una semana.
- **G2-A: la proporción revisada está saturada** —
  `02_signal_diagnostics.json`. 1046 de 1046 pares revisados, en los nueve
  buckets de rezago. La magnitud sí discrimina: su mediana cae de `0.037626`
  a 7 días a `0.000326` pasados 90.
- **Decisión C registrada** en `config/g2_signals.json`, sellada en
  `selection_config_sha256` antes de calcular N1: R pasa de proporción a
  magnitud. Declara también lo que **no** se movió —`loss_alarm` en 2.0,
  `recent_loss` sin ventana— y por qué.
- **G2, la compuerta** — `02_discordance.json`, clase **E2**.
  - **N1 = D(11,00) = 0.454545**, 25 de 55, Wilson 95 % [0.330253, 0.584773].
    Cero abstenciones en las cuatro ramas.
  - En la celda primaria toda la discordancia es de la cobertura: `d_10` iguala
    a `d_00` y `d_11` iguala a `d_01` en las 55 semanas, así que los dos
    contrastes de interacción valen 0 y la cota superior de Wilson sobre cada
    cero es `0.065285`.
  - **Pero eso es propio de la alarma 0.02.** A los otros dos puntos declarados
    de la malla R sí mueve: `0.254545` (14/55) a 0.01 y `0.818182` (45/55) a
    0.005. La discordancia es robusta; su atribución a la cobertura no lo es.
  - Ninguna rama emite `EVALUAR_REENTRENO` ni `ABSTENERSE`.
- **El README ya es el entregable.** Quince secciones con P2, G2-A y G2
  dentro, cada cifra con su rastro, y §10 «Where it fails» con la limitación
  anterior como la más dura del informe.
- **101 cifras rastreadas**, **114 pruebas**, **11 sellos**, `ruff` limpio.

## Lo que NO está hecho

- **G3 sin empezar.** Autorizado por el criterio, y por omisión solo dos
  configuraciones (00 y 11): la interacción medida en la celda primaria es 0.
  Antes de correrlo hay que decidir si la malla de R entra también ahí, porque
  la inercia de R no sobrevive a un paso de umbral.
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **Wilson no está en `referencias.md`.** La verificación de Wilson (1927) y
  Brown, Cai y DasGupta (2001) está delegada al subagente y pendiente de
  veredicto; hasta que vuelva, el README nombra el método sin citarlo.
- **P3 y P4 sin objeto**: M0 ganó, no hay candidato que promover.
- **Una sola semana cubierta** (`2026-W42`, 2 de 3 registros locales);
  `2026-W43` abrió sin captura y el cron sigue provisional.

## Siguiente acción concreta

1. **Cerrar la verificación de las dos referencias** y, si vuelven ✓, añadir
   Wilson y Brown-Cai-DasGupta a `referencias.md` con su fecha y su venue.
2. **Empujar.** El árbol está verde y el README ya corresponde a los
   artefactos; `verify_results.py` corre en CI y es lo que lo protege.
3. **Entonces G3**: trayectorias por política desde el mismo estado inicial y
   la región de costos sobre la malla declarada. `c_star` únicamente si hay
   cruce positivo y estable.

## Decisiones abiertas

- **Si G3 se corre sobre una sola celda de umbral o sobre la malla.** Correrlo
  solo en la primaria heredaría una atribución que la malla contradice; correrlo
  en las nueve multiplica por nueve un simulador de trayectorias.
- **Si los 2 registros semanales locales se quedan** en la evidencia
  operacional, y si el cron deja de ser provisional antes de congelar.
