"""Fase 3: propuestas de conocimiento, autoaprobación y versiones."""

import asyncio

import pytest

from storage import conocimiento, db, propuestas


def test_aprobar_palabra_publica_nueva_version():
    async def flujo():
        pid = await propuestas.crear(
            dominio_clave="fiebre",
            tipo="palabra",
            valor="calentura extrema",
            generado_por="u-1",
        )
        assert pid is not None

        aprobada = await propuestas.aprobar(pid, "u-2")
        assert aprobada["estado"] == "aprobada"
        assert aprobada["aprobado_por"] == "u-2"

        conocimiento.invalidar_cache()
        snapshot = conocimiento.snapshot_sincrono()
        assert "calentura extrema" in snapshot["fiebre"]["palabras_clave"]

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT COUNT(*) FROM kb_version WHERE activa = 1"
            ) as cur:
                assert (await cur.fetchone())[0] == 1
            async with con.execute("SELECT COUNT(*) FROM kb_version") as cur:
                assert (await cur.fetchone())[0] >= 2
        finally:
            await con.close()

    asyncio.run(flujo())


def test_no_se_puede_aprobar_la_propia_propuesta():
    async def flujo():
        pid = await propuestas.crear(
            dominio_clave="fiebre",
            tipo="palabra",
            valor="fiebre persistente",
            generado_por="autor",
        )
        with pytest.raises(propuestas.Autoaprobacion):
            await propuestas.aprobar(pid, "autor")

    asyncio.run(flujo())


def test_rechazar_exige_motivo_y_cierra():
    async def flujo():
        pid = await propuestas.crear(
            dominio_clave="fiebre",
            tipo="ejemplo",
            valor="ejemplo para rechazo",
            generado_por="u-1",
        )
        with pytest.raises(propuestas.ConflictoPropuesta):
            await propuestas.rechazar(pid, "u-2", "")

        rechazada = await propuestas.rechazar(pid, "u-2", "no aplica")
        assert rechazada["estado"] == "rechazada"
        assert rechazada["motivo_rechazo"] == "no aplica"

    asyncio.run(flujo())


def test_propuesta_duplicada_pendiente_no_se_duplica():
    async def flujo():
        primera = await propuestas.crear(
            dominio_clave="lesion_piel",
            tipo="palabra",
            valor="ronchas grandes",
            generado_por="u-1",
        )
        segunda = await propuestas.crear(
            dominio_clave="lesion_piel",
            tipo="palabra",
            valor="RONCHAS GRANDES",
            generado_por="u-1",
        )
        assert primera is not None
        assert segunda is None

    asyncio.run(flujo())
