---
name: congelar-metodo
description: Prepara y ejecuta la congelación del método, el acto que separa el desarrollo de la evaluación sobre la cohorte confirmatoria. Usar solo cuando G0, G1 y G2 estén cerradas y el método esté decidido. Comprueba las precondiciones, reúne las dos cotas del sello temporal y entrega el contenido exacto del acta.
allowed-tools: Read, Grep, Bash(git log*), Bash(git rev-parse*), Bash(git status*), Bash(git remote*), Bash(uv run *), Bash(openssl ts*), Bash(sha256sum*), WebFetch(domain:api.github.com)
---

# Congelar el método

Esto ocurre **una vez en la vida del proyecto** y no se puede deshacer. Lo que
está en juego: las semanas restantes de la temporada son la cohorte
confirmatoria, y su valor entero viene de que el método se fijó antes de que
ocurrieran. Mirarlas antes destruye eso, y mirarlas «un poquito» también.

El acta es `reports/results/frozen_method.json`.

## Precondiciones: todas, sin excepción

Comprobar y **reportar cada una**. Si alguna falla, parar y decir cuál.

1. **G0, G1 y G2 cerradas**, con sus artefactos en `reports/results/`:
   `00_source_feasibility.json`, `01_vertical_slice.json`,
   `02_decision_sensitivity.json`.
2. **Las cifras de esas compuertas están en el README y en el verificador.**
   Correr `/auditar-cifras` y exigir cero huérfanas y cero sin fila.
3. **El veredicto de G2 autoriza seguir.** Si G2 cerró corto, no hay nada que
   congelar: el proyecto ya terminó con su hallazgo.
4. **El estado del arte revisado.** Correr `/revisar-estado-del-arte`. Si
   apareció trabajo que cambie el posicionamiento, éste es el único momento en
   que se puede responder a él.
5. **La captura ha corrido y está conciliada.** Correr `/registro-semanal`.
   Congelar sin evidencia operacional previa deja el proyecto sin la mitad que
   lo sostiene.
6. **`uv run ruff check .` y `uv run pytest` limpios**, y el árbol de trabajo sin
   cambios pendientes. El commit de congelación debe describir exactamente el
   código que existía.
7. **La política de madurez decidida con la medición de G0/G2**, no heredada, y
   con su malla de sensibilidad declarada.
8. **La malla de costos declarada**, y la métrica de pérdida con su `s_dev` fija
   y su ventana de calibración. No están en los datos: son parámetros.

## El acta

Reunir y presentar, ya relleno:

```
frozen_at                     fecha y hora UTC
project_commit_sha            HEAD de este repositorio
spec_sha256                   hash de la especificación congelada
code_sha256                   hash del árbol de src/ y scripts/
lock_sha256                   hash de uv.lock
eligible_universe             fuente canónica, señal, geografía, primer y
                              último reference_time, y la regla con que se
                              declaró (fecha de mandato o cobertura medida)
decision_calendar             los cortes semanales nacionales programados
horizon                       definición exacta, con fechas, no «+1 semana»
maturity_policy               días, elección de etiqueta, dónde se declaró y
                              la malla de sensibilidad
loss                          métrica, s_dev, ventana de calibración, número
                              de pares usados, y el fallback si s_dev no existe
monitor_rules                 umbrales, ventanas, precedencia entre reglas
ablation                      las cuatro ramas del 2x2 y qué información lleva
                              cada una
estimands                     N1 y los secundarios, con sus denominadores
abstention_rule               cuándo el monitor se abstiene
gate_to_g3                    criterio declarado, decidido antes de la cohorte
policies                      P0-P3, si G3 procede
cost_grid                     la malla de c sobre la que se reporta
uncertainty                   procedimiento, con el esquema de bloques
stopping_rules                qué cierra el proyecto y con qué conclusión
max_known_report_time         el report_time más nuevo conocido en la fuente
external_commit_sha           sha de un commit externo ya publicado (el hub)
external_commit_at            su fecha
timestamp_proof               el sello externo y cómo verificarlo
```

## Las dos cotas del sello

**Una fecha de commit propia no es prueba**: la del committer es una variable de
entorno y la fija quien commitea.

### Cota inferior — gratis, ya la da el diseño

Incluir en el acta `external_commit_sha` y `max_known_report_time`: valores que
**no existían antes**. Prueban que el acta no se creó *antes* de que existieran.

```bash
git rev-parse HEAD                 # el commit de este repositorio
```

Y el commit más reciente del hub que toca `target-data/target-hospital-admissions.csv`,
por la API de GitHub. **Ése es el testigo ajeno.**

### Cota superior — una llamada, y es la que falta

Exige un testigo externo **en el momento de congelar**. Autoridades de tiempo
libres, utilizables con el `openssl` que ya está instalado: `https://freetsa.org/tsr`,
`http://timestamp.digicert.com`, `time.certum.pl` (gratuito para uso privado).

```bash
sha256sum reports/results/frozen_method.json      # el hash que se sella
openssl ts -query -data reports/results/frozen_method.json -sha256 -cert -out acta.tsq
# enviar acta.tsq al TSA y guardar la respuesta acta.tsr junto al acta
openssl ts -verify -in acta.tsr -data reports/results/frozen_method.json -CAfile cadena.pem
```

**Conservar la cadena de certificados y los datos de revocación**: la
verificación se rompe cuando el certificado del TSA expira, y un sello que no se
puede verificar no es un sello. Los servidores libres no dan garantía de
disponibilidad ni valor legal — sirven como prueba técnica, que es exactamente
lo que este proyecto necesita.

**Si se usa OpenTimestamps**: una prueba recién enviada está **pendiente** y no
es prueba. Solo cuenta cuando `ots upgrade` la cierra contra la cadena y
`ots verify` la confirma, lo que tarda horas. Guardar el `.ots` **completo**, no
la solicitud.

### Lo que el sello no demuestra

Acota la existencia de un hash en el tiempo. **No demuestra que el autor no viera
otros datos antes**: el aislamiento de la cohorte sigue siendo necesario y es
una propiedad del procedimiento, no del sello.

## Por qué lo escribe la persona y no el modelo

`Edit(reports/**)` está **denegado en los permisos**, así que el modelo no puede
escribir este archivo. Es deliberado, y es la única pieza del harness con esa
fricción: la regla dice *«no se escribe para desbloquear»*, y la forma de
garantizarlo es que quien lo escriba sea quien decide, no quien está bloqueado.

El procedimiento:

1. La skill presenta el acta completa y el resultado de las ocho precondiciones.
2. La persona la escribe. En la sesión, con el prefijo `!`.
3. Se obtiene el sello de la cota superior y se guarda junto al acta.
4. La persona commitea con un mensaje que diga qué se congeló. **Ese commit es
   la evidencia**, así que no se enmienda ni se rebasa: los permisos deniegan
   `git commit --amend`, `git rebase` y `git push --force` por esta razón.

## Después de congelar

- El control del acceso confirmatorio pasa a estar activo: `load_as_of` rechaza
  un corte confirmatorio si el acta no existe o su hash no coincide.
- **Todo hallazgo posterior a ver la cohorte es exploratorio** y se reporta en
  una sección separada. Genera hipótesis; no confirma.
- Si la temporada sigue abierta al publicar, se publica «confirmatorio en curso»
  con los periodos efectivamente puntuados y los pendientes nombrados.
- Una captura anterior a la congelación es evidencia operacional y archivo
  propio; **no** es evaluación confirmatoria.
