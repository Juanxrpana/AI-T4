"""Cliente HTTP hacia el sistema PHP existente.

Limitación conocida: el sistema PHP heredado no filtra por ID en sus
endpoints AJAX. Aquí hacemos los filtros en memoria cuando es necesario.
"""

import httpx
from config import settings


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


async def get_especialidades() -> list[dict]:
    return await _get("/Api/apiEspecialidades")


async def get_doctores_por_id_categoria(id_categoria: int) -> list[dict]:
    return await _get(f"/Api/apiDoctoresPorEspecialidad/{id_categoria}")