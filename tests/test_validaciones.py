"""Fase 3: cola de validación, lease, conflicto y accesos."""

import asyncio

import pytest

from storage import db, evidencia, sesiones, validaciones


async def _crear_caso(sid: str, peticion: str) -> int:
    await sesiones.crear_sesion(sid, "u-val")
    consulta = await sesiones.obtener_o_crear_consulta(sid, "u-val")
    turno = await sesiones.crear_turno(consulta["id"], peticion)

    async with db.unidad_de_trabajo() as con:
        evidencia_id = await evidencia.guardar_evidencia(
            con,
            turno_id=turno["id"],
            consulta_id=consulta["id"],
            resumen_ficha={"motivo": "prueba", "dominio": "fiebre"},
            respuesta_final="Orientación de prueba",
            componentes=[
                {"nombre": "dominio", "valor": 1.0, "peso": 0.25},
                {"nombre": "especialidad", "valor": 0.0, "peso": 0.25},
                {"nombre": "respuestas", "valor": 0.5, "peso": 0.25},
                {"nombre": "sin_degradar", "valor": 1.0, "peso": 0.25},
            ],
            revision_requerida=True,
            motivo_revision="confianza_baja",
        )
        return await evidencia.crear_validacion(
            con,
            consulta_id=consulta["id"],
            evidencia_turno_id=evidencia_id,
            motivo="confianza_baja",
        )


def test_dos_revisores_solo_uno_toma_el_caso():
    async def flujo():
        vid = await _crear_caso("val-tomar", "pet-val-tomar")
        primera = await validaciones.tomar(vid, "rev-1")
        assert primera["estado"] == "asignada"
        assert primera["asignado_a"] == "rev-1"
        assert primera["expira_en"]

        with pytest.raises(validaciones.ConflictoValidacion) as exc:
            await validaciones.tomar(vid, "rev-2")
        assert exc.value.detalle["asignado_a"] == "rev-1"

    asyncio.run(flujo())


def test_decidir_exige_motivo_al_corregir():
    async def flujo():
        vid = await _crear_caso("val-motivo", "pet-val-motivo")
        await validaciones.tomar(vid, "rev-1")
        with pytest.raises(validaciones.MotivoRequerido):
            await validaciones.decidir(vid, "rev-1", "corregir")

        resultado = await validaciones.decidir(
            vid, "rev-1", "corregir", motivo_codigo="dominio_incorrecto"
        )
        assert resultado["estado"] == "corregida"

    asyncio.run(flujo())


def test_decidir_otro_actor_es_conflicto():
    async def flujo():
        vid = await _crear_caso("val-otro", "pet-val-otro")
        await validaciones.tomar(vid, "rev-1")
        with pytest.raises(validaciones.ConflictoValidacion):
            await validaciones.decidir(vid, "rev-2", "validar")

    asyncio.run(flujo())


def test_detalle_no_registra_acceso_y_visto_si():
    async def flujo():
        vid = await _crear_caso("val-acceso", "pet-val-acceso")
        datos = await validaciones.detalle(vid)
        assert datos is not None

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT COUNT(*) FROM acceso_caso WHERE validacion_id = ?",
                (vid,),
            ) as cur:
                assert (await cur.fetchone())[0] == 0
        finally:
            await con.close()

        await validaciones.visto(vid, "rev-1", "10")
        await validaciones.visto(vid, "rev-1", "10")

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT COUNT(*) FROM acceso_caso WHERE validacion_id = ?",
                (vid,),
            ) as cur:
                assert (await cur.fetchone())[0] == 1
        finally:
            await con.close()

    asyncio.run(flujo())


def test_lease_expirada_se_puede_retomar():
    async def flujo():
        vid = await _crear_caso("val-lease", "pet-val-lease")
        await validaciones.tomar(vid, "rev-1")

        con = await db.conectar()
        try:
            await con.execute(
                "UPDATE validacion SET expira_en = datetime('now', '-1 hour') "
                "WHERE id = ?",
                (vid,),
            )
            await con.commit()
        finally:
            await con.close()

        segunda = await validaciones.tomar(vid, "rev-2")
        assert segunda["asignado_a"] == "rev-2"

    asyncio.run(flujo())


def test_liberar_expiradas_devuelve_a_pendiente():
    async def flujo():
        vid = await _crear_caso("val-liberar", "pet-val-liberar")
        await validaciones.tomar(vid, "rev-1")

        con = await db.conectar()
        try:
            await con.execute(
                "UPDATE validacion SET expira_en = datetime('now', '-1 hour') "
                "WHERE id = ?",
                (vid,),
            )
            await con.commit()
        finally:
            await con.close()

        assert await validaciones.liberar_expiradas() >= 1

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT estado, asignado_a FROM validacion WHERE id = ?", (vid,)
            ) as cur:
                fila = await cur.fetchone()
        finally:
            await con.close()

        assert fila["estado"] == "pendiente"
        assert fila["asignado_a"] is None

    asyncio.run(flujo())
