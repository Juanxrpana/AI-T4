---
title: "MIDI — Paquete de diagramación para presentación formal"
subtitle: "Sistema CEM Jehová Rafa · Componente inteligente"
version: "1.0"
date: "2026-11-20"
---

# Paquete de diagramación — MIDI

Este paquete reúne los tres entregables gráficos solicitados para la presentación formal del componente inteligente **MIDI** (Módulo Inteligente de Derivación e Información) del **Centro de Especialidades Médicas Jehová Rafa**.

Cada documento es autónomo: contiene el diagrama, su explicación, las tablas de apoyo y un guion breve para exponerlo.

## 1. Inventario de entregables

| N.º | Archivo | Diagrama principal | Propósito en la presentación |
|---|---|---|---|
| 1 | [`01-diagrama-general-caso-sistema.md`](./01-diagrama-general-caso-sistema.md) | Diagrama general de casos de uso del sistema | Mostrar **quién usa el sistema**, **qué hace** y **dónde aparece MIDI** dentro del CEM Jehová Rafa. |
| 2 | [`02-arquitectura-componente-inteligente.md`](./02-arquitectura-componente-inteligente.md) | Arquitectura del componente inteligente | Evidenciar las **capas, componentes, flujos y mecanismos de inteligencia** de MIDI. |
| 3 | [`03-base-de-conocimiento-relacional.md`](./03-base-de-conocimiento-relacional.md) | Modelo relacional de la base de conocimiento | Presentar **las tablas que conforman la base de conocimiento**, sus relaciones, llaves y reglas de integridad. |

## 2. Orden sugerido de exposición

| Momento | Diapositiva | Documento | Tiempo estimado |
|---|---|---|---|
| Apertura | Contexto: sistema CEM + MIDI | Doc. 1, sección 1 | 1 min |
| 1 | Casos de uso generales | Doc. 1, diagrama | 3 min |
| 2 | Caso de uso central «Orientar consulta» | Doc. 1, sección 5 | 2 min |
| 3 | Arquitectura por capas | Doc. 2, vista 1 | 3 min |
| 4 | Núcleo inteligente | Doc. 2, vista 2 | 3 min |
| 5 | Flujo de una consulta | Doc. 2, secuencia | 2 min |
| 6 | Base de conocimiento curada | Doc. 3, diagrama A | 3 min |
| 7 | Base de conocimiento operativa | Doc. 3, diagrama B | 2 min |
| 8 | Integridad y ciclo de vida | Doc. 3, secciones 6–8 | 2 min |
| Cierre | Alcance, límites y conclusiones | Doc. 1, sección 8; Doc. 2, sección 7 | 1 min |

**Duración total sugerida:** 20–22 minutos, con 5 minutos adicionales para preguntas.

## 3. Convenciones de nomenclatura

| Prefijo | Significado | Ejemplo |
|---|---|---|
| `CU-xx` | Caso de uso | `CU-05` Aplicar cuestionario guiado |
| `C-xx` | Componente de arquitectura | `C-05` Base de conocimiento curada |
| `TAB-xx` | Tabla o entidad del modelo de datos | `TAB-01` `dominio` |
| `RF-xx` | Requisito funcional referenciado | `RF-05` Orientación clínica |
| `RNF-xx` | Requisito no funcional | `RNF-03` Latencia y respaldo |

## 4. Leyenda visual utilizada

| Color | Significado |
|---|---|
| Azul oscuro | Actores humanos |
| Azul claro | Casos de uso o componentes de exposición |
| Índigo | Núcleo inteligente de MIDI |
| Verde | Datos, conocimiento y memoria |
| Naranja | Sistemas externos (PHP, MariaDB, proveedores de IA) |
| Gris | Canal de presentación e integración |

## 5. Cómo renderizar y exportar

### 5.1 Diagramas Mermaid

Los diagramas están escritos en **Mermaid**, por lo que se renderizan directamente en GitHub, GitLab, Obsidian, Notion y Visual Studio Code (extensión *Markdown Preview Mermaid Support*).

Para exportar a SVG o PNG de alta resolución:

```bash
# 1. Copiar el bloque Mermaid a un archivo .mmd
# 2. Ejecutar Mermaid CLI
npx -y @mermaid-js/mermaid-cli -i diagrama.mmd -o diagrama.svg -b transparent
npx -y @mermaid-js/mermaid-cli -i diagrama.mmd -o diagrama.png -w 2400 -b white
```

También puede pegarlo en <https://mermaid.live> y usar **Actions → Download PNG/SVG**.

### 5.2 Diagramas PlantUML de respaldo

Cada documento incluye, al final, la fuente **PlantUML** equivalente para quienes prefieran exportar desde <https://www.plantuml.com/plantuml> o la herramienta local:

```bash
plantuml -tpng diagrama.puml
plantuml -tsvg diagrama.puml
```

### 5.3 Recomendación para diapositivas

- Usar fondo blanco o transparente y exportar en **SVG** para evitar pixelado.
- En 16:9, ubicar el diagrama a ancho completo y dejar la tabla explicativa en la diapositiva siguiente.
- Para el diagrama de casos de uso, usar orientación **horizontal**; para arquitectura y modelo relacional, **vertical**.

## 6. Fuentes de verdad del contenido

| Tema | Archivo del repositorio |
|---|---|
| Punto de entrada y flujo HTTP | `main.py` |
| Motor del cuestionario y aprendizaje | `ai/cuestionario.py` |
| Esquema de respuesta | `ai/schemas.py` |
| Proveedores y cadena de respaldo | `ai/proveedores.py`, `ai/gemini.py`, `ai/openai_compatible.py` |
| Prompt del sistema | `guia.md`, `ai/comun.py` |
| Herramientas de solo lectura | `tools/clinica.py` |
| Integración PHP | `tools/php_client.py` |
| Base de conocimiento curada | `knowledge/dominios.json` |
| Conocimiento aprendido | `knowledge/aprendido.json` |
| Persistencia local | `storage/db.py`, `storage/sesiones.py`, `storage/memoria.py`, `storage/auditoria.py` |
| Rutas del frontend | `config/modulos.py` |
| Contexto del sistema | `EGM.md`, `propuesta.md`, `metodologia.md` |

## 7. Nota de alcance

Los diagramas describen el sistema **tal como está implementado en este repositorio** y distinguen explícitamente lo que es una **propuesta de normalización** (modelo relacional de la base de conocimiento curada) de lo que **ya existe físicamente** (archivos JSON y tablas SQLite). Esta distinción es importante para no atribuir al sistema actual tablas o funcionalidades que todavía no están desplegadas.

## 8. Glosario breve

| Término | Definición |
|---|---|
| **MIDI** | Módulo Inteligente de Derivación e Información; componente FastAPI del CEM Jehová Rafa. |
| **KB** | *Knowledge Base* o base de conocimiento: dominios, preguntas, señales, especialidades y pruebas. |
| **Dominio** | Motivo clínico agrupador (dolor torácico, fiebre, dolor abdominal, lesión en la piel). |
| **Cuestionario guiado** | Máquina de estados que formula entre 3 y 5 preguntas antes de orientar. |
| **Señal de alarma** | Síntoma o frase que obliga a derivar de inmediato a emergencia. |
| **NLU simbólica** | Detección de dominio por palabras clave y similitud con ejemplos aprendidos. |
| **LLM** | Modelo de lenguaje usado para redactar la orientación final. |
| **Embedding** | Vector numérico que representa el significado de un texto para comparar similitud. |
| **Guardrail** | Validación que impide respuestas fuera del esquema, del catálogo o del alcance clínico. |
| **Memoria operativa** | Sesiones, mensajes y resúmenes persistidos en SQLite. |
| **Auditoría** | Registro append-only de cada consulta, modelo, latencia y respuesta. |
| **Catálogo** | Lista real de especialidades del CEM, obtenida desde PHP y cacheada 10 minutos. |
