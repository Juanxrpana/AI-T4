"""Fase 0: la alarma usa la misma evidencia y no dispara con negaciones."""

import ai.cuestionario as cuestionario


def test_alarma_negada_no_dispara():
    assert cuestionario.hay_alarma(
        "no tengo dificultad para respirar", "fiebre"
    ) is False


def test_alarma_sin_dolor_no_dispara():
    assert cuestionario.hay_alarma("sin dolor de pecho", "dolor_toracico") is False


def test_alarma_no_tengo_dolor_no_dispara():
    assert cuestionario.hay_alarma(
        "no tengo dolor de pecho", "dolor_toracico"
    ) is False


def test_alarma_positiva():
    assert cuestionario.hay_alarma("dolor de pecho opresivo", "dolor_toracico") is True


def test_alarma_positiva_aunque_haya_negacion_lejana():
    assert cuestionario.hay_alarma(
        "no tengo fiebre pero me falta el aire", "dolor_toracico"
    ) is True


def test_dominio_no_detecta_negacion():
    assert cuestionario.detectar_dominio("no tengo fiebre") is None


def test_dominio_detecta_positivo():
    assert cuestionario.detectar_dominio("tengo fiebre") == "fiebre"
    assert cuestionario.detectar_dominio("me duele el pecho") == "dolor_toracico"
