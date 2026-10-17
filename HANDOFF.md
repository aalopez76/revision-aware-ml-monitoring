# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 16 de octubre de 2026
**Fase:** **G0 cerrada con veredicto PROCEED.** Las primeras cifras del proyecto
existen, están rastreadas y son citables. Siguiente compuerta: **G1**.

## Qué está hecho

- **Repositorio alineado con la especificación congelada V3.3** y commiteado:
  documentos, cuatro reglas, tres hooks, cinco skills, dos subagentes, módulos,
  scripts y CI describiendo el mismo método. `freeze_guard` retirado,
  `MATURITY_DAYS = 45` retirado, ILINet/FluView V3 retirado.
- **Clave de la API configurada y funcionando.** Vive en `.env` (gitignored) y la
  carga `uv` por `UV_ENV_FILE`, fijado en `.claude/settings.json`.
- **`sources.py` envuelve `epidatpy`**, el cliente oficial de V5, y añade el
  calendario de publicaciones —que el cliente no expone— y el lector del canal
  del hub. La clave viaja por basic auth, así que el `request_url` que se guarda
  como procedencia no puede llevarla.
- **G0 ejecutada:** `scripts/00_source_feasibility.py` →
  `reports/results/00_source_feasibility.json`, 13 peticiones, 6,8 segundos, con
  `request_url` y `observed_at` de cada consulta.
- **18 cifras rastreadas** en `scripts/verify_results.py`, verificadas en CI. El
  verificador se extendió con `ExactClaim` para fechas y veredictos: la regla
  dice que **toda** cifra necesita fila, y una fecha es una cifra.
- **Cuatro hallazgos de G0 que corrigieron supuestos del planteamiento**, ya
  escritos en el README, en `datos.md` y como corrección en `referencias.md`:
  - historia de eventos 322 semanas contra historia de versiones **99**; 223
    semanas de evento sin ninguna versión. La cobertura del dato no es la
    cobertura de vintages, y el factor era **3×**;
  - `/archive/` **no es** diffs ni todas las versiones: 100 de 102 publicaciones
    llevan fila, y una semana aparece en 17 de ellas (mediana). Cada release
    reexpresa una ventana final;
  - las publicaciones **no son semanales**: 189 fechas, mediana de 2 por semana
    ISO, 3 días entre ellas. El proxy «un commit = una publicación» subcontaba
    por la mitad;
  - `fill_method` forma parte de la clave primaria de la fuente.
- **El universo elegible quedó resuelto por los datos:** el archivo empieza el
  2024-11-19, 18 días después de que el mandato de reporte volviera, así que el
  periodo voluntario no tiene historia de versiones que contaminar.
- **Las dos reconstrucciones concuerdan:** 245 semanas nacionales solapadas entre
  el hub y V5, **cero en desacuerdo**. Valida la serie de valores, no los tiempos.
- **Techo de N1 conocido: 99 cortes** semanales nacionales, antes de que la
  madurez y la disponibilidad de etiquetas lo poden.

## Lo que NO está hecho

- **G1 no existe.** `load_as_of` está declarada con su contrato y sin
  implementar; `as_of_view` —la compuerta pura— sí está implementada y probada
  con propiedades. No hay `forecasting.py`, `monitoring.py`, `evaluation.py` ni
  `evidence.py`.
- **`fill_method` no está en el esquema del panel** todavía, aunque la regla ya
  lo exige.
- **El repositorio no está en remoto y la captura nunca ha corrido.** Sigue
  siendo lo único irrecuperable, y hoy mismo la fuente publicó otra vez: el
  calendario pasó de 188 a 189 entradas en un día.

## Siguiente acción concreta

1. **Remoto y empujar.** Decidir visibilidad y crear el remoto; la captura
   semanal arranca y deja de perderse evidencia operacional.
2. **Añadir `fill_method` al esquema del panel** y a las pruebas del triángulo.
   Es mecánico y lo exige `datos.md`.
3. **G1, el vertical slice.** En este orden:
   - implementar `load_as_of` contra el contrato ya escrito, aprovechando que la
     reconstrucción `archive → snapshot` se midió exacta: una sola consulta de
     archivo basta y evita pagar un `/snapshot/` por corte;
   - baseline mínimo, predicción inmutable con su manifiesto;
   - una señal y una recomendación de las cinco, con falla segura;
   - la figura: pronóstico original, versiones posteriores del objetivo y
     cobertura publicada, con ejes separados.
4. Antes de G2, **declarar el soporte mínimo** con el que N1 se considera
   estimable. El techo es 99 y ya es conocido, así que esto se decide ahora y no
   después de ver el resultado.

## Decisiones abiertas

- **Visibilidad del remoto** (público o privado). Afecta al cron: GitHub solo
  desactiva por inactividad los schedules de repositorios públicos.
- **Malla de umbrales para N1**, en lugar de un punto: la magnitud de N1 depende
  en parte de dónde cae el umbral base respecto de la frontera de decisión. Se
  fija antes de G2.
- **Soporte mínimo predeclarado** — ver el punto 4 de arriba.
- **Estratificación por horizonte efectivo.** Si una publicación llega tarde, la
  última semana elegible es más antigua y el horizonte deja de ser constante en
  distancia de evento; mezclar horizontes en la pérdida media sesgaría la
  comparación entre políticas.
