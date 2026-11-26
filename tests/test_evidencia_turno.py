"""Fase 2: evidencia por turno, componentes, candidatos y validación."""

import asyncio

from storage import db, evidencia, sesiones


def test_evidencia_y_validacion_en_una_transaccion():
    async def flujo():
        sid = "ev-turno"
        await sesiones.crear_sesion(sid, "u-ev")
        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-ev")
        turno = await sesiones.crear_turno(consulta["id"], "pet-ev")

        componentes = [
            {"nombre": "dominio", "valor": 1.0, "peso": 0.25},
            {"nombre": "especialidad", "valor": 1.0, "peso": 0.25},
            {"nombre": "respuestas", "valor": 1.0, "peso": 0.25},
            {"nombre": "sin_degradar", "valor": 1.0, "peso": 0.25},
        ]

        async with db.unidad_de_trabajo() as con:
            evidencia_id = await evidencia.guardar_evidencia(
                con,
                turno_id=turno["id"],
                consulta_id=consulta["id"],
                resumen_ficha={
                    "motivo": "me duele el pecho",
                    "dominio": "dolor_toracico",
                    "respuestas": {"intensidad": "7"},
                    "especialidad": "CARDIOLOGIA",
                    "controles": [],
                    "patologias": [],
                },
                respuesta_final="Le sugiero Cardiología.",
                componentes=componentes,
                candidatos=[
                    {"dominio": "dolor_toracico", "dominio_id": None, "score": 1.0}
                ],
                revision_requerida=True,
                motivo_revision="confianza_baja",
            )
            validacion_id = await evidencia.crear_validacion(
                con,
                consulta_id=consulta["id"],
                evidencia_turno_id=evidencia_id,
                motivo="confianza_baja",
            )

        datos = await evidencia.listar_por_turno(turno["id"])
        assert datos is not None
        assert datos["evidencia"]["confianza_total"] == 1.0
        assert datos["evidencia"]["revision_requerida"] == 1
        assert len(datos["evidencia"]["ficha_hash"]) == 64
        assert len(datos["evidencia"]["respuesta_hash"]) == 64
        assert len(datos["componentes"]) == 4
        assert datos["candidatos"][0]["dominio_clave"] == "dolor_toracico"

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT estado, motivo_codigo, expira_en FROM validacion "
                "WHERE id = ?",
                (validacion_id,),
            ) as cur:
                validacion = await cur.fetchone()
            async with con.execute(
                "SELECT COUNT(*) FROM validacion_evento WHERE validacion_id = ?",
                (validacion_id,),
            ) as cur:
                eventos = (await cur.fetchone())[0]
        finally:
            await con.close()

        assert validacion["estado"] == "pendiente"
        assert validacion["motivo_codigo"] == "confianza_baja"
        assert validacion["expira_en"]
        assert eventos == 1

    asyncio.run(flujo())


def test_estimar_confianza_ponderada():
    componentes = [
        {"nombre": "a", "valor": 1.0, "peso": 0.75},
        {"nombre": "b", "valor": 0.0, "peso": 0.25},
    ]
    assert evidencia.estimar_confianza(componentes) == 0.75
    assert evidencia.estimar_confianza([]) == 0.0
