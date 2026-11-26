"""Fase 0: motor de evidencia (normalización, tokens, negación y polaridad)."""

import ai.evidencia as evidencia


def test_normalizar_quita_acentos():
    assert evidencia.normalizar("Torácico") == "toracico"


def test_detecta_positiva():
    resultados = evidencia.detectar_evidencia("tengo fiebre", ["fiebre"])
    assert resultados
    assert resultados[0]["polaridad"] == "positiva"


def test_detecta_negativa():
    resultados = evidencia.detectar_evidencia("no tengo fiebre", ["fiebre"])
    assert resultados
    assert resultados[0]["polaridad"] == "negativa"
    assert evidencia.coincide("no tengo fiebre", ["fiebre"]) is False


def test_sin_es_negacion():
    resultados = evidencia.detectar_evidencia("sin dolor de pecho", ["pecho"])
    assert resultados
    assert resultados[0]["polaridad"] == "negativa"


def test_doble_negacion_es_positiva():
    resultados = evidencia.detectar_evidencia("no sin fiebre", ["fiebre"])
    assert resultados
    assert resultados[0]["polaridad"] == "positiva"


def test_frase_con_stopwords():
    resultados = evidencia.detectar_evidencia("me falta el aire", ["falta de aire"])
    assert resultados
    assert resultados[0]["polaridad"] == "positiva"


def test_ausencia_de_es_negacion():
    resultados = evidencia.detectar_evidencia("ausencia de fiebre", ["fiebre"])
    assert resultados
    assert resultados[0]["polaridad"] == "negativa"


def test_negacion_lejana_no_afecta():
    assert evidencia.coincide(
        "no tengo fiebre pero me duele el pecho", ["pecho"]
    ) is True


def test_negacion_con_stopwords():
    assert evidencia.coincide("no tengo dolor de pecho", ["pecho"]) is False


def test_negacion_no_cruza_coma():
    assert evidencia.coincide(
        "no tengo fiebre, me duele el pecho", ["pecho"]
    ) is True


def test_similitud():
    assert evidencia.similitud("manchas rojas en la piel", "manchas rojas en la piel") == 1.0
    assert evidencia.similitud("manchas rojas", "dolor de pecho") == 0.0
