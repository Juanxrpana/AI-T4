"""Tests del aprendizaje de conocimiento por dominio."""

import ai.cuestionario as cuestionario


def test_aprende_ejemplo_y_reconoce_variante():
    ok = cuestionario.aprender_ejemplo("lesion_piel", "puntitos rojos en el cuello")
    assert ok is True

    # No contiene palabras clave exactas: se reconoce por el ejemplo aprendido.
    assert cuestionario.detectar_dominio("puntitos rojos en el cuello") == "lesion_piel"


def test_aprende_palabra_clave():
    ok = cuestionario.aprender_palabras("fiebre", ["calentura fuerte"])
    assert ok is True
    assert cuestionario.detectar_dominio("tengo calentura fuerte") == "fiebre"


def test_no_aprende_dominio_inexistente():
    assert cuestionario.aprender_ejemplo("no_existe", "algo") is False
