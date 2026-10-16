# Regla: el alcance es vinculante

La sección **«Scope & caveats»** del `README.md` no es una aspiración: es un
límite. Antes de añadir algo que no esté dentro, hay que decirlo y esperar
confirmación.

## El antecedente que explica esta regla

El proyecto que precede a éste se planteó como pieza de MLOps nivel plataforma y
colapsó: tres fases quedaron retractadas porque la evidencia operacional estaba
simulada. El patrón fue diagnóstico — las fases de ciencia eran reales y las de
ingeniería eran las falsificadas.

**Se falsifica lo que no se puede construir.** De ahí la regla siguiente.

## Fuera de alcance

- **La capa de plataforma.** Sin Kubernetes, sin Databricks, sin orquestador,
  sin feature store, sin nube gestionada. El scoring es un trabajo por lotes en
  contenedor, agendado por GitHub Actions. El mapeo a una plataforma gestionada
  **se describe, no se construye**: la profundidad del autor está en la mitad
  estadística del monitoreo, y construir una versión superficial de la otra
  demostraría menos que decir dónde está la línea.
- **El ciclo de vida del modelo.** Sin registry, sin promotion gate, sin
  rollback automatizado, sin máquina de estados de incidentes, sin inyección de
  fallos como subsistema. Una política de reentrenamiento necesita una función
  que reajuste y un manifiesto, no un registro de modelos.
- **Competir en exactitud de pronóstico.** El hub ya corre esa competencia. Este
  proyecto no envía pronóstico y no reclama ventaja; el campo del hub es
  referencia, no rival.
- **Atribución causal.** Por qué se reexpresó un valor, o qué hospitales habrían
  reportado, no está en estos datos. Revisión, cobertura y cambio del fenómeno
  **no son tres causas exclusivas identificables con datos agregados**: el cruce
  2x2 mide valor de disponer de información, no mecanismo.
- **Herramientas sin consumidor.** MLflow, SQLite, dashboard interactivo,
  modelos fundacionales, baterías de detectores. Entran cuando un problema
  observado las exija, con la alternativa mínima rechazada por escrito.
- **MCP, equipos de agentes y plugins.** Un servidor MCP sobre las mismas
  fuentes sería una segunda puerta al dato; las fases son secuenciales y
  dependientes, así que no hay exploración paralela que repartir; y un plugin
  empaqueta para varios repositorios, de los que aquí hay uno.

## El entregable

**El `README.md` es el entregable**, en inglés, con el repositorio como respaldo
reproducible. Un visitante debe entender en 60 segundos qué problema real
apareció, qué se construyó, qué decisión pudo medirse, con qué evidencia y qué
**no** puede concluirse.

## Terminado significa

**Obligatorio:**

- [ ] G0 documenta las ventanas reales de `report_time` y `reference_time`, con
      sus límites — medidas, no supuestas.
- [ ] V5 y el git del hub contrastados en puntos compatibles, o explicado por
      qué no se pudo.
- [ ] El contrato as-of conserva una historia sin mirar el futuro, y lo prueban
      pruebas generadas, no tres ejemplos.
- [ ] Una predicción y una recomendación **reales**, con manifiesto y hashes.
- [ ] Tasa de revisión con unidad y denominador coherentes.
- [ ] Cobertura incorporada como **información**, no como atribución causal.
- [ ] El cruce 2x2 completo: N1 con numerador, denominador y abstenciones; los
      cuatro efectos simples; los dos contrastes; contingencias y patrones. O la
      declaración honesta de falta de soporte.
- [ ] El veredicto de la compuerta G2, sea cual sea, con sus límites.
- [ ] El README muestra una decisión organizacional **propuesta**, no simulada
      como si hubiera habido una reunión o una aprobación.
- [ ] Cada cifra propia apunta a script → artefacto → clave.
- [ ] El estado prospectivo declarado: congelado, en curso, completo o no
      iniciado.
- [ ] Cero beneficios económicos y cero experiencia laboral inventados.
- [ ] Las referencias verificadas abriendo la fuente, y las correcciones
      registradas **como corrección, no borradas**.

**Condicional, solo si G2 abre la compuerta:**

- [ ] Trayectorias completas por política, sin fuga.
- [ ] La región de costos informada; `c_star` solo si hay cruce definido y
      estable.
- [ ] N3 caracterizado, sin atribuir consecuencias a un periodo sin prueba.

No se abre trabajo nuevo con ítems pendientes en la lista obligatoria.

## Documentos

**El README crece y nada más.** Sin fases numeradas como documentos, sin ADR por
decisión, sin bitácoras versionadas, sin auto-auditorías, sin reporte de modelo
aparte, sin casebook, sin blueprint empresarial separado, sin RACI extensa. La
lectura organizacional es **una sección del README**.

El único documento de estado es **`HANDOFF.md`**, en la raíz y versionado:
corto, solo el estado actual, no un historial. Lo reescribe `/handoff`.

Si parece necesario un documento de gobierno nuevo, **es una señal de alarma, no
una tarea.**

## El harness no es gobierno

`CLAUDE.md` y `.claude/` están versionados por una razón práctica: un harness
que vive en una sola máquina se pierde al clonar, y entonces las reglas no
obligan a nadie. Pero siguen siendo **infraestructura de desarrollo**
—permisos, reglas, hooks, skills, subagentes—, de la misma clase que el
`Makefile` y el `Dockerfile`, y **no son el entregable**.

La distinción es operativa: lo que vive en `.claude/` describe **cómo se
trabaja**. En el momento en que un archivo de `.claude/` empiece a describir
**qué se encontró**, es un documento de gobierno disfrazado y va al README o no
va.

`_borradores/` sigue fuera del repositorio.

## Terminar antes de ampliar

**La compuerta está en G2 y produce la primera cifra de punta a punta.** Si la
discordancia es pequeña, el soporte insuficiente o los faltantes dominantes, se
publica por qué no se justifica la especialización y el proyecto cierra corto,
en lugar de descubrirlo después de construir el simulador de políticas.

**No se amplía el alcance para rescatar una compuerta negativa.** Y cada entrega
debe valer por sí sola: si el proyecto se detiene al cerrar G0, lo que hay sigue
siendo un resultado publicable.
