# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 20 de octubre de 2026
**Fase:** **V1 cerrada con G0 + G1 + G2.** N1 = 0.454545 sobre 55 semanas.
G3 quedo autorizado por el criterio y **no se construye**: M0 no tiene
parametros, asi que su frontera de costos se deriva en lugar de simularse.

## Qué está hecho

- **G0 PROCEED, G1-core real y P2 sin promoción** —
  `00_source_feasibility.json`, `01_vertical_slice.json`,
  `01_modeling_support.json`, `01_model_comparison.json`. `s_dev = 4967.25`;
  93 orígenes elegibles a 45 días; sobre 55 semanas M0 `0.314624` contra
  `ridge_F1` `0.378141`, que gana 8 y pierde 47. **M0 sigue siendo el Champion**,
  y el producto es un **nowcast**, no un pronóstico a una semana.
- **G2-A y la Decisión C** — `02_signal_diagnostics.json`. 1046 de 1046 pares
  revisados en los nueve buckets, así que R pasa de proporción a magnitud en
  `config/g2_signals.json`, sellada antes de calcular N1 y declarando también
  lo que **no** se movió: `loss_alarm` en 2.0 y `recent_loss` sin ventana.
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
- **El README ya es el entregable**, con cada cifra rastreada y §10 «Where it
  fails» abriendo con la sensibilidad al umbral.
- **El intervalo, verificado y acotado.** `referencias.md` §8: Brown, Cai y
  DasGupta (2001) ✓ abriendo el fichero del editor; Wilson (1927) con metadatos
  confirmados y **texto no abierto**, así que sin ✓. La comprobación corrigió dos
  cosas antes de publicarlas: la justificación que iba a atribuírseles no está en
  su artículo, y a n = 55 ellos prefieren Agresti-Coull. Wilson se queda porque
  estaba declarado y sellado; el intercambio se declara en §10 del README.
- **101 cifras rastreadas**, **114 pruebas**, **11 sellos**, `ruff` limpio.

## Lo que NO está hecho

- **G3 no se construye, y la decisión está razonada en el README §8.** M0 no
  tiene parámetros (`forecasting.py:128`) y V3.3 §11 cuenta reentrenamientos
  **realizados**, así que `r_p = 0` en las cuatro políticas y `Δ(c) = 0` en
  todo `c ≥ 0`: empatan exactamente. N2 vacío, `c_star` indefinido (`0/0`),
  N3(c) = 0/55. Conclusión **B** por su cláusula de empate. Derivación
  algebraica condicionada, no simulación: etiquetada **E3**.
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **P3 y P4 sin objeto**: M0 ganó, no hay candidato que promover.
- **Una sola semana cubierta** (`2026-W42`, 2 de 3 registros locales);
  `2026-W43` abrió sin captura y el cron sigue provisional.

## Siguiente acción concreta

1. **Auditoría final del README y del código** con la mirada de un evaluador
   técnico senior: que cada cifra siga apuntando a su clave, que ninguna
   afirmación supere su evidencia, y que la primera pantalla se sostenga sola.
2. **Congelar el método**, que es el único ítem obligatorio que sigue abierto y
   que escribe la persona.

## Decisiones abiertas

- **Si una V2 estudia políticas de actuación** —investigar, esperar madurez,
  pedir información— en lugar de políticas de reentrenamiento. Es la evolución
  que el resultado de G2 sugiere, y exigiría definir qué acción cambia el
  resultado, cuánto cuesta y con qué evidencia se evalúa. No sería el G3
  original y no debe presentarse como tal.
- **Si los 2 registros semanales locales se quedan** en la evidencia
  operacional, y si el cron deja de ser provisional antes de congelar.
