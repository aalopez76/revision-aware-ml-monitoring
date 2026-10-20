# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 19 de octubre de 2026
**Fase:** **G2 cerrada. La compuerta se abrió.** N1 = 0.4546 sobre 55 semanas,
y toda la discordancia viene de la cobertura. G3 queda autorizado por el
criterio declarado, pero **primero el README**: la regla de alcance prohíbe
abrir trabajo nuevo con la lista obligatoria pendiente.

## Qué está hecho

- **G0, veredicto PROCEED** — `00_source_feasibility.json`. Sus hallazgos y el
  universo elegible están en el README y en `datos.md`.
- **G1-core ejecutada de verdad** — `01_vertical_slice.json`: `s_dev = 4967.25`
  sobre 24 pares, 14 cortes de replay, 30 predicciones inmutables, una corrida
  observada. `load_as_of` reconstruye desde **una** consulta y `confirmatory`
  falla sin acta antes de la red.
- **El producto es un nowcast**: a horizonte +1 `PRE_WEEK_FORECAST` es
  inalcanzable por aritmética.
- **Soporte medido** — `01_modeling_support.json`: 100 cortes, 93 elegibles a 45
  días. Retraso mediano 7 días, máximo 49.
- **P2 cerrada sin promoción** — `01_model_comparison.json`. Sobre 55 semanas:
  M0 `0.3146`, `ridge_F1` `0.3781`, `ridge_F0` `0.6029`. `ridge_F1` gana 8 y
  pierde 47. **M0 sigue siendo el Champion.**
- **G2-A: la proporción revisada está saturada** —
  `02_signal_diagnostics.json`. 1046 de 1046 pares revisados, en todos los
  buckets de rezago. Constante 1.0 bajo las dos anclas. La magnitud sí tiene
  dispersión y su mediana cae de 3.76 % a 7 días a 0.03-0.06 % pasados 90.
  La cobertura tenía el defecto simétrico: máximo observado 0.119 puntos contra
  una alarma de 2.0.
- **Decisión C registrada** en `config/g2_signals.json`, versionada y sellada
  en `selection_config_sha256`, **antes** de calcular N1: R pasa de proporción
  a magnitud. La config declara también lo que **no** se movió —`loss_alarm` en
  2.0 y `recent_loss` sin ventana— y por qué: al leer P2 ya se había visto la
  distribución de pérdidas, así que cualquier valor nuevo estaría elegido
  habiendo mirado.
- **G2, la compuerta** — `02_discordance.json`, clase **E2** (replay
  controlado: los pronósticos se reconstruyen, no se emitieron).
  - **N1 = D(11,00) = 0.454545**, 25 de 55, Wilson 95 % **[0.330, 0.585]**.
  - **Toda la discordancia es de la cobertura.** Cobertura sola mueve 25 de 55;
    **revisiones solas mueven cero.** `D(11,01) = 0`, así que los dos
    contrastes de interacción valen exactamente 0 y **R está perfectamente
    inerte**. Es medición, no defecto: la magnitud recorre 0.0060-0.0160 y
    nunca alcanza la alarma de 0.02.
  - **Ninguna rama recomienda jamás EVALUAR_REENTRENO.** La discordancia es
    enteramente CONTINUAR → INVESTIGAR_DATO.
  - **N1 recorre 0.4546 a 0.8182 en la malla de nueve celdas**; la primaria es
    la más baja. La compuerta se abre en las nueve, así que el veredicto no
    depende de la celda.
  - **El estrato tardío queda vacío por construcción**, no por medición:
    conservar el origen más temprano conserva el rezago más corto.
- **68 cifras rastreadas**, **114 pruebas**, **11 sellos**, todo verde.

## Lo que NO está hecho

- **El README no lleva nada de P2, G2-A ni G2.** Es el entregable, y la lista
  obligatoria de `alcance.md` pide el veredicto de G2 con sus límites, el
  estado prospectivo declarado y cada cifra con su rastro.
- **G3 sin empezar.** Autorizado por el criterio, y por omisión solo dos
  configuraciones (00 y 11): la interacción medida es 0, así que no entra una
  tercera.
- **El método no está congelado** y `frozen_method.json` no existe. La escribe
  la persona; los permisos deniegan al modelo escribir en `reports/`.
- **P3 y P4 sin objeto**: M0 ganó, no hay candidato que promover.
- **Una sola semana cubierta** (`2026-W42`, 2 de 3 registros locales);
  `2026-W43` abrió sin captura y el cron sigue provisional.
- **Tres commits sin empujar** desde `f2ae35d`.

## Siguiente acción concreta

1. **Llevar P2, G2-A y G2 al README**, en inglés, con el rastro cifra → script
   → clave para cada una. El titular honesto es que la discordancia existe y
   **no viene de donde el proyecto esperaba**: viene de la cobertura, y el
   factor de revisiones no mueve ninguna recomendación en esta serie.
2. **Añadir la sección de dónde falla**, que no es opcional: la alarma de
   cobertura se declaró sobre un desarrollo no representativo —0.033 puntos de
   techo contra 2.82 en evaluación— y eso es lo que cuesta declarar sobre una
   ventana que no representa el periodo evaluado.
3. **Solo entonces G3**: trayectorias por política desde el mismo estado
   inicial, y la región de costos sobre la malla declarada. `c_star` únicamente
   si hay cruce positivo y estable.

## Decisiones abiertas

- **Si el hallazgo de que R no mueve nada se reporta como paso o se degrada
  más.** Parece lo bastante importante para ser el titular, y por la regla del
  proyecto ésa es exactamente la señal de dejarlo como una comprobación dentro
  de G2, con su cifra y su cautela.
- **Si los 2 registros semanales locales se quedan** en la evidencia
  operacional, y si el cron deja de ser provisional antes de congelar.
