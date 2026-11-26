"""Confianza calibrada de la orientación y muestra dorada.

Los seis componentes y sus pesos son fijos. La confianza no bloquea la
respuesta: solo decide si el caso entra a la cola de revisión.
"""

import hashlib

PESOS = {
    "coincidencia_keyword": 0.35,
    "similitud_ejemplo": 0.20,
    "margen_top1_top2": 0.20,
    "num_candidatos": 0.10,
    "preguntas_respondidas": 0.10,
    "penalizacion_negacion": 0.05,
}

UMBRAL_CONFIANZA = 0.60
UMBRAL_MARGEN = 0.15
TASA_MUESTRA = 20  # 1 de cada 20 turnos = 5 %


def margen(top1: float, top2: float) -> float:
    return round(max(0.0, float(top1) - float(top2)), 4)


def banda(confianza: float) -> str:
    if confianza >= 0.75:
        return "alta"
    if confianza >= 0.50:
        return "media"
    return "baja"


def componentes(
    *,
    top1: float,
    top2: float,
    n_candidatos: int,
    respondidas: int,
    min_preguntas: int,
    negaciones: int,
) -> list[dict]:
    """Construye los seis componentes con sus pesos fijos."""
    top1 = max(0.0, min(1.0, float(top1)))
    top2 = max(0.0, min(1.0, float(top2)))

    if n_candidatos <= 0:
        certeza_candidatos = 0.0
    elif n_candidatos == 1:
        certeza_candidatos = 1.0
    elif n_candidatos == 2:
        certeza_candidatos = 0.5
    elif n_candidatos == 3:
        certeza_candidatos = 0.25
    else:
        certeza_candidatos = 0.0

    valores = {
        "coincidencia_keyword": 1.0 if top1 >= 0.999 else 0.0,
        "similitud_ejemplo": top1,
        "margen_top1_top2": min(1.0, margen(top1, top2) / 0.5),
        "num_candidatos": certeza_candidatos,
        "preguntas_respondidas": min(
            1.0, respondidas / max(1, int(min_preguntas))
        ),
        "penalizacion_negacion": 0.0 if negaciones > 0 else 1.0,
    }
    return [
        {"nombre": nombre, "valor": valores[nombre], "peso": PESOS[nombre]}
        for nombre in PESOS
    ]


def calcular(componentes: list[dict]) -> float:
    total = 0.0
    for componente in componentes:
        total += float(componente.get("valor", 0)) * float(
            componente.get("peso", 0)
        )
    return round(max(0.0, min(1.0, total)), 4)


def evaluar(
    *,
    total: float,
    margen_top: float,
    n_candidatos: int,
    tipo_respuesta: str | None,
) -> tuple[bool, str | None]:
    """Devuelve (revisar, motivo). `aclaracion` nunca genera revisión."""
    if tipo_respuesta == "aclaracion":
        return False, None

    motivos: list[str] = []
    if n_candidatos == 0:
        motivos.append("sin_dominio")
    if margen_top < UMBRAL_MARGEN:
        motivos.append("margen_estrecho")
    if total < UMBRAL_CONFIANZA:
        motivos.append("confianza_baja")
    return bool(motivos), ",".join(motivos) if motivos else None


def es_muestra(turno_id: int) -> bool:
    """Muestra determinista del 5 % por `turno_id` (estable entre reintentos)."""
    digest = hashlib.sha256(f"muestra:{int(turno_id)}".encode("utf-8")).digest()
    return digest[0] % TASA_MUESTRA == 0
