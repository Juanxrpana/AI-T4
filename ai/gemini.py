"""Implementación con Gemini: tool calling + salida estructurada."""

from pathlib import Path
from google import genai
from google.genai import types

from ai.base import ProveedorIA
from ai.schemas import RespuestaOrientacion
from config import settings, RUTAS_FRONTEND, ruta_cita_con_especialidad
from tools import TOOLS


class ProveedorGemini(ProveedorIA):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.modelo = settings.MODELO_GEMINI
        self.guia = Path("guia.md").read_text(encoding="utf-8")
        self.max_iteraciones = 6

    def _config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self.guia,
            temperature=0.3,
            tools=TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True,  # controlamos el loop para loguear cada tool call
            ),
        )

    def _construir_accion(self, r: RespuestaOrientacion) -> dict:
        """Añade el botón de acción. NO lo decide Gemini, lo decide FastAPI."""
        if r.tipo_respuesta == "orientacion" and r.especialidad_sugerida:
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
                print(f"🔧 tool: {fc.name}({dict(fc.args) if fc.args else {}})")
                resultado = await self._ejecutar_tool(fc)
                print(f"   → {resultado}")
                partes.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": resultado}
                    )
                )
            response = await chat.send_message(partes)
            iteraciones += 1

        texto = response.text or "{}"
        try:
            respuesta = RespuestaOrientacion.model_validate_json(texto)
        except Exception:
            respuesta = RespuestaOrientacion(
                tipo_respuesta="derivar",
                mensaje="No pude generar una orientación clara. Consulte el caso con un médico.",
                observacion=f"Respuesta cruda: {texto[:200]}",
            )

        return {
            **respuesta.model_dump(),
            "accion_sugerida": self._construir_accion(respuesta),
        }