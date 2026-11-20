---
title: "Arquitectura del componente inteligente MIDI"
subtitle: "Sistema CEM Jehová Rafa · Vista de componentes y flujo inteligente"
version: "1.0"
date: "2026-11-20"
---

# 2. Arquitectura del componente inteligente

## 2.1 Ficha del diagrama

| Elemento | Detalle |
|---|---|
| **Nombre** | Arquitectura del componente inteligente MIDI |
| **Tipo** | Diagrama de arquitectura por capas + vista de componentes del núcleo inteligente |
| **Propósito** | Evidenciar dónde reside la inteligencia, cómo se coordinan sus componentes y cómo se integra con el sistema PHP y los proveedores de IA |
| **Alcance** | Servicio FastAPI MIDI, base de conocimiento, memoria, proveedores de IA y sistemas externos |
| **Nivel** | Arquitectura lógica / componentes |
| **Fuente** | `main.py`, `ai/`, `tools/`, `storage/`, `knowledge/`, `config/` |

## 2.2 Vista 1: arquitectura por capas

> **Lectura del diagrama:** se organiza en tres columnas. La izquierda muestra el acceso y la exposición; el centro, el núcleo inteligente; la derecha, la integración y los sistemas externos. Las etiquetas son cortas para favorecer la lectura en diapositiva; el detalle de archivos y funciones está en la tabla 2.4.

```mermaid
flowchart LR
    subgraph LEFT["1-2 · ACCESO Y EXPOSICIÓN"]
        direction TB
        UI["Navegador<br/>chat"]
        PROXY["ControllerChat<br/>proxy PHP"]
        EP["POST /orientar"]
        AUTH["API key"]
        IDENT["Identidad<br/>por headers"]
        AUX["API de soporte"]
        UI -->|"consulta"| PROXY
        PROXY -->|"POST + headers"| EP
        EP --> AUTH
        EP --> IDENT
        EP --> AUX
    end

    subgraph CORE["3 · NÚCLEO INTELIGENTE MIDI"]
        direction TB
        ORQ["C-01<br/>Orquestador"]
        NLU["C-02<br/>NLU simbólica"]
        DM["C-03<br/>Motor de<br/>inferencia"]
        ALR["C-04<br/>Motor de<br/>alarmas"]
        LLM["C-08<br/>Capa generativa<br/>LLM"]
        GRD["C-09<br/>Guardrails"]
        KB[("C-05<br/>KB curada")]
        MEM[("C-06<br/>Memoria<br/>SQLite")]
        VEC["C-07<br/>Memoria<br/>vectorizada"]
        AUD["C-12<br/>Auditoría"]
        ORQ --> NLU
        ORQ --> DM
        ORQ --> ALR
        ORQ --> LLM
        NLU --> KB
        DM --> KB
        ALR --> KB
        ORQ --> MEM
        ORQ --> VEC
        VEC --> MEM
        LLM --> GRD
    end

    subgraph RIGHT["4-5 · INTEGRACIÓN Y EXTERNOS"]
        direction TB
        CLI["C-10<br/>php_client<br/>GET"]
        CACHE["Caché catálogo<br/>600 s"]
        TOOLS["C-11<br/>Tools solo<br/>lectura"]
        PHP["CEMJR PHP"]
        DB[("MariaDB")]
        IA["Proveedores IA"]
        EMB["Embeddings"]
        CLI --> CACHE
        TOOLS --> CLI
        CLI --> PHP
        PHP --> DB
    end

    EP --> ORQ
    ORQ --> CLI
    LLM --> IA
    VEC --> EMB
    GRD --> EP
    EP --> MEM
    EP --> AUD
    EP --> PROXY

    classDef channel fill:#f8fafc,color:#0f172a,stroke:#64748b,stroke-width:1.5px
    classDef api fill:#f0f9ff,color:#0c4a6e,stroke:#0369a1,stroke-width:1.5px
    classDef core fill:#eef2ff,color:#1e1b4b,stroke:#4338ca,stroke-width:2px
    classDef data fill:#ecfdf5,color:#064e3b,stroke:#047857,stroke-width:1.5px
    classDef ext fill:#fff7ed,color:#7c2d12,stroke:#ea580c,stroke-width:1.5px

    class UI,PROXY,CLI,CACHE,TOOLS channel
    class EP,AUTH,IDENT,AUX api
    class ORQ,NLU,DM,ALR,LLM,GRD core
    class KB,MEM,VEC,AUD data
    class PHP,DB,IA,EMB ext
```

## 2.3 Vista 2: componentes del núcleo inteligente

> **Lectura del diagrama:** esta vista aísla el núcleo. Se distinguen cuatro formas de inteligencia: **simbólica** (reglas y palabras clave), **determinista** (máquina de estados), **estadística** (similitud y embeddings) y **generativa** (modelo de lenguaje). Los guardrails controlan la salida antes de llegar al usuario.

```mermaid
flowchart LR
    IN["Consulta + contexto<br/>usuario · sesión · historial"] --> ORQ["C-01<br/>Orquestador"]
    ORQ --> NLU["C-02<br/>NLU simbólica"]
    NLU -->|"dominio detectado"| DM["C-03<br/>Motor de inferencia"]
    DM -->|"siguiente pregunta"| Q["Pregunta al usuario<br/>tipo aclaracion"]
    DM -->|"información suficiente"| FICHA["Constructor de ficha<br/>construir_ficha"]
    ORQ --> ALR["C-04<br/>Motor de alarmas"]
    ALR -->|"alarma"| EMG["Respuesta de emergencia"]
    CTX["Contexto clínico<br/>controles + patologías"] --> FICHA
    MEMV["C-07<br/>Memoria vectorizada"] --> FICHA
    KB[("C-05<br/>KB curada")] --> NLU
    KB --> DM
    KB --> ALR
    KB --> FICHA
    FICHA --> LLM["C-08<br/>Capa generativa"]
    LLM -->|"JSON crudo"| VAL["C-09<br/>Guardrails y validación"]
    VAL -->|"especialidad válida"| OUT["Orientación final<br/>tipo orientacion"]
    VAL -->|"especialidad inválida"| CAT["Catálogo real"]
    CAT --> OUT
    VAL -->|"emergencia / datos / navegación"| OUT
    OUT --> AUD["C-12<br/>Auditoría"]
    OUT --> MEM["C-06<br/>Sesión y mensajes"]

    classDef symbolic fill:#eef2ff,color:#1e1b4b,stroke:#4338ca,stroke-width:2px
    classDef determinist fill:#ede9fe,color:#2e1065,stroke:#6d28d9,stroke-width:2px
    classDef stat fill:#ecfdf5,color:#064e3b,stroke:#047857,stroke-width:2px
    classDef gen fill:#fff7ed,color:#7c2d12,stroke:#ea580c,stroke-width:2px
    classDef guard fill:#fef2f2,color:#7f1d1d,stroke:#dc2626,stroke-width:2px
    classDef core fill:#e0e7ff,color:#1e1b4b,stroke:#4338ca,stroke-width:2.5px
    classDef io fill:#f8fafc,color:#0f172a,stroke:#64748b,stroke-width:1.5px

    class NLU symbolic
    class DM,ALR determinist
    class KB,MEMV,MEM,AUD stat
    class LLM gen
    class VAL guard
    class ORQ core
    class IN,Q,FICHA,CTX,EMG,OUT,CAT io
```

## 2.4 Inventario de componentes

| ID | Componente | Archivo / función | Tipo de inteligencia | Entradas | Salidas |
|---|---|---|---|---|---|
| **C-01** | Orquestador de diálogo | `main.py:_procesar`, `_flujo_cuestionario`, `_flujo_general`, `_finalizar` | Híbrida (coordina reglas y LLM) | Consulta, sesión, usuario, historial | Respuesta estructurada |
| **C-02** | Comprensión simbólica / detección de dominio | `ai/cuestionario.py:detectar_dominio`, `_similitud` | Simbólica + estadística léxica | Texto libre | Clave de dominio o `None` |
| **C-03** | Motor de inferencia del cuestionario | `ai/cuestionario.py:proxima_pregunta`, `registrar_respuesta`, `es_suficiente`, `progreso` | Determinista (máquina de estados) | Estado de la sesión y KB | Siguiente pregunta o cierre |
| **C-04** | Motor de alarmas | `ai/cuestionario.py:hay_alarma` | Simbólica (reglas) | Motivo y respuestas | Booleano de emergencia |
| **C-05** | Base de conocimiento curada | `knowledge/dominios.json`, `knowledge/aprendido.json` | Conocimiento declarativo | — | Dominios, preguntas, señales, pruebas |
| **C-06** | Memoria operativa | `storage/sesiones.py`, `storage/memoria.py` | Persistencia | Sesión, usuario, paciente | Estado, historial, resúmenes |
| **C-07** | Memoria vectorizada | `ai/embeddings.py`, `storage/memoria.py` | Estadística (similitud coseno) | Texto de resumen o consulta | Vector y ranking de recuerdos |
| **C-08** | Capa generativa | `ai/gemini.py`, `ai/openai_compatible.py`, `ai/proveedores.py`, `guia.md` | Generativa (LLM) | Ficha clínica o consulta + historial | JSON `RespuestaOrientacion` |
| **C-09** | Guardrails y validación | `ai/schemas.py`, `ai/comun.py:validar_respuesta` | Simbólica (validación) | JSON del modelo | Respuesta corregida y segura |
| **C-10** | Adaptador de integración PHP | `tools/php_client.py` | Integración (solo GET) | Endpoint y headers | JSON de PHP o `None` |
| **C-11** | Herramientas de solo lectura | `tools/clinica.py:TOOLS` | Tool calling | Argumentos de la herramienta | Datos clínicos o directorio |
| **C-12** | Auditoría | `storage/auditoria.py` | Trazabilidad | Evento de consulta | Registro append-only |

## 2.5 ¿Dónde se evidencia la inteligencia?

| Mecanismo | Implementación | Qué aporta | Límite de diseño |
|---|---|---|---|
| **Clasificación simbólica** | Coincidencia normalizada de palabras clave y similitud Jaccard ≥ 0,6 con ejemplos aprendidos. | Clasifica el motivo en un dominio sin depender del LLM; es reproducible. | Si la frase no comparte tokens ni palabras clave, cae al flujo general. |
| **Aprendizaje incremental** | `aprender_ejemplo` y `aprender_palabras` guardan frases y claves en `aprendido.json`; se fusionan al cargar. | MIDI mejora el reconocimiento con el uso real, sin reentrenar el modelo. | Máximo de 50 ejemplos por dominio; requiere revisión humana. |
| **Máquina de estados** | `nueva_sesion`, `proxima_pregunta`, `registrar_respuesta`, `es_suficiente`, `progreso`. | Garantiza 3–5 preguntas, evita repetir y permite mostrar progreso. | Las preguntas son finitas y curadas por dominio. |
| **Razonamiento por reglas** | `hay_alarma`, `especialidad_candidata`, `resumen_contexto`, `construir_ficha`. | Aplica criterios clínicos explícitos y auditables. | No sustituye el juicio médico. |
| **Recuperación de contexto** | `_resolver_paciente`, `_cargar_contexto`, `php_client`. | Personaliza la orientación con controles y patologías reales. | Solo lectura; depende de la disponibilidad de PHP. |
| **Memoria semántica** | `embeddings.embed`, `memoria.buscar_similares`, similitud coseno. | Permite recuperar resúmenes parecidos por significado. | La recuperación automática en la ficha está disponible como capacidad, pero el flujo actual prioriza la memoria exacta por usuario/paciente. |
| **Generación controlada** | Prompt `guia.md` + catálogo real + esquema Pydantic + `validar_respuesta`. | Redacta una orientación natural sin inventar especialidades. | El modelo no decide el botón ni la ruta; eso lo hace FastAPI. |
| **Cadena de respaldo** | `ProveedorFallback` y modelos de respaldo. | Mantiene el servicio ante 503, 429 o timeout. | No garantiza disponibilidad si todos los proveedores fallan. |

## 2.6 Flujo de datos de una consulta

| Paso | Acción | Componente | Persistencia |
|---:|---|---|---|
| 1 | El navegador envía la consulta al proxy PHP. | Canal | — |
| 2 | PHP agrega API key y headers de usuario y llama a `/orientar`. | Exposición | — |
| 3 | FastAPI valida la API key y recupera la sesión. | `verificar_api_key`, `sesiones` | SQLite |
| 4 | Se recupera el historial reciente y se registra el mensaje del usuario. | `historial_para_gemini`, `agregar_mensaje` | SQLite |
| 5 | Se detecta el dominio clínico. | `detectar_dominio` | — |
| 6 | Se resuelve el paciente y se carga su contexto. | `_resolver_paciente`, `_cargar_contexto` | SQLite / PHP |
| 7 | Se evalúan señales de alarma. | `hay_alarma` | — |
| 8 | Se elige la siguiente pregunta o se cierra el cuestionario. | `proxima_pregunta`, `es_suficiente` | — |
| 9 | Se construye la ficha clínica. | `construir_ficha` | — |
| 10 | El proveedor de IA redacta la orientación. | `proveedor.orientar` | — |
| 11 | Se valida el JSON contra el esquema y el catálogo. | `RespuestaOrientacion`, `validar_respuesta` | — |
| 12 | Se agrega la acción sugerida. | `_accion`, `construir_accion` | — |
| 13 | Se guarda el estado y el mensaje del asistente. | `guardar_estado`, `agregar_mensaje` | SQLite |
| 14 | Se registra la auditoría. | `auditoria.registrar` | SQLite |
| 15 | Se devuelve el JSON al proxy y se pinta en el chat. | Exposición / canal | — |

## 2.7 Diagrama de secuencia complementario

```mermaid
sequenceDiagram
    autonumber
    participant UI as Navegador (chat)
    participant PHP as ControllerChat (PHP)
    participant API as FastAPI /orientar
    participant ORQ as Orquestador MIDI
    participant KB as KB curada
    participant SQL as SQLite MIDI
    participant CLI as php_client
    participant LLM as Proveedor IA

    UI->>PHP: POST Chat/preguntar
    PHP->>API: POST /orientar + X-API-Key + X-Usuario-*
    API->>API: verificar_api_key
    API->>SQL: obtener sesión e historial
    API->>SQL: agregar mensaje del usuario
    API->>ORQ: _procesar(consulta, historial, estado, usuario)

    ORQ->>KB: detectar_dominio(consulta)
    alt Dominio conocido
        ORQ->>CLI: buscar_paciente / controles / patologías
        CLI->>PHP: GET /Api/...
        PHP-->>CLI: JSON de solo lectura
        CLI-->>ORQ: contexto clínico
        ORQ->>KB: evaluar alarma y siguiente pregunta
        alt Información insuficiente
            ORQ-->>API: respuesta aclaracion + progreso
        else Información suficiente
            ORQ->>LLM: ficha clínica + catálogo
            LLM-->>ORQ: JSON RespuestaOrientacion
        end
    else Sin dominio
        ORQ->>LLM: consulta + historial
        LLM-->>ORQ: JSON RespuestaOrientacion
    end

    ORQ->>ORQ: validar catálogo / acción sugerida
    API->>SQL: guardar estado + mensaje del asistente
    API->>SQL: registrar auditoría
    API-->>PHP: JSON RespuestaOrientacion
    PHP-->>UI: render del chat y botón de acción
```

## 2.8 Decisiones de arquitectura

| ID | Decisión | Justificación | Consecuencia |
|---|---|---|---|
| **DA-01** | Separar el motor determinista del LLM. | El LLM no decide cuándo preguntar ni cuándo terminar; eso hace el cuestionario. | Respuestas más reproducibles y auditables. |
| **DA-02** | Inyectar el catálogo real en el prompt y validarlo después. | Evita sugerir especialidades inexistentes. | Si el catálogo no está disponible, se degrada a `derivar` o `catalogo`. |
| **DA-03** | No escribir en MariaDB. | MIDI es un componente de orientación, no el sistema de registro clínico. | Toda escritura clínica queda en PHP. |
| **DA-04** | Persistir sesiones, memoria y auditoría en SQLite. | Aísla al componente y evita acoplamiento con la base clínica. | Requiere respaldo y retención propios. |
| **DA-05** | Usar una cadena de proveedores. | Un pico de demanda o cuota no debe tumbar la demo. | Aumenta la complejidad de configuración y logs. |
| **DA-06** | Validar la salida con Pydantic y reglas de catálogo. | El modelo puede alucinar o devolver JSON inválido. | Se devuelve una respuesta controlada en lugar de un error. |
| **DA-07** | Decidir el botón de acción en FastAPI, no en el modelo. | Evita rutas inventadas o acciones no autorizadas. | El botón solo aparece con especialidad válida. |
| **DA-08** | Mantener herramientas de solo lectura. | Reduce el riesgo de acciones clínicas no autorizadas. | El alta de paciente se confirma en PHP (endpoint propuesto) y la cita se gestiona en el módulo existente. |

## 2.9 Requisitos no funcionales asociados

| ID | Requisito | Cómo se atiende |
|---|---|---|
| **RNF-01** | Seguridad de acceso | `X-API-Key` con comparación en tiempo constante; identidad por headers del proxy. |
| **RNF-02** | Privacidad | MIDI no escribe en la base clínica; la auditoría es local y debe tener retención controlada. |
| **RNF-03** | Disponibilidad | Cadena de proveedores, timeouts y respuestas de respaldo. |
| **RNF-04** | Rendimiento | Caché de catálogo de 10 minutos, embeddings en segundo plano y límite de historial. |
| **RNF-05** | Trazabilidad | Auditoría append-only con modelo, latencia, dominio y respuesta. |
| **RNF-06** | Consistencia del contrato | Esquema `RespuestaOrientacion` y validación defensiva. |
| **RNF-07** | Mantenibilidad | KB en JSON, rutas en `config/modulos.py`, proveedores intercambiables. |
| **RNF-08** | Explicabilidad | Reglas explícitas, catálogo real y lenguaje no diagnóstico. |

## 2.10 Límites y observaciones para la defensa

| Tema | Estado actual | Implicación |
|---|---|---|
| Diagnóstico | Prohibido por prompt y por diseño. | MIDI orienta y deriva; no diagnostica ni receta. |
| Escritura clínica | No existe desde FastAPI. | El alta de paciente se confirma en PHP (endpoint propuesto); la cita se gestiona en el módulo existente. |
| Disponibilidad de citas | No se consulta dentro del chat. | El botón abre el módulo; no reserva. |
| Memoria vectorizada | Se calcula y se expone por `/memoria/similares`. | La ficha admite `recuerdos`, pero el flujo actual usa la memoria exacta por usuario/paciente. |
| Aprendizaje | Guarda ejemplos y palabras clave. | No reentrena el modelo; mejora la clasificación simbólica. |
| Dependencia externa | PHP y proveedores de IA. | Si fallan, hay respuestas de respaldo, pero se degrada la orientación. |
| Auditoría | Append-only local. | Falta definir política formal de retención y borrado. |

## 2.11 Guion breve para la diapositiva

> «La arquitectura separa responsabilidades. El canal y el proxy PHP no contienen inteligencia: solo transportan. FastAPI expone el contrato. El núcleo índigo es donde ocurre la inteligencia: una capa simbólica detecta el dominio, un motor determinista decide qué preguntar, un motor de alarmas protege el caso urgente, una base de conocimiento curada aporta las reglas y una capa generativa redacta la orientación. Antes de responder, los guardrails validan el esquema y el catálogo real. Nada de esto escribe en la base clínica: MIDI lee por HTTP y devuelve un JSON que el sistema PHP pinta.»

## 2.12 Apéndice: fuente PlantUML de la vista por capas

```plantuml
@startuml Arquitectura_MIDI
skinparam shadowing false
skinparam defaultFontName Arial
skinparam rectangle {
  BackgroundColor #F8FAFC
  BorderColor #64748B
}

package "1 · CANAL DE PRESENTACIÓN" {
  [Navegador\nchatModal.js] as UI
  [ControllerChat\nproxy PHP] as PROXY
}

package "2 · EXPOSICIÓN · FastAPI" {
  [POST /orientar] as EP
  [verificar_api_key] as AUTH
  [_datos_usuario] as IDENT
  [API de soporte\n/sesiones · /auditoria\n/conocimiento · /memoria] as AUX
}

package "3 · NÚCLEO INTELIGENTE MIDI" {
  [C-01\nOrquestador] as ORQ
  [C-02\nNLU simbólica] as NLU
  [C-03\nMotor de inferencia] as DM
  [C-04\nMotor de alarmas] as ALR
  database "C-05\nKB curada" as KB
  database "C-06\nMemoria operativa" as MEM
  [C-07\nMemoria vectorizada] as VEC
  [C-08\nCapa generativa] as LLM
  [C-09\nGuardrails] as GRD
  [C-12\nAuditoría] as AUD
}

package "4 · INTEGRACIÓN" {
  [C-10\nphp_client GET] as CLI
  [Caché catálogo\nTTL 600 s] as CACHE
  [C-11\nTools solo lectura] as TOOLS
}

package "5 · SISTEMAS EXTERNOS" {
  [CEMJR PHP\nControllerApi] as PHP
  database "MariaDB" as DB
  [Proveedores IA] as IA
  [Gemini Embeddings] as EMB
}

UI --> PROXY
PROXY --> EP : POST + headers
EP --> AUTH
EP --> IDENT
EP --> ORQ : _procesar
ORQ --> NLU : detectar dominio
NLU --> KB
ORQ --> DM : preguntas
DM --> KB
ORQ --> ALR : alarmas
ALR --> KB
ORQ --> CLI : contexto
CLI --> CACHE
CLI --> PHP : GET /Api
PHP --> DB
ORQ --> MEM
ORQ --> VEC
VEC --> EMB
VEC --> MEM
ORQ --> LLM : ficha
LLM --> IA
LLM --> GRD : JSON
GRD --> EP : respuesta válida
EP --> MEM : estado y mensajes
EP --> AUD
AUD --> MEM
EP --> PROXY : JSON
PROXY --> UI
TOOLS --> CLI
ORQ --> TOOLS

@enduml
```

## 2.13 Apéndice: fuente PlantUML del núcleo inteligente

```plantuml
@startuml Nucleo_Inteligente_MIDI
skinparam shadowing false
skinparam defaultFontName Arial
left to right direction

[Consulta + contexto] as IN
[C-01 Orquestador] as ORQ
[C-02 NLU simbólica] as NLU
[C-03 Motor de inferencia] as DM
[C-04 Motor de alarmas] as ALR
database "C-05 KB curada" as KB
[C-06 Memoria operativa] as MEM
[C-07 Memoria vectorizada] as VEC
[C-08 Capa generativa] as LLM
[C-09 Guardrails] as GRD
[C-12 Auditoría] as AUD
[Pregunta al usuario] as Q
[Ficha clínica] as FICHA
[Respuesta de emergencia] as EMG
[Orientación final] as OUT
[Catálogo real] as CAT

IN --> ORQ
ORQ --> NLU
NLU --> DM : dominio
DM --> Q : siguiente pregunta
DM --> FICHA : suficiente
ORQ --> ALR
ALR --> EMG : alarma
KB --> NLU
KB --> DM
KB --> ALR
KB --> FICHA
MEM --> FICHA : contexto
VEC --> FICHA : recuerdos
FICHA --> LLM
LLM --> GRD : JSON
GRD --> OUT : válido
GRD --> CAT : especialidad inválida
CAT --> OUT
OUT --> AUD
OUT --> MEM

@enduml
```
