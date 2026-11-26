# Etapa 7 — Critic Review

* **Objetivo:** `design_draft.md`
* **Rango:** 1..277 (`FeatureRange`); `DetailedRange = N/A`
* **Fecha:** 2026-11-26
* **Revisores:** `egm-design`, `egm-structural`, `egm-style` (sesiones nuevas)
* **Estándares:** `feature-spec-standard` para Design y Structural; Style sin estándar
* **Contexto:** `EGM.md`, `concepts_brief.md`, `main.py`, `storage/*`, `ai/*`, `tools/php_client.py`, `guia.md`, `REPASO.md`

> **Límite de acceso:** `ControllerApi.php`, `ControllerChat.php` y el resto del sistema PHP están fuera del directorio de trabajo y no se pudieron leer. Las afirmaciones sobre HMAC, `ControllerValidaciones`, sesión PHP y la cola PHP quedan **sin verificar**. Design Critic sí contrastó los conteos del seed contra `knowledge/dominios.json` y `knowledge/aprendido.json`.

---

## Veredicto

**No pasa el `feature-spec-standard`.** La especificación es detallada en mecánica de esquema, pero:

- omite las dos áreas obligatorias del estándar: **Alternatives Considered** y **Risks & Mitigations**;
- deja vivo el defecto de alarma/negación que ella misma denuncia;
- tiene contradicciones internas de roles, de estado de la cola y de versionado del conocimiento;
- promete evidencia y reproducibilidad que el esquema no puede sostener.

Se consolidan **9 Blockers**, **15 Majors** y **~20 Nits**. Varios Blockers ya habían sido anticipados en `zoom_out_report.md` (B3, B9) y `comprehension_report.md` (B5, B9); se mantienen porque siguen sin resolverse.

---

## Blockers

### B1. Falta la sección obligatoria de alternativas
**Fuentes:** Structural #1, Design #1. **Alcance:** documento completo; estándar 13–21.

La especificación propone un solo camino (KB SQLite, una tabla `dominio_elemento`, cola PHP, validación posterior, fase 1 congelada) y nunca evalúa alternativas viables. `concepts_brief.md` tiene "Alternatives Weighed", pero el draft no lo traslada. El estándar dice que un spec **falla** si no demuestra que otras opciones se consideraron y rechazaron por razones concretas.

**Mínimo:** alternatives para: JSON-como-verdad vs SQLite; una tabla `dominio_elemento` vs tablas por tipo; cola PHP vs panel FastAPI; validación antes de responder vs posterior; normalizar columnas JSON ahora vs fase 2; ficha completa vs resumen estructurado. Cada rechazo con trade-off técnico, no "lo decidió el autor".

### B2. Falta Risks & Mitigations / Limits
**Fuentes:** Structural #2, Design #2. **Alcance:** documento completo; §9 (271–277); estándar 23–27 y 38–39.

§9 son supuestos, no riesgos. No hay tabla de fallos, impactos, mitigaciones, dueño ni métrica. Faltan, entre otros: falso positivo de emergencia; confianza mal calibrada; fallo de escritura de evidencia; contención de escritores SQLite; migración/seed parcial; compromiso o replay del HMAC; PII en evidencia/auditoría; caída de PHP; coste/límite del LLM; pérdida de `storage/midi.db` (local y `.gitignore`); y que la revisión posterior no protege la consulta actual. Tampoco hay rollback ni kill-switch de la ruta de validación/KB.

### B3. La alarma/negación no se migra a la nueva detección
**Fuentes:** Design #3; ya en Zoom Out B1. **Alcance:** L23, L165–192; `ai/cuestionario.py:188–191`; `main.py:289–293`.

El Problem denuncia que `hay_alarma` usa la misma lógica de subcadena («no tengo dificultad para respirar» puede disparar emergencia). §4 solo dice que reemplaza `detectar_dominio`; nunca dice que `hay_alarma` pase por límites de palabra y polaridad. Si queda igual, el falso positivo exacto sigue vivo en la ruta de seguridad.

**Mínimo:** un motor compartido de evidencia (tokenización, límites de palabra, negación, polaridad) para dominio **y** alarma; umbral/recall propios de alarma; set dorado con negaciones y verdaderos positivos; persistir término, polaridad y decisión en evidencia/auditoría.

### B4. `UNIQUE (dominio_id, tipo, valor_normalizado)` choca con alias y con señales duplicadas
**Fuente:** Design #4. **Alcance:** L104–107, L250–251; `knowledge/dominios.json`.

El normalizador quita acentos: `torácico` y `toracico` colisionan. El seed quiere 39 palabras (29 canónicas + 10 alias) con `alias_de`, pero un alias con el mismo `valor_normalizado` viola el UNIQUE. En señales pasa igual: 31 valores crudos → 25 únicos normalizados por 6 pares de acentos (`sudoracion/sudoración`, `convulsion/convulsión`, `deshidratacion/deshidratación`, `vomito/vómito con sangre`, `hinchazon/hinchazón de labios`, `hinchazon/hinchazón de cara`). El diseño solo describe alias para palabras clave.

**Mínimo:** una política de dedup/alias para **todos** los `tipo`; índice único parcial `WHERE alias_de IS NULL` o tabla de alias; seed de solo únicos normalizados con conteo reportado; test que siembre todas las filas y verifique 39→29+10, 31→25+6 (o la alternativa documentada), cero violaciones y detección sin cambios.

### B5. La cola de validación no tiene modelo de estado/asignación representable
**Fuentes:** Design #5, Style #1/#5/#6/#19, Comprehension #1. **Alcance:** L121–124, L160–161, L206–215, L221–224; criterio 47.

`validacion` se declara append-only ("no se actualiza, se añade evento") pero tiene `estado`, `revisor_id`, `decision` y requiere `tomar()` + `409` si otro la tomó. No hay tabla de caso pendiente, ni `asignado_a`/`tomado_en`/lock, ni máquina de estados. `validacion_evento` exige un `validacion_id` que puede no existir antes de decidir. `/validaciones/{id}` no dice si `id` es evidencia o validación. `alerta_revision` es opcional. La cola no se puede implementar de forma fiable.

**Mínimo:** un modelo: `validacion` como caso con `estado`, `asignado_a`, `tomado_en`, `version` optimista; o `caso_revision` separado. Definir estados y transiciones (pendiente, asignada, vista, validada, corregida, descartada, expirada), claim atómico (`UPDATE ... WHERE estado='pendiente'`), historial de eventos por caso y un único id de endpoint. Diagrama de estados + test de concurrencia con dos revisores.

### B6. `kb_version` es metadato, no una versión recuperable del conocimiento
**Fuente:** Design #6. **Alcance:** L119, L126, L196–204, L227, L238; goals 34–35; criterio 45.

`kb_version` guarda solo `version`, `hash`, `normalizer_version`, `descripcion`, `autor`, `creado_en`. `dominio_elemento` no tiene `kb_version_id`, `valid_from/valid_to` ni snapshot. Aprobar una propuesta muta elementos in place y escribe una fila de versión. Por eso `evidencia_turno.kb_version_id` no resuelve el conocimiento exacto de ese turno: no se puede reproducir la detección, comparar versiones ni revertir una publicación.

**Mínimo:** cada `kb_version` como snapshot inmutable (set completo o export content-addressed) y `kb_version_id` o intervalos de validez en los elementos; puntero de versión activa y operación de revert. Test: aprobar → nueva versión; evidencia antigua resuelve la vieja; revert restaura la detección anterior.

### B7. La transacción de evidencia y su política de fallo no están definidas
**Fuente:** Design #7. **Alcance:** L119, L156–157; `main.py:479–508`; `storage/sesiones.py`, `auditoria.py`, `memoria.py`.

El paso 6 mete evidencia, candidatos, mensaje del asistente y auditoría en una transacción, pero hoy la auditoría es best-effort (`main.py` captura el fallo y responde igual) y cada repositorio abre su propio `aiosqlite.connect`. No se dice si un fallo de evidencia bloquea la respuesta. Si es best-effort, "toda orientación final tiene evidencia" es falso; si bloquea, una llamada exitosa al LLM puede terminar en error. Además, `sesiones.estado_json` sigue siendo la máquina de estados y `consulta`/`turno` serían una segunda fuente de verdad, sin regla de consistencia.

**Mínimo:** política explícita: escritura durable de turno/evidencia antes de responder, con camino degradado documentado, o error reintentable. Un único factory de conexión/unit-of-work e incluir `sesiones.estado_json`, `consulta`, `turno`, `mensajes`, `auditoria` y `evidencia_turno` en la misma transacción donde haga falta. Tests de inyección de fallo y métrica de turnos finales sin evidencia.

### B8. Solo las preguntas se filtran explícitamente por aprobación
**Fuente:** Design #8. **Alcance:** L109, L169, L239; criterio 46.

Se dice que `tipo='pregunta'` se lee solo con `estado='aprobado'`, pero no que `detectar_candidatos` y `hay_alarma` filtren `estado='aprobado'`, `activo=1` y dominio activo. Los cuatro ejemplos legacy se importan como `pendiente`; sin filtros explícitos pueden afectar la detección y violar "ninguna propuesta no aprobada cambia `detectar_dominio`". Tampoco se dice cómo recarga el proceso el conocimiento aprobado (caché/invalidación).

**Mínimo:** una consulta `cargar_conocimiento_activo()` usada por detección, alarmas, preguntas y ficha (dominio activo, elemento activo, estado aprobado, tipos). Definir caché e invalidación en cambio de `kb_version`. Tests de que pendientes/rechazados/alias no cambian detección ni alarma, y que un cambio aprobado se ve de forma determinista.

### B9. Contradicción de roles: especialista vs solo super usuario en fase 1
**Fuentes:** Style #1, Design #14, Comprehension #4. **Alcance:** L13, L36, L161, L212, L275.

El Overview y los Goals dicen que el especialista es el revisor natural y el super usuario absorbe lo que el especialista no valida; §5.1 dice que en fase 1 **solo** `admin_super_usuario` lista y decide y que `doctor` queda para una fase posterior; el paso 10 dice que solo el super usuario decide. El fallback "si no valida" no tiene disparador y no hay expiración ni escalado. La implementación construiría la autorización equivocada.

**Mínimo:** o se declara la fase 1 como triage de super usuario y se quita la promesa del especialista, o se incluye el rol doctor ahora con verificación PHP. Definir expiración/escalado, estado `expirada`, dueño y métrica. Test de que el rol correcto puede y el incorrecto no.

---

## Majors

### Evidencia, reproducibilidad y revisión

**M1. El esquema de evidencia no soporta la cola ni la reproducibilidad.** (Design #9, Style #3) `evidencia_turno` no tiene el texto de la respuesta final (solo `respuesta_hash`), pero la cola debe mostrarla. `mensaje_id` es singular con dos mensajes por turno. `componentes` no tiene forma definida (¿JSON? ¿tabla hija?). Faltan `scoring_version`, `detector_version`, `umbral_version`, `prompt_hash`, algoritmo/canonicalización del hash. **Mínimo:** `respuesta_final`, ids de mensaje usuario/asistente (o tabla de enlace), esquema de `componentes`, versiones y hash canónico; test de que una fila de evidencia se puede renderizar y re-verificar.

**M2. Idempotencia de `/orientar` y unicidad de consulta ausentes.** (Design #10) `turno.peticion_id` no tiene origen; el request actual solo trae `consulta` y `session_id`. Reintentos de PHP, timeouts o doble submit crean consultas/turnos duplicados. "Una consulta abierta por sesión" necesita índice único parcial; la asignación de `seq` es racista. **Mínimo:** `peticion_id` (UUID de PHP) en el contrato, unique + devolver el turno existente, `seq` en la misma transacción, índice parcial de consulta abierta, test de concurrencia.

**M3. El objeto de revisión es un resumen, no la ficha.** (Design #11, Comprehension #9) El Goal dice que el especialista valida "la ficha y la respuesta final", pero la evidencia guarda un resumen y la cola muestra solo el resumen. Un resumen puede omitir el detalle que explica la decisión. No se dice si `resumen_ficha` es determinista o generado por el LLM. **Mínimo:** ficha estructurada fiel y redactada con todos los campos que vio el LLM, o redefinir el objeto como "resumen + respuesta final" y registrar la limitación como riesgo aceptado con muestreo/auditoría. Definir el esquema del resumen y su generación.

**M4. Fórmula de confianza, desempate, calibración y muestreo sin definir.** (Design #12, Style #3; ya en Zoom Out M2/M7) Se nombran componentes, pero no fórmula, pesos, normalización, semántica del umbral, top-k ni desempate determinista. `num_candidatos` se define como "número de dominios sobre el umbral" y a la vez es componente: circular. No hay plan de calibración, ni muestreo de alta confianza, ni bandas definidas. **Mínimo:** función y pesos (o artefacto versionado enlazado), desempate, top-k, bandas, muestreo 5–10% de alta confianza, dueño de calibración, tamaño mínimo y fecha de revisión de umbrales.

**M5. HMAC: supuestos, no diseño.** (Design #13, Style #9, Zoom Out M10) El token es la única autorización de decisiones de revisión, pero no se define custodia/rotación de clave, TTL, skew, anti-replay del `nonce`, audience/endpoint binding, comparación en tiempo constante, TLS ni CSRF en POST de PHP. "Si PHP no puede firmarlo, se cambia a servidor-a-servidor" es un fallback sin diseño. **Mínimo:** formato/algoritmo, TTL corto, nonce de un solo uso o caché anti-replay, rotación con `kid`, almacenamiento del secreto, skew, audience/método, TLS, CSRF, rate limit y fallback concreto; tests de expirado, replay, rol/audience incorrectos y CSRF ausente.

**M6. Sincronización y backfill del catálogo sin definir.** (Design #15, Zoom Out M9) No se dice cuándo/cómo se sincroniza (`startup`, periódico, on-demand), cómo se crean snapshots, cómo se normalizan nombres, cómo se hace upsert/desactivación ni cómo se rellena `catalogo_id` nulo. El caché puede estar vacío al arrancar; un seed sin catálogo deja todos los `catalogo_id` nulos. **Mínimo:** job de sync (startup + periódico), snapshot, upsert por `id_categoria`, no borrar filas referenciadas, backfill por nombre normalizado, edad en `/salud`, comportamiento con PHP caído y test de arranque sin catálogo + backfill posterior.

**M7. Retención/PII y "reconstrucción" se contradicen.** (Design #16, Zoom Out M4/M16, Style #7, Comprehension #12) Se dice que la evidencia sobrevive al borrado de sesión y que el vínculo permite reconstruir "si hay una disputa autorizada", pero `DELETE /sesiones` borra todos los `mensajes` y la sesión. La retención se difiere ("según la política que se defina"). `resumen_ficha`, `validacion.comentario` y `auditoria.consulta` contienen datos clínicos/PII sin anonimización, cifrado ni retención por tabla. **Mínimo:** retención/borrado/anonimización por tabla (`mensajes`, `auditoria`, `consulta`, `turno`, `evidencia`, `validacion`, `acceso_caso`); decidir si la evidencia conserva copia redactada para disputas; si no, quitar la promesa de reconstrucción; hook/job de borrado, controles de acceso y test de `DELETE /sesiones`.

**M8. Runner de migraciones, backup y criterios de aceptación insuficientes.** (Design #17) `schema_migrations` se declara, pero no hay runner: formato, orden, checksums, transacciones, idempotencia ni baseline de la base existente. `init_db` solo hace `CREATE TABLE IF NOT EXISTS`. El backup es copia plana antes de WAL; rollback dice "restaurar la copia", pero no trata `-wal`/`-shm` ni el apagado del servicio. Los criterios fijan 10 sesiones/90 mensajes/45 auditorías/1 memoria, que son de entorno y la base está `.gitignore`d. Fail-closed solo mira dominios en cero, no seed parcial. **Mínimo:** runner con transacción/checksum por migración y baseline; backup con API de SQLite o `VACUUM INTO` y checkpoint WAL; test de restore con servicio detenido; invariantes de snapshot de origen + expectativas del seed, y fallo si faltan dominios o preguntas.

**M9. Contrato PHP sin verificar y sin especificar.** (Design #18, Comprehension #11) Se nombran `ControllerValidaciones`, `vistaValidaciones/cola.php`, `detalle.php`, verificación de rol, firma de token y `409` sin request/response, CSRF, mapeo de errores, mapeo de roles, pseudocódigo de firma ni orden de despliegue. Los controladores están fuera del árbol y no se verificaron. **Mínimo:** contrato PHP concreto (rutas, métodos, payloads, códigos, sesión/CSRF, `admin_super_usuario`, firma) y marca "no verificado hasta inspeccionar PHP"; tests con signer stub; si PHP no se puede modificar, declararlo blocker.

**M10. Autorización de aprobación y separación de funciones sin definir.** (Design #19, Zoom Out M12) No se dice quién puede proponer, aprobar o publicar, ni si el aprobador debe diferir del proponente, ni qué rol exige `POST /conocimiento` (hoy solo API key). `POST /propuestas/{id}/aprobar` no dice su rol. **Mínimo:** matriz de autorización (proponer/aprobar/rechazar/publicar) con roles y separación; claims HMAC o identidad de servicio; `autor`, `origen` y `motivo` en la propuesta; auditar proponente y aprobador; tests negativos (doctor no puede aprobar si no le toca; proponente no autoaprueba).

**M11. Matriz de disparo de revisión contradictoria.** (Design #20, Style #2, Comprehension #8) `revision_requerida` se dispara con `catalogo` o `derivar`, pero §9 dice que la cola clínica revisa solo `orientacion` con ficha y que `emergencia`/`general` son `no_aplica`. `catalogo`/`derivar` suelen venir del flujo general y pueden no tener ficha. Además, la degradación operativa (`catalogo no disponible`, `fallback`) no entra en la cola clínica, pero `catalogo`/`derivar` sí la disparan. **Mínimo:** matriz por `tipo_respuesta` y flujo: evidencia, revisión clínica/operativa/ninguna y motivo; separar `revision_clinica` de `revision_operativa`; resolver el caso `catalogo`/`derivar`.

**M12. Acciones FK, índices e índices únicos parciales ausentes.** (Design #21, Zoom Out M5) FKs sin `ON DELETE`/`ON UPDATE`; `consulta.session_id` sin FK ni política de borrado; borrar sesión deja huérfanos. `validacion` referencia dominios/especialidades originales/corregidas sin FK ni snapshot. No hay índices para filtros de cola/joins de evidencia, ni parcial único de consulta abierta por sesión, ni parcial para `(dominio_id, tipo, clave)` nullable. Un `/salud` que reporta `foreign_keys` no prueba que todos los repositorios lo activen. **Mínimo:** acciones FK (`RESTRICT` para conocimiento, `SET NULL`/sin FK para evidencia histórica), columnas snapshot en `validacion`, índices en `evidencia_turno(revision_requerida, creado_en)`, `validacion(estado, creado_en)`, `turno(consulta_id)`, `mensajes(consulta_id/turno_id)`, `auditoria(consulta_id/turno_id)`, parciales de consulta abierta y claves nullables; pragma por factory + test.

**M13. Endpoints existentes y logging clínico crudo no se abordan.** (Design #22) La seguridad solo añade HMAC a los endpoints nuevos. `GET /sesiones/{session_id}` y `GET /auditoria` exponen datos clínicos solo con API key, sin usuario/rol. `main.py:445–448` registra la consulta clínica cruda, contra "sin texto clínico crudo"; `auditoria.consulta` guarda texto clínico crudo. **Mínimo:** autorización por usuario/rol o documentar el límite servicio-a-servicio; redactar/quitar texto clínico de logs; retención/anonimización de auditoría; tests de que los logs no contienen texto clínico libre y que roles no autorizados no leen sesiones/auditoría.

### Modelo de datos, seeds y operación

**M14. `capa_error` y propuestas de dominio nuevo no son representables.** (Design #23, Style #4, Comprehension #13) `propuesta_conocimiento` no tiene `capa_error` aunque el texto dice que lo guarda; `dominio_id` nullable "para proponer dominio nuevo" pero faltan `nombre`, `min_preguntas`, `max_preguntas`, `orden`. **Mínimo:** `capa_error` con enum/CHECK; `tipo='dominio'` con payload o tabla `propuesta_dominio` y comportamiento de aprobación.

**M15. Polaridad de candidatos y terminología inconsistentes.** (Design #24, Style #13/#14, Comprehension #14/#15) Se dice que la polaridad negativa se registra en `termino`, pero `turno_dominio_candidato` no tiene `polaridad`/`negado`; codificarla en texto libre es frágil. El seed dice "12 hallazgos" pero el enum tiene `descartar`, no `hallazgo`; "5 especialidades" son 5 relaciones con 2 nombres distintos. **Mínimo:** `polaridad`/`negado` y ventana/offset del match; estandarizar "hallazgo" vs `descartar`; hacer que los conteos del seed usen los nombres del enum.

**M16. `alerta_revision` opcional y estado duplicado.** (Style #6, Design #5) Una tabla presentada como opcional ("si se separa la cola de la evidencia") no puede ser contrato de fase 1. Compite con `revision_requerida`. **Mínimo:** incluirla con fase declarada o eliminarla; una sola fuente de verdad del estado de cola.

**M17. Detalles operativos sin especificar.** (Design #25, Style #8) Cursor pagination sin campo/orden/desempate; `Idempotency-Key` sin store/TTL/scope/conflicto; sin SLOs/alertas de edad de cola, completitud de evidencia o correcciones; llamadas LLM de propuestas sin límite por caso/día, timeout o fallback; `flujo` incluye `emergencia` aunque es un resultado; `schema_migrations` sin PK/unique. **Mínimo:** cursor `(creado_en, id)`, store de idempotencia por actor+endpoint+key con TTL, SLOs/umbrales, límites de LLM, `flujo` como camino y `tipo_respuesta` como resultado, decidir `alerta_revision`, PK en `schema_migrations`.

### Redacción y estilo

**M18. Supuestos duplicados y repetición defensiva.** (Style #8, #10) §9 repite decisiones ya dichas (umbrales en 183, no-consultas-sintéticas en 258, fase 2 en 15/58/86). "La validación/confianza no bloquea ni cambia la respuesta" se repite cinco veces. **Acción:** eliminar duplicados; conservar el Non-Goal y el paso 8. Sustituir "fase 2 acordada" por una referencia.

**M19. "Valida" ambiguo.** (Style #11) En el paso 5, "valida" se usa para validación de esquema en un documento donde "validación" es revisión clínica. **Acción:** "valida la respuesta contra el esquema y el catálogo" o "verifica la respuesta".

**M20. `detectar_dominio`: reemplazo vs envoltorio.** (Style #12) "Se sustituye por dos funciones" se contradice con "se conserva como envoltorio". **Acción:** "se añade `detectar_candidatos`; `detectar_dominio` se conserva como envoltorio".

**M21. Etiquetas del seed y "5 especialidades".** (Style #13/#15, Comprehension #15) "Señales"/"hallazgos"/"relaciones" no coinciden con el enum; "5 especialidades" son 5 relaciones/2 nombres. **Acción:** usar nombres del enum y aclarar "5 relaciones (2 nombres distintos)".

**M22. "Set dorado" sin definir.** (Style #14) Se usa como artefacto definido pero no se dice qué contiene, criterio de paso ni dónde vive. **Acción:** definirlo una vez y referenciarlo.

**M23. "Aprendizaje en cada consulta" exagera.** (Style #16) `main.py` solo llama `aprender_ejemplo` al detectar un dominio nuevo. **Acción:** "al iniciar un dominio".

**M24. Deriva de identificadores.** (Style #17) `confianza`/`margen` vs `confianza_total`/`margen_top1_top2`; "toda conexión de escritura" vs "todas las conexiones". **Acción:** usar los nombres exactos de columna y el mismo alcance.

**M25. Redacción del Overview/Problem.** (Style #18) "El paciente sigue siendo recomendado" (se recomienda la especialidad, no el paciente); "no bloquea… no obligado a agendar" duplicado; tautología en línea 25; jerga "no tiene superficie" en 27. **Acción:** recortar a la afirmación verificable.

**M26. `confianza_llm` especulativa.** (Style #20) Describe una columna hipotética que no decide el flag en fase 1. **Acción:** DROP o "no se implementa en fase 1".

**M27. `motivo_codigo` en aprobación.** (Style #21) "Aprueba, corrige o descarta. Exige `motivo_codigo`" implica razón también al aprobar. **Acción:** exigirlo al corregir/descartar, salvo que aprobar también lo requiera.

---

## Nits

| # | Hallazgo | Fuente |
|---|---|---|
| N1 | Encabezados H2 en inglés y cuerpo en español; falta simetría | Structural #4 |
| N2 | Marcadores `*` y `-` alternados | Structural #5 |
| N3 | "componentes" sin backticks en la tabla de `evidencia_turno` | Structural #6 |
| N4 | `---` aislado tras el front-matter, sin función | Structural #7 |
| N5 | "Criterios medibles:" es párrafo, no heading/lista con ancla | Structural #8 |
| N6 | `peticion_id`, "banda de confianza", "set dorado", `prompt_version`, "caso" sin definir | Style #16 / Comprehension #16 |
| N7 | Conteos base (10/90/45/30/39/29/4) sin fecha, query ni archivo | Comprehension #17 |
| N8 | Ruta de llamada de la cola (JS navegador vs proxy PHP) ambigua | Comprehension #18 |
| N9 | Sincronización de catálogo sin mecanismo (quién/cuándo/retención) | Comprehension #19 |
| N10 | Aprobación de propuesta sin actor declarado | Comprehension #20 |
| N11 | "Legado" sin campo marcador (`consulta_id IS NULL`?) | Style #15 |
| N12 | `validacion` mutable vs append-only (detalle de B5) | Style #19 |
| N13 | `motivo_codigo` y `capa_error` sin enum de valores | Style #5 / Design #23 |
| N14 | `schema_migrations` sin PK/unique; cursor sin campo/orden | Design #25 |
| N15 | No hay enlaces cruzados a artefactos del proyecto (JSON, `guia.md`, PHP) | Comprehension #11 |

---

## Matriz de trazabilidad (Blockers y Majors)

| ID | Hallazgo | Structural | Style | Design | Etapas previas |
|---|---|---|---|---|---|
| B1 | Alternatives missing | #1 | — | #1 | — |
| B2 | Risks & Mitigations missing | #2 | — | #2 | — |
| B3 | Alarma/negación no migrada | — | — | #3 | Zoom Out B1 |
| B4 | UNIQUE vs alias/señales | — | #13 | #4 | — |
| B5 | Cola sin estado/asignación | — | #1/#5/#6 | #5 | Comprehension #1 |
| B6 | `kb_version` no recuperable | — | — | #6 | — |
| B7 | Transacción/fallo de evidencia | — | — | #7 | — |
| B8 | Filtro de aprobación incompleto | — | — | #8 | — |
| B9 | Contradicción de roles | — | #1 | #14 | Comprehension #4 |
| M1 | Esquema de evidencia insuficiente | — | #3 | #9 | — |
| M2 | Idempotencia/consulta única | — | — | #10 | — |
| M3 | Revisión es resumen, no ficha | — | — | #11 | Comprehension #9 |
| M4 | Confianza sin fórmula/calibración/muestreo | — | #3 | #12 | Zoom Out M2/M7 |
| M5 | HMAC sin diseño | — | #9 | #13 | Zoom Out M10 |
| M6 | Catálogo sin sync/backfill | — | — | #15 | Zoom Out M9 |
| M7 | Retención/PII vs reconstrucción | — | #7 | #16 | Zoom Out M4/M16; Comprehension #12 |
| M8 | Migración/backup/criterios | — | — | #17 | — |
| M9 | Contrato PHP sin verificar | — | — | #18 | Comprehension #11 |
| M10 | Autorización de aprobación | — | — | #19 | Zoom Out M12 |
| M11 | Matriz de revisión contradictoria | — | #2 | #20 | Comprehension #8 |
| M12 | FK/índices/parciales | — | — | #21 | Zoom Out M5 |
| M13 | Endpoints existentes/logs crudos | — | — | #22 | — |
| M14 | `capa_error`/dominio nuevo | — | #4 | #23 | Comprehension #13 |
| M15 | Polaridad/terminología | — | #13/#14 | #24 | Comprehension #14/#15 |
| M16 | `alerta_revision` opcional | — | #6 | #5 | — |
| M17 | Detalles operativos | — | #8 | #25 | — |
| M18–M27 | Redacción/estilo | #4–#8 | #8–#21 | — | — |

---

## Qué se sostiene

- **Structural:** sin saltos de nivel (H1→H2→H3→H4); tablas con separadores coherentes; ambos bloques Mermaid balanceados; lista anidada bien indentada; no hay enlaces que validar. Las secciones presentes siguen un orden lógico; el problema es lo que falta, no lo que está mal puesto.
- **Design:** los conteos de palabras clave (39→29+10) son correctos; los de señales necesitan política (31→25+6). La verificación se hizo contra `knowledge/dominios.json` y `knowledge/aprendido.json`.
- **Style KEEP:** umbrales provisionales con trigger de calibración (183); FK nullables que nombran `DELETE /sesiones` y retención (134); no guardar prompt crudo (204); fallback de catálogo no disponible (252); rollback hasta probar el seed en base vacía (260); API key de transporte vs identidad HMAC del revisor (269).

---

## Orden de resolución recomendado

1. **B3** (alarma/negación) — daño clínico vivo; es el primer bloque.
2. **B1 + B2** (alternativas y riesgos) — obligatorios del estándar; habilitan el resto de la revisión.
3. **B5 + B9 + B6 + B7** (cola, roles, versionado, transacción) — sin esto no hay revisión ni reproducibilidad.
4. **B4 + B8** (alias/dedup y filtro de aprobación) — seeds y gobernanza.
5. **M1–M17** por tema: evidencia, migración, seguridad, PHP, retención.
6. **M18–M27 y N1–N15** — limpieza editorial.

---

## Nota de acceso

Para una revisión de implementación real (Etapa 9, si se añade un plan detallado) o para validar la parte PHP de esta etapa, hay que copiar los controladores y vistas PHP relevantes a `context/` dentro del directorio de trabajo o conceder acceso. Sin eso, las afirmaciones sobre `ControllerValidaciones`, HMAC y sesión PHP quedan como **no verificadas**.
