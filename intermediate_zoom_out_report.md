# Etapa 8 — Intermediate Zoom Out

* **Objetivo:** `design_draft.md`
* **Rango:** 1..277 (`FeatureRange`); `DetailedRange = N/A`
* **Fecha:** 2026-11-26
* **Revisor:** `egm-zoom-out` (sesión nueva)
* **Estándar:** `zoom-out-standard.md`
* **Contexto:** `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`, `EGM.md`, `concepts_brief.md`, código FastAPI/SQLite y PHP copiado a `context/php/`

> **Estado del texto:** `design_draft.md` no cambió desde la Etapa 5. No hay mitigación textual de ningún Blocker ni Major previo. La revisión confirma que las objeciones siguen abiertas y añade cinco hallazgos nuevos. La Etapa 9 no aplica: no hay plan de implementación detallado.

---

## Veredicto

**No pasa.** La dirección de tres planos (conocimiento / operación / revisión) sigue siendo correcta. El alcance no: el plano de revisión es un segundo subsistema de administración dimensionado para 4 dominios y 0 validaciones, y al plano de operación le falta la pieza clave — **una sola conexión/unit-of-work y un solo loader de conocimiento**. Sin eso, las garantías de FK y de aprobación son afirmaciones, no invariantes.

---

## 1. Estado de los hallazgos previos

Todos los Blockers y Majors de las Etapas 5–7 siguen abiertos. Agrupados:

| Hallazgo previo | Estado | Evidencia en el texto actual |
|---|---|---|
| Zoom Out B1 / Critic B3 — alarma/negación | **Sin resolver** | §4 (L167–192) solo reemplaza `detectar_dominio`; `hay_alarma` sigue por subcadena (`ai/cuestionario.py:188–191`, llamado en `main.py:291`). |
| Critic B1/B2 — alternativas y riesgos | **Sin resolver** | No hay secciones nuevas; §9 (L271–277) son supuestos, no riesgos ni alternativas rechazadas. |
| Zoom Out M1 — colapso de fases | **Sin resolver** | El draft sigue metiendo las fases 1–5 del brief en "fase 1"; `concepts_brief.md` define 0–6 con gates. |
| Zoom Out M2 / Critic M4 — confianza routing vs revisión | **Sin resolver** | Un solo umbral sirve a `detectar_dominio` ("supera el umbral", L170) y a `revision_requerida` (L183); sin fórmula, pesos ni escala. |
| Zoom Out M3 / Critic M1/M3 — alcance/esquema de evidencia | **Sin resolver** | `evidencia_turno` (L119) sigue sin `respuesta_final`, `scoring_version`, `detector_version`; `general`/`emergencia` siguen `no_aplica`. |
| Zoom Out M4/M5/M7/M16 / Critic B6/B7/M7/M12 — durabilidad, FK, retención | **Sin resolver** | Sin acciones FK, sin unit-of-work, sin retención por tabla; `DELETE /sesiones` sigue dejando huérfanos. |
| Zoom Out M6/M8/M11/M12/M17 / Critic B5/B9/M11/M16 — plano de revisión | **Sin resolver** | Sin unidad de cola, máquina de estados ni lease; contradicción especialista vs `admin_super_usuario`; GET escribe `acceso_caso`; `alerta_revision` opcional; nueve familias de métricas. |
| Zoom Out M9/M10 / Critic M5/M6/M9 — catálogo, HMAC, PHP | **Sin resolver** | Sigue el segundo catálogo y un tercer mecanismo de auth; verificado abajo. |
| Zoom Out M13/M14/M15 / Critic B4/B8/M8/M14 — transacción, alias, políticas | **Sin resolver** | Auditoría dentro de la transacción del turno; alias vs `UNIQUE(valor_normalizado)`; retención/alcance de cola diferidos. |
| Comprehension #1–#13 | **Sin resolver** | Unidad de cola, `consulta`/`turno`, ficha, roles, frontera PHP, retención y ruta de corrección siguen sin definir. |
| Nits N1–N15 | **Sin resolver** | Cursor pagination, `Idempotency-Key`, checksums, campo de polaridad, terminología, enlaces cruzados. |

### Verificación contra el código

- **Autorización (M10, B9, Critic M9).** El router PHP autoriza por `id_rol` numérico + módulo + uno de cuatro verbos vía `ModeloPermisos` (`Rutas.php:199–232`, `ModeloPermisos.php:20–42`). **No existe `admin_super_usuario`.** `ControllerChat` exige sesión + CSRF (`ControllerChat.php:15–32`) y envía `X-Usuario-Rol` desde `$_SESSION['rol']` (línea 78); el login sí setea `$_SESSION['rol']` e `id_rol` (`ControllerIniciarSesion.php:359–360`), así que el header **no está vacío** por defecto (corrección al revisor: el subset copiado no incluía el login). `ControllerApi` ya usa key compartida + `X-Usuario-Id` + `esPersonalDelCentro` (`ControllerApi.php:9–22,113–135`). PHP ya usa JWT HS256 con `JWT_SECRET` en el flujo móvil (`Rutas.php:7,135–141`). El `admin_super_usuario` + `VALIDACION_HMAC_KEY` + `nonce` del draft es un tercer mecanismo para un solo caller y mueve autorización a FastAPI, contra el invariante del proyecto (`EGM.md:48–49,107`). La solución menor: registrar `Validaciones` en `ModeloPermisos`/`equivalentes.php`, validar sesión + CSRF en PHP y pasar `id_usuario`/`id_rol` verificados con la key existente, o reutilizar el JWT existente.
- **Catálogo (M9/M6).** `php_client.py:63–92` ya cachea `/Api/apiEspecialidades` 600 s y `main.py:51` lo precarga. `cuestionario.especialidad_candidata` resuelve nombres contra el catálogo vivo y cae a `CONSULTA GENERAL`. Las tres tablas nuevas duplican caché y diseño; guardar el `id_categoria`/`nombre` usado por turno sigue siendo menor.
- **Cierre/ciclo de vida (M11, Comprehension #8).** `main.py:342` marca `estado["completo"] = True` para **cualquier** respuesta no `aclaracion` del flujo general, incluidos `datos`, `navegacion` y `registro_paciente`; `_finalizar` y `_cierre_general` también lo hacen. El draft cierra `consulta` solo con `orientacion`, `emergencia`, `derivar` o `catalogo` (L163) y no dice qué pasa con los otros tipos terminales. Hay dos reglas de cierre: `estado_json` y `consulta.estado` pueden discrepar.
- **Conexión/transacción (B7, Comprehension #6).** `storage/db.py` solo tiene `init_db`; `sesiones.py`, `auditoria.py` y `memoria.py` abren cada uno su `aiosqlite.connect(DB_PATH)`. No hay `conectar()`, aunque L247 dice "todas las conexiones usan la fábrica". `main.py:490–508` trata auditoría como best-effort y responde igual, contra L157 (una transacción para evidencia, mensaje y auditoría). La fábrica/unit-of-work no está en la arquitectura, el mermaid ni la lista de componentes, aunque los goals 1, 5 y 7 dependen de ella.
- **Límite clínico de SQLite (M16).** `EGM.md:51` dice que SQLite no es la base clínica; `resumen_ficha` (L198) guarda motivo, antecedentes y especialidad de forma durable. `docs/03` §3.16 trata texto clínico y embeddings como sensibles. El draft no declara el resumen como copia derivada con retención concreta; L268 lo difiere.
- **Tres copias de la respuesta (M4/M7).** `main.py:487` escribe el texto del asistente en `mensajes.texto`; `main.py:505` escribe la respuesta completa en `auditoria.json_respuesta`; el draft añade la respuesta final a `evidencia_turno` (L200). Tres copias, tres ciclos de vida: `borrar_sesion` borra mensajes (`sesiones.py:97–101`), auditoría nunca se borra, evidencia no tiene retención. El draft dice "sin duplicar la conversación" pero no dice cuál es canónica ni cuál sobrevive al borrado.

---

## 2. Hallazgos nuevos

### N1 — Major — El diseño KB relacional de `docs/03` queda reemplazado en silencio
**Alcance:** §2.1 (L90–111), §7 (L249–254); `docs/03-base-de-conocimiento-relacional.md` §3.3, §3.10–3.12, §3.14; `EGM.md:84`.

`docs/03` ya documenta el modelo KB del proyecto: tablas por tipo, `dominio.clave` como PK, mapeo JSON→tabla, conteos observados (4 dominios, 19 preguntas, 39 palabras, 31 señales, 11 pruebas, 12 asociaciones, 12 hallazgos, 4 ejemplos) y una tabla de retención sugerida (sesión 90 días, auditoría 1 año). El draft introduce otro modelo (`dominio.id` surrogate, una `dominio_elemento` polimórfica, `catalogo_id`) y no lo menciona. Hay dos modelos ER para la misma KB. **Mínimo:** declarar `docs/03` superado y mapear viejo→nuevo, o adoptar su modelo. Reutilizar su mapeo, conteos y retención cerraría además M15 con un default explícito.

### N2 — Major — Un ciclo de aprobación generalizado a los ocho `tipo` de `dominio_elemento`
**Alcance:** L95, L100, L108–109, L239.

`estado`/`origen`/`alias_de`/`catalogo_id` aplican a toda fila, pero solo `palabra_clave`, `pregunta` y `ejemplo` tienen ruta de propuesta/aprobación descrita. `senal_alarma`, `especialidad`, `prueba`, `asociacion` y `descartar` son listas de referencia que siempre estarán `aprobado`; cada loader debe decidir cómo tratar `pendiente`/`rechazado` en ellas, y B8 ya muestra que esa regla no está especificada. Es generalidad especulativa. **Mínimo:** una regla de lectura (`activo=1 AND estado='aprobado'`) para todos los tipos, sembrar los tipos de referencia aprobados y no construir rutas de propuesta para ellos; o limitar las columnas de gobernanza a los tipos gobernados.

### N3 — Major — La compuerta de confianza se construye antes de tener volumen para calibrarla
**Alcance:** L35, L165–192, L183–190, L221, L225, §9 L274.

Se añaden seis componentes, `scoring_version`, umbrales, margen, bandas, calibración y muestra de control antes de tener una sola validación. El problema raíz es evidencia y aprobación, no ranking. Con 45 auditorías y 0 validaciones, revisar todos los turnos finales es factible y más simple: conservar `detectar_candidatos` y los componentes persistidos como evidencia, pero **quitar `confianza_total` como compuerta** hasta que haya datos. Eso elimina configuración de umbral, margen, filtros de banda, dueño de calibración y el problema de muestreo (M7). Si el entregable académico exige el índice, mantenerlo como señal almacenada y **no gating**.

### N4 — Nit — El criterio de aceptación es anterior a las filas legacy
**Alcance:** L45, L258.

"Toda orientación final tiene consulta, turno, resumen de evidencia, confianza explicable y estado de revisión" es falso para las 45 auditorías históricas que el diseño deja legacy con ids nulos. `/salud` nunca podrá afirmarlo. **Mínimo:** acotar el criterio a post-migración o añadir marcador `legacy`.

### N5 — Nit — `POST /conocimiento` cambia de semántica sin nota de compatibilidad
**Alcance:** L236; `main.py:553–574`; `EGM.md:26`; `REPASO.md:170`.

El endpoint hoy devuelve `{ok, dominio, aprendido}` y escribe de inmediato; el draft lo convierte en creador de propuesta pendiente. No nombra caller, forma de respuesta ni deprecación. **Mínimo:** versionar el endpoint o conservar la forma (`ok`, `dominio`, `pendiente`) y documentar el consumidor.

---

## 3. ¿Sigue en pie la arquitectura de alto nivel?

**Sí a nivel de planos; no a nivel de incremento.**

- **En pie:** la descomposición conocimiento / operación / revisión es correcta. Conservar `mensajes`, `auditoria`, `sesiones` y `memorias` y añadir ids nullable preserva `DELETE /sesiones` y la retención de auditoría. Envolver `detectar_dominio` y reutilizar `_normalizar` es buena reutilización.
- **No en pie:** el "plano de revisión" es un segundo subsistema de administración (controlador, vistas, auth, estado de caso, event log, access log, propuestas, versionado de KB) para 4 dominios y 0 validaciones. Al plano de operación le falta la pieza de la que dependen todos los goals: **una sola conexión/unit-of-work y un solo loader de conocimiento**. Sin eso, las garantías de FK y aprobación son afirmaciones.
- **Secuencia:** la recomendación de `zoom_out_report.md` sigue: (1) motor compartido de alarma/negación; (2) migración KB + identidad `consulta`/`turno`; (3) evidencia para todo turno final + retención/outbox; (4) cola/roles de revisión; (5) confianza y propuestas. Los hallazgos nuevos acortan 4–5: revisar todos los turnos finales primero, añadir el score después y reconciliar `docs/03` antes de construir el esquema.

---

## 4. Nota de alcance

La Etapa 9 (Implementation Readiness) **no aplica**: el documento no tiene plan de implementación detallado. Si se añade uno, habrá que ejecutar la Etapa 9 sobre `DetailedRange` con `egm-implementation-readiness`, `egm-codebase-details` y `egm-style`.
