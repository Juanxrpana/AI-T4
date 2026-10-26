# Documento de traspaso — Componente Inteligente CEM Jehová Rafa

Guarda esto como `TRASPASO.md` en la raíz del proyecto. Contiene todo lo necesario para que otra IA retome sin fricción.

---

## 1. Contexto del proyecto

**Qué es:** Proyecto universitario de último año. Sistema web para el Centro de Especialidades Médicas «Jehová Rafa» (El Tocuyo, Venezuela).

**Qué se está construyendo ahora:** Un **componente inteligente** — API en FastAPI que consulta a Gemini para orientar a la secretaria sobre qué especialidad médica corresponde al motivo de consulta de un paciente.

**Naturaleza académica:** El informe escrito pesa tanto como el código. Cada decisión técnica debe quedar justificada y documentada. Nada de afirmar cosas que no funcionan.

---

## 2. Arquitectura general

```
Navegador (modal chat)
    ↓ fetch con CSRF
PHP (ControllerChat → preguntar)
    ↓ curl con X-API-Key y headers de sesión
FastAPI (componente IA)
    ↓ google-genai
Gemini (con tool calling)
    ↓ httpx
PHP (ControllerApi → datos de BD)
    ↓ PDO
MariaDB
```

**Principios rectores:**
- FastAPI **no** accede a la base de datos directamente. Pide datos por HTTP a PHP.
- El componente IA es **solo lectura**: nunca modifica nada.
- La especialidad sugerida **debe** existir en el catálogo real del centro.
- Prompt separado del código (en `guia.md`).

---

## 3. Dos repositorios

### Repo A — Sistema PHP (existente, ya en producción en local)
```
C:\xampp\htdocs\Sistema-del--CEM--JEHOVA-RAFA\
```

**Archivos que TOCAMOS (nuevos o modificados):**
- `src/controllers/ControllerApi.php` → **NUEVO/MODIFICADO**. Endpoints de solo lectura para el componente IA, autenticados con `X-API-Key`: `apiEspecialidades`, `apiDoctoresPorEspecialidad` y `apiDatosUsuario` (datos del paciente del usuario logueado).
- `src/modelos/ModeloApi.php` → **NUEVO**. Consultas read-only del componente IA (personal→paciente por cédula, historial+controles, citas, hospitalizaciones).
- `src/controllers/ControllerChat.php` → **MODIFICADO**. `preguntar()` (proxy a FastAPI) + `chat()` redirige a inicio.
- `src/vistas/head/head.php` → **MODIFICADO**. CSS del modal, link de Chatbot abre el modal, incluye `modalChat.php`.
- `src/vistas/head/footer.php` → **MODIFICADO**. Añade `<script type="module" src="chatModal.js">`.
- `src/vistas/vistaChat/modalChat.php` → **NUEVO**. Botón flotante + HTML del modal.
- `src/assets/cssVista/chatModal.css` → **NUEVO**. Estilos del botón flotante y del modal.
- `src/assets/js/chatModal.js` → **NUEVO**. Lógica del botón/modal.
- `src/vistas/vistaChat/chat.php` → **DESUSADO**. Ya no se usa; se puede borrar.
- `.htaccess` → **MODIFICADO**. Corregida la regla de bloqueo (`controladores` → `controllers`).
- `.env` → **MODIFICADO**. Añadidas `API_KEY_IA` y `IA_API_URL`.

### Repo B — Componente IA (propio, separado)
```
C:\Users\Edouard\Documents\universidad\proyecto\AI-T4\
```
(o donde decidas; es un repo Git independiente)

**Estructura:**
```
componente_ia/
├── main.py
├── guia.md              # guía activa que se envía a Gemini
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   ├── __init__.py
│   ├── settings.py      # pydantic-settings
│   └── modulos.py       # RUTAS_FRONTEND + helper
├── ai/
│   ├── __init__.py
│   ├── base.py          # clase abstracta ProveedorIA
│   ├── schemas.py       # Pydantic: RespuestaOrientacion, AccionSugerida
│   ├── cuestionario.py  # motor del cuestionario (dominios + progreso)
│   └── gemini.py        # ProveedorGemini
├── knowledge/
│   └── dominios.json    # 4 dominios: torácico, fiebre, abdominal, piel
├── storage/
│   ├── db.py            # SQLite (sesiones, mensajes, auditoría, memorias)
│   ├── sesiones.py
│   ├── auditoria.py
│   └── memoria.py       # resumen por usuario/paciente
├── tools/
    ├── __init__.py
    ├── php_client.py    # httpx + caché del catálogo
    └── clinica.py       # listar_doctores, mis_datos, buscar_paciente, datos_clinicos_paciente
```

---

## 4. Contrato de la API FastAPI

### `POST /orientar`
Headers obligatorios: `X-API-Key`
Headers opcionales (los pone PHP): `X-Usuario-Id`, `X-Usuario-Rol`, `X-Usuario-Nombre`

**Body:**
```json
{
  "consulta": "texto del motivo de consulta",
  "session_id": "uuid-o-null"
}
```

**Respuesta (éxito):**
```json
{
  "session_id": "uuid",
  "tipo_respuesta": "emergencia | orientacion | catalogo | aclaracion | derivar | datos | navegacion",
  "mensaje": "...",
  "especialidad_sugerida": "Cardiología o null",
  "especialidades_disponibles": ["..."],
  "pregunta_aclaratoria": "",
  "observacion": "",
  "accion_sugerida": {
    "etiqueta": "Agendar cita con Cardiología",
    "ruta": "/Citas/citasHoy?especialidad=Cardiolog%C3%ADa",
    "visible": true
  }
}
```

Otros endpoints: `GET /`, `GET /sesiones/{id}`, `DELETE /sesiones/{id}`.

---

## 5. Contrato PHP ↔ FastAPI

### Endpoints en `ControllerApi.php` (los llama FastAPI)
```
GET /Api/apiEspecialidades                     → [{id_categoria, nombre}, ...]
GET /Api/apiDoctoresPorEspecialidad/{id}       → [{id_personal, nombre_doctor, apellido_doctor}, ...]
GET /Api/apiDatosUsuario/{id_usuario}          → {acceso, paciente, historial[], citas[], hospitalizaciones[]}
GET /Api/apiBuscarPaciente?q=...                → [{id_paciente, cedula, nombre, apellido}]
GET /Api/apiControlesPaciente/{id_paciente}    → [{fecha_control, diagnostico, sintomas, ...}]
GET /Api/apiPatologiasPaciente/{id_paciente}   → [{nombre_patologia, fecha_registro}]
```
Todos requieren `X-API-Key` que coincida con `$_ENV['API_KEY_IA']`.

`apiDatosUsuario` resuelve el paciente del usuario **por cédula**
(`personal.cedula = paciente.cedula`). Solo acceso para personal del centro
(con fila en `personal`); un usuario normal recibe `acceso: "denegado"`.

Los tres endpoints de pacientes (`buscar`, `controles`, `patologias`) exigen
además `X-Usuario-Id` de un usuario del personal (`validarPersonalDelCentroApi`).
`apiControlesPaciente` devuelve los últimos 6 meses; si no hay, los últimos 5.

### Endpoints en `ControllerChat.php` (los llama el navegador)
```
POST   /Chat/preguntar       →  proxy a FastAPI (/orientar)
POST   /Chat/borrarMemoria   →  proxy a FastAPI (DELETE /memoria)
```
Requieren CSRF y sesión activa.

---

## 6. Decisiones de diseño importantes (no cambiar sin razón)

1. **FastAPI no toca MariaDB.** Todo pasa por HTTP a PHP. Razón: menos credenciales expuestas, diagrama de despliegue más simple, la BD sigue siendo responsabilidad del sistema PHP.

2. **El catálogo se inyecta al system prompt** (no se pide por tool). Razón: ahorra una vuelta completa de tool calling, ~50% menos tokens. Se cachea 10 minutos en `php_client.py`.

3. **`thinking_budget=0`.** Razón: no necesitamos razonamiento interno para tarea administrativa; ahorra 40-60% de tokens.

4. **Historial limitado a `MAX_HISTORIAL = 4` mensajes.** Razón: acota el gasto cuadrático de conversaciones largas.

5. **Validación defensiva en Python** (`ai/gemini.py`): si Gemini alucina una especialidad que no está en el catálogo, se degrada a `catalogo`. Razón: la IA **no puede** sugerir algo inexistente.

6. **`accion_sugerida` la construye FastAPI, no Gemini.** Razón: las rutas del frontend no deben vivir dentro del prompt (acoplamiento).

7. **Modelo actual: `gemini-3.8-flash`.** Google cambió los modelos el 2026. Si falla, actualizar `MODELO_GEMINI` en `.env`.

8. **Los datos personales los resuelve PHP, no Gemini.** La tool `mis_datos()`
   no recibe argumentos: el `id_usuario` viaja por contexto (`X-Usuario-Id` desde
   PHP) y PHP decide qué paciente leer y si hay acceso. Gemini nunca elige a quién
   consultar. Requiere personal del centro (fila en `personal`); usuarios normales
   reciben `acceso: "denegado"`.

---

## 7. Reglas de la guía (`guia.md`)

- Gemini **solo** sugiere especialidades del catálogo.
- En `emergencia`, `catalogo`, `datos` y `navegacion`: `especialidad_sugerida = null`.
- En `navegacion`: `modulo_sugerido` (pacientes, clientes, citas, doctores,
  especialidades, hospitalización, insumos, reportes…) y FastAPI arma el botón
  con `RUTAS_FRONTEND`. Si piden ver una lista, **no se niega por privacidad**:
  solo ofrece el botón, sin volcar datos de pacientes.
- `mensaje` breve y útil: **puede** incluir una explicación general de posibles
  causas, dejando claro que es orientativo.
- **Prohibido** el diagnóstico definitivo, las recetas y las certezas
  ("tiene", "es", "compatible con"). Sí se permite "puede estar relacionado con…".
- No responder todo con "agende una cita": primero explicar, luego recomendar.
- Devuelve **solo** JSON, sin bloques markdown.

---

## 8. Estado actual del código

### ✅ Funcional
- Endpoint `/orientar` responde correctamente.
- Tool calling hacia PHP funcionando (`listar_doctores`).
- **Datos del usuario logueado**: la tool `mis_datos()` trae historial/controles,
  síntomas, citas y hospitalizaciones del paciente vinculado por cédula. Solo
  personal del centro (doctores, secretaría, administradores); usuarios normales
  reciben `acceso: "denegado"`. Nuevo tipo de respuesta `datos`.
- **Navegación a módulos**: si piden ver listas (pacientes, citas, doctores,
  insumos, reportes…), responde con tipo `navegacion` y botón al módulo correcto
  (`RUTAS_FRONTEND`), sin negarse por privacidad ni volcar datos.
- **MIDI + cuestionario guiado**: 4 dominios (dolor torácico, fiebre, dolor
  abdominal y lesión en la piel) en `knowledge/dominios.json`; motor en
  `ai/cuestionario.py`. Una pregunta por mensaje, 3-5 en total, progreso,
  emergencia sin preguntar y orientación final con listas + botón a Citas.
- **Anti-repetición**: el historial guarda también la pregunta del asistente; el
  flujo general (síntomas fuera de los dominios) hace una pregunta por mensaje y
  cierra a las 5 aunque falte detalle.
- **Historial del paciente**: `apiBuscarPaciente`, `apiControlesPaciente` y
  `apiPatologiasPaciente` (por cédula, validando personal), más las tools
  `buscar_paciente` y `datos_clinicos_paciente`. Ventana: últimos 6 meses (si no
  hay, últimos 5 controles).
- **Persistencia SQLite**: sesiones, mensajes, auditoría y memorias (`storage/`).
  Endpoints `GET /auditoria` y `DELETE /memoria`.
- **Memoria por usuario/paciente**: resumen de antecedentes para no reconsultar
  a PHP en cada mensaje. Se borra con el botón **«Borrar memoria»**
  (`/Chat/borrarMemoria`).
- Validación de especialidades contra catálogo real.
- Emergencias clasificadas y sin botón.
- Filtro `hash_equals`/`compare_digest` para la API key (fail-closed en ambos lados).
- **Integración PHP completa**: botón flotante + modal (`modalChat.php`,
  `chatModal.css`, `chatModal.js`) presentes en todas las páginas vía
  `head.php`/`footer.php`, y proxy `POST /Chat/preguntar` en `ControllerChat.php`
  con sesión + CSRF + auditoría en bitácora.
- **Chat persistente**: el historial se guarda en `localStorage`. Al recargar la
  página (p. ej. al cambiar de módulo desde un botón), al reabrir el asistente
  aparecen **“Continuar chat”** y **“Nuevo chat”** en vez de borrarse.
- El proxy envía `X-Usuario-Id/Rol/Nombre`; el componente los registra en su log.
- **Tests automáticos** de `/orientar`, cuestionario, emergencia, auditoría,
  persistencia, `listar_doctores` y `mis_datos` (`tests/`, con `pytest`).
  **22 tests en verde**.
- Hardening: `lifespan` en vez de `on_event`, `logging` en vez de `print`,
  respuesta de error sin filtrar detalles internos, catálogo con reintento
  perezoso, CORS desactivado salvo que `CORS_ORIGINS` traiga orígenes.
- **Fallback entre modelos**: si `MODELO_GEMINI` responde 503/429 o tarda más de
  `IA_TIMEOUT_MODELO` segundos, se prueba `MODELOS_FALLBACK` en orden. Probado en
  vivo: `gemini-3.8-flash` (503) → `gemini-3.5-flash` responde.
- **Historial multi-turno corregido**: el historial se pasa como `history=` al
  crear el chat (antes se enviaba una lista de `Content` a `send_message`, que
  lanzaba `ValueError`).

### ⚠️ Pendiente de verificar
- Prueba en el navegador: cuestionario completo, progreso, listas y «Borrar
  memoria» (el flujo API→PHP→Gemini ya se probó con TestClient).
- Que la ruta de acción (`/Citas/citasHoy?especialidad=…`) preseleccione la
  especialidad en el modal de citas (hoy solo navega al módulo).

### 🔴 Problemas conocidos
- `ControllerApi.php` — los endpoints `apiEspecialidades` y `apiDoctoresPorEspecialidad` **no validan unhashId** porque no reciben IDs hasheados; trabajan con IDs enteros directos.
- Las rutas del frontend en `config/modulos.py` están **hardcodeadas** (ahora incluyen el prefijo `/Sistema-del--CEM--JEHOVA-RAFA`). Si cambian en PHP, hay que actualizarlas.
- El caché del catálogo es **por proceso**. Si levantas varias instancias de uvicorn, cada una tendrá su caché.
- La memoria es un **resumen en SQLite**, sin embeddings; la búsqueda semántica/vectorizada queda pendiente.
- `GET /auditoria` se protege solo con la **API key** (no por rol).

---

## 9. Comandos útiles

### Arrancar FastAPI
```bash
cd C:\Users\Edouard\Documents\universidad\proyecto\AI-T4
uvicorn main:app --reload --port 8000
```
Docs: http://127.0.0.1:8000/docs

### Correr los tests
```bash
cd C:\Users\Edouard\Documents\universidad\proyecto\AI-T4
python -m pytest -q
```

### Probar directo con curl
```bash
curl -X POST http://127.0.0.1:8000/orientar ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: cambia_esto_por_algo_largo_y_aleatorio" ^
  -d "{\"consulta\": \"paciente con manchas rojas en la piel\"}"
```

### Arrancar Apache/MySQL
Abrir XAMPP Control Panel → Start Apache + Start MySQL.

---

## 10. Variables de entorno

### `.env` de PHP (repo A)
```env
API_KEY_IA=cambia_esto_por_algo_largo_y_aleatorio
IA_API_URL=http://127.0.0.1:8000/orientar
```

### `.env` del componente IA (repo B)
```env
GEMINI_API_KEY=tu_api_key_de_google_ai_studio
PHP_BASE_URL=http://localhost/Sistema-del--CEM--JEHOVA-RAFA
API_KEY_COMPARTIDA=cambia_esto_por_algo_largo_y_aleatorio
MODELO_GEMINI=gemini-3-flash-preview
# Si el principal da 503/429 o tarda más de IA_TIMEOUT_MODELO, se prueba el siguiente.
MODELOS_FALLBACK=gemini-3.5-flash,gemini-3.8-flash,gemini-3.1-flash-lite,gemini-3.7-flash
IA_TIMEOUT_MODELO=8
```

**Importante:** `API_KEY_IA` (PHP) y `API_KEY_COMPARTIDA` (FastAPI) **deben ser el mismo valor**.

---

## 11. Vocabulario del dominio

- **categoria_servicio** → catálogo que la secretaria ve como "especialidad" al agendar (Cardiología, Oftalmología, CONSULTA GENERAL, etc.).
- **especialidad** → categoría profesional del personal (`personal.id_especialidad`). **No** es lo mismo que `categoria_servicio`.
- **personal** → doctores (filtrados por `tipodecategoria = 'Doctor'`).
- **serviciomedico** → servicio específico con precio y tipo. Vinculado a una `categoria_servicio`.
- **personal_has_serviciomedico** → qué doctores ofrecen qué servicios.
- **paciente vs cliente** → dos entidades separadas. El paciente es quien asiste a consulta; el cliente es quien paga.
- **hashId / unhashId** → función del sistema para no exponer IDs numéricos en el frontend.

---

## 12. Preguntas frecuentes y trampas

**¿Por qué el componente no lee MariaDB?**
Porque PHP ya lo hace. Duplicar la lógica de negocio en Python es mala idea.

**¿Por qué hay una sola guía (`guia.md`)?**
Antes había `guia.md` (larga) y `guia_compacta.md` (activa). Se unificaron en un
único `guia.md` compacto para no duplicar reglas ni tokens. Es el archivo que se
envía a Gemini.

**¿Por qué no usar el SDK con `response_schema`?**
Lo probamos; hay conflictos con `automatic_function_calling`. La solución actual (validar JSON manualmente + limpiar markdown) es más frágil pero funciona con la versión actual del SDK.

**¿Por qué la especialidad va con `.title()`?**
El catálogo tiene `CONSULTA GENERAL` en mayúsculas, feo en un botón. `.title()` lo normaliza a `Consulta General`. Si el frontend PHP necesita el nombre exacto del catálogo, quitar esta normalización.

**¿Qué pasa si Gemini cambia de modelo otra vez?**
Editar `MODELO_GEMINI` en el `.env`. Nada más.

**¿Qué pasa si el usuario cierra el navegador?**
La sesión vive en RAM del servidor. Al volver con el mismo `session_id` (guardado en `localStorage`), continúa. Si reinicia el servidor, se pierde.

---

## 13. Próximos pasos sugeridos (por prioridad)

1. **Probar el modal end-to-end** en el navegador (botón flotante → proxy → FastAPI → Gemini).
2. **Verificar que la acción** `/Citas/citasHoy?especialidad=…` preselecciona la especialidad.
3. **Persistir sesiones** en SQLite (cuando haya tiempo).
4. **Comprimir aún más la guía** si los tokens siguen altos.
5. **Panel de administración** para gestionar el catálogo sin tocar PHP.

### Hecho recientemente
- Integración PHP del modal + proxy `Chat/preguntar` (CSRF, sesión, auditoría).
- Datos del usuario logueado vía `mis_datos()` + `ControllerApi::apiDatosUsuario` + `ModeloApi`.
- **MIDI**: cuestionario guiado por 4 dominios (`knowledge/dominios.json` + `ai/cuestionario.py`).
- **Historial por cédula**: `apiBuscarPaciente`, `apiControlesPaciente`, `apiPatologiasPaciente` + tools.
- **SQLite**: sesiones, mensajes, auditoría y memoria (`storage/`); `GET /auditoria` y `DELETE /memoria`.
- **Modal**: progreso, listas de orientación y botón «Borrar memoria».
- Hardening del componente (lifespan, logging, key fail-closed, sin fugas).
- Tests `pytest` (`tests/`, 22 en verde).
- Corregida la regla de `.htaccess` que bloqueaba `src/controladores` en vez de `src/controllers`.

---

## 14. Cosas que NO hacer

- ❌ No exponer la `GEMINI_API_KEY` al frontend.
- ❌ No meter lógica de negocio en `guia.md` (es solo prompt).
- ❌ No reescribir el sistema PHP para "modernizarlo" — funciona, no se toca.
- ❌ No permitir que el componente escriba en la BD.
- ❌ No cambiar `personal_has_serviciomedico` ni `categoria_servicio` sin avisar al equipo.
- ❌ No añadir features sin actualizar primero este documento.

---

## 15. Contacto y contexto humano

- **Usuario principal:** secretaria / administradora.
- **Rol del programador:** administrador del sistema (rol 10 en `segurity.rol`).
- **Nivel del desarrollador:** estudiante de último año de ingeniería, con experiencia en Python. Puede leer código técnico.
- **Restricción de tiempo:** entrega universitaria. Priorizar funcionalidad sobre elegancia cuando haya que elegir.

---

## 16. MIDI: mini consulta + cuestionario + memoria

> Estado: **IMPLEMENTADO (MVP)**. Ver el estado detallado en la sección 8.

**Nombre:** el asistente se llama **MIDI** (no es acrónimo ni abreviatura).
Significado de trabajo propuesto: **Módulo Inteligente de Derivación e
Información** (se puede cambiar sin tocar código).

**Objetivo:** que MIDI no solo redirija. Debe indagar un poco (consulta breve),
dar una interpretación orientativa con lenguaje prudente, considerar el
historial del paciente y terminar recomendando al doctor.

### 16.1 Mini consulta
- Preguntas: **entre 3 y 5** para casos no urgentes (mínimo 3, máximo 5). La
  **emergencia** no pregunta: alerta de inmediato.
- Lenguaje: "puede estar relacionado con…", "habría que descartar…", "suelen
  indicarse pruebas como…". **Prohibido**: "tiene", "es", "compatible con",
  "le indico X", medicamentos ni dosis.
- Formato: listas estructuradas `posibles_asociaciones`, `a_descartar`,
  `pruebas_sugeridas` + `recomendacion`. **Sin** cuidados generales ni fármacos.
- Botón final: **Citas con la especialidad preseleccionada**
  (`/Citas/citasHoy?especialidad=…`). El usuario elige el doctor.
- Preguntas típicas: desde cuándo, dónde/localización, qué lo desencadena o
  alivia, síntomas asociados (fiebre, dolor, picazón), si ingirió/usó algo
  nuevo, episodios anteriores.

### 16.2 Historial del paciente
- Se identifica pidiendo la **cédula** en la consulta, validando que el rol del
  usuario tenga acceso al módulo **Pacientes**.
- Datos a considerar: **patologías**, **controles/consultas** (diagnóstico,
  historial clínico, medicamentos recetados y resultados) y **citas**.
- Solo los **últimos 6 meses** de controles/consultas para no arrastrar años de
  historial.
- La memoria evita volver a consultar al mismo paciente en cada mensaje.

### 16.3 Memoria (propia, no mem0)
- Decisión: **memoria propia con SQLite + embeddings** (sin mem0), para no
  depender de servicios externos ni Docker en Windows.
- Alcance: **por usuario** (staff), pero **etiquetada por paciente** para no
  mezclar historiales.
- Guarda **resumen por paciente + hechos de la conversación** (preferencias y
  contexto), vectorizados con embeddings de **Gemini** (misma API key).
- Se borra **manualmente** con un botón **“Borrar memoria”** en el modal.

### 16.4 Contrato propuesto (confirmar al implementar)
Extender `RespuestaOrientacion` con campos opcionales:
```
posibles_asociaciones: list[str]   # "puede estar relacionado con…"
a_descartar: list[str]             # "habría que descartar…"
pruebas_sugeridas: list[str]       # "suelen indicarse pruebas como…"
recomendacion: str                 # acudir/agendar con la especialidad
```
Se mantiene `especialidad_sugerida` (del catálogo) y `accion_sugerida` lo arma
FastAPI. `aclaracion` sigue usando `pregunta_aclaratoria`.

### 16.5 Pendiente al implementar
- Subir `MAX_HISTORIAL` (hoy 4 = 2 turnos) a ~12-14 para sostener 3-5 preguntas
  más sus respuestas.
- **Forzar el conteo en código, no solo en el prompt**: contar las respuestas
  `aclaracion` de la sesión; si van menos de 3, obligar a preguntar; si llegan a
  5, obligar a concluir.
- Endpoint PHP read-only para historial por cédula, con validación de permiso
  sobre el módulo Pacientes.
- Actualizar `guia.md` (nombre MIDI, criterios, lenguaje, uso del
  historial y la memoria).
- Renderizar las listas nuevas en `chatModal.js` + `chatModal.css` y añadir el
  botón **“Borrar memoria”**.
- Tests: 3-5 preguntas, lenguaje prohibido ausente, acción final a Citas,
  historial por cédula, memoria por usuario/paciente.
- La **emergencia** mantiene prioridad: no pregunta.

### 16.6 Resueltas (24-oct-2026)
- Ventana de historial: **últimos 6 meses**.
- Memoria: **resumen por paciente + hechos de conversación**.
- Borrado: **manual** con botón “Borrar memoria”.
- Embedder: **Gemini** (`text-embedding`, misma API key).

---

**Última actualización:** 24 de octubre de 2026.

Si otra IA lee esto: empieza por el punto 8 (estado actual), luego el 4 (contratos), y pregunta al humano **antes** de cambiar cualquier decisión del punto 6.
