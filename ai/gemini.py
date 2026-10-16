"""Implementación con Gemini: tool calling + salida estructurada.

Optimizaciones de tokens aplicadas:
- thinking_budget=0: Gemini no razona internamente (no lo necesitamos).
- Catálogo inyectado al system prompt: ahorra una vuelta de tool calling.
- max_output_tokens: acota respuestas largas innecesarias.
"""

from pathlib import Path
import logging

from google import genai
from google.genai import types

from ai.base import ProveedorIA
from ai.schemas import RespuestaOrientacion
from config import settings, RUTAS_FRONTEND, ruta_cita_con_especialidad
from tools import TOOLS
import tools.php_client as php_client

logger = logging.getLogger("asistente.gemini")


class ProveedorGemini(ProveedorIA):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.modelo = settings.MODELO_GEMINI
        self.guia = Path("guia_compacta.md").read_text(encoding="utf-8")
        self.max_iteraciones = 4  # antes 6, con menos tools 4 basta

    async def precargar_catalogo(self) -> None:
        """Carga el catálogo de especialidades al arrancar la API.

        Se llama una sola vez desde el startup de FastAPI. A partir de
        ahí el caché se refresca solo cada 10 minutos.
        """
        await php_client.get_catalogo_especialidades()

    def _system_prompt(self) -> str:
        """Guía + catálogo real inyectado. Se construye una vez por request,
        pero el catálogo viene del caché en memoria (sin I/O)."""
        catalogo = php_client.get_catalogo_cache_sincrono()
        if catalogo:
            lista = "\n".join(f"- {c['nombre']}" for c in catalogo)
        else:
            lista = "(catálogo no disponible en este momento)"

        return (
            f"{self.guia}\n\n"
            f"## Catálogo actual de especialidades del centro\n"
            f"{lista}\n\n"
            f"## Directorio de doctores\n"
            f"Para consultar qué doctores hay en una especialidad, "
            f"usa la herramienta `listar_doctores(especialidad)`.\n\n"
            f"## Datos del usuario logueado\n"
            f"Si la persona pide su historial, síntomas, citas u hospitalizaciones, "
            f"usa la herramienta `mis_datos()` (sin argumentos) y responde con "
            f"`tipo_respuesta: \"datos\"` usando lo que devuelva."
        )

    def _config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self._system_prompt(),
            temperature=0.3,
            max_output_tokens=1000,
            tools=TOOLS,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,
            ),
        )

    def _construir_accion(self, r: RespuestaOrientacion) -> dict:
        """Añade el botón de acción. NO lo decide Gemini, lo decide FastAPI."""
        if r.tipo_respuesta == "orientacion" and r.especialidad_sugerida:
            nombre = r.especialidad_sugerida.title()
            return {
                "etiqueta": f"Agendar cita con {r.especialidad_sugerida}",
                "ruta": ruta_cita_con_especialidad(r.especialidad_sugerida),
                "visible": True,
            }
        if r.tipo_respuesta == "catalogo":
            return {
                "etiqueta": "Ver catálogo completo",
                "ruta": RUTAS_FRONTEND["citas_nueva"],
                "visible": True,
            }
        return {"etiqueta": "", "ruta": "", "visible": False}

    async def _ejecutar_tool(self, fc: types.FunctionCall) -> dict:
        fn = next((t for t in TOOLS if t.__name__ == fc.name), None)
        if fn is None:
            return {"error": f"Tool '{fc.name}' no permitida"}
        try:
            return await fn(**(dict(fc.args) if fc.args else {}))
        except Exception as e:
            return {"error": str(e)}
        
    async def orientar(
        self,
        consulta: str,
        historial: list[dict] | None = None,
    ) -> dict:
        # Reintento perezoso: si el arranque no pudo cargar el catálogo
        # (PHP estaba caído), se vuelve a intentar antes de construir el prompt.
        if not php_client.get_catalogo_cache_sincrono():
            try:
                await php_client.get_catalogo_especialidades()
            except Exception:
                logger.warning("No se pudo refrescar el catálogo de especialidades")

        chat = self.client.aio.chats.create(
            model=self.modelo,
            config=self._config(),
        )

        contenido: list[types.Content] | str = consulta
        if historial:
            contenido = [
                types.Content(
                    role=m["role"],
                    parts=[types.Part.from_text(text=m["text"])],
                )
                for m in historial
            ] + [types.Content(role="user", parts=[types.Part.from_text(text=consulta)])]

        response = await chat.send_message(contenido)

        iteraciones = 0
        while response.function_calls and iteraciones < self.max_iteraciones:
            partes = []
            for fc in response.function_calls:
                logger.info("tool: %s(%s)", fc.name, dict(fc.args) if fc.args else {})
                resultado = await self._ejecutar_tool(fc)
                logger.debug("tool %s -> %s", fc.name, resultado)
                partes.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": resultado}
                    )
                )
            response = await chat.send_message(partes)
            iteraciones += 1

        texto = self._limpiar_json(response.text or "{}")
        try:
            respuesta = RespuestaOrientacion.model_validate_json(texto)
        except Exception:
            # El texto crudo queda en el log del servidor, nunca en la respuesta.
            logger.warning("Respuesta de Gemini no parseable: %.200s", texto)
            respuesta = RespuestaOrientacion(
                tipo_respuesta="derivar",
                mensaje="No pude generar una orientación clara. Consulte el caso con un médico.",
                observacion="",
            )

        # === Validación defensiva ===
        # En emergencia y catalogo, la especialidad siempre va vacía.
        if respuesta.tipo_respuesta in ("emergencia", "catalogo", "datos"):
            respuesta.especialidad_sugerida = None

        # La especialidad sugerida debe existir en el catálogo real.
        # Si no existe, se degrada a catalogo con las opciones reales.
        if respuesta.especialidad_sugerida:
            catalogo = php_client.get_catalogo_cache_sincrono()
            nombres = {c["nombre"].strip().lower() for c in catalogo}
            if respuesta.especialidad_sugerida.strip().lower() not in nombres:
                respuesta.tipo_respuesta = "catalogo"
                respuesta.especialidades_disponibles = [c["nombre"] for c in catalogo]
                respuesta.especialidad_sugerida = None
                respuesta.observacion = (
                    "La especialidad sugerida no está disponible en el centro. "
                    "Se muestran las opciones actuales."
                )

        return {
            **respuesta.model_dump(),
            "accion_sugerida": self._construir_accion(respuesta),
        }
    @staticmethod
    def _limpiar_json(texto: str) -> str:
        """Quita bloques markdown ```json ... ``` si Gemini los mete."""
        texto = texto.strip()
        if texto.startswith("```"):
            # Quita la primera línea (```json o ```) y la última (```)
            lineas = texto.split("\n")
            if lineas and lineas[0].startswith("```"):
                lineas = lineas[1:]
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()
        return texto