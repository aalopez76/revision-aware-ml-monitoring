# Regla: el dato y su defecto

## Dos puertas, y ninguna más

**`src/revmon/sources.py` es la única que habla con la red** y
**`src/revmon/panel.py` la única que lee `data/`.**

La razón no es orden: la cantidad central del proyecto es **qué se podía saber y
cuándo**, así que una segunda ruta al dato es una segunda definición de esa
cantidad, y es exactamente por donde entra un look-ahead sin que nadie lo vea.

Con un cliente de terceros —`epidatpy`— las peticiones ocurren dentro de la
librería, así que la puerta no es el lugar donde se abre el socket: **es el
módulo al que se le permite importar el cliente.** Un `import epidatpy` en un
script es una segunda puerta aunque no contenga una sola llamada HTTP.

Lo comprueba `.claude/hooks/puerta_unica.py` tras cada edición, con cuatro
patrones: leer el parquet, parsear una fuente cruda, abrir algo bajo `data/`, y
usar una ruta interna de otro módulo. Si hace falta un dato que el panel no
expone, la corrección es **ampliar el panel**, no abrir una segunda ruta.

## Las dos fuentes, y por qué no se funden

**Canónica propuesta, sujeta a G0:** Delphi Epidata V5, `source="nhsn"`.
Objetivo `confirmed_admissions_flu_ew`; cobertura
`hosprep_confirmed_admissions_flu_ew` (conteo de hospitales que reportan, **no**
de hospitalizaciones) y la familia `hosprep_pct_*`.

**Segunda reconstrucción:** la historia de git de
`cdcepi/FluSight-forecast-hub` sobre `target-data/target-hospital-admissions.csv`.

Son **dos canales de publicación, no dos mediciones independientes del
fenómeno**. Se comparan bajo definiciones, geografías y cortes compatibles, y el
desacuerdo se reporta con ejemplos reproducibles en lugar de «corregirse».

> **Un commit del hub no es el instante en que un valor estuvo disponible en
> NHSN.** Equiparar `hub_commit_at` con `source_report_date` sin prueba es la
> confusión que este proyecto estudia, cometida por el propio proyecto.

ILINet / FluView quedó **retirado**: es otra serie, no alimenta esta pregunta, y
sus métodos V3/V4 se deprecan desde octubre de 2026.

## Siete conceptos de tiempo

Viven en `src/revmon/temporal.py`. Cuatro se observan y los demás se declaran o
son cortes, no relojes:

| concepto | qué es |
|---|---|
| `event_week_end` | la semana que el valor describe |
| `source_report_date` | la publicación que declara V5. **Granularidad de día**, no una hora verificada |
| `hub_commit_at` | cuándo el hub lo puso en su repositorio. Otro canal |
| `observed_at` | cuándo **este sistema** lo recuperó y validó |
| `maturity_rule` | política **declarada** de elegibilidad de etiquetas |
| `decision_as_of` | el corte de información de una decisión |
| `vintage_id` | identidad de versión. **No es una fecha** |

**No hay constante de madurez en el módulo.** El `MATURITY_DAYS = 45` anterior
venía del comportamiento documentado de Delphi sobre **otra serie** y había
empezado a leerse como una propiedad de este blanco. Es una política que se
suministra, se declara dónde se fijó, y se reporta con su sensibilidad sobre la
malla predeclarada `(45, 60, 90)`. Hay una prueba que impide que la constante
vuelva.

Y como `source_report_date` solo identifica un día, un replay público coloca el
corte **un día después** de la publicación declarada. Afirmar visibilidad
intradía que nunca se demostró es la clase de optimismo pequeño que se convierte
en fuga.

## El panel canónico

Una fila por fuente × señal × geografía × semana del evento × versión publicada.
Eso es un triángulo de revisiones: leer una clave hacia abajo muestra cómo se
fue reexpresando el valor de una semana; tomar la última versión anterior al
corte muestra cómo se veía el mundo en ese momento.

**`derive_revisions` no adivina qué reloj ordena las versiones**: el llamador
tiene que nombrarlo. Un panel ordenado por el reloj equivocado redefine en
silencio qué significa «la versión siguiente».

**Una versión que no reexpresó nada se conserva**: una republicación que no
cambió ningún valor es evidencia de que esa semana no se revisó nada, y tirarla
sesgaría la tasa de revisión hacia abajo.

## El denominador de la tasa de revisión

**Nunca** filas devueltas por `/archive/` sobre filas devueltas por `/archive/`.

- **Denominador:** pares elegibles (señal, geografía, semana del evento,
  publicación posterior) donde el registro existía antes y después y ambos
  valores son comparables bajo reglas fijadas.
- **Numerador:** los pares cuyo valor cambió.
- Altas, bajas, faltantes, republicaciones sin cambio y publicaciones sin
  observación elegible **se reportan por separado**; ninguno se cuenta como «sin
  revisión».

`/metadata/report_times/` da el calendario de publicaciones de la fuente; **no
garantiza una fila por cada combinación de señal y geografía.**

### Lo que `/archive/` devuelve, medido en G0

La documentación se contradecía: la página general de V5 llamaba a sus filas
diffs y el docstring del cliente decía que devuelve todas las versiones. **No es
ninguna de las dos.** Medido con los dos ejes acotados (2025-09-01 a 2026-10-10):
**100 de 102 publicaciones** llevaron fila para la señal objetivo, y una semana de
evento dada aparece en **17 de ellas** (mediana; mín 2, máx 41).

Es decir: las republicaciones sin cambio **sí** se conservan, y las claves **no**
están en todas las publicaciones — cada release reexpresa una ventana final de
semanas. Así que el denominador por pares elegibles de arriba no era una cautela:
era la definición correcta, y ahora tiene medición detrás.

Reconstruir un snapshot desde el archivo reprodujo el `/snapshot/` directo
**exactamente en los tres cortes de prueba**, con cero discrepancias de valor y
cero claves de un solo lado. Eso permite reconstruir desde una sola consulta de
archivo en lugar de pagar un `/snapshot/` por corte, que es el endpoint que
filtra en el cliente y por tanto el caro.

## El universo elegible

Un cambio de régimen de reporte altera la cobertura sin alterar el fenómeno, que
es el peor confusor disponible para este proyecto. Fechas verificadas:
obligatorio del **2020-09-02 al 2024-04-30**; **voluntario del 2024-05-01 al
2024-10-31**, con los CDC advirtiendo que esos datos pueden no ser plenamente
representativos; obligatorio otra vez **desde 2024-11-01** por requisito de CMS.

El universo se **declara en G0, antes de ver resultados**: por omisión
`reference_time >= 2024-11-01`, y preferiblemente por cobertura medida
(`flag_hosprep_*`) en lugar de un corte de calendario, para que el criterio sea
observable. No se revisa después.

**G0 lo resolvió casi solo:** el archivo de versiones empieza el **2024-11-19**,
18 días después de que el mandato volviera. El periodo voluntario **no tiene
historia de versiones**, así que el peor confusor disponible no tiene por dónde
contaminar. La declaración describe lo que existe, no excluye algo.

## La clave primaria la fija la fuente

`key_columns` de V5, medido: `signal · report_time · geo_type · geo_value ·
fill_method · reference_time`. **`fill_method` forma parte de la identidad**, así
que el panel lo carga y el denominador lo cuenta: dos filas que difieren solo en
ese campo no son una revisión una de otra. `extra_key_columns` está vacío y
`value_columns` es solo `value`.

## Qué está prohibido

- Leer `data/` sin pasar por `panel.py`, o importar un cliente de red fuera de
  `sources.py`.
- Editar a mano cualquier cosa bajo `data/` o `reports/`. Los permisos lo
  deniegan: **todo lo que hay en `reports/` lo escribió un script.**
- Inventar una captura. **Si una corrida no ocurrió, no hay archivo.** Un dato
  perdido se reconsulta si la fuente lo conserva; una ejecución perdida no. Lo
  audita `/registro-semanal`.
- Fundir los dos canales como si fueran la misma medición.

## El entorno

Todo corre dentro de `.venv`, construido con `uv sync --locked` desde el
`uv.lock` versionado. **Nunca el Python global**: lo bloquea
`.claude/hooks/venv_guard.py`. Una cifra producida con otras versiones no es la
misma cifra.

El acceso anónimo a la API está limitado a **60 peticiones por hora** y admite
selección múltiple en a lo sumo dos parámetros; la clave gratuita levanta ambos
límites. Y `snapshot` filtra geografía y `reference_time` **en el cliente**, así
que cada llamada paga el dataset completo: la reconstrucción necesita
presupuesto de consultas, no un bucle.

## La cohorte confirmatoria

No se toca hasta congelar. El control está en el dato —`panel.as_of_view` y los
modos de `ReplayMode`—, **no** en un guardián que mire nombres de archivo. Está
en `.claude/rules/metodo.md`.
