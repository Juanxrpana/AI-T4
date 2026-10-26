"""Herramientas de solo lectura que Gemini puede invocar.

- `listar_doctores`: doctores de una especialidad.
- `mis_datos`: datos del paciente del usuario logueado.
- `buscar_paciente`: busca pacientes por cédula/nombre (para la consulta).
- `datos_clinicos_paciente`: controles recientes + patologías de un paciente.
"""

import asyncio

import tools.php_client as php_client


async def listar_doctores(especialidad: str) -> list[dict]:
    """Lista los doctores activos de una especialidad.

    Args:
        especialidad: Nombre exacto de la especialidad. Debe existir
            en el catálogo que aparece en las instrucciones del sistema.

    Returns:
        Lista de doctores con su id y nombre completo. Vacía si la
        especialidad no existe o no tiene doctores asignados.
    """
    catalogo = await php_client.get_catalogo_especialidades()
    match = next(
        (f for f in catalogo
         if f.get("nombre", "").strip().lower() == especialidad.strip().lower()),
        None,
    )
    if not match:
        return []

    doctores = await php_client.get_doctores_por_id_categoria(match["id_categoria"])
    return [
        {
            "id": d.get("id_personal"),
            "nombre": f"{d.get('nombre_doctor', '').strip()} "
                      f"{d.get('apellido_doctor', '').strip()}".strip(),
        }
        for d in doctores
        if d.get("id_personal")
    ]


async def mis_datos() -> dict:
    """Datos clínicos del usuario logueado (el que consulta).

    Usa esta herramienta cuando la persona pida "mi historial", "mis síntomas",
    "mis citas" o "mis hospitalizaciones". No recibe parámetros: el usuario se
    toma de la sesión de la petición actual.

    Returns:
        dict con `acceso` ("permitido"/"denegado"), `paciente` y las listas
        `historial`, `citas` y `hospitalizaciones`.
    """
    usuario = php_client.usuario_actual.get()
    if not usuario:
        return {"ok": False, "error": "No hay usuario identificado en la consulta."}

    return await php_client.get_mis_datos(int(usuario))


async def buscar_paciente(q: str) -> list[dict]:
    """Busca pacientes por cédula, nombre o apellido (máximo 10).

    Úsala para identificar al paciente antes de consultar su historial. Si hay
    varias coincidencias, pide confirmar la cédula exacta.
    """
    q = (q or "").strip()
    if len(q) < 2:
        return []

    return await php_client.buscar_paciente(q)


async def datos_clinicos_paciente(id_paciente: int) -> dict:
    """Controles recientes (últimos 6 meses) y patologías de un paciente."""
    paciente_id = int(id_paciente)
    controles, patologias = await asyncio.gather(
        php_client.get_controles_paciente(paciente_id),
        php_client.get_patologias_paciente(paciente_id),
    )

    return {
        "paciente_id": paciente_id,
        "controles": controles,
        "patologias": patologias,
    }


# Catálogo inyectado en el prompt; estas son las tools que Gemini puede invocar.
TOOLS = [listar_doctores, mis_datos, buscar_paciente, datos_clinicos_paciente]