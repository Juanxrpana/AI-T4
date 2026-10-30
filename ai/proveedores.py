"""Registro de proveedores de IA y cadena de respaldo.

`crear_proveedor()` construye el proveedor principal (`PROVEEDOR_IA`) y, si se
configura, envuelve la cadena `PROVEEDORES_FALLBACK`. Añadir un proveedor nuevo
es solo agregar su configuración aquí (o usar `custom` sin tocar código).
"""

import logging
from uuid import uuid4

from ai.base import ProveedorIA
from ai.gemini import ProveedorGemini
from ai.openai_compatible import ConfigProveedor, ProveedorOpenAICompatible
from config import settings

logger = logging.getLogger("asistente.proveedores")


class ProveedorFallback(ProveedorIA):
    """Prueba los proveedores en orden hasta que uno responda."""

    def __init__(self, proveedores: list[ProveedorIA]):
        if not proveedores:
            raise ValueError("La cadena de proveedores está vacía")
        self.proveedores = proveedores
        self.ultimo: ProveedorIA | None = None

    @property
    def nombre_modelo(self) -> str:
        actual = self.ultimo or self.proveedores[0]
        return getattr(actual, "nombre_modelo", type(actual).__name__)

    async def precargar_catalogo(self) -> None:
        for proveedor in self.proveedores:
            try:
                await proveedor.precargar_catalogo()
                return
            except Exception:
                logger.warning(
                    "No se pudo precargar el catálogo con %s",
                    type(proveedor).__name__,
                )

    async def orientar(
        self,
        consulta: str,
        historial: list[dict] | None = None,
    ) -> dict:
        errores: list[Exception] = []
        for proveedor in self.proveedores:
            try:
                respuesta = await proveedor.orientar(consulta, historial)
                self.ultimo = proveedor
                return respuesta
            except Exception as e:
                logger.warning(
                    "Proveedor %s falló (%s); probando el siguiente",
                    getattr(proveedor, "nombre_modelo", type(proveedor).__name__),
                    e,
                )
                errores.append(e)

        raise RuntimeError(f"Todos los proveedores fallaron: {errores[-1]}")


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _timeout() -> float:
    # Los modelos OpenAI-compatible suelen tardar más que Gemini; damos margen.
    return max(45.0, float(settings.IA_TIMEOUT_MODELO))


def _debug() -> dict:
    return {"debug": settings.IA_DEBUG, "debug_dir": settings.IA_DEBUG_DIR}


def _config(nombre: str) -> ConfigProveedor:
    if nombre == "opencode":
        return ConfigProveedor(
            nombre="opencode",
            api_key=settings.OPENCODE_API_KEY,
            base_url=settings.OPENCODE_BASE_URL,
            modelo=settings.MODELO_OPENCODE,
            modelos_fallback=_lista(settings.MODELOS_FALLBACK_OPENCODE),
            # OpenCode Go usa esta cabecera para routing y prompt caching.
            headers={"x-opencode-session": str(uuid4())},
            timeout=_timeout(),
            **_debug(),
        )

    if nombre == "groq":
        return ConfigProveedor(
            nombre="groq",
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
            modelo=settings.MODELO_GROQ,
            modelos_fallback=_lista(settings.MODELOS_FALLBACK_GROQ),
            timeout=_timeout(),
            **_debug(),
        )

    if nombre == "openai":
        return ConfigProveedor(
            nombre="openai",
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            modelo=settings.MODELO_OPENAI,
            modelos_fallback=_lista(settings.MODELOS_FALLBACK_OPENAI),
            # Los modelos nuevos de OpenAI rechazan max_tokens.
            max_tokens_param="max_completion_tokens",
            timeout=_timeout(),
            **_debug(),
        )

    if nombre == "custom":
        return ConfigProveedor(
            nombre="custom",
            api_key=settings.CUSTOM_API_KEY,
            base_url=settings.CUSTOM_BASE_URL,
            modelo=settings.MODELO_CUSTOM,
            modelos_fallback=_lista(settings.MODELOS_FALLBACK_CUSTOM),
            timeout=_timeout(),
            **_debug(),
        )

    raise ValueError(f"Proveedor desconocido: '{nombre}'")


def construir(nombre: str) -> ProveedorIA:
    nombre = (nombre or "").strip().lower()
    if nombre == "gemini":
        return ProveedorGemini()
    return ProveedorOpenAICompatible(_config(nombre))


def crear_proveedor() -> ProveedorIA:
    principal = (settings.PROVEEDOR_IA or "").strip().lower()
    if not principal:
        raise ValueError(
            "Configura PROVEEDOR_IA en .env (opencode, gemini, groq, openai o custom)"
        )
    proveedores = [construir(principal)]

    for nombre in _lista(settings.PROVEEDORES_FALLBACK):
        nombre = nombre.lower()
        if not nombre or nombre == principal:
            continue
        try:
            proveedores.append(construir(nombre))
        except Exception as e:
            # Un respaldo mal configurado no debe impedir que arranque la app.
            logger.warning(
                "No se pudo inicializar el proveedor de respaldo '%s': %s",
                nombre,
                e,
            )

    if len(proveedores) == 1:
        return proveedores[0]
    return ProveedorFallback(proveedores)
