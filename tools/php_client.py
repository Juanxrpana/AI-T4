"""Cliente HTTP hacia el sistema PHP existente.

Incluye caché del catálogo de especialidades para evitar golpear
PHP en cada consulta. El caché se refresca solo cada 10 minutos.
"""

import time
import httpx
from config import settings


# Caché a nivel de módulo (vive mientras el proceso esté arriba)
_catalogo_cache: list[dict] = []
_catalogo_ts: float = 0.0
_CATALOGO_TTL = 600  # 10 minutos


async def _get(endpoint: str) -> list[dict]:
    """GET al sistema PHP con API key compartida. Devuelve lista o []."""
    url = f"{settings.PHP_BASE_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(
                url, headers={"X-API-Key": settings.API_KEY_COMPARTIDA}
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"] or []
            return []
        except httpx.HTTPError as e:
            print(f"[php_client] Error en {url}: {e}")
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
        print(f"🔄 Catálogo refrescado: {len(_catalogo_cache)} especialidades")

    return _catalogo_cache


def get_catalogo_cache_sincrono() -> list[dict]:
    """Lectura sincrónica del caché, sin llamar a PHP.

    Úsala solo después de haber llamado a get_catalogo_especialidades()
    al menos una vez (por ejemplo, desde el startup).
    """
    return _catalogo_cache


async def get_doctores_por_id_categoria(id_categoria: int) -> list[dict]:
    return await _get(f"/Api/apiDoctoresPorEspecialidad/{id_categoria}")