# HANDOFF

> Estado actual, corto. **No es un historial** — se reescribe, no se acumula.
> Lo reescribe la skill `/handoff`.

**Última actualización:** 15 de octubre de 2026
**Fase:** antes de **G0**. El repositorio está realineado con la especificación
congelada V3.3; **no existe ninguna cifra propia.**

## Qué está hecho

- **Especificación congelada:** `When_the_Past_Moves_Especificacion_Ejecutable_V3_3_2026.txt`
  es la guía de implementación. Las versiones anteriores quedan como historia de
  decisiones y no se borran.
- **Repositorio realineado a V3.3**, de punta a punta: README (entregable, en
  inglés, con los resultados marcados «not evaluated yet»), `CLAUDE.md`, las
  cuatro reglas, los hooks, los nombres de módulos y scripts, el `Makefile`, el
  `Dockerfile` y los dos workflows.
- **`freeze_guard.py` retirado.** Vigilaba la capa equivocada —`re.search` sobre
  el texto del comando— y en la sesión anterior bloqueó escribir prosa que
  mencionaba un nombre de archivo. El control vive ahora en el dato:
  `panel.as_of_view` con los modos de `ReplayMode`, y una **prueba de
  propiedades con Hypothesis** que genera historiales aleatorios de
  publicaciones y cortes y afirma que ninguna fila futura pasa nunca.
- **`MATURITY_DAYS = 45` retirado** como constante. La madurez es ahora una
  `MaturityPolicy` que hay que suministrar y que declara dónde se fijó; la malla
  de sensibilidad `(45, 60, 90)` está predeclarada, y una prueba impide que la
  constante vuelva.
- **ILINet / FluView V3 retirado** del proyecto: otra serie, y además ruta
  deprecada desde octubre de 2026.
- **Puerta única reenunciada y ampliada:** `sources.py` es la única que habla con
  la red y `panel.py` la única que lee `data/`. El hook ahora también marca
  **importar un cliente de red** fuera de `sources.py`, porque con un cliente de
  terceros las peticiones ocurren dentro de la librería.
- **Esquema del panel migrado** a los conceptos de V3.3, y `derive_revisions`
  —la pieza más valiosa del repositorio— conservada y **obligada a que el
  llamador nombre qué reloj ordena las versiones**.
- **Entorno y calidad, corridos hoy:** `uv lock` resuelve 37 paquetes con
  `epidatpy 0.7.0`, `hypothesis 6.170.0` y `pyarrow 26.0.0`; `ruff check .`
  limpio; **37 pruebas en verde**; el verificador reporta 0 cifras rastreadas,
  que es lo correcto porque el README no enuncia ninguna cifra propia.
- **API de V5 introspeccionada, no supuesta:** los métodos V5 existen como
  métodos de `EpiDataContext` (`epidata_snapshot`, `epidata_archive`,
  `epidata_meta`), no como exportaciones de módulo. `EpiDataCall.request_url()`
  da la consulta reproducible que G0 necesita como procedencia, y
  `epidata_meta("nhsn")` expone `report_time_range`, que es la respuesta directa
  a cuánta historia de versiones hay.

## Lo que NO está hecho

- **Ninguna consulta a la fuente.** `reports/results/` está vacío a propósito.
- **No hay clave de la API.** El acceso anónimo son 60 peticiones/hora, lo que
  hace impracticable reconstruir snapshots sucesivos.
- **La captura nunca ha corrido: el repositorio no está en remoto.** Nada está
  commiteado todavía.
- **`load_as_of` está declarada y no implementada.** Su contrato enumera lo que
  tiene que cumplir para pasar G1. La compuerta pura (`as_of_view`) sí está
  implementada y probada.
- **`forecasting.py`, `monitoring.py`, `evaluation.py` y `evidence.py` no
  existen.** Nacen en G1/G2, cuando tengan su primera necesidad verificable.

## Siguiente acción concreta

1. **Registrar la clave de la API de Delphi** (formulario web, llega por correo)
   y guardarla como secreto `DELPHI_EPIDATA_KEY` del repositorio y en `.env`.
   Es tarea de la persona y es gratis.
2. **Primer commit y remoto.** La captura empieza a correr; en repositorio
   público GitHub desactiva el cron tras 60 días sin actividad, así que el
   remoto no es solo el arranque.
3. **G0, en este orden**, con las respuestas guardadas como procedencia:
   - probar la autenticación contra una ruta **v5** real: el mecanismo de clave
     está documentado como común a toda la API, pero ningún ejemplo usa una ruta
     v5;
   - `epidata_meta("nhsn")` → `report_time_range` y `reference_time_range`
     efectivos, que es lo que nadie sabe hoy;
   - **resolver la contradicción de `/archive/`**: la página general de V5 lo
     describe como diffs y el docstring del cliente dice que devuelve todas las
     versiones. La diferencia **es** el denominador de la tasa de revisión. Se
     resuelve contra `/snapshot/` en varios cortes;
   - confirmar por nombre `hosprep_pct_confirmed_admissions_flu_ew`: la familia
     está documentada, ese miembro no;
   - alinear una muestra compatible contra el git del hub y dejar la tabla de
     discrepancias.
4. Escribir `scripts/00_source_feasibility.py` con esas mediciones y su JSON, y
   **añadir sus filas al verificador en el mismo commit** que ponga las cifras
   en el README.

## Decisiones abiertas

- **Visibilidad del remoto** (público o privado). Afecta al cron: GitHub solo
  desactiva por inactividad los schedules de repositorios públicos.
- **Malla de umbrales para N1.** Pendiente de la última revisión: reportar N1
  sobre una malla predeclarada de umbrales del monitor en lugar de en un punto,
  porque la magnitud de N1 depende en parte de dónde cae el umbral base
  respecto de la frontera de decisión. Se fija antes de G2.
- **Soporte mínimo predeclarado.** El denominador máximo alcanzable es
  calculable en G0 desde el calendario; conviene declarar antes de G2 cuál es el
  mínimo con el que N1 se considera estimable, en lugar de juzgarlo después.
- **Estratificación por horizonte efectivo.** Si una publicación llega tarde, la
  última semana elegible es más antigua y el horizonte deja de ser constante en
  distancia de evento; mezclar horizontes en la pérdida media sesgaría la
  comparación entre políticas. Decidir si se fija el objetivo o se estratifica.
