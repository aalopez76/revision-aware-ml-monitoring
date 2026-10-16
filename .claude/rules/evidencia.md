# Regla: toda afirmación necesita respaldo

Sostiene el marco del proyecto: **demostración de oficio, no descubrimiento.**
Vale para el README, las referencias, el HANDOFF, los comentarios del código y
cualquier texto que salga del repositorio.

## 1. Cifras

**Ninguna cifra entra a un documento si no la produce un script del
repositorio.**

El rastro es mecánico: cada script de `scripts/` escribe su JSON en
`reports/results/`, y toda cifra de un documento debe poder señalarse como
*«script → archivo → clave»*. Lo comprueba
`scripts/verify_results.py`, que corre en CI y lee solo JSON
versionado.

- **Una cifra en el README sin su fila en el verificador es un defecto**, no una
  excepción.
- El script y el README se actualizan **en el mismo commit**.
- Nada de redondear de memoria, copiar de una sesión anterior o reusar un número
  de la conversación.
- Las cifras de escala —ubicaciones, semanas, versiones— también cuentan.
- Nada bajo `reports/` se edita a mano: los permisos lo deniegan. Lo que está
  ahí lo escribió un script, y por eso vale como evidencia.

Las cifras atribuidas a trabajo publicado son la excepción, y llevan su cita.

Para auditar el rastro completo existe la skill `/auditar-cifras`. **Esto no lo
hace un hook, a propósito**: distinguir una cifra propia de una atribuida exige
juicio, y un hook que se equivoca en eso enseña a ignorarlo.

Y el verificador comprueba **correspondencia**, no corrección: que la cifra
publicada siga coincidiendo con el artefacto que la respalda. No demuestra que
el cómputo sea correcto. Para eso están los invariantes y las pruebas.

## 1 bis. Las tres clases de evidencia

Todo lo que sale del repositorio lleva una de estas tres etiquetas, visible:

| | qué es | qué NO autoriza |
|---|---|---|
| **E1 · real** | consultas efectivas, corridas, logs, versiones, predicciones y resultados reproducibles | nada que no se midió |
| **E2 · controlada** | replay retrospectivo, contrafactuales, fallos inyectados | presentarse como incidente real |
| **E3 · propuesta** | roles, criterios de aprobación, arquitectura de evolución | presentarse como experiencia o como acuerdo |

Dos distinciones que se confunden solas y por eso van escritas:

- **«Verificado documentalmente» y «medido en datos» son estados diferentes.**
  Haber leído que un endpoint se comporta de un modo no es haberlo comprobado.
  Ocurrió en este proyecto: la documentación general describe `/archive/` como
  diffs y el docstring del cliente instalado dice que devuelve todas las
  versiones. Hasta que una consulta lo resuelva, ninguna de las dos lecturas se
  usa como premisa.
- **Un replay reconstruido hoy no prueba que el sistema corriera entonces.** Una
  corrida observada y un replay histórico se etiquetan distinto, siempre.

## 2. Referencias

**Ninguna referencia se escribe sin haberla verificado.**

Verificar significa **abrir la fuente** y confirmar autores, año, título, venue
y la afirmación que se le atribuye. No basta recordarla, y **no basta el resumen
de un buscador.**

- Las verificadas llevan ✓ en `referencias.md`, con la fecha de verificación.
- Las demás van en la sección «consultadas, no verificadas» y **ningún
  entregable se apoya en ellas**.
- **Verificar también el venue y la provenance.** Dos de las nueve son revisadas
  por pares y cuatro son preprints de autor único; eso se dice donde se usan.

El 14 de octubre de 2026 esta verificación corrigió **tres atribuciones falsas y
un número** ya escritos en el planteamiento. Están registradas al final de
`referencias.md`. **No se borran**: el registro de la corrección vale más que la
afirmación que corrigió.

Para verificar, delegar al subagente `verificador-de-fuentes`: trabaja en
contexto aislado, abre las fuentes y devuelve un veredicto por referencia. No
edita documentos, lo cual es la mitad del punto.

## 3. El guardarraíl contra convertir un hallazgo en tesis

Éste es el modo de falla propio de este portafolio, y ya ocurrió cuatro veces.

> **Si un hallazgo parece lo bastante importante para ser el titular, ésa es la
> señal de degradarlo a paso.**

El proyecto **no tiene tesis**. Todo hallazgo entra como una comprobación dentro
de la fase donde apareció, con su cita y su número.

| Como tesis | Como paso |
|---|---|
| «Descubrí que los monitores confunden revisión con deriva» | «Medí con qué frecuencia lo hacen en esta serie, y lo reporto con su cautela» |
| Necesita defenderse; si la premisa cae, se derrumba el proyecto | **No puede fallar**: si casi nunca ocurre, «lo medí y casi nunca ocurre» sigue siendo un buen paso |

Antes de escribir «nadie ha hecho X», buscarlo activamente en contra. Para eso
existe el subagente `adversario`, cuyo único trabajo es encontrar el
contraejemplo — y existe porque la sesión que escribió la afirmación es la peor
candidata para atacarla.

## 4. Alcance de lo que se afirma

- **No se reclama originalidad.** Los métodos están publicados y citados.
- **Tres nombres prohibidos, porque cada uno afirma más de lo que se mide:**
  - «valor de información» para una discordancia de recomendaciones. Eso tiene
    un significado decision-teórico preciso y esto no es eso: mide que la
    recomendación cambió, no que mejorara.
  - «falsa alarma» para una recomendación que cambia bajo un contrafactual. El
    contraste no identifica la causa de la original.
  - «concept drift demostrado» para un residuo sin explicar. Queda como
    explicación posible, nombrada como tal.
- **Lo que se puede concluir está acotado:** «en una temporada de vigilancia de
  influenza en Estados Unidos, con vintages de granularidad semanal, el detector
  X disparó por revisión en tal fracción de los casos». **No** «los monitores de
  la industria están mal».
- Donde el resultado sea negativo, ambiguo o peor que la referencia simple, **se
  reporta igual.**

## 5. Límites

Los límites declarados en el README se repiten en cualquier entregable derivado.
No se publica un resultado sin sus límites al lado.
