"""Herramientas de solo lectura que Gemini puede invocar.

- `listar_doctores`: doctores de una especialidad.
- `mis_datos`: datos clínicos del usuario logueado (historial, síntomas, citas
  y hospitalizaciones). No recibe argumentos: el usuario lo fija el backend a
  partir de los headers X-Usuario-*, así Gemini nunca elige a quién leer.
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


# Catálogo inyectado en el prompt; estas son las tools que Gemini puede invocar.
TOOLS = [listar_doctores, mis_datos]