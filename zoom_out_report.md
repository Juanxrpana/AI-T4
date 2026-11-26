# Etapa 5 — Zoom Out inicial

* **Objetivo:** `design_draft.md` (277 líneas)
* **Rango revisado:** 1..277 (`FeatureRange`). No hay `## Detailed Implementation Plan`; `DetailedRange = N/A`.
* **Fecha:** 2026-11-26
* **Modo:** revisión interactiva, etapa por etapa
* **Lentes:** `egm-zoom-out` + `egm-inventive-catalyst` (sesiones nuevas, aisladas)
* **Estándar:** `zoom-out-standard.md`

> **Límite de acceso:** los revisores no pudieron leer `ControllerApi.php` ni `ControllerChat.php` porque están fuera del directorio de trabajo (`permission denied: external_directory`). Las afirmaciones sobre HMAC, sesión PHP, `ControllerValidaciones` y la cola PHP quedan **sin verificar contra el código**. El resto se contrastó con `EGM.md`, `REPASO.md` y el código FastAPI/SQLite.

---

## Veredicto

**No pasa como está.** El documento define bien el problema y tiene buenos instintos de compatibilidad, pero:

1. deja vivo el defecto de alarma/negación que él mismo denuncia;
2. concentra cinco fases acordadas en una sola "fase 1" sin gates intermedios;
3. añade maquinaria de calibración, snapshots, HMAC y métricas que los datos actuales (45 auditorías, 4 dominios) no justifican;
4. promete evidencia y revisión para "toda orientación final", pero la evidencia no es reconstruible y solo cubre el cuestionario.

El camino más corto es separar el trabajo en incrementos y corregir primero el daño clínico.

---

## Hallazgos consolidados

### Bloqueadores

#### B1. La alarma/negación sigue por subcadena
**Fuentes:** Zoom Out (Bloqueador), Inventive (Mayor, F3). **Alcance:** L23, L152–159, L167–192, L45–47.

El problema identifica que `hay_alarma` dispara con «no tengo dificultad para respirar», pero el plan técnico solo reemplaza `detectar_dominio`. `hay_alarma` no pasa por la lógica de polaridad y la confianza **no es gating** («La respuesta no cambia por la confianza», L159). Es el peor reparto: la ruta crítica de seguridad conserva el falso positivo y la ruta rutinaria se vuelve más lista.

**Mínimo necesario:** un motor compartido `detectar_evidencia(texto, términos)` con límites de palabra, alcance de negación y polaridad, usado por **dominio y alarma**. Set dorado con «no tengo fiebre», «sin dolor de pecho», «no tengo dificultad para respirar», doble negación y negación dentro de una frase positiva. Versión y umbral propios para alarma.

---

### Mayores

#### M1. "Fase 1" son las fases 1–5 del plan acordado
**Fuente:** Zoom Out. **Alcance:** L13–15, L86, L31–39.

El brief separaba migración, identidad consulta/turno, detector, cola de validación y aprendizaje gobernado. El draft mete todo en "fase 1" y solo difiere la normalización de columnas. Es una migración big-bang con autenticación nueva, cola nueva y scoring nuevo en un incremento, sin gates de salida.

**Corte recomendado:** (a) migración KB + identidad consulta/turno; (b) evidencia; (c) confianza/cola/HMAC cuando haya datos y rol revisor real.

#### M2. La confianza hace dos trabajos incompatibles
**Fuentes:** Inventive (F1), Zoom Out (mayor sobre scoring). **Alcance:** L35, L165–192, L120, L183.

El texto dice que la confianza "solo marca revisión y no cambia la respuesta", pero `detectar_dominio` devuelve el primer candidato "que supera el umbral" y el único umbral definido es `confianza >= 0.60` + `margen >= 0.15`. Si es el mismo umbral, **sí cambia** el routing y la respuesta. Si es otro, no está especificado.

**Resolución:** separar elegibilidad de routing (regla versionada, p. ej. coincidencia positiva) del score de revisión (calibrable). Persistir `deteccion_version` y `scoring_version` por separado. Si se mantiene un solo umbral, declarar que la respuesta cambia con él y borrar el invariante "no cambia".

#### M3. La evidencia/validación excluye las salidas menos deterministas
**Fuente:** Inventive (F2). **Alcance:** L152–160, L196–204, L206–215, L271–276, L45.

`evidencia_turno` se construye desde `construir_ficha`, que solo existe en el cuestionario. El flujo general produce `orientacion` directo del LLM sin ficha; §9 lo marca `no_aplica`; `emergencia` también. A la vez, §4 marca `catalogo`/`derivar` para revisión y §9 los excluye de la cola. Resultado: lo menos determinista (general, emergencia, fallbacks) es lo que no tiene evidencia revisable, y lo más determinista (cuestionario) es lo que sí.

**Resolución:** un sobre de evidencia terminal para **todo** `tipo_respuesta`: `consulta_id`, `turno_id`, `mensaje_id`, hashes de prompt/historial, modelo, snapshot de catálogo, candidatos y componentes. En general, evidencia mínima (hashes, versión de prompt, modelo, catálogo) sin duplicar la conversación. `no_aplica` debe ser un estado registrado, no una omisión.

#### M4. La evidencia no se puede reconstruir
**Fuente:** Inventive (F4). **Alcance:** L196–204, L246–260, L268.

Se guarda `ficha_hash`, pero la ficha no se persiste. `estado_json` y `memorias.datos_json` se sobrescriben; `DELETE /sesiones` borra `mensajes`; `resumen_ficha` "se anonimiza o borra según la política que se defina". Un hash de una fuente que ya no existe es testigo de integridad, no evidencia reproducible.

**Resolución:** snapshot inmutable por turno de las entradas estructuradas (motivo, respuestas, dominio, especialidad, snapshot de catálogo, hash de contexto) + hash exacto de ficha + versiones. Si se exige recuperar la ficha exacta, cifrarla con retención corta y registro de acceso; si no, declarar que el hash **no** reconstruye. Definir matriz de retención/redacción por tabla y hacer la redacción un evento auditable.

#### M5. La estrategia de FK abandona la integridad en el plano de evidencia
**Fuente:** Inventive (F5). **Alcance:** L117–134, L246–248, L43.

Se promete `foreign_keys=1` y `foreign_key_check` en cero, pero `mensajes` y `auditoria` quedan sin FK y `consulta.session_id` sin FK para que `DELETE /sesiones` siga funcionando. La integridad solo es cierta porque los vínculos que importan para la evidencia no se aplican. Borrar una sesión deja `consulta`, `turno`, `evidencia_turno` y `validacion` huérfanos; `mensaje_id`/`turno_id` pueden apuntar a filas borradas.

**Resolución:** separar plano de sesión viva y plano de caso/evidencia. `ON DELETE SET NULL` para `evidencia_turno.mensaje_id`, `auditoria.mensaje_id`/`turno_id` y `consulta.session_id` (nullable o `session_ref`). `RESTRICT` en la raíz del caso; borrar un caso es un archivado explícito, no un cascade de sesión.

#### M6. El modelo de estado de la cola está duplicado y sin fuente de verdad
**Fuentes:** Zoom Out, Inventive (F8). **Alcance:** L119–125, L158–160, L206–224.

No queda claro qué tabla lista la cola. `revision_requerida` y `alerta_revision` compiten como llave; `validacion` dice "no se actualiza, se añade evento" pero tiene `estado`, `revisor_id`, `decision` y correcciones; `acceso_caso` y `validacion_evento` registran ambos acciones de actor.

**Resolución:** elegir un modelo. Preferible CQRS: `validacion_evento` append-only como escritura y `validacion_actual` como proyección de estado/lease, actualizada en la misma transacción. La cola lee la proyección; `tomar()` es un update condicional con unicidad de asignación activa. Eliminar `alerta_revision` o convertirla en proyección. Si CQRS es demasiado, hacer `validacion` mutable y `validacion_evento` auditoría, y decirlo.

#### M7. Revisión opcional sin muestra de control: sesgo de selección
**Fuente:** Inventive (F6). **Alcance:** L183–190, L233–242, L271–276.

Los umbrales son provisionales "hasta tener validaciones suficientes", pero solo entran a revisión casos de baja confianza, margen pequeño, multi-dominio, `catalogo` o `derivar`. Los errores de alta confianza nunca se muestrean: el sistema no puede estimar su tasa de error ni calibrar el umbral. Solo aprende de lo que el score ya desconfía.

**Resolución:** cohorte de control independiente del score: muestra aleatoria fija de `orientacion` de alta confianza (y una pequeña de `emergencia`/`general`) con `motivo_muestreo`. Calibrar `umbral_confianza`/`margen` con esas discrepancias. Tasa dinámica permitida, nunca decidida por el score bajo prueba.

#### M8. El revisor especialista y la cola de solo super usuario se contradicen
**Fuente:** Inventive (F7). **Alcance:** L36, L206–215, L161.

El texto dice que el especialista es el revisor natural y que, si no valida, el super usuario toma el caso. Pero §5.1 dice que en fase 1 **solo** `admin_super_usuario` lista y decide, y el rol `doctor` queda diferido. El fallback "si no valida" no tiene disparador porque el especialista no puede validar. El `409` "otro revisor tomó el caso" no tiene lease ni expiración: un revisor que abandona bloquea el fallback para siempre.

**Resolución:** o se declara la fase 1 como triage de super usuario y se quita la promesa del especialista, o se emiten capability tokens con `especialidad_id` y `puede_validar`, cola filtrada por especialidad y super usuario como override. Añadir `tomado_en`, `expira_en` y liberación/reasignación automática; el `409` devuelve dueño y expiración.

#### M9. Los snapshots de catálogo duplican un catálogo que PHP ya posee
**Fuente:** Zoom Out. **Alcance:** L96–98, L110, L119.

`catalogo_especialidad`, `catalogo_snapshot` y `catalogo_snapshot_item` crean un segundo catálogo, con trigger y retención sin definir. `php_client` ya cachea el catálogo y PHP es la fuente.

**Resolución:** reutilizar la ruta de lectura existente y guardar el **valor usado** en el turno (id/nombre de especialidad), no una réplica completa. Si se necesita auditoría del catálogo, guardar un hash y la fecha de la consulta.

#### M10. HMAC propio para un solo caller
**Fuente:** Zoom Out. **Alcance:** L231, L269.

FastAPI solo se llama servidor-a-servidor detrás de la API key compartida y PHP ya valida sesión y rol. Añadir un segundo secreto, `nonce`, `exp` y verificación propia crea autenticación a medida para un solo consumidor. No elimina la confianza de fondo: un PHP comprometido tiene ambos secretos.

**Resolución:** reutilizar API key + sesión PHP (o un token firmado estándar) y documentar el riesgo residual de confiar en headers. Si se mantiene, justificar el threat model y la rotación.

#### M11. `GET /validaciones/{id}` escribe `acceso_caso`
**Fuente:** Zoom Out. **Alcance:** L222, L267.

Un GET con efecto de escritura se contamina con prefetch, reintentos o crawlers y mete una escritura en la ruta caliente de la cola.

**Resolución:** registrar el acceso en PHP (donde ya hay sesión) o exponer `POST /validaciones/{id}/visto`.

#### M12. La aprobación de cuatro ojos no se aplica
**Fuente:** Zoom Out. **Alcance:** L123, L238.

Se guardan `generado_por` y `aprobado_por`, pero nunca se comprueba que sean distintos. La gobernanza no se resuelve si el super usuario aprueba su propia propuesta.

**Resolución:** check explícito de actor distinto o declarar que la autoaprobación está permitida (y por qué).

#### M13. Auditoría dentro de la transacción del turno
**Fuente:** Inventive (F9). **Alcance:** L157, L266.

El contrato actual dice que un fallo de auditoría se registra y **no** interrumpe la respuesta. Meter `auditoria` en la transacción del turno hace que un fallo de auditoría tumbe evidencia y mensaje, y el paciente reintente otra llamada al LLM. A la vez se lista "auditorías fallidas" como métrica, lo que implica que puede fallar sola.

**Resolución:** outbox `turno_evento` en la misma transacción + relay con reintento e idempotencia, o `auditoria.registrar` fuera de la transacción con reconciliación y `turno.auditoria_estado`. La respuesta no depende del éxito de auditoría.

#### M14. Los alias chocan con el UNIQUE normalizado
**Fuente:** Inventive (F10). **Alcance:** L104–107, L249–252.

`UNIQUE (dominio_id, tipo, valor_normalizado)` con `_normalizar` que quita acentos: `torácico` y `toracico` normalizan igual; `presión/presion`, `escalofríos/escalofrios`, `cólico/colico`, `picazón/picazon` también. El seed de 39 originales (29 canónicos + 10 alias) no cabe en una tabla con ese UNIQUE.

**Resolución:** índice único parcial solo para canónicos (`WHERE alias_de IS NULL`) + `UNIQUE(alias_de, valor)` para alias, o tabla `dominio_elemento_alias`. El loader ignora alias para detección.

#### M15. Políticas requeridas quedan abiertas
**Fuentes:** Zoom Out, Inventive (F4). **Alcance:** L268, L271–276.

Retención/anonimización de evidencia y alcance de la cola para `emergencia`/`general` se difieren ("según la política que se defina", "salvo que el autor decida lo contrario"). El brief decía que no quedaban decisiones abiertas. Sin ellas no se pueden cerrar las tablas de evidencia.

**Resolución:** resolver o fijar un default explícito antes de bloquear el modelo de evidencia.

#### M16. La evidencia clínica cambia en silencio el límite de SQLite
**Fuente:** Zoom Out. **Alcance:** L196–204, L268.

`EGM.md` dice que SQLite no es la base clínica. `resumen_ficha` guarda motivo, antecedentes y especialidad: contenido clínico, durable, en SQLite. El cambio de límite es implícito.

**Resolución:** declarar que es una copia derivada de evidencia, no una segunda historia clínica, y emparejarla con una regla de retención concreta.

#### M17. Observabilidad sobreconstruida
**Fuente:** Zoom Out. **Alcance:** L225, L264–266.

Nueve familias de métricas + `/validaciones/resumen` + `/salud` para 45 auditorías. `/validaciones/resumen` duplica datos de cola ya prometidos en `/salud`.

**Resolución:** empezar con 2–3 señales (backlog/edad de cola, fallback, violaciones de migración) y añadir una métrica cuando una decisión dependa de ella.

---

### Nits

- **N1. Mecánica prematura:** cursor pagination, `Idempotency-Key` sin tabla, checksums, `normalizer_version` (L183, L221, L224, L111, L127). Con decenas de casos bastan offset/limit y un UNIQUE de decisión.
- **N2. Altitud:** Jaccard exacto, ventana de tokens, lista `no/sin/niega/ausencia de/nunca` y frases doradas (L176–192) son implementación. A nivel de diseño: "coincidencia con límites de palabra y polaridad; una coincidencia solo negada no selecciona dominio".
- **N3. Contrato del loader de alias sin definir:** los alias no deben ser reglas, pero no se dice cómo los filtra `detectar_candidatos` (L107).
- **N4. Columnas y campos diferidos/indefinidos:** `revisor_especialidad_id`, `dominio_corregido_id`, `especialidad_corregida_id`, `confianza_llm`, `capa_error` (no está en la tabla), `peticion_id`, `componentes`, `admin_super_usuario` (no coincide con `rol 10` de `REPASO.md`) (L118–123, L190, L242, L212).
- **N5. `propuesta_conocimiento` no puede representar un dominio nuevo:** `dominio_id` nullable sin campos de dominio y la aprobación exige dominio activo (L123, L238). Separar `propuesta_dominio` o quitar el caso nuevo en fase 1.
- **N6. `Idempotency-Key` sin persistencia:** reintento tras timeout puede duplicar decisión, propuesta o `kb_version` (L224).

---

## Matriz de trazabilidad

| ID | Hallazgo | Severidad | Zoom Out | Inventive |
|---|---|---|---|---|
| B1 | Alarma/negación sin corregir | Blocker | ✔ | F3 |
| M1 | "Fase 1" = 5 fases | Major | ✔ | — |
| M2 | Confianza: routing vs revisión | Major | ✔ | F1 |
| M3 | Evidencia excluye general/emergencia/fallbacks | Major | — | F2 |
| M4 | Evidencia no reconstruible | Major | ✔ | F4 |
| M5 | FK abandonadas en evidencia | Major | — | F5 |
| M6 | Cola/estado duplicado | Major | ✔ | F8 |
| M7 | Sin muestra de control | Major | — | F6 |
| M8 | Especialista vs super usuario; sin lease | Major | — | F7 |
| M9 | Snapshots de catálogo | Major | ✔ | — |
| M10 | HMAC propio | Major | ✔ | — |
| M11 | GET con escritura | Major | ✔ | — |
| M12 | Cuatro ojos no aplicado | Major | ✔ | — |
| M13 | Auditoría en transacción | Major | — | F9 |
| M14 | Alias vs UNIQUE | Major | — | F10 |
| M15 | Políticas abiertas | Major | ✔ | F4 |
| M16 | Límite clínico de SQLite | Major | ✔ | — |
| M17 | Observabilidad sobreconstruida | Major | ✔ | — |
| N1–N6 | Mecánica/altitud/campos/alias/idempotencia | Nit | ✔ | ✔ |

---

## Qué se sostiene

- Conservar `mensajes`, `auditoria`, `sesiones` y `memorias` y añadir ids nullable es el movimiento correcto: preserva `DELETE /sesiones` y la retención de auditoría.
- Envolver `detectar_dominio` en lugar de romper llamadas existentes es buena reutilización, igual que reutilizar `_normalizar`.
- Sembrar los cuatro ejemplos aprendidos como `pendiente` evita una compuerta que nace obsoleta.
- Mantener las columnas JSON operativas y nombrar la fase 2 es un control de alcance honesto.
- Conservar conteos, `foreign_key_check`, arranque fail-closed y rollback probado es proporcionado.

---

## Secuencia recomendada

1. **Corregir B1** (motor de evidencia compartido para dominio y alarma + set dorado de negaciones). Es el único daño clínico vivo.
2. **Incremento A:** migración KB + identidad `consulta`/`turno`, con conteos, `foreign_key_check`, seed y rollback. Sin cola, sin scoring, sin HMAC.
3. **Incremento B:** sobre de evidencia para todo tipo de respuesta + retención/redacción decididas + outbox de auditoría.
4. **Incremento C:** confianza separada (routing vs revisión), muestra de control, cola con lease y gobernanza de cuatro ojos. HMAC solo si el threat model lo exige.

---

## Decisiones abiertas que bloquean el modelo de datos

- Retención/anonimización de `resumen_ficha` y evidencia.
- Alcance de la cola para `emergencia` y `general`.
- Si `validacion` es mutable + evento o CQRS.
- Si se mantiene el rol especialista en fase 1 o solo super usuario.
- Si el catálogo se replica o se guarda solo el valor usado.
