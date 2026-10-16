"""Herramientas de solo lectura que Gemini puede invocar.

Cada función lleva un docstring que Gemini usa como descripción de la
herramienta. Los type hints importan: el SDK los usa para armar el schema.
"""

import tools.php_client as php_client


async def listar_especialidades() -> list[str]:
    """Devuelve la lista de especialidades médicas disponibles en el centro.

    Úsala SIEMPRE antes de sugerir una especialidad, para verificar
    que exista en el catálogo real del centro.

    Returns:
        Lista de nombres de especialidades activas.
    """
    filas = await php_client.get_especialidades()
    return sorted(
        {f.get("nombre", "").strip() for f in filas if f.get("nombre")}
    )


async def listar_doctores(especialidad: str) -> list[dict]:
    """Lista los doctores activos de una especialidad.

    Args:
        especialidad: Nombre exacto de la especialidad (debe existir en el catálogo).

    Returns:
        Lista de doctores con su id y nombre completo.
    """
    filas = await php_client.get_especialidades()
    match = next(
        (f for f in filas
         if f.get("nombre", "").strip().lower() == especialidad.strip().lower()),
        None,
    )
    if not match or not match.get("id_categoria"):
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


# Lista que se le pasa al SDK de Gemini
TOOLS = [listar_especialidades, listar_doctores]