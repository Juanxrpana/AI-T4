"""Helpers compartidos por los proveedores de IA.

Aquí vive todo lo que no depende del SDK del proveedor: construcción del
system prompt, validación defensiva de la respuesta, botón de acción y limpieza
del JSON. Así Gemini y los proveedores OpenAI-compatible (OpenCode, Groq,
OpenAI, etc.) se comportan igual.
"""

from pathlib import Path

from ai.schemas import RespuestaOrientacion
from config import ETIQUETAS_MODULOS, RUTAS_FRONTEND, ruta_cita_con_especialidad
import tools.php_client as php_client


def leer_guia() -> str:
    return Path("guia.md").read_text(encoding="utf-8")


def system_prompt(guia: str) -> str:
    catalogo = php_client.get_catalogo_cache_sincrono()
    if catalogo:
        lista = "\n".join(f"- {c['nombre']}" for c in catalogo)
    else:
        lista = "(catálogo no disponible en este momento)"

    return (
        f"{guia}\n\n"
        f"## Catálogo actual de especialidades del centro\n"
        f"{lista}\n\n"
        f"## Directorio de doctores\n"
        f"Para consultar qué doctores hay en una especialidad, "
        f"usa la herramienta `listar_doctores(especialidad)`.\n\n"
        f"## Datos del usuario logueado\n"
        f"Si la persona pide su historial, síntomas, citas u hospitalizaciones, "
        f"usa la herramienta `mis_datos()` (sin argumentos) y responde con "
        f"`tipo_respuesta: \"datos\"` usando lo que devuelva.\n\n"
        f"## Navegación a módulos\n"
        f"Si piden ver una lista o ir a un módulo (pacientes, clientes, citas, "
        f"citas de hoy, citas realizadas, doctores, especialidades, "
        f"hospitalización, insumos, reportes), NO te niegues por privacidad: "
        f"no estás mostrando datos, solo ofreces el botón al módulo. Responde "
        f"con `tipo_respuesta: \"navegacion\"` y `modulo_sugerido` con uno de: "
        f"pacientes, clientes, citas, citas_hoy, citas_realizadas, doctores, "
        f"especialidades, hospitalizacion, insumos, insumos_vencidos, reportes. "
        f"No incluyas datos de pacientes en el mensaje."
    )


def construir_accion(r: RespuestaOrientacion) -> dict:
    """Añade el botón de acción. NO lo decide el modelo, lo decide FastAPI."""
    if r.tipo_respuesta == "orientacion" and r.especialidad_sugerida:
        return {
            "etiqueta": f"Agendar cita con {r.especialidad_sugerida}",
            "ruta": ruta_cita_con_especialidad(r.especialidad_sugerida),
            "visible": True,
        }
    if r.tipo_respuesta == "catalogo":
        return {
            "etiqueta": "Ver catálogo completo",
            "ruta": RUTAS_FRONTEND["especialidades"],
            "visible": True,
        }
    if r.tipo_respuesta == "navegacion" and r.modulo_sugerido in RUTAS_FRONTEND:
        return {
            "etiqueta": ETIQUETAS_MODULOS.get(
                r.modulo_sugerido, f"Ir a {r.modulo_sugerido}"
            ),
            "ruta": RUTAS_FRONTEND[r.modulo_sugerido],
            "visible": True,
        }
    return {"etiqueta": "", "ruta": "", "visible": False}


def validar_respuesta(r: RespuestaOrientacion) -> RespuestaOrientacion:
    """Corrige la salida del modelo contra el catálogo y los módulos reales."""
    # En emergencia, catalogo, datos y navegacion, la especialidad va vacía.
    if r.tipo_respuesta in ("emergencia", "catalogo", "datos", "navegacion"):
        r.especialidad_sugerida = None

    # Navegación: si el módulo no es válido, no se inventa una ruta.
    if r.tipo_respuesta == "navegacion" and r.modulo_sugerido not in RUTAS_FRONTEND:
        r.modulo_sugerido = None

    # La especialidad sugerida debe existir en el catálogo real.
    # Si no existe, se degrada a catalogo con las opciones reales.
    if r.especialidad_sugerida:
        catalogo = php_client.get_catalogo_cache_sincrono()
        nombres = {c["nombre"].strip().lower() for c in catalogo}
        if r.especialidad_sugerida.strip().lower() not in nombres:
            r.tipo_respuesta = "catalogo"
            r.especialidades_disponibles = [c["nombre"] for c in catalogo]
            r.especialidad_sugerida = None
            r.observacion = (
                "La especialidad sugerida no está disponible en el centro. "
                "Se muestran las opciones actuales."
            )

    return r


def limpiar_json(texto: str) -> str:
    """Quita bloques markdown ```json ... ``` si el modelo los mete."""
    texto = (texto or "").strip()
    if texto.startswith("```"):
        lineas = texto.split("\n")
        if lineas and lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip() == "```":
            lineas = lineas[:-1]
        texto = "\n".join(lineas).strip()
    return texto
