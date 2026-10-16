"""Herramientas de solo lectura que Gemini puede invocar.

El catálogo de especialidades ya no es una tool: se inyecta en el
system prompt al arrancar. Solo queda listar_doctores.
"""

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


# Solo queda una tool: el catálogo va inyectado en el prompt
TOOLS = [listar_doctores]