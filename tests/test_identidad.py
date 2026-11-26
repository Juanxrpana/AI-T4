"""Fase 1: identidad consulta/turno e idempotencia por `peticion_id`."""

import asyncio
import json

import pytest

from storage import db, sesiones


def _flujo(accion):
    asyncio.run(accion())


def test_misma_peticion_devuelve_el_mismo_turno():
    async def flujo():
        sid = "ident-idem"
        await sesiones.crear_sesion(sid, "u-idem")
        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-idem")

        primero = await sesiones.crear_turno(consulta["id"], "pet-1", "hola")
        segundo = await sesiones.crear_turno(consulta["id"], "pet-1", "hola")

        assert primero["id"] == segundo["id"]
        assert primero["seq"] == 1

    _flujo(flujo)


def test_peticion_id_guarda_la_respuesta_para_replay():
    async def flujo():
        sid = "ident-replay"
        await sesiones.crear_sesion(sid, "u-replay")
        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-replay")
        turno = await sesiones.crear_turno(consulta["id"], "pet-replay")
        await sesiones.actualizar_turno(
            turno["id"], respuesta_json={"mensaje": "respuesta original"}
        )

        repetido = await sesiones.crear_turno(consulta["id"], "pet-replay")
        assert repetido["id"] == turno["id"]
        assert (
            json.loads(repetido["respuesta_json"])["mensaje"]
            == "respuesta original"
        )

    _flujo(flujo)


def test_peticion_id_no_cruza_consultas():
    async def flujo():
        await sesiones.crear_sesion("ident-cruce-a", "u")
        await sesiones.crear_sesion("ident-cruce-b", "u")
        c1 = await sesiones.obtener_o_crear_consulta("ident-cruce-a", "u")
        c2 = await sesiones.obtener_o_crear_consulta("ident-cruce-b", "u")

        await sesiones.crear_turno(c1["id"], "pet-cruce")
        with pytest.raises(sesiones.PeticionIdConflicto):
            await sesiones.crear_turno(c2["id"], "pet-cruce")

    _flujo(flujo)


def test_consultas_y_turnos_siguen_la_secuencia():
    async def flujo():
        sid = "ident-seq"
        await sesiones.crear_sesion(sid, "u-seq")

        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-seq")
        otra = await sesiones.obtener_o_crear_consulta(sid, "u-seq")
        assert otra["id"] == consulta["id"]

        t1 = await sesiones.crear_turno(consulta["id"], "pet-seq-1", "uno")
        t2 = await sesiones.crear_turno(consulta["id"], "pet-seq-2", "dos")
        assert (t1["seq"], t2["seq"]) == (1, 2)

    _flujo(flujo)


def test_aclaracion_no_cierra_y_el_cierre_abre_otra_consulta():
    async def flujo():
        sid = "ident-cierre"
        await sesiones.crear_sesion(sid, "u-cierre")

        primera = await sesiones.obtener_o_crear_consulta(sid, "u-cierre")
        await sesiones.cerrar_consulta(primera["id"], "orientacion")

        segunda = await sesiones.obtener_o_crear_consulta(sid, "u-cierre")
        assert segunda["id"] != primera["id"]

    _flujo(flujo)


def test_borrar_sesion_conserva_el_caso_y_los_turnos():
    async def flujo():
        sid = "ident-borrar"
        await sesiones.crear_sesion(sid, "u-borrar")
        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-borrar")
        turno = await sesiones.crear_turno(consulta["id"], "pet-borrar")
        await sesiones.agregar_mensaje(sid, "user", "hola", consulta["id"], turno["id"])

        await sesiones.borrar_sesion(sid)

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT session_id, estado FROM consulta WHERE id = ?",
                (consulta["id"],),
            ) as cur:
                fila = await cur.fetchone()
            async with con.execute(
                "SELECT COUNT(*) FROM turno WHERE consulta_id = ?",
                (consulta["id"],),
            ) as cur:
                turnos = (await cur.fetchone())[0]
            async with con.execute(
                "SELECT COUNT(*) FROM mensajes WHERE session_id = ?", (sid,)
            ) as cur:
                mensajes = (await cur.fetchone())[0]
        finally:
            await con.close()

        assert fila is not None
        assert fila["session_id"] is None
        assert fila["estado"] == "abierta"
        assert turnos == 1
        assert mensajes == 0

    _flujo(flujo)
