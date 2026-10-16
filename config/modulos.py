"""Diccionario de rutas del frontend para los botones de acción.

Cuando cambian rutas en el sistema PHP, se editan aquí y listo.
"""

from urllib.parse import quote

# Prefijo del sistema PHP (mismo que usa el resto del frontend).
BASE = "/Sistema-del--CEM--JEHOVA-RAFA"

RUTAS_FRONTEND = {
    "citas_nueva":     f"{BASE}/Citas/citasHoy",
    "citas_lista":     f"{BASE}/Citas/citas",
    "clientes_lista":  f"{BASE}/Clientes/Clientes",
    "pacientes_lista": f"{BASE}/Pacientes/getPacientes",
    "doctores_lista":  f"{BASE}/Doctores/doctores",
}


def ruta_cita_con_especialidad(nombre_especialidad: str) -> str:
    """Ruta al modal de cita con la especialidad preseleccionada."""
    return f"{RUTAS_FRONTEND['citas_nueva']}?especialidad={quote(nombre_especialidad)}"