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
            json={"consulta": "manchas rojas en la piel"},
            headers={"X-API-Key": API_KEY, "X-Usuario-Nombre": "Ana"},
        )
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "orientacion"
        assert cuerpo["session_id"]
        assert cuerpo["accion_sugerida"]["visible"] is True


def _mock_php_paciente(monkeypatch, id_paciente=999):
    async def fake_buscar(q):
        return [{"id_paciente": id_paciente, "cedula": "2000002", "nombre": "Ana", "apellido": "Pérez"}]

    async def fake_controles(pid):
        return [{
            "fecha_control": "2026-01-01 10:00:00",
            "diagnostico": "Asma",
            "medicamentosRecetados": "Salbutamol",
            "sintomas": "Disnea",
        }]

    async def fake_patologias(pid):
        return [{"nombre_patologia": "ASMA", "fecha_registro": "2025-01-01"}]

    monkeypatch.setattr(main.php_client, "buscar_paciente", fake_buscar)
    monkeypatch.setattr(main.php_client, "get_controles_paciente", fake_controles)
    monkeypatch.setattr(main.php_client, "get_patologias_paciente", fake_patologias)


def test_cuestionario_no_deriva_con_un_sintoma(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "fiebre", "session_id": "q-solo"},
            headers={"X-API-Key": API_KEY},
        )
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "aclaracion"
        assert cuerpo["tipo_respuesta"] != "derivar"


def test_cuestionario_pide_cedula(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "me duele el pecho", "session_id": "q-cedula"},
            headers={"X-API-Key": API_KEY},
        )
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "aclaracion"
        assert "cédula" in cuerpo["pregunta_activa"].lower()


def test_cuestionario_flujo_completo(monkeypatch):
    _mock_php_paciente(monkeypatch, id_paciente=888)

    with _cliente(monkeypatch) as c:
        headers = {"X-API-Key": API_KEY, "X-Usuario-Id": "u-flujo"}

        # 1) Sintoma -> pide cedula
        r = c.post("/orientar", json={"consulta": "me duele el pecho", "session_id": "q-flujo"}, headers=headers)
        assert r.json()["tipo_respuesta"] == "aclaracion"

        # 2) Cedula -> primera pregunta del dominio
        r = c.post("/orientar", json={"consulta": "2000002", "session_id": "q-flujo"}, headers=headers)
        assert r.json()["tipo_respuesta"] == "aclaracion"

        # 3) Tres respuestas -> orientacion final
        for respuesta in ["7", "no", "con el esfuerzo"]:
            r = c.post("/orientar", json={"consulta": respuesta, "session_id": "q-flujo"}, headers=headers)

        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "orientacion"
        assert cuerpo["progreso"] == 100
        assert cuerpo["pruebas_sugeridas"]
        assert cuerpo["accion_sugerida"]["visible"] is True


def test_cuestionario_emergencia_no_pregunta(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={"consulta": "dolor de pecho opresivo con falta de aire"},
            headers={"X-API-Key": API_KEY},
        )
        cuerpo = r.json()
        assert cuerpo["tipo_respuesta"] == "emergencia"
        assert cuerpo["pregunta_activa"] == ""


def test_dominio_piel_pregunta_dirigida(monkeypatch):
    _mock_php_paciente(monkeypatch, id_paciente=777)

    with _cliente(monkeypatch) as c:
        headers = {"X-API-Key": API_KEY, "X-Usuario-Id": "u-piel"}

        r = c.post("/orientar", json={"consulta": "tengo roja la piel", "session_id": "piel-1"}, headers=headers)
        assert r.json()["tipo_respuesta"] == "aclaracion"

        r = c.post("/orientar", json={"consulta": "2000002", "session_id": "piel-1"}, headers=headers)
        d = r.json()
        assert "parte del cuerpo" in (d.get("pregunta_activa") or "").lower()


def _respuesta_aclaracion():
    return {
        "tipo_respuesta": "aclaracion",
        "mensaje": "Necesito más información.",
        "especialidad_sugerida": None,
        "especialidades_disponibles": [],
        "pregunta_aclaratoria": "¿Desde cuándo?",
        "observacion": "",
        "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
    }


def test_flujo_general_cierra_tras_5_preguntas(monkeypatch):
    import tools.php_client as php_client

    monkeypatch.setattr(
        php_client,
        "get_catalogo_cache_sincrono",
        lambda: [{"nombre": "CONSULTA GENERAL"}],
    )

    with _cliente(monkeypatch, orientar=lambda consulta, historial=None: _respuesta_aclaracion()) as c:
        headers = {"X-API-Key": API_KEY, "X-Usuario-Id": "u-gen"}

        for i in range(5):
            r = c.post(
                "/orientar",
                json={"consulta": f"respuesta {i}", "session_id": "gen-1"},
                headers=headers,
            )
            assert r.json()["tipo_respuesta"] == "aclaracion"

        r = c.post(
            "/orientar",
            json={"consulta": "ultima respuesta", "session_id": "gen-1"},
            headers=headers,
        )
        d = r.json()
        assert d["tipo_respuesta"] == "orientacion"
        assert d["progreso"] == 100
        assert d["accion_sugerida"]["visible"] is True


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
            json={"consulta": ""},
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


def test_auditoria_registra_y_lista(monkeypatch):
    with _cliente(monkeypatch) as c:
        c.post(
            "/orientar",
            json={"consulta": "manchas rojas en la piel", "session_id": "aud-1"},
            headers={"X-API-Key": API_KEY, "X-Usuario-Id": "u-aud"},
        )

        r = c.get("/auditoria?limite=10", headers={"X-API-Key": API_KEY})
        assert r.status_code == 200
        filas = r.json()
        assert isinstance(filas, list)
        assert any(f["session_id"] == "aud-1" for f in filas)
