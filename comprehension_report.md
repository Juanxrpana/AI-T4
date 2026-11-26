# Etapa 6 — Comprehension Test

* **Objetivo:** `design_draft.md`
* **Rango:** 1..277 (`FeatureRange`); `DetailedRange = N/A`
* **Fecha:** 2026-11-26
* **Revisor:** `egm-comprehension` (lector ingenuo, sesión nueva)
* **Estándar:** ninguno (la prueba es de autocontención, no de detalle)

> Reporte del revisor. Se conserva el texto original (inglés) para no alterar el parafraseo ni los hallazgos. El parafraseo es la prueba principal: si es incorrecto, eso mismo es un hallazgo.

---

**What this proposes**

MIDI would get three new pieces. First, a relational clinical knowledge base in SQLite rooted in `dominio`, with every domain list (keywords, alarms, questions, specialties, tests, associations, discards, examples) in one `dominio_elemento` table under real foreign keys; `knowledge/dominios.json` and `knowledge/aprendido.json` stop being the source of truth and become a versioned seed. Second, explicit identity for each clinical episode (`consulta`) and exchange (`turno`), so that the ficha, the final answer, the audit row and any later medical validation all hang off the same turn. Third, a stored, deterministic confidence score that flags doubtful, multi-domain or non-clinical responses for later, optional review; the review queue and screen live in the existing PHP system while FastAPI exposes `/validaciones`, `/propuestas` and `/salud`, and corrections become pending knowledge proposals that must be approved before they change detection. A migration seeds the new tables from the current JSON, preserves the existing rows and the four operational JSON columns, and adds evidence hashes, version stamps, health, metrics and retention; normalizing those columns is deferred to phase 2.

**How the existing system works, per this document**

MIDI is the FastAPI component that orients a patient toward a specialty; its clinical knowledge lives in two JSON files read and merged in memory, automatic learning saves the user's phrase on every domain detection, and `POST /conocimiento` writes examples and keywords immediately, with no approval and no knowledge version. SQLite stores sessions, messages, memory and audit, but `session_id` is reused across consultations, `mensajes` has neither `consulta_id` nor `turno_id`, `agregar_mensaje` returns no id, audit is linked neither to the message nor to the ficha, and the ficha is built in memory and thrown away. Domain detection returns the first keyword substring match or the best Jaccard example above 0.6, with no score, top-k or margin, and `hay_alarma` uses the same substring logic, so negations ("no tengo fiebre") trigger domains and alarms. The current base holds 10 sessions, 90 messages, 45 audits (30 with null domain), 4 domains, 19 questions, 39 curated keywords (29 after normalization) and 4 learned examples; medical validation has no queue, role, state or owner, and the API only requires a shared key and trusts the role headers PHP sends. The specialty catalogue and patient data continue to come from the existing PHP system.

---

**1. Blocker — the review queue has no defined unit of work or lifecycle**
Affected scope: §3 steps 9–10 (lines 160–161), §5.1 (206–215), §5.2 table (219–229), tables `validacion`, `validacion_evento`, `alerta_revision` (121–124).
The document says `/validaciones` lists cases, that `{id}/tomar` claims one, and that `{id}/decision` approves/corrects/discards, but it never says which row a "pending case" is. A `validacion` row requires `revisor_id`, `decision`, `estado` and `motivo_codigo`, yet it is described as "no se actualiza, se añade evento"; `validacion_evento` is append-only, so the claim ("tomado") and later state have nowhere to live, and `alerta_revision` is explicitly "opcional". Nothing states when the `validacion` row is inserted, with which initial state, or how the queue is populated in the first place. I can paraphrase the steps individually but not the lifecycle they are supposed to form, which is one of the document's three pillars.

**2. Major — `consulta` and `turno` are never defined, and `consulta` names two different things**
Affected scope: Overview (11–15), Goal 3 (33), §2.2 `consulta`/`turno` (117–118), §3 step 1–6 (152–157).
The input field of `POST /orientar` is `consulta` (a string), `auditoria.consulta` stores that string, and the new table is also called `consulta`. The document never states that the table means "one clinical episode inside a session" or that a `turno` is one request/response; both have to be inferred. It also never says whether aclaración messages create `turno` rows without evidence, or how that squares with `evidencia_turno UNIQUE(turno_id)` plus step 6 ("transacción por turno") versus line 119 ("se escribe en el turno final, no en cada aclaración"). A naive reader will read "abre o recupera la consulta" as the same object as the user's text.

**3. Major — the confidence index is promised as "explicable" but its computation is absent**
Affected scope: §4, table 174–181, thresholds 183–188.
Six components are named and the document says "la fórmula y los pesos se guardan con `scoring_version`", but no formula, no weights, no output range and no relation between `confianza_total` and `margen_top1_top2` are given. A reader cannot tell whether `0.60` of confidence and `0.15` of margin are on the same scale, how `penalizacion_negacion` combines with positive evidence, or what a `confianza_total` value of, say, 0.62 means. Since Goal 6 sells this as an explicable index, the document should let the reader explain it; it does not.

**4. Major — who reviews, and who operates MIDI, contradicts itself and is never defined**
Affected scope: line 11 ("orienta al paciente"), line 36 ("el especialista… es el revisor natural"), mermaid line 74 ("Recepción / Doctor chat"), §5.1 line 212 (only `admin_super_usuario`, `doctor` reserved for a later phase), §9 line 275.
The Overview describes a specialist-first workflow where the super user only absorbs what the specialist did not validate; §5.1 says in phase 1 only the super user can list and decide and the `doctor` role is reserved for later. The diagram, at the same time, shows reception and doctors using the chat. None of `super usuario`, `admin_super_usuario`, `doctor` or `recepción` is defined, linked, or mapped to the PHP session roles, and the document also says MIDI "orienta al paciente" while the chat is operated by staff. The reader cannot tell who is expected to use the queue or the chat in this phase.

**5. Major — the alarm path is left untouched although it is part of the problem**
Affected scope: Problem line 23, §4 line 167, §4 line 192.
The Problem states that `hay_alarma` uses the same substring logic and that "no tengo dificultad para respirar" can fire an alarm; §4 replaces only `detectar_dominio` and never says whether `hay_alarma` is rebuilt on `detectar_candidatos` and the negation window. Given that `emergencia` is one of the responses that closes a consultation (line 163) and is declared `no_aplica` for review (§9), the reader cannot tell whether the false-alarm defect is in scope or silently dropped.

**6. Major — the foreign-key precondition is assumed rather than stated, and `conectar()` is ambiguous**
Affected scope: Goal 1 (31), §7 step 2 (247), line 256.
The document asserts "`PRAGMA foreign_keys=ON` se aplica en todas las conexiones" and writes "`storage/db.py:conectar()` … Todas las conexiones usan la fábrica" without saying that today each repository opens its own `aiosqlite.connect(DB_PATH)` and the pragma is off, or whether `conectar()` already exists or is to be created (the current `storage/db.py` has no such function). A reader can easily conclude that turning the pragma on in `init_db` is enough, which is the exact error the design is meant to avoid. Also unstated: whether the new `consulta.session_id` is a FK to `sesiones` and what that implies for `DELETE /sesiones`.

**7. Major — columns and states are used in the prose but missing from the tables**
Affected scope: line 119 (`componentes`), 183 (`scoring_version`), 190 (`confianza_llm`), 242 (`capa_error`), 275 (`no_aplica`).
None of these appears in the declared schemas or enums. `componentes` is a bare word inside a column list: it is unclear whether it is one column (and if so, whether it is JSON, against the document's own anti-JSON stance) or shorthand for six component columns. `no_aplica` has no field to live in (`revision_requerida` is a boolean), and it is unclear whether `emergencia`/`general` still receive an `evidencia_turno` row, although Goal 45 says every final orientation has one. `degradado` (line 118) is a boolean with no reason, so the two conditions the document distinguishes ("catálogo no disponible" vs "proveedor en fallback") cannot be told apart. A reader following the schema cannot implement or query what the prose promises.

**8. Major — the request/response lifecycle is assumed, not described**
Affected scope: §3 line 155, `flujo` enum 117, line 163, step 8 line 159.
"Aplica el cuestionario" and "usa el flujo general" are pivotal (they decide whether there is a domain, a ficha, evidence or review), but neither flow is described: the guided 3–5-question questionnaire, the LLM flow with its 5-question cap, and how a session knows a consultation has closed (the `estado_json` complete flag) are all taken for granted. The `flujo` value `otro` and the possible `consulta.estado` values are never explained. The document returns `RespuestaOrientacion` but enumerates only `orientacion`, `emergencia`, `derivar` and `catalogo`; the actual contract also has `aclaracion`, `datos`, `navegacion` and `registro_paciente`, and the document never says what happens to those turns (evidence? review status? consultation closure?). Step 7 also omits the `catalogo`/`derivar` trigger that §4 later adds, so the two lists disagree.

**9. Major — "ficha" and "resumen_ficha" are never defined**
Affected scope: lines 11, 19, 34, 119, 198–204.
The ficha is the object the doctor reviews and the thing `ficha_hash` covers, but it is used from the Overview on and only obliquely identified at line 199 as "el texto exacto que recibió el LLM". The document never lists its fields (motivo, answers, history, up to five controls, memories), never says whether `resumen_ficha` is deterministic extraction or a second LLM call (the brief's "si se genera con el LLM, se genera una vez" is absent here), and never says who builds it. A reader cannot tell what is being hashed, reviewed, anonymized or reconstructed.

**10. Major — "seed versionado" contradicts "eliminar los JSON" and "conservar los JSON"**
Affected scope: Overview line 15, Goal 2 (32), §7 steps 4 and 8 (249–260).
Line 15 says the two JSON files "se convierten en un seed versionado"; Goal 2 says they stop being the source of truth; §7 seeds from `dominios.json` and says to keep the JSON "hasta que el seed esté probado en una base vacía". The reader cannot tell whether the JSON files remain in the repository as the seed source, are deleted after migration, or are only a temporary deployment fallback, nor what makes a seed "versioned" (a file, a table, a git tag?).

**11. Major — the PHP boundary is unverifiable and its scope is unclear**
Affected scope: §1 mermaid (72–84), §5.1 (206–215), line 231, line 273.
"El sistema PHP existente" is never located, linked or described: no repository, framework, auth mechanism, menu structure or file conventions. `ControllerValidaciones` with `cola()/detalle()/tomar()/decidir()/propuestas()` is introduced as if it exists, and nothing says it is new; the same applies to `vistaValidaciones/cola.php`, `detalle.php` and the "enlace en el menú de administración". The PHP sources are outside this working directory and could not be read, so these claims cannot be checked; this affects comprehension because the reader cannot tell what must be built, what already exists, or whether `admin_super_usuario` and the session roles are real. The document also contains no links or cross-references to any project artifact (knowledge JSONs, `ai/schemas.py`, `docs/03`, `guia.md`, PHP repo), which is the root cause of several gaps above.

**12. Major — retention and "reconstruction" contradict each other**
Affected scope: §5 line 204, §8 line 268, §2.2 line 134.
§5 says the detail stays in `mensajes` and that `consulta_id`/`turno_id` allow reconstructing the case "si hay una disputa autorizada"; §8 says `resumen_ficha` is anonymized or deleted "cuando se elimina la sesión, según la política que se defina" — and `DELETE /sesiones` deletes messages. If both happen, the promised reconstruction is impossible, and the policy is explicitly left undefined. The document also does not say whether `evidencia_turno.mensaje_id` is a FK to `mensajes` (only the reverse direction is addressed), so the reader cannot tell what breaks when a session is deleted.

**13. Major — the correction → proposal path cannot be reconstructed**
Affected scope: §6 (235–242), §5.2 (226–228), `propuesta_conocimiento` (123).
"El LLM se invoca solo cuando el revisor pide generar propuestas, con límite de 3 palabras y 2 preguntas" has no endpoint, no UI action and no request/response contract; `POST /propuestas/{id}/aprobar` presupposes proposals that nothing in the design creates. "Una corrección con `motivo_codigo` de dominio o pregunta puede generar propuestas" does not say which proposals, for which `tipo`, or with what `clave`/`valor`, and which `motivo_codigo` values qualify is vague. `capa_error` is said to be stored on the proposal but is absent from the table. Finally, `dominio_id` is nullable "para proponer un dominio nuevo", but the listed columns carry no `nombre`, `min_preguntas` or `max_preguntas`, so a new-domain proposal cannot be represented. A reader cannot follow the learning loop end to end.

**14. Nit — negation polarity has no field**
Affected scope: §4 line 192, `turno_dominio_candidato` (120).
"A coincidence negada … se registra en `termino` con polaridad negativa." `termino` is a single text column and no polarity field exists; the reader must guess the encoding (prefix, sign, separate row) and how the UI/queue would display it.

**15. Nit — seed vocabulary does not match the `tipo` enum, and "5 especialidades" is ambiguous**
Affected scope: §7 step 4 (250–252), `dominio_elemento.tipo` (100).
"31 señales", "12 hallazgos" and "5 relaciones de especialidad" do not map one-to-one onto `senal_alarma`, `descartar` and `especialidad`; "hallazgos" in particular has no obvious `tipo`. Line 252 then says "Las 5 especialidades se resuelven … contra el catálogo", but there are 5 relations and only 2 distinct names (`CARDIOLOGIA`, `CONSULTA GENERAL`), so a reader may expect five catalogue rows.

**16. Nit — several project-specific terms are used as if already known**
Affected scope: `peticion_id` (118, step 2), "banda de confianza" (213), "set dorado de pruebas" (192, 255), `prompt_version` (119, 201), "caso" (160–161, 222).
`peticion_id` has no stated origin or format; nothing says how many confidence bands exist or where the cut-offs are; the "golden set" is referred to as if it already exists and is maintained somewhere; `prompt_version` has no stated source (a hash of `guia.md`?); "caso" is used interchangeably for a consultation, a turn with evidence, and a validation row. Each is small, but together they force the reader to invent the vocabulary.

**17. Nit — baseline counts have no provenance**
Affected scope: Problem line 25.
"10 sesiones, 90 mensajes, 45 auditorías… 30 sin dominio… 39 palabras… 29… 4 ejemplos" is presented without a date, a query or a file reference, yet these numbers are later used as migration acceptance criteria (Goals 38, line 44). A reader cannot reproduce them or tell whether they describe the current dev database or a snapshot.

**18. Nit — the queue UI's call path is ambiguous**
Affected scope: line 160, line 215, line 231.
"La cola PHP consulta `GET /validaciones`" and "la UI recarga el estado" suggest browser JavaScript, while "el token no se expone al navegador: lo genera el servidor PHP" requires server-side calls. It is unclear whether the PHP page proxies every call to FastAPI or whether some page script calls FastAPI directly; that distinction changes the whole security story for the queue.

**19. Nit — catalogue synchronization is asserted but not described**
Affected scope: `catalogo_especialidad`, `catalogo_snapshot` (96–98), line 110, line 252, `/salud` (229, 264).
Nothing says where the catalogue comes from (the document only says "sincronización con PHP"), how often a snapshot is taken, who triggers it, how long it lives, or what happens when PHP is unreachable at seed time. The reader knows a snapshot exists and reports its "edad", but not the mechanism that produces it.

**20. Nit — approval of a proposal has no stated actor**
Affected scope: §5.2 line 227, §6 line 238.
`POST /propuestas/{id}/aprobar` publishes knowledge and creates a `kb_version`, but the document never says who may call it, whether it is subject to the same `admin_super_usuario` rule as the review queue, or whether the approver must differ from the proposer. Given that the whole learning gate rests on this endpoint, the missing actor is a comprehension gap even if the endpoint list is otherwise clear.
