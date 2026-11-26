# Goldfish Annotated Review Report

**Target:** `design_draft.md` (`full file, lines 1–277`)
**Source:** Blockers B1–B9 de `critic_report.md` (Etapa 7), confirmados sin mitigar en `intermediate_zoom_out_report.md` (Etapa 8).
**Scope:** solo Blockers. Majors y Nits quedan para una ronda posterior.

## Prioritized Findings & AI Suggestions

### B1. Falta Alternatives Considered [`egm-structural`, `egm-design`] — Severity: Blocker
* **Affected Scope:** documento completo; estándar `feature-spec-standard` 13–21.
* **Discrepancy Description:** el draft propone un solo camino y no evalúa alternativas viables; el estándar dice que el spec falla si no demuestra que otras opciones se consideraron y rechazaron por razones concretas.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** es un requisito obligatorio del estándar y `concepts_brief.md` ya tiene "Alternatives Weighed"; el draft debe trasladarlo y ampliarlo.
* ***Proposed Edit:***
  * Location: al final del documento (después de la línea 277), nuevo H2.
  * Change: insertar una sección `## Alternatives Considered` con esta tabla:

```markdown
## Alternatives Considered

| Alternativa | Por qué se rechazó |
|---|---|
| JSON (`dominios.json` + `aprendido.json`) como fuente de verdad | Sin FK, sin versión, sin autoría ni rollback; el aprendizaje automático no pasa por aprobación. Se conserva solo como seed versionado. |
| Tablas por tipo (`dominio_palabra`, `dominio_pregunta`, ...) en vez de una `dominio_elemento` | Multiplica el DDL y las consultas del loader para 8 listas pequeñas; una tabla con `tipo` + `CHECK` y un índice parcial cubre el caso con menos superficie. |
| Cola de validación dentro de FastAPI | Duplica sesión, CSRF, roles y menú que PHP ya tiene; el proyecto concentra autorización en PHP. |
| Validación médica antes de responder | Bloquea la recomendación y convierte al revisor en cuello de botella; el brief exige que la recomendación no se bloquee. |
| Normalizar `estado_json`, `datos_json`, `embedding` y `json_respuesta` en la fase 1 | Reescritura de `main.py` y cuatro repositorios en el mismo incremento; se acordó fase 2 con contratos y pruebas propias. |
| Guardar la ficha completa en vez de un resumen | Más PII durable y retención sin resolver; el resumen estructurado + hash reduce exposición, a costa de no reconstruir el texto exacto (riesgo aceptado explícito). |
```

### B2. Falta Risks & Mitigations / Limits [`egm-structural`, `egm-design`] — Severity: Blocker
* **Affected Scope:** documento completo; estándar 23–27 y 38–39; §9 (271–277).
* **Discrepancy Description:** §9 contiene supuestos, no riesgos; no hay fallos, impactos, mitigaciones, dueño ni métrica.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** el estándar exige límites y mitigaciones explícitos; sin ellos no se puede decidir qué se acepta.
* ***Proposed Edit:***
  * Location: al final del documento, nuevo H2 después de `## Alternatives Considered`.
  * Change: insertar `## Risks & Mitigations` con esta tabla (mínimo):

```markdown
## Risks & Mitigations

| Riesgo | Disparador | Impacto | Mitigación | Dueño / métrica |
|---|---|---|---|---|
| Falso positivo de emergencia por negación | `hay_alarma` por subcadena | Alarma innecesaria; ansiedad y coste | Motor compartido con límites de palabra, negación y polaridad; set dorado; umbral/recall propios | Alarma: tasa de FP/TP |
| Confianza mal calibrada | Umbrales 0.60/0.15 sin datos | Falsa assurance o cola vacía | Muestra de control de alta confianza; fecha de revisión; versión de scoring | Calibración: errores por banda |
| Fallo al escribir evidencia | SQLite bloqueada o error | Turno sin evidencia o error al paciente | Unit-of-work + política durable; outbox de auditoría; reintento idempotente | Turnos sin evidencia |
| Contención de escritores SQLite | Varias peticiones concurrentes | `database is locked` y latencia | `busy_timeout`, WAL, una conexión por unidad de trabajo; un worker en fase 1 | Errores de lock |
| Migración/seed parcial | Corte a mitad del seed | KB incompleta o detección distinta | Transacción por migración, `foreign_key_check`, fail-closed por dominios/preguntas faltantes, rollback probado | Migración: checksum/estado |
| Compromiso o replay del token de revisor | Secreto filtrado o token robado | Decisiones de revisión no autorizadas | TTL corto, nonce/replay cache, rotación `kid`, TLS, CSRF, audience/método; o reutilizar JWT existente | Auth: 401/409 por replay |
| PII en evidencia/auditoría | Texto clínico persistido | Exposición y retención indefinida | Retención por tabla, redacción/anonimización, acceso auditado, no guardar prompt crudo | Retención: filas vencidas |
| PHP no disponible | Caída del sistema PHP | Sin catálogo, sin cola, sin datos de paciente | Degradación explícita: catálogo cacheado con edad, `catalogo`/`derivar`, cola en pausa | Salud: edad de catálogo |
| Coste/límite del LLM | Cuota agotada o 429 | Respuesta degradada | Fallback determinista, timeout por modelo, límite por caso/día, métrica de fallback | LLM: 429/fallback |
| Pérdida de `storage/midi.db` | Borrado o disco | Pérdida de sesiones/evidencia local | Backup con API de SQLite/`VACUUM INTO`, checkpoint WAL, restore probado; la KB se re-siembra | Backup: último OK |
| La revisión posterior no protege la consulta actual | Revisión solo post-hoc | El paciente ya recibió la respuesta | Riesgo aceptado explícito; la validación es control de calidad, no compuerta | Aceptado |
```

### B3. La alarma/negación no se migra [`egm-design`; ya en `zoom_out_report.md` B1] — Severity: Blocker
* **Affected Scope:** §4 (167–192), Problem (23), `ai/cuestionario.py:188–191`, `main.py:289–293`.
* **Discrepancy Description:** el Problem denuncia que `hay_alarma` dispara con «no tengo dificultad para respirar», pero §4 solo reemplaza `detectar_dominio`; `hay_alarma` nunca pasa por polaridad.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** es la ruta de seguridad clínica; dejar el falso positivo vivo contradice el objetivo del diseño.
* ***Proposed Edit:***
  * Location: §4, tras el párrafo de `detectar_candidatos` (línea ~170) y en el criterio medible (línea ~47).
  * Change: añadir:
    > `hay_alarma` se migra al mismo motor de evidencia: tokenización, límites de palabra, ventana de negación y polaridad. Una coincidencia solo negada no dispara alarma. La alarma tiene umbral y recall propios, versión propia (`alarm_version`) y un set dorado con «no tengo dificultad para respirar», «sin dolor de pecho», doble negación y un positivo real. La decisión, el término y la polaridad se guardan en evidencia/auditoría.

  * Change: añadir al criterio medible: "Ninguna alarma se dispara por una coincidencia negada; el set dorado de alarma pasa al 100%."

### B4. UNIQUE normalizado vs alias y señales duplicadas [`egm-design`] — Severity: Blocker
* **Affected Scope:** §2.1 (104–107), §7 (249–252).
* **Discrepancy Description:** `UNIQUE (dominio_id, tipo, valor_normalizado)` rechaza alias que normalizan igual (`torácico`/`toracico`) y no cubre las 31 señales crudas → 25 únicas (6 pares de acentos).
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** el seed no puede cumplir 39→29+10 y 31→25+6 con esa restricción.
* ***Proposed Edit:***
  * Location: §2.1, reglas de `dominio_elemento` (104–107) y §7 paso 4 (250–252).
  * Change: reemplazar el UNIQUE por:
    - índice único parcial `(dominio_id, tipo, valor_normalizado) WHERE alias_de IS NULL`;
    - `UNIQUE(alias_de, valor)` para alias;
    - política de dedup para **todos** los `tipo` (no solo `palabra_clave`);
    - seed con conteos explícitos: 39 palabras → 29 canónicas + 10 alias; 31 señales → 25 únicas + 6 alias; test que siembra todas las filas y verifica cero violaciones y detección sin cambios.

### B5. La cola no tiene unidad de caso, estado ni lease [`egm-design`, `egm-style`, `egm-comprehension`] — Severity: Blocker
* **Affected Scope:** §2.2 (121–124), §3 (160–161), §5.1 (206–215), §5.2 (219–229).
* **Discrepancy Description:** `validacion` se declara append-only pero tiene estado/decisión; no hay caso pendiente, asignación, lease ni transiciones; `validacion_evento` exige un id que puede no existir; `alerta_revision` compite como llave.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** sin unidad de caso y claim atómico, dos revisores pueden pisarse y el `409` no tiene dueño ni expiración.
* ***Proposed Edit:***
  * Location: §2.2 (121–124), §3 (160–161), §5.1/§5.2 (206–229).
  * Change: usar `validacion` como **caso mutable** con `estado` (`pendiente`, `asignada`, `vista`, `validada`, `corregida`, `descartada`, `expirada`), `asignado_a`, `tomado_en`, `expira_en`, `version`; `validacion_evento` append-only como historial; eliminar `alerta_revision`. `GET /validaciones/{id}` usa `validacion.id`. `tomar()` es `UPDATE ... WHERE estado='pendiente'` (o reasignación si expiró); el `409` devuelve dueño y `expira_en`. Añadir diagrama de estados y test de dos revisores concurrentes.

### B6. `kb_version` no es un snapshot recuperable [`egm-design`] — Severity: Blocker
* **Affected Scope:** §2.2 (119, 126), §5 (196–204), §6 (238); goals 34–35.
* **Discrepancy Description:** `kb_version` guarda hash/metadatos, pero los elementos se mutan in place; `evidencia_turno.kb_version_id` no resuelve el conocimiento exacto.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** sin snapshot no hay reproducción, comparación ni revert.
* ***Proposed Edit:***
  * Location: §2.2 (119, 126) y §6 (238).
  * Change: `kb_version` inmutable + `kb_elemento_snapshot(kb_version_id, dominio_id, tipo, clave, valor, valor_normalizado, estado, alias_de)`; `evidencia_turno.kb_version_id` apunta al snapshot; puntero `kb_version.activa` (o tabla `kb_activa`); revert = activar una versión anterior. Test: aprobar → nueva versión; evidencia antigua resuelve la vieja; revert restaura la detección.

### B7. Transacción de evidencia y política de fallo sin definir [`egm-design`] — Severity: Blocker
* **Affected Scope:** §2.2 (129–134), §3 (156–157), §7 (247); `storage/db.py`, `main.py:490–508`.
* **Discrepancy Description:** no hay factory/unit-of-work; cada repositorio abre su conexión; la auditoría es best-effort y el draft la mete en la transacción del turno; `estado_json` y `consulta.estado` pueden discrepar.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** sin una unidad de trabajo, las FK y la evidencia son afirmaciones; sin política de fallo, la respuesta y la evidencia pueden divergir.
* ***Proposed Edit:***
  * Location: §2.2 (129–134), §3 (156–157), §7 paso 2 (247).
  * Change: añadir `storage/db.py:conectar()` con `PRAGMA foreign_keys=ON`, `busy_timeout` y WAL; un unit-of-work por turno que incluya `consulta`, `turno`, `mensajes`, `evidencia_turno` y `sesiones.estado_json`; auditar por outbox (`turno_evento`) para que un fallo de auditoría no tumbe el turno; política: evidencia durable antes de responder; si falla, `503` reintentable y log; reconciliación de `estado_json`/`consulta.estado` con una tabla de mapeo; tests de inyección de fallo.

### B8. Solo las preguntas se filtran por aprobación [`egm-design`] — Severity: Blocker
* **Affected Scope:** §2.1 (109), §4 (169), §6 (239); criterio 46.
* **Discrepancy Description:** `detectar_candidatos` y `hay_alarma` no declaran filtros de `estado='aprobado'`, `activo=1` y dominio activo; los ejemplos legacy `pendiente` podrían afectar la detección.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** contradice "ninguna propuesta no aprobada cambia `detectar_dominio`".
* ***Proposed Edit:***
  * Location: §2.1 (109), §4 (169), §6 (239).
  * Change: definir `cargar_conocimiento_activo()` único para detección, alarma, preguntas y ficha, con `dominio.activo=1 AND elemento.activo=1 AND elemento.estado='aprobado'` y filtro de tipo; invalidar caché al cambiar `kb_version`; tests de que pendientes/rechazados/alias no cambian detección ni alarma y que un aprobado se ve de forma determinista.

### B9. Contradicción de roles y tercer mecanismo de auth [`egm-style`, `egm-design`, `egm-comprehension`] — Severity: Blocker
* **Affected Scope:** Overview (13), Goal (36), §3 (161), §5.1 (212), §5.2 (231), §9 (275); `Rutas.php`, `ModeloPermisos.php`, `ControllerChat.php`, `ControllerIniciarSesion.php`.
* **Discrepancy Description:** el texto dice especialista como revisor natural y super usuario como fallback, pero §5.1 dice que en fase 1 solo `admin_super_usuario` decide y `doctor` queda diferido; no hay lease ni expiración. Además, `admin_super_usuario` no existe en PHP (roles numéricos `id_rol` + `ModeloPermisos`), y el `VALIDACION_HMAC_KEY` es un tercer mecanismo cuando ya hay API key y JWT HS256.
* ***AI Suggestion:*** PROPOSE FIX
* ***Justification:*** la implementación construiría la autorización equivocada; el proyecto ya tiene un modelo de roles y un JWT.
* ***Proposed Edit:***
  * Location: Overview (13), Goal (36), §5.1 (212), §5.2 (231), §9 (275).
  * Change: declarar la fase 1 como **triage del super usuario** mapeado al `id_rol` existente (10/Superadmin o el que corresponda) y `ModeloPermisos`; mover la validación por especialista a fase 2; añadir `expira_en`/escalado y estado `expirada`; reutilizar el JWT HS256 existente (`JWT_SECRET`) o la API key + sesión PHP verificada en lugar de `VALIDACION_HMAC_KEY`; si se mantiene un token, mapear `id_rol`/`especialidad_id` y documentar custodia/rotación; añadir matriz de autorización y tests de rol correcto/incorrecto.

---

## Resumen de categorías

| ID | Sugerencia | Motivo |
|---|---|---|
| B1 | PROPOSE FIX | Requisito obligatorio del estándar |
| B2 | PROPOSE FIX | Requisito obligatorio del estándar |
| B3 | PROPOSE FIX | Daño clínico vivo |
| B4 | PROPOSE FIX | El seed no puede cumplir el UNIQUE |
| B5 | PROPOSE FIX | La cola no es implementable |
| B6 | PROPOSE FIX | No hay reproducibilidad |
| B7 | PROPOSE FIX | FK/evidencia sin garantía |
| B8 | PROPOSE FIX | Contradice el invariante de aprobación |
| B9 | PROPOSE FIX | Roles/auth inconsistentes con PHP |

**ESCLALATE:** ninguno.
**CONTEST:** ninguno.
**DECLINE:** ninguno (solo se revisan Blockers).
