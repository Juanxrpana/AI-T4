"""Cliente HTTP hacia el sistema PHP existente.

Incluye:
- Caché del catálogo de especialidades (se refresca cada 10 minutos).
- El `id_usuario` de la consulta actual, para que PHP pueda resolver los datos
  del usuario logueado sin que Gemini elija a quién leer.
"""

import contextvars
import logging
import time
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("asistente.php_client")

# Identidad del usuario que está consultando en la petición actual.
usuario_actual: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "usuario_actual", default=None
)

# Caché a nivel de módulo (vive mientras el proceso esté arriba)
_catalogo_cache: list[dict] = []
_catalogo_ts: float = 0.0
_CATALOGO_TTL = 600  # 10 minutos


def _headers() -> dict:
    headers = {"X-API-Key": settings.API_KEY_COMPARTIDA}
    usuario = usuario_actual.get()
    if usuario:
        headers["X-Usuario-Id"] = str(usuario)
    return headers


async def _get_json(endpoint: str) -> Any:
    """GET al sistema PHP con API key. Devuelve el JSON tal cual (dict o list)."""
    url = f"{settings.PHP_BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url, headers=_headers())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            logger.warning("Error en %s: %s", url, e)
            return None


async def _get(endpoint: str) -> list[dict]:
    """GET que garantiza una lista (para catálogos). Devuelve [] si falla."""
    data = await _get_json(endpoint)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"] or []
    return []


async def get_catalogo_especialidades(forzar_refresh: bool = False) -> list[dict]:
    """Devuelve el catálogo completo (id_categoria + nombre). Cacheado.

    Se refresca automáticamente cada 10 minutos. Pasa forzar_refresh=True
    si necesitas bypass del caché.
    """
    global _catalogo_cache, _catalogo_ts

    ahora = time.time()
    expirado = (ahora - _catalogo_ts) > _CATALOGO_TTL

    if forzar_refresh or expirado or not _catalogo_cache:
        filas = await _get("/Api/apiEspecialidades")
        _catalogo_cache = [
            f for f in filas
            if f.get("id_categoria") and f.get("nombre")
        ]
        _catalogo_ts = ahora
        logger.info("Catálogo refrescado: %d especialidades", len(_catalogo_cache))

    return _catalogo_cache


def get_catalogo_cache_sincrono() -> list[dict]:
    """Lectura sincrónica del caché, sin llamar a PHP.

    Úsala solo después de haber llamado a get_catalogo_especialidades()
    al menos una vez (por ejemplo, desde el startup).
    """
    return _catalogo_cache


async def get_doctores_por_id_categoria(id_categoria: int) -> list[dict]:
    return await _get(f"/Api/apiDoctoresPorEspecialidad/{id_categoria}")


async def get_mis_datos(id_usuario: int) -> dict:
    """Datos clínicos del paciente asociado al usuario logueado."""
    data = await _get_json(f"/Api/apiDatosUsuario/{id_usuario}")
    if isinstance(data, dict):
        return data
    return {"ok": False, "error": "No se pudieron obtener los datos del usuario."}
