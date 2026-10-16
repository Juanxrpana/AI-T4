"""Diccionario de rutas del frontend para los botones de acción.

Cuando cambian rutas en el sistema PHP, se editan aquí y listo.
"""

from urllib.parse import quote

RUTAS_FRONTEND = {
    "citas_nueva":     "/Citas/citasHoy",
    "citas_lista":     "/Citas/citas",
    "clientes_lista":  "/Clientes/Clientes",
    "pacientes_lista": "/Pacientes/getPacientes",
    "doctores_lista":  "/Doctores/doctores",
}


def ruta_cita_con_especialidad(nombre_especialidad: str) -> str:
    """Ruta al modal de cita con la especialidad preseleccionada."""
    return f"{RUTAS_FRONTEND['citas_nueva']}?especialidad={quote(nombre_especialidad)}"