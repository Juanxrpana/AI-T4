"""Diccionario de rutas del frontend para los botones de acción.

Cuando cambian rutas en el sistema PHP, se editan aquí y listo.
"""

from urllib.parse import quote

# Prefijo del sistema PHP (mismo que usa el resto del frontend).
BASE = "/Sistema-del--CEM--JEHOVA-RAFA"

RUTAS_FRONTEND = {
    "citas_nueva":       f"{BASE}/Citas/citasHoy",
    "citas":             f"{BASE}/Citas/citas",
    "citas_hoy":         f"{BASE}/Citas/citasHoy",
    "citas_realizadas":  f"{BASE}/Citas/citasRealizadas",
    "pacientes":         f"{BASE}/Pacientes/getPacientes",
    "clientes":          f"{BASE}/Clientes/Clientes",
    "doctores":          f"{BASE}/Doctores/doctores",
    # Catálogo de especialidades (categorías de servicio) del centro.
    "especialidades":    f"{BASE}/Servicios/servicios",
    "hospitalizacion":   f"{BASE}/Hospitalizacion/hospitalizacion",
    "insumos":           f"{BASE}/Insumos/insumos",
    "insumos_vencidos":  f"{BASE}/Insumos/InsumosVencidos",
    "reportes":          f"{BASE}/Reportes/reportes",
}

# Etiqueta del botón para cada módulo (navegación).
ETIQUETAS_MODULOS = {
    "citas":            "Ver citas",
    "citas_hoy":        "Ver citas de hoy",
    "citas_realizadas": "Ver citas realizadas",
    "pacientes":        "Ver lista de pacientes",
    "clientes":         "Ver clientes",
    "doctores":         "Ver directorio médico",
    "especialidades":   "Ver especialidades",
    "hospitalizacion":  "Ver hospitalización",
    "insumos":          "Ver insumos",
    "insumos_vencidos": "Ver insumos vencidos",
    "reportes":         "Ver reportes",
}


def ruta_cita_con_especialidad(nombre_especialidad: str) -> str:
    """Ruta al modal de cita con la especialidad preseleccionada."""
    return f"{RUTAS_FRONTEND['citas_nueva']}?especialidad={quote(nombre_especialidad)}"
