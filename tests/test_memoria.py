"""Tests de la memoria vectorizada (embeddings + similitud)."""

import asyncio

from ai.embeddings import coseno
from storage import init_db
from storage import memoria


def test_coseno():
    assert abs(coseno([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(coseno([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_guardar_y_buscar_similares():
    asyncio.run(init_db())

    asyncio.run(memoria.guardar("u-sim", 1, "manchas rojas en la piel", {"x": 1}))
    asyncio.run(memoria.actualizar_embedding("u-sim", 1, [1.0, 0.0]))

    asyncio.run(memoria.guardar("u-sim", 2, "dolor de pecho", {"y": 1}))
    asyncio.run(memoria.actualizar_embedding("u-sim", 2, [0.0, 1.0]))

    resultados = asyncio.run(memoria.buscar_similares("u-sim", [0.9, 0.1], k=1))

    assert resultados[0]["id_paciente"] == "1"
    assert resultados[0]["score"] > 0.9
