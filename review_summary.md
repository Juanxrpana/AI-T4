# Resumen de revisión EGM — `design_draft.md`

* **Documento:** `design_draft.md` (277 líneas)
* **Rango:** 1..277 (`FeatureRange`); `DetailedRange = N/A`
* **Fecha:** 2026-11-26
* **Modo:** interactivo, etapa por etapa
* **Etapas ejecutadas:** 5 (Zoom Out inicial), 6 (Comprehension), 7 (Critic), 8 (Intermediate Zoom Out)
* **Etapa 9:** no aplica (no hay plan de implementación detallado)
* **Contexto PHP:** copiado a `context/php/` (ControllerApi, ControllerChat, ControllerUsuarios, ControllerRoles, Rutas, ModeloPermisos)

## Veredicto

**No pasa el `feature-spec-standard`.** La dirección de tres planos (conocimiento / operación / revisión) es correcta. El incremento no: el plano de revisión es un segundo subsistema de administración para 4 dominios y 0 validaciones, y al plano de operación le falta una sola conexión/unit-of-work y un loader único de conocimiento. El defecto de alarma/negación que el propio documento denuncia sigue vivo.

## Reportes

| Etapa | Archivo | Contenido |
|---|---|---|
| 5 | `zoom_out_report.md` | Simplicidad/YAGNI + contradicciones; 1 Blocker, 17 Majors |
| 6 | `comprehension_report.md` | Parafraseo + huecos de comprensión; 1 Blocker, 12 Majors, 7 Nits |
| 7 | `critic_report.md` | Design + Structural + Style; 9 Blockers, 15 Majors, ~20 Nits |
| 8 | `intermediate_zoom_out_report.md` | Re-auditoría con PHP accesible; prior findings sin mitigar + 5 nuevos |

## Blockers abiertos (Etapa 7 consolidada)

1. **B1** — Falta Alternatives Considered (obligatorio del estándar).
2. **B2** — Falta Risks & Mitigations / Limits.
3. **B3** — `hay_alarma` sigue por subcadena; la negación no se aplica a la alarma.
4. **B4** — `UNIQUE (dominio_id, tipo, valor_normalizado)` choca con alias y señales duplicadas (39→29+10, 31→25+6).
5. **B5** — La cola no tiene unidad de caso, máquina de estados ni lease; `validacion` es append-only y mutable a la vez.
6. **B6** — `kb_version` no es un snapshot recuperable; no se puede reproducir la detección de un turno.
7. **B7** — La transacción de evidencia y su política de fallo no están definidas (auditoría best-effort vs transacción).
8. **B8** — Solo las preguntas se filtran por `estado='aprobado'`; detección y alarma no.
9. **B9** — Contradicción de roles: especialista vs solo `admin_super_usuario` en fase 1.

## Hallazgos nuevos de la Etapa 8

- **N1 (Major):** `docs/03-base-de-conocimiento-relacional.md` ya define otro modelo KB y el draft lo reemplaza en silencio.
- **N2 (Major):** un ciclo de aprobación generalizado a los 8 `tipo` de `dominio_elemento`.
- **N3 (Major):** la compuerta de confianza se construye antes de tener volumen para calibrarla.
- **N4 (Nit):** el criterio "toda orientación final tiene evidencia" es falso para las 45 auditorías legacy.
- **N5 (Nit):** `POST /conocimiento` cambia de semántica sin nota de compatibilidad.

## Orden recomendado

1. **B3** (alarma/negación) — daño clínico vivo.
2. **B1 + B2** (alternativas y riesgos) — obligatorios del estándar.
3. **B5 + B9 + B6 + B7** (cola, roles, versionado, transacción).
4. **B4 + B8** (alias/dedup y filtro de aprobación).
5. Majors por tema: evidencia, migración, seguridad, PHP, retención.
6. Nits y limpieza editorial.

## Siguiente paso

Para habilitar la Etapa 9 hace falta añadir a `design_draft.md` una sección **`## Detailed Implementation Plan`** (con el plan por incrementos, contratos y pruebas). Antes de redactarla conviene resolver o aceptar explícitamente los Blockers B1–B9; el orden de arriba es el más corto.

## Nota de acceso

La parte PHP ya está en `context/php/`. `ControllerValidaciones` y sus vistas **no existen** todavía; el draft las describe como si fueran a construirse. `admin_super_usuario` tampoco existe: los roles son `id_rol` numérico + `ModeloPermisos`.
