"""Fase 4: confianza calibrada, bandas y muestra dorada."""

from ai import confianza


def test_pesos_suman_uno():
    assert round(sum(confianza.PESOS.values()), 6) == 1.0
    assert len(confianza.PESOS) == 6


def test_componentes_y_calculo_extremos():
    completos = confianza.componentes(
        top1=1.0,
        top2=0.0,
        n_candidatos=1,
        respondidas=3,
        min_preguntas=3,
        negaciones=0,
    )
    assert confianza.calcular(completos) == 1.0

    vacios = confianza.componentes(
        top1=0.0,
        top2=0.0,
        n_candidatos=0,
        respondidas=0,
        min_preguntas=3,
        negaciones=1,
    )
    assert confianza.calcular(vacios) == 0.0


def test_bandas():
    assert confianza.banda(0.75) == "alta"
    assert confianza.banda(0.74) == "media"
    assert confianza.banda(0.50) == "media"
    assert confianza.banda(0.49) == "baja"


def test_margen():
    assert confianza.margen(0.9, 0.6) == 0.3
    assert confianza.margen(0.4, 0.8) == 0.0


def test_aclaracion_nunca_revisa():
    revisar, motivo = confianza.evaluar(
        total=0.1, margen_top=0.0, n_candidatos=0,
        tipo_respuesta="aclaracion",
    )
    assert revisar is False
    assert motivo is None


def test_confianza_baja_y_margen_estrecho_revisan():
    revisar, motivo = confianza.evaluar(
        total=0.4, margen_top=0.05, n_candidatos=2,
        tipo_respuesta="orientacion",
    )
    assert revisar is True
    assert "confianza_baja" in motivo
    assert "margen_estrecho" in motivo


def test_sin_dominio_revisa():
    revisar, motivo = confianza.evaluar(
        total=0.0, margen_top=0.0, n_candidatos=0,
        tipo_respuesta="orientacion",
    )
    assert revisar is True
    assert "sin_dominio" in motivo


def test_muestra_determinista_y_tasa():
    assert confianza.es_muestra(123) == confianza.es_muestra(123)
    total = sum(1 for turno in range(1, 10001) if confianza.es_muestra(turno))
    tasa = total / 10000
    assert 0.035 <= tasa <= 0.065
