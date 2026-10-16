"""Tests de los endpoints HTTP de FastAPI.

No se llama a Gemini ni a PHP: se reemplaza el proveedor por dobles de prueba.
"""

from fastapi.testclient import TestClient

import main

API_KEY = "test-api-key"


def _respuesta_ok():
    return {
        "tipo_respuesta": "orientacion",
        "mensaje": "Le sugiero Cardiología.",
        "especialidad_sugerida": "Cardiología",
        "especialidades_disponibles": [],
        "pregunta_aclaratoria": "",
        "observacion": "",
        "accion_sugerida": {
            "etiqueta": "Agendar cita con Cardiología",
            "ruta": "/Sistema-del--CEM--JEHOVA-RAFA/Citas/citasHoy",
            "visible": True,
        },
    }


def _cliente(monkeypatch, orientar=None):
    """Devuelve un TestClient con el proveedor mockeado."""

    async def _precargar():
        return None

    async def _orientar(consulta, historial=None):
        if orientar is not None:
            return orientar(consulta, historial)
        return _respuesta_ok()

    monkeypatch.setattr(main.proveedor, "precargar_catalogo", _precargar)
    monkeypatch.setattr(main.proveedor, "orientar", _orientar)
    return TestClient(main.app)


def test_raiz(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert r.json()["estado"] == "ok"


def test_orientar_con_key_valida(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "paciente con dolor de pecho"},
            headers={"X-API-Key": API_KEY, "X-Usuario-Nombre": "Ana"},
        )
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "orientacion"
        assert cuerpo["session_id"]
        assert cuerpo["accion_sugerida"]["visible"] is True


def test_orientar_sin_key(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post("/orientar", json={"consulta": "dolor de pecho"})
        assert r.status_code == 401


def test_orientar_key_incorrecta(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "dolor de pecho"},
            headers={"X-API-Key": "otra-clave"},
        )
        assert r.status_code == 401


def test_orientar_consulta_corta(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "a"},
            headers={"X-API-Key": API_KEY},
        )
        assert r.status_code == 422


def test_error_del_proveedor_no_filtra_detalle(monkeypatch):
    def _explota(consulta, historial):
        raise RuntimeError("secreto interno 123")

    with _cliente(monkeypatch, orientar=_explota) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "algo"},
            headers={"X-API-Key": API_KEY},
        )
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "derivar"
        assert cuerpo["observacion"] == ""
        assert "secreto" not in r.text


def test_contexto_de_usuario_se_propaga(monkeypatch):
    visto = {}

    def _captura(consulta, historial=None):
        import tools.php_client as php_client

        visto["usuario"] = php_client.usuario_actual.get()
        return _respuesta_ok()

    with _cliente(monkeypatch, orientar=_captura) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "mis citas"},
            headers={"X-API-Key": API_KEY, "X-Usuario-Id": "42"},
        )
        assert r.status_code == 200

    assert visto["usuario"] == "42"


def test_sesion_se_guarda_y_se_borra(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "un motivo de consulta", "session_id": "s-1"},
            headers={"X-API-Key": API_KEY},
        )
        assert r.status_code == 200
        assert r.json()["session_id"] == "s-1"

        r = c.get("/sesiones/s-1", headers={"X-API-Key": API_KEY})
        assert r.status_code == 200
        assert len(r.json()["historial"]) == 2

        r = c.delete("/sesiones/s-1", headers={"X-API-Key": API_KEY})
        assert r.status_code == 204

        r = c.get("/sesiones/s-1", headers={"X-API-Key": API_KEY})
        assert r.status_code == 404
