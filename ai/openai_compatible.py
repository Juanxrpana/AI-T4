"""Proveedor genérico para cualquier API compatible con OpenAI.

Sirve para OpenCode Go, Groq, OpenAI/ChatGPT, DeepSeek, Ollama, vLLM, etc.
Solo cambia la configuración (base_url, api_key, modelo y headers); la lógica
de mensajes, tool calling y salida JSON es la misma.

Para añadir un proveedor nuevo basta con:
- crear su `ConfigProveedor` en `ai/proveedores.py`, o
- usar el proveedor `custom` apuntando a cualquier endpoint compatible.
"""

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from openai import AsyncOpenAI, BadRequestError

from ai.base import ProveedorIA
from ai.schemas import RespuestaOrientacion
from ai import comun
from tools import TOOLS
import tools.php_client as php_client

logger = logging.getLogger("asistente.openai_compatible")

_TIPOS_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class ConfigProveedor:
    nombre: str
    api_key: str
    base_url: str
    modelo: str
    modelos_fallback: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    # OpenAI nuevo usa max_completion_tokens; el resto, max_tokens.
    max_tokens_param: str = "max_tokens"
    max_tokens: int = 2000
    usar_json: bool = True
    timeout: float = 45.0
    # Diagnóstico de respuestas vacías: metadatos siempre; payload crudo si debug.
    debug: bool = False
    debug_dir: str = "storage/debug_ia"


def esquema_tool(fn) -> dict:
    """Convierte una función de `tools/clinica.py` al esquema de OpenAI."""
    propiedades = {}
    requeridos = []
    for nombre, param in inspect.signature(fn).parameters.items():
        propiedades[nombre] = {
            "type": _TIPOS_JSON.get(param.annotation, "string"),
        }
        if param.default is inspect.Parameter.empty:
            requeridos.append(nombre)

    descripcion = (fn.__doc__ or "").strip().split("\n\n")[0]
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": descripcion or fn.__name__,
            "parameters": {
                "type": "object",
                "properties": propiedades,
                "required": requeridos,
            },
        },
    }


def mensajes_openai(
    consulta: str,
    historial: list[dict] | None,
    guia: str,
) -> list[dict]:
    """System prompt + historial (Gemini usa "model"; OpenAI usa "assistant")."""
    mensajes = [{"role": "system", "content": comun.system_prompt(guia)}]
    for m in historial or []:
        rol = "assistant" if m.get("role") == "model" else m.get("role", "user")
        mensajes.append({"role": rol, "content": m.get("text", "")})
    mensajes.append({"role": "user", "content": consulta})
    return mensajes


def _resumen_content(contenido) -> dict:
    """Resume el content sin volcarlo (puede tener datos clínicos)."""
    if contenido is None:
        return {"tipo": "null"}
    if isinstance(contenido, str):
        return {
            "tipo": "str",
            "len": len(contenido),
            "strip_len": len(contenido.strip()),
            "blanco": not contenido.strip(),
        }
    if isinstance(contenido, list):
        texto = "".join(
            p.get("text", "") for p in contenido if isinstance(p, dict)
        )
        return {
            "tipo": "list",
            "partes": len(contenido),
            "len": len(texto),
            "blanco": not texto.strip(),
        }
    return {"tipo": type(contenido).__name__}


def _resumen_reasoning(msg_dump: dict) -> dict:
    """Detecta si el modelo puso la respuesta en un campo de razonamiento."""
    salida = {}
    for clave in ("reasoning_content", "reasoning", "thinking"):
        valor = msg_dump.get(clave)
        if valor is None:
            continue
        if isinstance(valor, str):
            salida[clave] = {
                "tipo": "str",
                "len": len(valor),
                "strip_len": len(valor.strip()),
            }
        else:
            salida[clave] = {"tipo": type(valor).__name__}
    return salida


def _es_json(texto: str) -> bool:
    if not texto or not texto.strip():
        return False
    try:
        return isinstance(json.loads(comun.limpiar_json(texto)), dict)
    except (TypeError, ValueError):
        return False


class ProveedorOpenAICompatible(ProveedorIA):
    def __init__(self, config: ConfigProveedor):
        if not config.api_key:
            raise ValueError(
                f"Falta la API key del proveedor '{config.nombre}'"
            )
        if not config.base_url or not config.modelo:
            raise ValueError(
                f"Faltan base_url o modelo del proveedor '{config.nombre}'"
            )

        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            default_headers=config.headers or None,
            timeout=config.timeout,
        )
        self.modelos = [config.modelo]
        for m in config.modelos_fallback:
            if m and m not in self.modelos:
                self.modelos.append(m)
        self.modelo_actual = config.modelo
        self.guia = comun.leer_guia()
        self.max_iteraciones = 4
        self._json_soportado = config.usar_json
        self._tools = [esquema_tool(fn) for fn in TOOLS]
        self._ultima_peticion: dict | None = None
        self._ultima_latencia_ms: int | None = None

    @property
    def nombre_modelo(self) -> str:
        return f"{self.config.nombre}:{self.modelo_actual}"

    async def precargar_catalogo(self) -> None:
        await php_client.get_catalogo_especialidades()

    async def _ejecutar_tool(self, nombre: str, args: dict) -> dict:
        fn = next((t for t in TOOLS if t.__name__ == nombre), None)
        if fn is None:
            return {"error": f"Tool '{nombre}' no permitida"}
        try:
            return await fn(**args)
        except Exception as e:
            return {"error": str(e)}

    def _resumen_peticion(self, peticion: dict) -> dict:
        mensajes = peticion.get("messages") or []
        return {
            "model": peticion.get("model"),
            "mensajes": len(mensajes),
            "roles": [m.get("role") for m in mensajes],
            "tools": len(peticion.get("tools") or []),
            "json_mode": "response_format" in peticion,
            "temperature": peticion.get("temperature"),
            "max_tokens": peticion.get(self.config.max_tokens_param),
        }

    async def _crear(
        self,
        modelo: str,
        mensajes: list[dict],
        usar_tools: bool = True,
        usar_json: bool | None = None,
    ):
        json_activo = (
            self._json_soportado
            if usar_json is None
            else (self._json_soportado and usar_json)
        )
        peticion = {
            "model": modelo,
            "messages": mensajes,
            self.config.max_tokens_param: self.config.max_tokens,
            "temperature": 0.3,
        }
        if usar_tools and self._tools:
            peticion["tools"] = self._tools
            peticion["tool_choice"] = "auto"
            # No combinar tools con response_format: varios gateways
            # OpenAI-compatible devuelven 200 con content vacío si van juntos.
            json_activo = False
        if json_activo:
            peticion["response_format"] = {"type": "json_object"}

        # Algunos endpoints no soportan response_format, temperature o tools.
        # Se quitan uno a uno y se reintenta en vez de fallar.
        while True:
            self._ultima_peticion = self._resumen_peticion(peticion)
            if self.config.debug:
                logger.info(
                    "Petición %s: %s", self.config.nombre, self._ultima_peticion
                )
            inicio = time.perf_counter()
            try:
                respuesta = await self.client.chat.completions.create(**peticion)
                self._ultima_latencia_ms = int((time.perf_counter() - inicio) * 1000)
                return respuesta
            except BadRequestError as e:
                for clave in ("response_format", "temperature", "tools"):
                    if clave in peticion:
                        peticion.pop(clave)
                        if clave == "response_format":
                            self._json_soportado = False
                        if clave == "tools":
                            peticion.pop("tool_choice", None)
                        logger.warning(
                            "Proveedor %s no acepta %s; reintentando sin ello",
                            self.config.nombre,
                            clave,
                        )
                        break
                else:
                    raise e

    @staticmethod
    def _texto(mensaje) -> str:
        """Texto útil del mensaje; rescata el JSON de reasoning si content vino vacío."""
        contenido = getattr(mensaje, "content", None)
        if isinstance(contenido, str) and contenido.strip():
            return contenido
        if isinstance(contenido, list):
            partes = [p.get("text", "") for p in contenido if isinstance(p, dict)]
            unido = "".join(partes)
            if unido.strip():
                return unido

        # Algunos modelos dejan la respuesta en reasoning_content/reasoning.
        extra = getattr(mensaje, "model_extra", None) or {}
        for campo in ("reasoning_content", "reasoning"):
            valor = getattr(mensaje, campo, None) or extra.get(campo)
            if not isinstance(valor, str):
                continue
            inicio = valor.find("{")
            fin = valor.rfind("}")
            if inicio != -1 and fin > inicio:
                candidato = valor[inicio:fin + 1]
                if _es_json(candidato):
                    return candidato
        return ""

    def _diagnostico(self, respuesta, modelo: str, etapa: str) -> dict:
        """Metadatos de la respuesta, sin volcar el contenido clínico."""
        choices = getattr(respuesta, "choices", None) or []
        choice = choices[0] if choices else None
        mensaje = getattr(choice, "message", None)
        dump = {}
        if mensaje is not None:
            try:
                dump = mensaje.model_dump()
            except Exception:
                dump = {}
            # Incluye campos extra del proveedor (reasoning_content, etc.).
            extra = getattr(mensaje, "model_extra", None) or {}
            if extra:
                dump = {**extra, **dump}
        usage = {}
        try:
            if getattr(respuesta, "usage", None):
                usage = respuesta.usage.model_dump()
        except Exception:
            usage = {}

        tool_calls = dump.get("tool_calls") or []
        return {
            "proveedor": self.config.nombre,
            "modelo": modelo,
            "etapa": etapa,
            "id": getattr(respuesta, "id", None),
            "created": getattr(respuesta, "created", None),
            "modelo_respuesta": getattr(respuesta, "model", None),
            "system_fingerprint": getattr(respuesta, "system_fingerprint", None),
            "request_id": getattr(respuesta, "_request_id", None),
            "latencia_ms": getattr(self, "_ultima_latencia_ms", None),
            "choices": len(choices),
            "finish_reason": getattr(choice, "finish_reason", None),
            "content": _resumen_content(dump.get("content")),
            "tool_calls": [
                tc.get("function", {}).get("name") for tc in tool_calls
            ],
            "refusal": dump.get("refusal"),
            "claves_mensaje": sorted(dump.keys()),
            "reasoning": _resumen_reasoning(dump),
            "usage": usage,
            "peticion": getattr(self, "_ultima_peticion", None),
        }

    def _diagnosticar(self, respuesta, modelo: str, etapa: str) -> dict:
        diagnostico = self._diagnostico(respuesta, modelo, etapa)
        logger.warning(
            "Diagnóstico IA %s: %s",
            self.config.nombre,
            json.dumps(diagnostico, ensure_ascii=False, default=str),
        )
        self._volcar_debug(respuesta, diagnostico, etapa)
        return diagnostico

    def _volcar_debug(self, respuesta, diagnostico: dict, etapa: str) -> None:
        """Guarda el payload crudo solo si IA_DEBUG está activo."""
        if not self.config.debug:
            return
        try:
            carpeta = Path(self.config.debug_dir)
            carpeta.mkdir(parents=True, exist_ok=True)
            sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            nombre = f"{sello}_{uuid4().hex[:8]}_{etapa}.json"
            ruta = carpeta / nombre
            try:
                crudo = respuesta.model_dump()
            except Exception:
                crudo = str(respuesta)
            ruta.write_text(
                json.dumps(
                    {"diagnostico": diagnostico, "respuesta": crudo},
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            logger.warning("Payload de debug guardado en %s", ruta)
        except Exception:
            logger.exception("No se pudo guardar el payload de debug")

    async def _con_modelo(self, modelo: str, mensajes: list[dict]) -> dict:
        self.modelo_actual = modelo
        conversacion = list(mensajes)
        respuesta = await self._crear(modelo, conversacion)

        for iteracion in range(self.max_iteraciones + 1):
            mensaje = respuesta.choices[0].message
            tool_calls = getattr(mensaje, "tool_calls", None)

            if not tool_calls:
                break

            if iteracion >= self.max_iteraciones:
                # Demasiadas herramientas: pedir el cierre limpio con JSON.
                respuesta = await self._crear(
                    modelo, conversacion, usar_tools=False, usar_json=True
                )
                break

            conversacion.append({
                "role": "assistant",
                "content": mensaje.content or "",
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            })

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (TypeError, ValueError):
                    args = {}
                logger.info("tool: %s(%s)", tc.function.name, args)
                resultado = await self._ejecutar_tool(tc.function.name, args)
                conversacion.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(resultado, ensure_ascii=False, default=str),
                })

            respuesta = await self._crear(modelo, conversacion)

        texto = self._texto(respuesta.choices[0].message)

        if not texto:
            self._diagnosticar(respuesta, modelo, "fase1_vacio")

        # Fase 1 (tools, sin JSON mode) puede devolver texto directo, tool
        # calls o vacío. Si no hay JSON válido, se fuerza una llamada final
        # sin tools y con JSON mode (evita el conflicto tools + response_format).
        if not _es_json(texto):
            respuesta = await self._crear(
                modelo, conversacion, usar_tools=False, usar_json=True
            )
            texto = self._texto(respuesta.choices[0].message)

        if not _es_json(texto):
            self._diagnosticar(respuesta, modelo, "sin_json")
            conversacion.append({
                "role": "user",
                "content": "Devuelve ahora únicamente el objeto JSON solicitado, sin texto adicional.",
            })
            respuesta = await self._crear(
                modelo, conversacion, usar_tools=False, usar_json=True
            )
            texto = self._texto(respuesta.choices[0].message)

        texto = comun.limpiar_json(texto)
        if not texto:
            self._diagnosticar(respuesta, modelo, "vacio_final")
            r = RespuestaOrientacion(
                tipo_respuesta="derivar",
                mensaje="No pude generar una orientación clara. Consulte el caso con un médico.",
                observacion="",
            )
        else:
            try:
                r = RespuestaOrientacion.model_validate_json(texto)
            except Exception:
                self._diagnosticar(respuesta, modelo, "json_invalido")
                r = RespuestaOrientacion(
                    tipo_respuesta="derivar",
                    mensaje="No pude generar una orientación clara. Consulte el caso con un médico.",
                    observacion="",
                )

        r = comun.validar_respuesta(r)
        return {
            **r.model_dump(),
            "accion_sugerida": comun.construir_accion(r),
        }

    async def orientar(
        self,
        consulta: str,
        historial: list[dict] | None = None,
    ) -> dict:
        if not php_client.get_catalogo_cache_sincrono():
            try:
                await php_client.get_catalogo_especialidades()
            except Exception:
                logger.warning("No se pudo refrescar el catálogo de especialidades")

        mensajes = mensajes_openai(consulta, historial, self.guia)

        ultimo_error: Exception | None = None
        for modelo in self.modelos:
            try:
                return await asyncio.wait_for(
                    self._con_modelo(modelo, mensajes),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError as e:
                logger.warning(
                    "Modelo %s excedió %.1fs; probando el siguiente",
                    modelo,
                    self.config.timeout,
                )
                ultimo_error = e
            except Exception as e:
                logger.warning("Modelo %s falló (%s); probando el siguiente", modelo, e)
                ultimo_error = e

        raise RuntimeError(
            f"Ningún modelo de {self.config.nombre} respondió: {ultimo_error}"
        )
