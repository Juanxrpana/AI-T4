"""Embeddings de Gemini para la memoria vectorizada."""

import asyncio
import logging

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger("asistente.embeddings")

_client = None


def _cliente():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=12000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
    return _client


async def embed(texto: str) -> list[float] | None:
    """Devuelve el vector del texto o None si el servicio falla."""
    texto = (texto or "").strip()
    if not texto:
        return None

    try:
        respuesta = await asyncio.wait_for(
            _cliente().aio.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=texto,
            ),
            timeout=12,
        )
        if not respuesta.embeddings:
            return None
        return [float(v) for v in respuesta.embeddings[0].values]
    except Exception as e:
        logger.warning("Embedding falló: %s", str(e)[:120])
        return None


def coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores."""
    if not a or not b or len(a) != len(b):
        return 0.0

    producto = sum(x * y for x, y in zip(a, b))
    norma_a = sum(x * x for x in a) ** 0.5
    norma_b = sum(y * y for y in b) ** 0.5

    if not norma_a or not norma_b:
        return 0.0

    return producto / (norma_a * norma_b)
