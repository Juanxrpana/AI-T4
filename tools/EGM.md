# Cliente PHP y herramientas de solo lectura

## Overview

`tools` contiene el puente HTTP entre el servicio FastAPI y el sistema PHP CEMJR, y las herramientas que el modelo puede invocar. El cliente usa `httpx` con GET, la API key compartida y, cuando existe, el `id_usuario` de la consulta actual. No escribe en MySQL ni en PHP.

El catálogo de especialidades se cachea 10 minutos. Las herramientas exponen doctores, datos del usuario logueado, búsqueda de pacientes y datos clínicos; todas son de solo lectura.

## Interface

### `tools/php_client.py`

- `usuario_actual`: `ContextVar` con el `id_usuario` de la petición actual.
- `_headers()`: devuelve `X-API-Key` y, si hay contexto, `X-Usuario-Id`.
- `_get_json(endpoint)`: GET a `PHP_BASE_URL + endpoint` con timeout de 10 s; devuelve JSON o `None`.
- `_get(endpoint)`: igual que `_get_json`, pero garantiza una lista.
- `get_catalogo_especialidades(forzar_refresh=False)`: consulta `/Api/apiEspecialidades`, filtra filas con `id_categoria` y `nombre`, y cachea 600 s.
- `get_catalogo_cache_sincrono()`: lee el caché sin llamar a PHP.
- `get_doctores_por_id_categoria(id_categoria)`: `/Api/apiDoctoresPorEspecialidad/{id}`.
- `get_mis_datos(id_usuario)`: `/Api/apiDatosUsuario/{id_usuario}`.
- `buscar_paciente(q)`: `/Api/apiBuscarPaciente?q=...`.
- `get_controles_paciente(id_paciente)`: `/Api/apiControlesPaciente/{id}`.
- `get_patologias_paciente(id_paciente)`: `/Api/apiPatologiasPaciente/{id}`.

### `tools/clinica.py`

- `listar_doctores(especialidad)`: resuelve la especialidad en el catálogo y consulta sus doctores.
- `mis_datos()`: datos clínicos del usuario actual; no recibe parámetros.
- `buscar_paciente(q)`: búsqueda por cédula/nombre/apellido; mínimo 2 caracteres.
- `datos_clinicos_paciente(id_paciente)`: controles y patologías en paralelo.
- `TOOLS`: lista de herramientas expuestas al proveedor de IA.

## Invariants

- **Solo lectura.** Todas las llamadas a PHP son `GET`; no hay `POST`, `PUT` ni `DELETE` en `php_client`.
- **Autenticación.** Toda llamada envía `X-API-Key` con `settings.API_KEY_COMPARTIDA`. La clave debe coincidir con `API_KEY_IA` en el `.env` de CEMJR.
- **Identidad.** `X-Usuario-Id` solo se envía si `usuario_actual` tiene valor. `main.py` lo establece antes de procesar la consulta; los endpoints de pacientes de `ControllerApi` lo exigen.
- **Catálogo.** El catálogo se cachea 600 s; si PHP falla, se conserva el último valor. `get_catalogo_cache_sincrono` no hace red y puede devolver una lista vacía al arranque.
- **Endpoints existentes.** Las rutas usadas son las de `ControllerApi`: especialidades, doctores por especialidad, datos de usuario, búsqueda de pacientes, controles y patologías. No hay endpoint de creación de pacientes ni de disponibilidad de citas.
- **Sin CSRF.** Al ser servicio a servicio no hay cookie de sesión ni CSRF; la autorización depende de la API key y del `X-Usuario-Id`.
- **Sin escritura.** Las herramientas no crean ni modifican pacientes, citas, facturas ni historia clínica.

## Side Effects

- Peticiones HTTP GET a `PHP_BASE_URL`.
- Caché en memoria del catálogo.
- Logs de error HTTP.
- `ContextVar` de usuario por petición.
- Sin escritura en MySQL, sin archivos y sin correo.

## Verification

- Run: `pytest`
- Nota: algunas pruebas requieren `.env`, API key y PHP disponible; no ejecutar contra producción sin una copia controlada.
