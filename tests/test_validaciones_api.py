"""Fase 3: contratos HTTP de la cola de validación."""

import asyncio

from fastapi.testclient import TestClient

import main
from storage import db, evidencia, sesiones

API_KEY = "test-api-key"


def _cliente(monkeypatch):
    async def _precargar():
        return None

    async def _orientar(consulta, historial=None):
        return {
            "tipo_respuesta": "orientacion",
            "mensaje": "Orientación",
            "especialidad_sugerida": "Cardiología",
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "observacion": "",
            "accion_sugerida": {"etiqueta": "Ver", "ruta": "/", "visible": True},
        }

    monkeypatch.setattr(main.proveedor, "precargar_catalogo", _precargar)
    monkeypatch.setattr(main.proveedor, "orientar", _orientar)
    return TestClient(main.app)


def _crear_caso(sid: str, peticion: str) -> int:
    async def flujo():
        await sesiones.crear_sesion(sid, "u-api")
        consulta = await sesiones.obtener_o_crear_consulta(sid, "u-api")
        turno = await sesiones.crear_turno(consulta["id"], peticion)
        async with db.unidad_de_trabajo() as con:
            evidencia_id = await evidencia.guardar_evidencia(
                con,
                turno_id=turno["id"],
                consulta_id=consulta["id"],
                resumen_ficha={"motivo": "api", "dominio": "fiebre"},
                respuesta_final="Orientación API",
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

    return asyncio.run(flujo())


def _headers(actor="rev-api", rol="10"):
    return {
        "X-API-Key": API_KEY,
        "X-Usuario-Id": actor,
        "X-Usuario-Rol": rol,
    }


def test_cola_exige_rol(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.get(
            "/validaciones",
            headers={"X-API-Key": API_KEY, "X-Usuario-Id": "x"},
        )
        assert r.status_code == 403


def test_tomar_decidir_y_visto_por_http(monkeypatch):
    vid = _crear_caso("val-http", "pet-val-http")

    with _cliente(monkeypatch) as c:
        r = c.get("/validaciones", headers=_headers())
        assert r.status_code == 200
        assert any(item["id"] == vid for item in r.json()["items"])

        r = c.get(f"/validaciones/{vid}", headers=_headers())
        assert r.status_code == 200
        assert r.json()["accesos"] == []

        r = c.post(f"/validaciones/{vid}/visto", headers=_headers())
        assert r.status_code == 200

        r = c.post(f"/validaciones/{vid}/tomar", headers=_headers("rev-1"))
        assert r.status_code == 200
        assert r.json()["asignado_a"] == "rev-1"

        r = c.post(f"/validaciones/{vid}/tomar", headers=_headers("rev-2"))
        assert r.status_code == 409
        assert r.json()["detail"]["asignado_a"] == "rev-1"

        r = c.post(
            f"/validaciones/{vid}/decidir",
            headers=_headers("rev-1"),
            json={"decision": "corregir"},
        )
        assert r.status_code == 422

        r = c.post(
            f"/validaciones/{vid}/decidir",
            headers=_headers("rev-1"),
            json={"decision": "corregir", "motivo_codigo": "dominio_incorrecto"},
        )
        assert r.status_code == 200
        assert r.json()["estado"] == "corregida"

        r = c.get(f"/validaciones/{vid}", headers=_headers())
        assert r.status_code == 200
        assert len(r.json()["accesos"]) == 1


def test_salud_responde(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.get("/salud")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["foreign_key_check"] == []
